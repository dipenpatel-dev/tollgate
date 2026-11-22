#!/usr/bin/env python3
"""Calendar connector `calendar`: pull today's events into the cache.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Write calendar.json (the daily brief seam) from a calendar API or,
  on a Mac, from the Calendar app.
Change log:
  - First version, ported from the calendar cache puller and its Keychain
    helper. First use now asks for the address and key through the connector
    framework; the key goes to the secret store, never to a file. The calendar
    names, the time zone and the day come from flags.

  calendar_connector.py [--calendar NAME ...] [--date YYYY-MM-DD] [--tz ZONE]
                        [--source api|macos] [--dry-run] [--no-day-cache]

`api` mode (default): the address is the calendar API base URL and the key is
an access token. It asks for `<address>/calendars/<NAME>/events` for each
--calendar (default `primary`). `macos` mode reads the Calendar app through
the `osascript` tool and the named --calendar entries; it needs no network.
Both modes still need the connector turned on first.
Events are written as {id, summary, start, end, attendees_count}. A same-day
copy is kept in the state folder, and a repeat run on the same day reuses it
(--no-day-cache forces a fresh read). Event titles are never printed or logged.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from connectors.registry import register, ensure, run_cli  # noqa: E402
from connectors.comms import comms_common as cc  # noqa: E402

NAME = "calendar"
SCRIPT_NAME = "calendar_pull"
OSASCRIPT_TIMEOUT = 15
APPLESCRIPT_DATE_FORMAT = "%A, %B %d, %Y at %I:%M:%S %p"
FIELD_SEPARATOR = "\t"

DRY_RUN_FIXTURE = [
    {"id": "fixture-1", "summary": "Standup", "start": "2026-01-01T09:00:00+00:00",
     "end": "2026-01-01T09:30:00+00:00", "attendees_count": 4},
    {"id": "fixture-2", "summary": "Client sync", "start": "2026-01-01T11:00:00+00:00",
     "end": "2026-01-01T12:00:00+00:00", "attendees_count": 2},
]

_APPLESCRIPT = """\
tell application "Calendar"
    set today_start to (current date)
    set hours of today_start to 0
    set minutes of today_start to 0
    set seconds of today_start to 0
    set today_end to today_start + (24 * 60 * 60) - 1
    set sep to tab
    set lf to linefeed
    set output to ""
    repeat with cal in calendars
        if name of cal is in {CALENDAR_NAMES} then
            set cal_events to (every event of cal whose start date >= today_start and start date <= today_end)
            repeat with ev in cal_events
                set att_count to count of (attendees of ev)
                set output to output & (uid of ev) & sep & (summary of ev) & sep & ((start date of ev) as string) & sep & ((end date of ev) as string) & sep & att_count & lf
            end repeat
        end if
    end repeat
    return output
