# Module:      plane_sync_ledger.py
# Description: Reads and writes the per-ticket ledger of what was already sent to Plane.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       plane sync ledger in the output folder; atomic overwrite through a temp file
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import contextlib
import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

LEDGER_FILE_NAME = "plane_sync_ledger.json"
TEMP_SUFFIX = ".tmp"
LEDGER_FILE_MODE = 0o600
TEMP_RANDOM_BYTES = 4
REQUIRED_KEYS = (
    "ticket_id", "project_id", "work_item_id", "number", "description_sha",
    "status_word", "session_offsets", "posted_keys",
)


class PlaneSyncLedgerError(RuntimeError):
    """Raised when the ledger file is not valid or cannot be written."""


@dataclass
class SyncLedger:
    ticket_id: str
    project_id: str
    work_item_id: str
    number: int
    description_sha: str | None
    status_word: str | None
    session_offsets: dict[str, int]
    posted_keys: list[str]


def ledger_path(state_root: Path, ticket_id: str) -> Path:
    return state_root / ticket_id / LEDGER_FILE_NAME


def _checked(data: Any, path: Path) -> SyncLedger:
    if not isinstance(data, dict):
        raise PlaneSyncLedgerError(f"{path.name} is not an object")
    for key in REQUIRED_KEYS:
        if key not in data:
            raise PlaneSyncLedgerError(f"{path.name} is missing key {key}")
    texts_ok = all(isinstance(data[k], str) for k in ("ticket_id", "project_id", "work_item_id"))
    optional_ok = all(data[k] is None or isinstance(data[k], str) for k in ("description_sha", "status_word"))
    offsets_ok = isinstance(data["session_offsets"], dict) and all(
        isinstance(k, str) and isinstance(v, int) for k, v in data["session_offsets"].items()
    )
    keys_ok = isinstance(data["posted_keys"], list) and all(isinstance(k, str) for k in data["posted_keys"])
    number_ok = isinstance(data["number"], int) and not isinstance(data["number"], bool)
    if not (texts_ok and optional_ok and offsets_ok and keys_ok and number_ok):
        raise PlaneSyncLedgerError(f"{path.name} has a value of the wrong type")
    return SyncLedger(**{key: data[key] for key in REQUIRED_KEYS})


def load_ledger(path: Path) -> SyncLedger | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PlaneSyncLedgerError(f"{path.name} is not valid JSON") from None
    return _checked(data, path)


def _write_temp_file(temp_path: Path, text: str) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = os.open(temp_path, flags, LEDGER_FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)


def save_ledger(path: Path, ledger: SyncLedger) -> None:
    unique = f".{os.getpid()}.{secrets.token_hex(TEMP_RANDOM_BYTES)}{TEMP_SUFFIX}"
    temp_path = path.with_name(path.name + unique)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_temp_file(temp_path, json.dumps(asdict(ledger), indent=2, sort_keys=True))
        os.replace(temp_path, path)
    except OSError:
        with contextlib.suppress(OSError):
            temp_path.unlink(missing_ok=True)
        raise PlaneSyncLedgerError(f"{path.name} cannot be written") from None
