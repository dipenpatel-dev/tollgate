# Module:      retire_session_logs.py
# Description: Moves vault session log files to archive/ subfolders and writes one archive summary.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# ChangeLog:
#   Initial implementation

import argparse
import shutil
import sys
from pathlib import Path

SESSION_GLOB = "*-session-*.md"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retire vault session logs to archive/ subfolders and write one archive summary."
    )
    parser.add_argument("--ticket", required=True, help="Ticket key (e.g. T-71).")
    parser.add_argument(
        "--terminal-status",
        required=True,
        dest="terminal_status",
        help="terminal_status value from state.md (e.g. 'SHIPPED 2026-06-05').",
    )
    parser.add_argument(
        "--close-date",
        required=True,
        dest="close_date",
        help="Close date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--outcome-sentence",
        required=True,
        dest="outcome_sentence",
        help="One sentence describing the terminal outcome. No patient identifiers.",
    )
    parser.add_argument(
        "--tree",
        action="append",
        default=[],
        metavar="PATH",
        help="Vault tree to scan (repeatable). First tree receives the archive summary.",
    )
    return parser.parse_args()


def _retire_tree(tree_path: Path) -> tuple[int, int]:
    """Move session logs from tree_path to tree_path/archive/. Returns (moved, already_archived)."""
    if not tree_path.exists():
        return 0, 0

    archive_dir = tree_path / "archive"
    already_archived = list(archive_dir.glob(SESSION_GLOB)) if archive_dir.exists() else []
    to_move = sorted(tree_path.glob(SESSION_GLOB))

    if not to_move:
        return 0, len(already_archived)

    archive_dir.mkdir(exist_ok=True)

    moved = 0
    for src in to_move:
        try:
            shutil.move(str(src), str(archive_dir / src.name))
            moved += 1
        except OSError:
            unmoved = len(to_move) - moved
            print(f"Move failed: {src}")
            print(f"  Moved: {moved}  Unmoved: {unmoved}")
            raise

    return moved, len(already_archived)


def _write_summary(
    summary_path: Path,
    ticket: str,
    terminal_status: str,
    close_date: str,
    outcome_sentence: str,
) -> None:
    """Write archive summary. No-op if already exists. Raises ValueError if outcome_sentence is empty."""
    if summary_path.exists():
        return

    if not outcome_sentence.strip():
        raise ValueError(f"outcome_sentence is empty for {ticket}. Archive summary not written.")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"# Archive Summary: {ticket}\n\n"
        f"Terminal status: {terminal_status}\n"
        f"Close date: {close_date}\n\n"
        f"{outcome_sentence}\n"
    )
    summary_path.write_text(content, encoding="utf-8")


def main() -> None:
    args = _parse_args()

    if not args.tree:
        print(f"Error: at least one --tree path is required for {args.ticket}.")
        sys.exit(1)

    total_moved = 0
    total_already_archived = 0

    try:
        for tree in args.tree:
            moved, already_archived = _retire_tree(Path(tree))
            total_moved += moved
            total_already_archived += already_archived
    except OSError:
        sys.exit(1)

    if total_moved == 0 and total_already_archived == 0:
        print(f"No session logs found for {args.ticket}.")
        sys.exit(0)

    summary_path = Path(args.tree[0]) / "archive" / f"{args.ticket}-archive-summary.md"

    try:
        _write_summary(
            summary_path,
            args.ticket,
            args.terminal_status,
            args.close_date,
            args.outcome_sentence,
        )
    except ValueError as exc:
        print(str(exc))
        sys.exit(1)

    if total_moved > 0:
        print(f"Retired {total_moved} session log(s) for {args.ticket}.")


if __name__ == "__main__":
    main()
