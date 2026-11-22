"""
module_name: run_log.py
description: Append safe structured logger. Writes JSON lines to run_log.jsonl under an exclusive file lock.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported. The log file lives in the logs folder from the path loader. Fixed allow list of keys and fixed reason words, so no raw error text is ever written.
"""

from __future__ import annotations

import fcntl
import json
import pathlib
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core.paths import get_path  # noqa: E402

LOG_NAME: str = "run_log.jsonl"
ALLOWED_KEYS: frozenset[str] = frozenset(
    {"script", "start_ts", "end_ts", "result", "reason", "reject_count"}
)


class _StrEnum(str, Enum):
    """String enum for Python 3.9 (enum.StrEnum needs 3.11). str() gives the value."""

    def __str__(self) -> str:
        return str(self.value)

    __format__ = str.__format__


class LogResult(_StrEnum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"


class LogReason(_StrEnum):
    AUTH_OK = "auth_ok"
    AUTH_FAILED = "auth_failed"
    API_OK = "api_ok"
    API_TIMEOUT = "api_timeout"
    API_4XX = "api_4xx"
    API_5XX = "api_5xx"
    SCHEMA_INVALID = "schema_invalid"
    PHI_REJECTED = "phi_rejected"
    PHI_REJECTED_ALL = "phi_rejected_all"
    WRITE_OK = "write_ok"


def logfile() -> Path:
    """The run log path, inside the logs folder. Created on first write."""
    return get_path("logs") / LOG_NAME


def append(record: dict[str, Any], path: Path | None = None) -> None:
    """Append one JSON line to run_log.jsonl under exclusive lock.

    Validates result and reason against their enums before writing.
    Raises ValueError if either field is missing or not a valid enum value.
    Raw exception text is not permitted in the reason field.
    """
    try:
        LogResult(record.get("result", ""))
    except ValueError:
        raise ValueError("run_log.append: invalid result. Must be a LogResult value.") from None
    try:
        LogReason(record.get("reason", ""))
    except ValueError:
        raise ValueError("run_log.append: invalid reason. Use LogReason enum values only.") from None

    missing = ALLOWED_KEYS - record.keys()
    if missing:
        raise ValueError(f"run_log.append: missing required fields: {sorted(missing)}")

    _validate_field_types(record)

    output = {k: v for k, v in record.items() if k in ALLOWED_KEYS}
    target = path or logfile()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        fh.write(json.dumps(output) + "\n")
        fh.flush()


def _validate_field_types(record: dict[str, Any]) -> None:
    script = record["script"]
    if not isinstance(script, str) or not script.strip() or "\n" in script or not script.isascii():
        raise ValueError("run_log.append: script must be a non-empty ASCII string with no newlines.")

    for ts_field in ("start_ts", "end_ts"):
        ts_val = record[ts_field]
        if not isinstance(ts_val, str):
            raise ValueError(f"run_log.append: {ts_field} must be an ISO format string.")
        try:
            datetime.fromisoformat(ts_val)
        except ValueError:
            raise ValueError(f"run_log.append: {ts_field} must be a valid ISO format datetime.") from None

    reject = record["reject_count"]
    if not isinstance(reject, int) or isinstance(reject, bool) or reject < 0:
        raise ValueError("run_log.append: reject_count must be a non-negative integer.")
