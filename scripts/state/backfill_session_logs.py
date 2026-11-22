# Module:      backfill_session_logs.py
# Description: One-time batch retirement of session logs for all terminal tickets.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# ChangeLog:
#   Initial implementation

from __future__ import annotations

import argparse
import re
import sys
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp, folder_name, iter_ticket_folders  # noqa: E402


SYSTEM_MAP_DIR = folder_name("system_map")
REFERENCE_DIR = folder_name("reference")
TICKETS_DIR = folder_name("tickets")
KNOWLEDGE_DIR = folder_name("knowledge")
EDUCATION_DIR = folder_name("education")
CONVERSATIONS_DIR_NAME = folder_name("conversations")
THREADS_DIR_NAME = folder_name("chat_threads")

SESSION_GLOB = "*-session-*.md"
SPECS_SUBPATH = (KNOWLEDGE_DIR + "/specs")
RETIRE_SCRIPT = Path(__file__).resolve().parent / "retire_session_logs.py"
DEFAULT_OUTCOME = "Retired by batch backfill (backfill_session_logs.py)."
TERMINAL_STATUSES = {"SHIPPED", "CLOSED", "ABANDONED"}


@dataclass
class _Candidate:
    key: str
    terminal_status: str
    tickets_tree: Path
    specs_tree: Path
    tickets_count: int
    specs_count: int


def _tickets_dir() -> Path:
    return get_path("tickets")


def _specs_dir() -> Path:
    return get_path("vault") / SPECS_SUBPATH


def _parse_frontmatter(state_file: Path) -> dict:
    """Extract YAML frontmatter from a state.md file. Returns empty dict if absent."""
    text = state_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _count_session_logs(tree: Path) -> int:
    """Count unarchived session logs directly in tree (not in archive/ subfolder)."""
    if not tree.exists():
        return 0
    return len(list(tree.glob(SESSION_GLOB)))


def _extract_close_date(terminal_status: str) -> str:
    """Parse YYYY-MM-DD from terminal_status value; fall back to today if absent."""
    match = re.search(r"\d{4}-\d{2}-\d{2}", terminal_status)
    if match:
        return match.group(0)
    return date.today().isoformat()


def _build_candidates(tickets_dir: Path, specs_root: Path) -> list[_Candidate]:
    """Scan the tickets folder for state files with a recognised terminal_status."""
    candidates = []
    state_files = []
    for folder in iter_ticket_folders(tickets_dir):
        state_file = folder / (folder.name + "-state.md")
        if state_file.is_file():
            state_files.append(state_file)
    for state_file in state_files:
        fm = _parse_frontmatter(state_file)
        terminal_status = str(fm.get("terminal_status", "")).strip()
        if not terminal_status:
            continue
        status_word = terminal_status.split()[0]
        if status_word not in TERMINAL_STATUSES:
            continue
        key = str(fm.get("ticket", "") or state_file.parent.name)
        tickets_tree = state_file.parent
        specs_tree = specs_root / key
        tickets_count = _count_session_logs(tickets_tree)
        specs_count = _count_session_logs(specs_tree)
        if tickets_count + specs_count == 0:
            continue
        candidates.append(
            _Candidate(
                key=key,
                terminal_status=terminal_status,
                tickets_tree=tickets_tree,
                specs_tree=specs_tree,
                tickets_count=tickets_count,
                specs_count=specs_count,
            )
        )
    return candidates


def _display_candidates(candidates: list[_Candidate]) -> None:
    """Print the full candidate list with per-tree session log counts."""
    print(f"\nSession logs to retire: {len(candidates)} ticket(s)\n")
    for c in candidates:
        print(
            f"  {c.key:<20} [{c.terminal_status}]"
            f"  tickets: {c.tickets_count}  specs: {c.specs_count}"
        )
    print()


def _retire_ticket(candidate: _Candidate) -> bool:
    """Call retire_session_logs.py for one ticket. Returns True on success."""
    close_date = _extract_close_date(candidate.terminal_status)
    cmd = [
        sys.executable,
        str(RETIRE_SCRIPT),
        "--ticket", candidate.key,
        "--terminal-status", candidate.terminal_status,
        "--close-date", close_date,
        "--outcome-sentence", DEFAULT_OUTCOME,
        "--tree", str(candidate.tickets_tree),
        "--tree", str(candidate.specs_tree),
    ]
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch retire session logs of finished tickets.")
    parser.add_argument("--yes", action="store_true", help="Proceed without asking. Without it the list is shown and you are asked.")
    parser.add_argument("--tickets-dir", type=Path, default=None, help="Default: the tickets path.")
    parser.add_argument("--specs-dir", type=Path, default=None, help="Default: specs folder in the vault.")
    args = parser.parse_args(argv)
    try:
        tickets_dir = args.tickets_dir or _tickets_dir()
        specs_dir = args.specs_dir or _specs_dir()
    except NotSetUp:
        print("not set up", file=sys.stderr)
        return 2
    candidates = _build_candidates(tickets_dir, specs_dir)

    if not candidates:
        print("No terminal tickets with unretired session logs found.")
        return 0

    _display_candidates(candidates)
    if not args.yes:
        response = input("Retire all listed session logs? Type 'yes' to proceed: ")
        if response != "yes":
            print("Aborted. No files moved.")
            return 0

    retired = 0
    failed: list[str] = []
    for c in candidates:
        if _retire_ticket(c):
            retired += 1
        else:
            print(f"FAILED: {c.key}")
            failed.append(c.key)

    print(f"\nBatch complete.  Retired: {retired}  Failed: {len(failed)}")
    if failed:
        print(f"Failed keys: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