end tell
"""


def local_tz(name=None):
    if name:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    return datetime.now().astimezone().tzinfo


def build_applescript(names):
    lit = "{" + ", ".join('"%s"' % n.replace('"', "").replace("\\", "") for n in names) + "}"
    return _APPLESCRIPT.replace("{CALENDAR_NAMES}", lit)


def parse_applescript_date(raw, tz):
    return datetime.strptime(raw.strip(), APPLESCRIPT_DATE_FORMAT).replace(tzinfo=tz).isoformat()


def parse_osascript_output(text, tz):
    """Parse tab separated lines; return (events, reason). Repeats by id are dropped."""
    seen, events = set(), []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) != 5:
            return [], cc.LogReason.SCHEMA_INVALID
        uid, summary, s_raw, e_raw, att = parts
        if uid in seen:
            continue
        seen.add(uid)
        try:
            events.append({"id": uid, "summary": summary,
                           "start": parse_applescript_date(s_raw, tz),
                           "end": parse_applescript_date(e_raw, tz),
                           "attendees_count": int(att)})
        except (ValueError, AttributeError):
            return [], cc.LogReason.SCHEMA_INVALID
    return events, cc.LogReason.API_OK


def project_api_event(raw):
    """Lean projection of one API event; None on a wrong shape."""
    if not isinstance(raw, dict) or "id" not in raw:
        return None

    def when(v):
        if not isinstance(v, dict):
            return ""
        return v.get("dateTime") or v.get("date") or ""
    att = raw.get("attendees", [])
    return {"id": raw["id"], "summary": raw.get("summary", ""),
            "start": when(raw.get("start")), "end": when(raw.get("end")),
            "attendees_count": len(att) if isinstance(att, list) else 0}


class CalendarClient:
    def __init__(self, address, key, http, runner=subprocess.run):
        self.address, self.key, self.http = address.rstrip("/"), key, http
        self.runner = runner

    def fetch_api(self, calendars, day, tz):
        start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
        end = start + timedelta(days=1)
        events, seen = [], set()
        for cal in calendars or ["primary"]:
            q = urllib.parse.urlencode({"timeMin": start.isoformat(), "timeMax": end.isoformat(),
                                        "singleEvents": "true", "orderBy": "startTime"})
            url = "%s/calendars/%s/events?%s" % (self.address, urllib.parse.quote(cal, safe=""), q)
            resp, reason = cc.call(self.http, "GET", url, timeout=15,
                                   headers={"Authorization": "Bearer " + self.key})
            if resp is None:
                return [], reason
            body = cc.body_of(resp)
            if not isinstance(body, dict) or not isinstance(body.get("items", []), list):
                return [], cc.LogReason.SCHEMA_INVALID
            for raw in body.get("items", []):
                rec = project_api_event(raw)
                if rec is None:
                    return [], cc.LogReason.SCHEMA_INVALID
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    events.append(rec)
        return events, cc.LogReason.API_OK

    def fetch_macos(self, names, tz):
        try:
            r = self.runner(["osascript", "-e", build_applescript(names)],
                            capture_output=True, text=True, timeout=OSASCRIPT_TIMEOUT)
        except subprocess.TimeoutExpired:
            return [], cc.LogReason.API_TIMEOUT
        except OSError:
            return [], cc.LogReason.AUTH_FAILED
        if r.returncode != 0:
            return [], cc.LogReason.AUTH_FAILED
        return parse_osascript_output(r.stdout.strip(), tz)


register(NAME, lambda address, key, http: CalendarClient(address, key, http))


def day_file(day):
    return cc.get_path("state") / "calendar" / ("calendar_%s.json" % day.isoformat())


def load_day(day):
    try:
        data = json.loads(day_file(day).read_text(encoding="utf-8")).get("data")
    except (OSError, ValueError, AttributeError):
        return None
    return data if isinstance(data, list) else None


def save_day(day, payload):
    p = day_file(day)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def main(argv=None, runner=None):
    ap = argparse.ArgumentParser(description="Pull today's calendar events to the cache.")
    ap.add_argument("--calendar", action="append", default=[], help="calendar name or id (repeat)")
    ap.add_argument("--date", help="day to read, YYYY-MM-DD (default today)")
    ap.add_argument("--tz", help="time zone name (default this computer's)")
    ap.add_argument("--source", choices=("api", "macos"), default="api")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-day-cache", action="store_true")
    args = ap.parse_args(argv)
    client = ensure(NAME)
    if runner:
        client.runner = runner
    tz = local_tz(args.tz)
    day = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now(tz).date()
    start = cc.now_iso()
    rejected = 0
    tally = {}
    if args.dry_run:
        clean, rejected = cc.scrub(DRY_RUN_FIXTURE, source="calendar")
        res, reason = cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK
    else:
        cached = None if args.no_day_cache else load_day(day)
        if cached is not None:
            clean, res, reason = cached, cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK
        else:
            if args.source == "macos":
                events, freason = client.fetch_macos(args.calendar, tz)
            else:
                events, freason = client.fetch_api(args.calendar, day, tz)
            if freason != cc.LogReason.API_OK:
                clean, res, reason = [], cc.LogResult.FAILED, freason
            else:
                clean, rejected = cc.scrub(events, source="calendar")
                clean = cc.redact_records(clean, tally)
                if events and not clean:
                    clean, res, reason = [], cc.LogResult.DEGRADED, cc.LogReason.PHI_REJECTED_ALL
                elif rejected:
                    res, reason = cc.LogResult.DEGRADED, cc.LogReason.PHI_REJECTED
                else:
                    res, reason = cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK
    if res != cc.LogResult.FAILED and not args.dry_run:
        save_day(day, cc.build_payload(clean, res, reason, rejected))
    return cc.finish(SCRIPT_NAME, "calendar", start, clean, res, reason, rejected, tally)


if __name__ == "__main__":
    sys.exit(run_cli(main) or 0)
