#!/usr/bin/env python3
"""Notes connector `notion`: save a page or database as a markdown note.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Read one page, or one database, by id and write it as a markdown
  note under the `meetings` or `references` folder.
Change log:
  - First version. NEW: there is no source file for this connector. It is
    written on the connector framework.

  notion_connector.py page ID     [--into meetings|references]
  notion_connector.py database ID [--into meetings|references]

Address: the notes API base URL, set at first use. Key: an integration token,
held in the secret store only. `page` reads the page title, its blocks (with
nested children, depth capped) and writes `<folder>/<slug>-<id8>.md`. A
`database` writes one note with a bullet per row title. The page title is used
in the file name only; titles and text are never printed or logged, only
counts. Rerunning the same id overwrites the same file.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from connectors.registry import register, ensure, run_cli  # noqa: E402
from connectors.comms import comms_common as cc  # noqa: E402

NAME = "notion"
SCRIPT_NAME = "notion_pull"
API_VERSION = "2022-06-28"
MAX_PAGES = 20
MAX_DEPTH = 3
ID_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def rich(parts):
    if not isinstance(parts, list):
        return ""
    return "".join(p.get("plain_text", "") for p in parts if isinstance(p, dict))


def title_of(obj):
    """Best title text of a page or database object."""
    if not isinstance(obj, dict):
        return ""
    if isinstance(obj.get("title"), list):
        return rich(obj["title"])
    for prop in (obj.get("properties") or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return rich(prop.get("title"))
    return ""


def block_to_md(block, depth):
    t = block.get("type", "")
    body = block.get(t) if isinstance(block.get(t), dict) else {}
    text = rich(body.get("rich_text"))
    pad = "  " * depth
    if t == "heading_1":
        return "# " + text
    if t == "heading_2":
        return "## " + text
    if t == "heading_3":
        return "### " + text
    if t == "bulleted_list_item":
        return pad + "- " + text
    if t == "numbered_list_item":
        return pad + "1. " + text
    if t == "to_do":
        return pad + "- [%s] %s" % ("x" if body.get("checked") else " ", text)
    if t == "quote":
        return "> " + text
    if t == "code":
        return "```%s\n%s\n```" % (body.get("language", ""), text)
    if t == "divider":
        return "---"
    return text


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "untitled"


class NotionClient:
    def __init__(self, address, key, http):
        self.address, self.key, self.http = address.rstrip("/"), key, http

    def _req(self, method, path, **kw):
        resp, reason = cc.call(self.http, method, self.address + path, timeout=30,
                               headers={"Authorization": "Bearer " + self.key,
                                        "Notion-Version": API_VERSION,
                                        "Content-Type": "application/json"}, **kw)
        if resp is None:
            return None, reason
        body = cc.body_of(resp)
        if not isinstance(body, dict):
            return None, cc.LogReason.SCHEMA_INVALID
        return body, cc.LogReason.API_OK

    def page(self, pid):
        return self._req("GET", "/pages/" + pid)

    def blocks(self, bid, depth=0):
        """Return (markdown lines, reason). Children are read down to MAX_DEPTH."""
        lines, cursor = [], None
        for _ in range(MAX_PAGES):
            path = "/blocks/%s/children?page_size=100" % bid
            if cursor:
                path += "&start_cursor=" + cursor
            body, reason = self._req("GET", path)
            if body is None:
                return None, reason
            for b in body.get("results", []):
                if not isinstance(b, dict):
                    continue
                lines.append(block_to_md(b, depth))
                if b.get("has_children") and depth < MAX_DEPTH and b.get("id"):
                    sub, reason = self.blocks(b["id"], depth + 1)
                    if sub is None:
                        return None, reason
                    lines.extend(sub)
            if not body.get("has_more"):
                break
            cursor = body.get("next_cursor")
            if not cursor:
                break
        return lines, cc.LogReason.API_OK

    def database(self, did):
        """Return (database object, [row titles], reason)."""
        meta, reason = self._req("GET", "/databases/" + did)
        if meta is None:
            return None, None, reason
        rows, cursor = [], None
        for _ in range(MAX_PAGES):
            payload = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            body, reason = self._req("POST", "/databases/%s/query" % did, data=json.dumps(payload))
            if body is None:
                return None, None, reason
            rows.extend(title_of(r) for r in body.get("results", []))
            if not body.get("has_more"):
                break
            cursor = body.get("next_cursor")
            if not cursor:
                break
        return meta, rows, cc.LogReason.API_OK


register(NAME, lambda address, key, http: NotionClient(address, key, http))


def write_note(folder_name, ident, title, lines, kind, stats=None):
    """Write the note. The privacy filter drops first, then secrets are redacted.

    `stats` (a dict) gets "phi" (title and lines dropped) and "secrets"
    (label -> count).
    """
    stats = stats if stats is not None else {}
    stats.setdefault("phi", 0)
    tally = stats.setdefault("secrets", {})
    folder = cc.get_path(folder_name)
    folder.mkdir(parents=True, exist_ok=True)
    clean_id = ident.replace("-", "")
    if title and not cc.scrub([{"t": title}], source="notion")[0]:
        stats["phi"] += 1
        title = ""
    kept = []
    for x in lines:
        if cc.scrub([{"t": x}], source="notion")[0]:
            kept.append(x)
        else:
            stats["phi"] += 1
    title = cc.redact_text(title or "", tally)
    lines = [cc.redact_text(x, tally) for x in kept]
    path = folder / ("%s-%s.md" % (slug(title), clean_id[:8]))
    head = ["# " + (title or "Untitled"), "", "Source: notion %s %s" % (kind, ident),
            "Fetched: " + cc.now_iso(), "", "---", ""]
    path.write_text("\n".join(head + lines) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Save a page or database as a markdown note.")
    ap.add_argument("kind", choices=("page", "database"))
    ap.add_argument("id")
    ap.add_argument("--into", choices=("meetings", "references"), default="references")
    args = ap.parse_args(argv)
    if not ID_RE.match(args.id):
        raise SystemExit("notion: the id must be letters, digits and dashes only")
    client = ensure(NAME)
    start = cc.now_iso()
    stats = {"phi": 0, "secrets": {}}
    if args.kind == "page":
        meta, reason = client.page(args.id)
        lines = None
        if meta is not None:
            lines, reason = client.blocks(args.id)
        if meta is None or lines is None:
            return _done(start, cc.LogResult.FAILED, reason, 0)
        write_note(args.into, args.id, title_of(meta), lines, "page", stats)
        return _done(start, cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK, len(lines), stats)
    meta, rows, reason = client.database(args.id)
    if meta is None:
        return _done(start, cc.LogResult.FAILED, reason, 0)
    write_note(args.into, args.id, title_of(meta), ["- " + (r or "Untitled") for r in rows], "database", stats)
    return _done(start, cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK, len(rows), stats)


def _done(start, result, reason, n, stats=None):
    stats = stats or {"phi": 0, "secrets": {}}
    cc.log_run(SCRIPT_NAME, start, result, reason, stats["phi"])
    print("notion: %s, %d items, %d phi dropped, %s" % (
        result.value, n, stats["phi"], cc.secrets_line(stats["secrets"])))
    return 0


if __name__ == "__main__":
    sys.exit(run_cli(main) or 0)
