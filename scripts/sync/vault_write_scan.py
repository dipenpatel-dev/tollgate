"""
vault_write_scan.py
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: Shared checks for the sync scripts that write transcripts and notes into the vault
       (sync_conversations.py, sync_meetings.py). Before a file is written, secrets are
       redacted with the same rules as hooks/scrub_secrets.py and the text is scanned with
       hooks/phi_patterns.py. A PHI hit at deny or ask level means the file is NOT written;
       a short quarantine record (file name, reason, no content) is appended instead.
       Also holds the state file helpers: a corrupt state file is reported and replaced by an
       empty state, and a state write is atomic.
ChangeLog:
  - Created.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

HOOKS_ENV_HOME = "TOLLGATE_HOME"
BLOCKING_LEVELS = ("deny", "ask")


class ScanResult:
    """Outcome of scanning one text: the scrubbed text, the secret labels redacted, and PHI labels."""

    def __init__(self, text: str, redacted: list[str], phi: list[str], weak: list[str]) -> None:
        self.text = text
        self.redacted = redacted
        self.phi = phi
        self.weak = weak

    @property
    def quarantine(self) -> bool:
        return bool(self.phi)

    def reason(self) -> str:
        return "PHI scan: " + ", ".join(self.phi)


def hooks_dir() -> Path:
    """The hooks folder: next to scripts/ in the repo, else TOLLGATE_HOME/hooks."""
    beside = Path(__file__).resolve().parents[2] / "hooks"
    if (beside / "phi_patterns.py").exists():
        return beside
    return Path(os.environ.get(HOOKS_ENV_HOME, "")).expanduser() / "hooks"


def _load():
    folder = str(hooks_dir())
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import phi_patterns  # type: ignore
    import scrub_secrets  # type: ignore
    return phi_patterns, scrub_secrets


def scan_text(text: str) -> ScanResult:
    """Redact secrets, then scan for PHI. Raises if the hook modules cannot be loaded (fail closed)."""
    phi_patterns, scrub_secrets = _load()
    scrubbed, redacted = scrub_secrets.scrub_text(text)
    findings = phi_patterns.scan_levels([scrubbed])
    phi = [f"{f.label} ({f.level.value})" for f in findings if f.level.value in BLOCKING_LEVELS]
    weak = [f.label for f in findings if f.level.value not in BLOCKING_LEVELS]
    return ScanResult(scrubbed, redacted, phi, weak)


def record_quarantine(log_path: Path, source_name: str, reason: str) -> None:
    """Append one line: time, source file name, reason. Never any of the content."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    clean_name = source_name.replace("\n", " ")[:200]
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(f"{stamp} | {clean_name} | not written to the vault | {reason}\n")


def load_json_state(path: Path, warn: Callable[[str], None] = lambda m: print(m, file=sys.stderr)) -> dict:
    """Read a JSON object state file. A missing file gives {}. A corrupt one warns and gives {}."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        warn(f"warning: state file {path.name} is unreadable ({type(error).__name__}); starting fresh")
        return {}
    if not isinstance(data, dict):
        warn(f"warning: state file {path.name} is not a JSON object; starting fresh")
        return {}
    return data


def write_json_atomic(path: Path, data: dict) -> None:
    """Write JSON to a temp file in the same folder, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def scan_or_none(text: str) -> Optional[ScanResult]:
    """scan_text, or None when the scan itself cannot run (the caller must then not write)."""
    try:
        return scan_text(text)
    except Exception:
        return None
