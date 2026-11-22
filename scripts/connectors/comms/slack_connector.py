#!/usr/bin/env python3
"""Chat connector `slack`: turn channel history into monthly markdown notes.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Write one markdown file per channel per month into the
  `conversations` folder, with thread replies inline under the parent.
Change log:
  - First version, ported from the Slack archive sync. It can read a local
    archive (the original path) or call the chat API through the framework.
    Channels come from flags, never from a fixed list. The cursor lives in the
    state folder.

  slack_connector.py --channel ID=name [--channel ...] [--dm ID=name ...]
                     [--archive PATH] [--tz ZONE] [--full]

Address: the chat API base URL, set at first use. Key: an access token, held
in the secret store only. With --archive PATH the notes are built from a local
SQLite archive instead of the API (and every direct message in it is included);
the connector must still be on. Output goes to
`<conversations>/slack/channels/<name>/<year>-<month>-<name>.md`, and
`.../dms/<slug>/` for direct messages. The cursor (newest message time per
channel) is kept in `<state>/slack/cursor.json`; --full ignores it.
Message text goes into the notes only. It is never printed or logged; the
script prints counts.
"""
import argparse
import json
import pathlib
import re
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from connectors.registry import register, ensure, run_cli  # noqa: E402
from connectors.comms import comms_common as cc  # noqa: E402

NAME = "slack"
SCRIPT_NAME = "sync_slack"
MAX_PAGES = 50
MONTH_NAMES = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
               7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
               12: "December"}


# ---- text ----

def resolve_user_mentions(text, users):
    return re.sub(r"<@([A-Z0-9]+)>", lambda m: "@" + users.get(m.group(1), m.group(1)), text)


def clean_text(text, users):
    if not text:
        return ""
    text = resolve_user_mentions(text, users)
    text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2", text)
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)
    return text.strip()


def to_dt(ts, tz):
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone(tz)


def slug(name):
    return re.sub(r"[^\w\-]", "-", name).lower().strip("-") or "unnamed"


# ---- rendering (messages are dicts: ts, parent, user, text) ----

def build_monthly(messages, users, tz, stats=None):
    """Group by (year, month); threads render inline under the parent.

    The privacy filter drops a message first, then secrets in what is kept are
    redacted. `stats` (a dict) gets "phi" (messages dropped) and "secrets"
    (label -> count).
    """
    stats = stats if stats is not None else {}
    stats.setdefault("phi", 0)
    tally = stats.setdefault("secrets", {})

    def keep(text):
        if not text:
            return None
        if not cc.scrub([{"t": text}], source="slack")[0]:
            stats["phi"] += 1
            return None
        return cc.redact_text(text, tally)

    replies = {}
    for m in messages:
        if m["parent"]:
            replies.setdefault(m["parent"], []).append(m)
    by_month = {}
    for m in messages:
        if m["parent"]:
            continue
        text = keep(clean_text(m["text"], users))
        if not text:
            continue
        dt = to_dt(m["ts"], tz)
        lines = by_month.setdefault((dt.year, dt.month), [])
        lines.append("### " + dt.strftime("%Y-%m-%d"))
        lines.append("**[%s] %s**: %s" % (dt.strftime("%H:%M"),
                                          users.get(m["user"], m["user"] or "unknown"), text))
        for r in replies.get(m["ts"], []):
            rtext = keep(clean_text(r["text"], users))
            if rtext:
                lines.append("  -> **[%s] %s**: %s" % (
                    to_dt(r["ts"], tz).strftime("%H:%M"),
                    users.get(r["user"], r["user"] or "unknown"), rtext))
        lines.append("")
    return by_month


