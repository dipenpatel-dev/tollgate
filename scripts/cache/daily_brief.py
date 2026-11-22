#!/usr/bin/env python3
"""
module_name: daily_brief.py
description: Assemble a daily brief from per source cache files. Generic: it knows no calendar, tracker or chat tool.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported. Sources are every <name>.json in the cache folder (or the names you pass). Local time zone from the system, or TOLLGATE_TZ. A connector fills a source by writing <name>.json with atomic_replace().
usage: python3 daily_brief.py [--source NAME ...]
  --source   a source that must be reported even when its file is missing (repeatable). Also TOLLGATE_BRIEF_SOURCES (comma separated).

Reads:   <cache folder>/<name>.json for each source.
Writes:  <cache folder>/daily_brief.json (atomic) and one line in the run log.
Seam:    a connector writes <name>.json with this shape, and the brief picks it up:
           {"_meta": {"pulled_at": "<ISO timestamp with zone>", "result": "success|degraded|failed",
                      "reason": "<LogReason value>", "reject_count": 0},
            "data": [ ... ]}

daily_brief.json:
  {"_meta": {"assembled_at", "result", "reason", "reject_count"},
   "sources": {"<name>": {"status", "pulled_at", "result", "reason", "reject_count", "data"}}}

Status:
  fresh    pulled_at is today (local time), not in the future, and result is success
  stale    file present but _meta missing or invalid, or pulled_at not today, in the future or unreadable
  degraded _meta.result is degraded
  failed   _meta.result is failed
  missing  no cache file
The status uses _meta only. It never reads the run log.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import datetime, timezone, tzinfo
from enum import Enum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from core.paths import NotSetUp, get_path  # noqa: E402
from cache_write import atomic_replace  # noqa: E402
from run_log import LogReason, LogResult, append  # noqa: E402

SCRIPT_NAME: str = "daily_brief"
BRIEF_NAME: str = "daily_brief.json"


class _StrEnum(str, Enum):
    """String enum for Python 3.9 (enum.StrEnum needs 3.11). str() gives the value."""

    def __str__(self) -> str:
        return str(self.value)

    __format__ = str.__format__


class BriefStatus(_StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    DEGRADED = "degraded"
    FAILED = "failed"
    MISSING = "missing"


class ReadState(_StrEnum):
    OK = "ok"
    ABSENT = "absent"
    UNREADABLE = "unreadable"


def local_tz() -> tzinfo:
    name = os.environ.get("TOLLGATE_TZ", "").strip()
    if name:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo or timezone.utc


def _parse_pulled_at_local(value: Any, tz: tzinfo) -> datetime | None:
    """ISO string to local datetime. None on any failure, including a missing zone."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(tz) if parsed.tzinfo is not None else None


def _read_cache_file(path: Path) -> tuple[dict[str, Any] | None, ReadState]:
    if not path.is_file():
        return None, ReadState.ABSENT
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None, ReadState.UNREADABLE
    if not isinstance(payload, dict):
        return None, ReadState.UNREADABLE
    return payload, ReadState.OK


def _classify(meta: Any, now_local: datetime) -> BriefStatus:
    if not isinstance(meta, dict):
        return BriefStatus.STALE
    result = meta.get("result")
    if result == LogResult.DEGRADED.value:
        return BriefStatus.DEGRADED
    if result == LogResult.FAILED.value:
        return BriefStatus.FAILED
    pulled = _parse_pulled_at_local(meta.get("pulled_at"), now_local.tzinfo)
    if (result == LogResult.SUCCESS.value and pulled is not None
            and pulled.date() == now_local.date() and pulled <= now_local):
        return BriefStatus.FRESH
    return BriefStatus.STALE


def _empty_block(status: BriefStatus) -> dict[str, Any]:
    return {"status": status.value, "pulled_at": None, "result": None, "reason": None, "reject_count": 0, "data": []}


def _source_block(payload: dict[str, Any], now_local: datetime) -> dict[str, Any]:
    meta = payload.get("_meta")
    meta_dict = meta if isinstance(meta, dict) else {}
    raw_reject = meta_dict.get("reject_count", 0)
    reject = raw_reject if isinstance(raw_reject, int) and not isinstance(raw_reject, bool) else 0
    data = payload.get("data")
    return {
        "status": _classify(meta, now_local).value,
        "pulled_at": meta_dict.get("pulled_at"),
        "result": meta_dict.get("result"),
        "reason": meta_dict.get("reason"),
        "reject_count": reject,
        "data": data if isinstance(data, list) else [],
    }


def discover_sources(cache_dir: Path, required: list[str] | None = None) -> list[tuple[str, Path]]:
    """Every <name>.json in the cache folder (except the brief), plus any required name even when absent."""
    names = {p.stem for p in cache_dir.glob("*.json") if p.name != BRIEF_NAME}
    names.update(required or [])
    return [(n, cache_dir / f"{n}.json") for n in sorted(names)]


def assemble_sources(sources: list[tuple[str, Path]], now_local: datetime) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, path in sources:
        payload, state = _read_cache_file(path)
        if state == ReadState.ABSENT:
            out[name] = _empty_block(BriefStatus.MISSING)
        elif state == ReadState.UNREADABLE:
            out[name] = _empty_block(BriefStatus.STALE)
        else:
            assert payload is not None
            out[name] = _source_block(payload, now_local)
    return out


def build_payload(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "_meta": {
            "assembled_at": datetime.now(timezone.utc).isoformat(),
            "result": LogResult.SUCCESS.value,
            "reason": LogReason.WRITE_OK.value,
            "reject_count": 0,
        },
        "sources": sources,
    }


def run(cache_dir: Path, required: list[str] | None = None, log_path: Path | None = None) -> dict[str, Any]:
    """Assemble and write the brief. Always appends one run log line. Returns the payload."""
    start_ts = datetime.now(timezone.utc).isoformat()
    now_local = datetime.now(local_tz())
    payload = build_payload(assemble_sources(discover_sources(cache_dir, required), now_local))
    result, reason = LogResult.SUCCESS, LogReason.WRITE_OK
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        atomic_replace(cache_dir / BRIEF_NAME, payload)
    except Exception:
        result, reason = LogResult.FAILED, LogReason.SCHEMA_INVALID
    append({"script": SCRIPT_NAME, "start_ts": start_ts, "end_ts": datetime.now(timezone.utc).isoformat(),
            "result": result.value, "reason": reason.value, "reject_count": 0}, log_path)
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assemble the daily brief from per source cache files.")
    parser.add_argument("--source", action="append", default=[], help="A source to report even when missing")
    args = parser.parse_args(argv)
    required = list(args.source) + [s.strip() for s in os.environ.get("TOLLGATE_BRIEF_SOURCES", "").split(",") if s.strip()]
    try:
        cache_dir = get_path("cache")
    except NotSetUp:
        print("not set up")
        return 2
    run(cache_dir, required)
    return 0  # 0 even on a write failure so a scheduler does not retry in a loop; the run log holds the result


if __name__ == "__main__":
    sys.exit(main())
