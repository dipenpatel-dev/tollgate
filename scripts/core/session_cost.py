#!/usr/bin/env python3
"""
module_name: session_cost.py
description: Session cost tracker. Reads a Claude session log and writes to a cost ledger in the output folder.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial port. Local time, no fixed time zone. Ledger path from the path loader.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp

# Pricing constants - update when model changes
# Check the provider price page and edit these four numbers when the model changes.
PRICE_INPUT_PER_MTK       = 3.00   # $ per million input tokens
PRICE_OUTPUT_PER_MTK      = 15.00  # $ per million output tokens
PRICE_CACHE_WRITE_PER_MTK = 3.75   # $ per million cache creation tokens
PRICE_CACHE_READ_PER_MTK  = 0.30   # $ per million cache read tokens

LEDGER_NAME      = "session-costs.jsonl"
RECENT_MINUTES   = 10
TOKENS_PER_MILLION = 1_000_000


def sessions_base(override: Optional[Path] = None) -> Path:
    """Folder that holds one sub-folder per project, each with session .jsonl files."""
    if override:
        return override
    config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if not config:
        sys.exit("not set up: pass --sessions-dir or set CLAUDE_CONFIG_DIR")
    return Path(config).expanduser() / "projects"


def ledger_path() -> Path:
    try:
        return get_path("output") / LEDGER_NAME
    except NotSetUp as exc:
        sys.exit(str(exc))


def derive_project_slug(cwd: Path) -> str:
    # Claude Code names a project folder by turning every character that is not a letter or digit into a dash.
    return re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def find_session_file(project_slug: str, override: Optional[Path],
                      base: Optional[Path] = None) -> Path:
    if override:
        return override

    sessions_dir = sessions_base(base) / project_slug
    if not sessions_dir.exists():
        sys.exit(
            f"No Claude sessions directory for cwd {Path.cwd()}. "
            "Pass --session-file PATH."
        )

    jsonl_files = sorted(
        sessions_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not jsonl_files:
        sys.exit(f"No .jsonl files found in {sessions_dir}.")

    cutoff = datetime.now(tz=timezone.utc).timestamp() - RECENT_MINUTES * 60
    recent = [p for p in jsonl_files if p.stat().st_mtime >= cutoff]
    if len(recent) > 1:
        print(
            f"Warning: multiple recently-modified sessions found. "
            f"Using {jsonl_files[0].name}. Pass --session-file PATH to override.",
            file=sys.stderr,
        )

    return jsonl_files[0]


def extract_session_id(session_file: Path) -> str:
    with open(session_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            session_id = entry.get("sessionId")
            if session_id:
                return session_id
    sys.exit(f"No sessionId found in {session_file}.")


def load_ledger() -> List[dict]:
    if not ledger_path().exists():
        return []
    entries = []
    with open(ledger_path()) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def append_ledger(entry: dict) -> None:
    ledger_path().parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path(), "a") as f:
        f.write(json.dumps(entry) + "\n")


def now_str() -> str:
    return datetime.now().astimezone().strftime("%H:%M")


def today_str() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def timestamp_to_str(ts: str) -> str:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.astimezone().strftime("%H:%M")


def _aggregate_tokens(
    session_file: Path,
) -> Tuple[int, int, int, int, Optional[str], bool]:
    input_tokens = output_tokens = cache_creation_tokens = cache_read_tokens = 0
    first_timestamp: Optional[str] = None
    has_assistant_entries = False

    with open(session_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if first_timestamp is None:
                first_timestamp = entry.get("timestamp")
            if entry.get("type") != "assistant":
                continue
            has_assistant_entries = True
            usage = entry.get("message", {}).get("usage", {})
            input_tokens          += usage.get("input_tokens", 0)
            output_tokens         += usage.get("output_tokens", 0)
            cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
            cache_read_tokens     += usage.get("cache_read_input_tokens", 0)

    return (
        input_tokens,
        output_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        first_timestamp,
        has_assistant_entries,
    )


def _get_start_time(
    ledger: List[dict], session_id: str, first_timestamp: Optional[str]
) -> str:
    for entry in ledger:
        if entry.get("sessionId") == session_id and entry.get("status") == "open":
            return entry.get("start", "unknown")
    if first_timestamp:
        return timestamp_to_str(first_timestamp)
    return "unknown"


def format_summary(entry: dict) -> str:
    date        = entry.get("date", "?")
    start       = entry.get("start", "?")
    end         = entry.get("end", "?")
    cost        = entry.get("cost_usd", 0.0)
    inp         = entry.get("input_tokens", 0)
    out         = entry.get("output_tokens", 0)
    cache_write = entry.get("cache_creation_tokens", 0)
    cache_read  = entry.get("cache_read_tokens", 0)
    tasks       = entry.get("tasks", "")
    return (
        f"{date} | {start}-{end} | ${cost:.2f} | "
        f"{inp // 1000}K in / {out // 1000}K out / "
        f"{cache_write // 1000}K write / {cache_read // 1000}K read | {tasks}"
    )


def run_start(session_id: str) -> None:
    ledger = load_ledger()
    for entry in ledger:
        if entry.get("sessionId") == session_id and entry.get("status") == "open":
            return

    stub = {
        "sessionId": session_id,
        "date":      today_str(),
        "start":     now_str(),
        "project":   derive_project_slug(Path.cwd()).lstrip("-"),
        "status":    "open",
    }
    append_ledger(stub)


def _compute_cost(inp: int, out: int, cache_write: int, cache_read: int) -> float:
    return (
        inp          / TOKENS_PER_MILLION * PRICE_INPUT_PER_MTK
        + out        / TOKENS_PER_MILLION * PRICE_OUTPUT_PER_MTK
        + cache_write / TOKENS_PER_MILLION * PRICE_CACHE_WRITE_PER_MTK
        + cache_read  / TOKENS_PER_MILLION * PRICE_CACHE_READ_PER_MTK
    )


def _build_closed_entry(
    session_id: str,
    start_time: str,
    inp: int,
    out: int,
    cache_write: int,
    cache_read: int,
    cost_usd: float,
    tasks: str,
) -> dict:
    return {
        "sessionId":             session_id,
        "date":                  today_str(),
        "start":                 start_time,
        "end":                   now_str(),
        "project":               derive_project_slug(Path.cwd()).lstrip("-"),
        "input_tokens":          inp,
        "output_tokens":         out,
        "cache_creation_tokens": cache_write,
        "cache_read_tokens":     cache_read,
        "cost_usd":              round(cost_usd, 4),
        "tasks":                 tasks,
        "status":                "closed",
    }


def run_close(session_id: str, session_file: Path, tasks: str) -> None:
    all_zero = all(
        v == 0.0
        for v in [
            PRICE_INPUT_PER_MTK,
            PRICE_OUTPUT_PER_MTK,
            PRICE_CACHE_WRITE_PER_MTK,
            PRICE_CACHE_READ_PER_MTK,
        ]
    )
    if all_zero:
        sys.exit(
            "Pricing constants not set. Fill in PRICE_* in session_cost.py before running."
        )

    ledger = load_ledger()
    for entry in ledger:
        if entry.get("sessionId") == session_id and entry.get("status") == "closed":
            print(format_summary(entry))
            return

    inp, out, cache_write, cache_read, first_ts, has_entries = _aggregate_tokens(
        session_file
    )
    if not has_entries:
        print(
            f"Warning: No assistant entries found in {session_file.name}.",
            file=sys.stderr,
        )

    start_time   = _get_start_time(ledger, session_id, first_ts)
    cost_usd     = _compute_cost(inp, out, cache_write, cache_read)
    closed_entry = _build_closed_entry(
        session_id, start_time, inp, out, cache_write, cache_read, cost_usd, tasks
    )
    append_ledger(closed_entry)
    print(format_summary(closed_entry))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Session cost tracker for Claude Code sessions."
    )
    parser.add_argument("--mode", choices=["start", "close"], required=True)
    parser.add_argument(
        "--tasks",
        default="",
        help="One-line summary of session tasks (required for --mode=close)",
    )
    parser.add_argument(
        "--session-file",
        type=Path,
        default=None,
        help="Override JSONL file path",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Folder with one sub-folder per project (default: CLAUDE_CONFIG_DIR/projects)",
    )
    args = parser.parse_args()

    project_slug = derive_project_slug(Path.cwd())
    session_file = find_session_file(project_slug, args.session_file, args.sessions_dir)
    session_id   = extract_session_id(session_file)

    if args.mode == "start":
        run_start(session_id)
    else:
        if not args.tasks:
            sys.exit("--tasks is required for --mode=close")
        run_close(session_id, session_file, args.tasks)


if __name__ == "__main__":
    main()