def write_files(out_dir, base, title, channel_id, by_month, tz):
    """One file per month. Appends new text; skips text already there."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for (year, month), lines in sorted(by_month.items()):
        if not lines:
            continue
        path = out_dir / ("%d-%02d-%s.md" % (year, month, base))
        new = "\n".join(lines)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if new.strip() in existing:
                continue
            path.write_text(existing.rstrip() + "\n\n" + new + "\n", encoding="utf-8")
        else:
            header = ["# %s - %d %s" % (title, year, MONTH_NAMES[month]), "",
                      "Channel ID: " + channel_id,
                      "Generated: " + datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z"),
                      "", "---", ""]
            path.write_text("\n".join(header + lines) + "\n", encoding="utf-8")
        written += 1
    return written


# ---- sources ----

class ApiSource:
    """Reads through the framework http. Returns (data, reason)."""

    def __init__(self, address, key, http):
        self.address, self.key, self.http = address.rstrip("/"), key, http

    def _get(self, method, **params):
        url = "%s/%s?%s" % (self.address, method, urllib.parse.urlencode(params))
        resp, reason = cc.call(self.http, "GET", url, timeout=30,
                               headers={"Authorization": "Bearer " + self.key})
        if resp is None:
            return None, reason
        body = cc.body_of(resp)
        if not isinstance(body, dict) or body.get("ok") is False:
            return None, cc.LogReason.SCHEMA_INVALID
        return body, cc.LogReason.API_OK

    def users(self):
        out, cursor = {}, ""
        for _ in range(MAX_PAGES):
            body, reason = self._get("users.list", cursor=cursor, limit=200)
            if body is None:
                return None, reason
            for u in body.get("members", []):
                out[u.get("id", "")] = (u.get("real_name") or u.get("name") or u.get("id", ""))
            cursor = (body.get("response_metadata") or {}).get("next_cursor", "")
            if not cursor:
                break
        return out, cc.LogReason.API_OK

    def messages(self, channel, since):
        msgs, cursor = [], ""
        for _ in range(MAX_PAGES):
            params = {"channel": channel, "limit": 200}
            if since:
                params["oldest"] = "%.6f" % float(since)
            if cursor:
                params["cursor"] = cursor
            body, reason = self._get("conversations.history", **params)
            if body is None:
                return None, reason
            for m in body.get("messages", []):
                if not isinstance(m, dict) or "ts" not in m:
                    continue
                msgs.append({"ts": m["ts"], "parent": "", "user": m.get("user", ""),
                             "text": m.get("text", "")})
                if m.get("reply_count") and m.get("thread_ts") == m["ts"]:
                    rb, rr = self._get("conversations.replies", channel=channel, ts=m["ts"])
                    if rb is None:
                        return None, rr
                    for r in rb.get("messages", []):
                        if isinstance(r, dict) and r.get("ts") and r["ts"] != m["ts"]:
                            msgs.append({"ts": r["ts"], "parent": m["ts"],
                                         "user": r.get("user", ""), "text": r.get("text", "")})
            cursor = (body.get("response_metadata") or {}).get("next_cursor", "")
            if not cursor:
                break
        msgs.sort(key=lambda x: float(x["ts"]))
        return msgs, cc.LogReason.API_OK


class ArchiveSource:
    """Reads a local SQLite archive, read only."""

    def __init__(self, path):
        self.conn = sqlite3.connect("file:%s?mode=ro" % urllib.parse.quote(str(path)), uri=True)
        self.conn.row_factory = sqlite3.Row

    def users(self):
        users = {}
        for row in self.conn.execute("SELECT ID, USERNAME, DATA FROM S_USER"):
            try:
                data = json.loads(row["DATA"]) if row["DATA"] else {}
            except (ValueError, TypeError):
                data = {}
            users[row["ID"]] = ((data.get("profile") or {}).get("real_name_normalized")
                                or data.get("real_name") or row["USERNAME"] or row["ID"])
        return users, cc.LogReason.API_OK

    def messages(self, channel, since):
        sql = ("SELECT TS, PARENT_ID, TXT, DATA FROM MESSAGE WHERE CHANNEL_ID = ?"
               + (" AND CAST(TS AS REAL) > ?" if since else "")
               + " ORDER BY CAST(TS AS REAL)")
        rows = self.conn.execute(sql, (channel, float(since)) if since else (channel,))
        out = []
        for r in rows:
            try:
                data = json.loads(r["DATA"]) if r["DATA"] else {}
            except (ValueError, TypeError):
                continue
            out.append({"ts": r["TS"], "parent": r["PARENT_ID"] or "",
                        "user": data.get("user", ""), "text": r["TXT"] or ""})
        return out, cc.LogReason.API_OK

    def dms(self, users):
        rows = self.conn.execute(
            "SELECT c.ID, c.DATA FROM CHANNEL c JOIN MESSAGE m ON m.CHANNEL_ID = c.ID "
            "WHERE json_extract(c.DATA, '$.is_im') = 1 OR json_extract(c.DATA, '$.is_mpim') = 1 "
            "GROUP BY c.ID HAVING COUNT(m.ID) > 0").fetchall()
        out = {}
        for r in rows:
            try:
                d = json.loads(r["DATA"]) if r["DATA"] else {}
            except (ValueError, TypeError):
                continue
            if d.get("is_mpim"):
                name = str(d.get("name", r["ID"])).replace("mpdm-", "").replace("--", "-")
            else:
                name = users.get(d.get("user", ""), d.get("user", "") or r["ID"])
            out[r["ID"]] = name
        return out

    def close(self):
        self.conn.close()


class SlackClient:
    def __init__(self, address, key, http):
        self.api = ApiSource(address, key, http)


register(NAME, lambda address, key, http: SlackClient(address, key, http))


# ---- cursor ----

def cursor_file():
    return cc.get_path("state") / "slack" / "cursor.json"


def load_cursor():
    try:
        data = json.loads(cursor_file().read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cursor(state):
    p = cursor_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2))


def parse_pairs(items):
    out = {}
    for item in items:
        cid, sep, name = item.partition("=")
        if not sep or not cid or not name:
            raise SystemExit("slack: --channel and --dm take ID=name")
        out[cid] = name
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write chat history as monthly markdown notes.")
    ap.add_argument("--channel", action="append", default=[], metavar="ID=name")
    ap.add_argument("--dm", action="append", default=[], metavar="ID=name")
    ap.add_argument("--archive", help="read a local SQLite archive instead of the API")
    ap.add_argument("--tz", help="time zone name (default this computer's)")
    ap.add_argument("--full", action="store_true", help="ignore the cursor")
    args = ap.parse_args(argv)
    client = ensure(NAME)
    channels, dms = parse_pairs(args.channel), parse_pairs(args.dm)
    if not channels and not dms and not args.archive:
        raise SystemExit("slack: give at least one --channel ID=name (or --archive PATH)")
    if args.tz:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(args.tz)
    else:
        tz = datetime.now().astimezone().tzinfo
    start = cc.now_iso()
    root = cc.get_path("conversations") / "slack"
    src = ArchiveSource(args.archive) if args.archive else client.api
    state = {} if args.full else load_cursor()
    users, reason = src.users()
    if users is None:
        return _fail(start, reason)
    if args.archive:
        dms = dict(dms)
        dms.update(src.dms(users))
    files = msgs_total = 0
    stats = {"phi": 0, "secrets": {}}
    failed = None
    targets = [("channels", c, n) for c, n in channels.items()] + \
              [("dms", c, n) for c, n in dms.items()]
    for kind, cid, name in targets:
        msgs, reason = src.messages(cid, state.get(cid))
        if msgs is None:
            failed = failed or reason
            continue
        if not msgs:
            continue
        by_month = build_monthly(msgs, users, tz, stats)
        base = slug(name)
        title = "#" + name if kind == "channels" else "DM - " + name
        files += write_files(root / kind / base, base, title, cid, by_month, tz)
        state[cid] = max(float(m["ts"]) for m in msgs)
        msgs_total += len(msgs)
    if args.archive:
        src.close()
    save_cursor(state)
    cc.log_run(SCRIPT_NAME, start, cc.LogResult.DEGRADED if failed else cc.LogResult.SUCCESS,
               failed or cc.LogReason.WRITE_OK, stats["phi"])
    print("slack: %s, %s" % (cc.counts(channels=len(targets), messages=msgs_total, files=files,
                                       phi_dropped=stats["phi"]), cc.secrets_line(stats["secrets"])))
    return 0


def _fail(start, reason):
    cc.log_run(SCRIPT_NAME, start, cc.LogResult.FAILED, reason, 0)
    print("slack: failed")
    return 0


if __name__ == "__main__":
    sys.exit(run_cli(main) or 0)
