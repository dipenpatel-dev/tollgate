#!/usr/bin/env python3
"""Shared parts for the chat, tracker, notes, calendar and git connectors.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: One place for the cache file format, the run log call, safe HTTP
  wrapping and the privacy rule (counts only, never message text or titles).
Change log:
  - First version.

A puller writes `<name>.json` into the cache folder in the format
`scripts/cache/daily_brief.py` reads. Every HTTP call goes through the
`http` object the registry hands to the client; nothing here imports a
request library except to name its error types.
"""
import json
import pathlib
import sys
import urllib.error
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1]
for _p in (SCRIPTS, SCRIPTS / "cache", SCRIPTS / "sync"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.paths import get_path, NotSetUp  # noqa: E402,F401
from cache_write import atomic_replace  # noqa: E402
from run_log import LogReason, LogResult, append  # noqa: E402
from phi_guard import scrub  # noqa: E402
import vault_write_scan  # noqa: E402

__all__ = ["get_path", "NotSetUp", "LogReason", "LogResult", "scrub",
           "build_payload", "write_cache", "log_run", "finish", "call",
           "body_of", "classify_status", "now_iso", "counts",
           "redact_text", "redact_records", "secrets_line"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_payload(data, result, reason, reject_count):
    """Wrap data in the _meta envelope the daily brief reads."""
    return {"_meta": {"pulled_at": now_iso(), "result": result.value,
                      "reason": reason.value, "reject_count": reject_count},
            "data": data}


def write_cache(name, payload):
    """Atomically write <name>.json into the cache folder."""
    folder = get_path("cache")
    folder.mkdir(parents=True, exist_ok=True)
    atomic_replace(folder / (name + ".json"), payload)


def log_run(script, start_ts, result, reason, rejected):
    append({"script": script, "start_ts": start_ts, "end_ts": now_iso(),
            "result": result.value, "reason": reason.value,
            "reject_count": rejected})


def redact_text(text, tally):
    """Replace each secret in text with [REDACTED:LABEL]; keep the rest of the text.

    Uses the same rules as the write hook (vault_write_scan.scan_text, only its
    secret redaction). `tally` is a dict of label -> count and is updated.
    Runs after the PHI filter and before the write. Never logs the text.
    """
    if not isinstance(text, str) or not text:
        return text
    found = vault_write_scan.scan_text(text)
    for label in found.redacted:
        tally[label] = tally.get(label, 0) + 1
    return found.text


def redact_records(node, tally):
    """A copy of a nested dict/list record with every string value redacted."""
    if isinstance(node, str):
        return redact_text(node, tally)
    if isinstance(node, dict):
        return {k: redact_records(v, tally) for k, v in node.items()}
    if isinstance(node, list):
        return [redact_records(v, tally) for v in node]
    return node


def secrets_line(tally):
    """Log-safe count of redactions by label, for example `2 secrets redacted (A 1, B 1)`."""
    total = sum(tally.values())
    if not total:
        return "0 secrets redacted"
    parts = ", ".join("%s %d" % (k, tally[k]) for k in sorted(tally))
    return "%d secret%s redacted (%s)" % (total, "" if total == 1 else "s", parts)


def finish(script, cache_name, start_ts, data, result, reason, rejected, tally=None):
    """Write the cache file unless the pull failed, log the run, print counts.

    Returns 0 on purpose: a scheduler must not loop on a failed pull. The run
    log and the daily brief hold the result. Only counts are printed.
    """
    if result != LogResult.FAILED:
        try:
            write_cache(cache_name, build_payload(data, result, reason, rejected))
        except OSError:
            result, reason = LogResult.FAILED, LogReason.SCHEMA_INVALID
    log_run(script, start_ts, result, reason, rejected)
    print("%s: %s, %d records, %d rejected, %s" % (script, result.value,
                                                 len(data) if result != LogResult.FAILED else 0,
                                                 rejected, secrets_line(tally or {})))
    return 0


def classify_status(status):
    if 400 <= status < 500:
        return LogReason.API_4XX
    if 500 <= status < 600:
        return LogReason.API_5XX
    return LogReason.SCHEMA_INVALID


def call(http, method, url, **kw):
    """One HTTP call through the handed-in client. Returns (response, reason).

    The response is None on failure. Error text is never kept, only the reason.
    """
    try:
        resp = http.request(method, url, **kw)
    except urllib.error.HTTPError as err:
        return None, classify_status(err.code)
    except (TimeoutError, urllib.error.URLError, OSError):
        return None, LogReason.API_TIMEOUT
    status = resp.get("status", 200) if isinstance(resp, dict) else 200
    if status >= 400:
        return None, classify_status(status)
    return resp, LogReason.API_OK


def body_of(resp):
    """The response body as parsed JSON; None when it is not JSON."""
    body = resp.get("body") if isinstance(resp, dict) else None
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", "replace")
    if isinstance(body, str):
        try:
            return json.loads(body)
        except ValueError:
            return None
    return body


def counts(**kw):
    """A log-safe line made only of numbers."""
    return ", ".join("%s=%d" % (k, int(v)) for k, v in sorted(kw.items()))
