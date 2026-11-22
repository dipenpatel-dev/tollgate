"""
sync_conversations.py
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: Convert Claude Code JSONL session files into markdown in the conversations folder.
       Output goes to the conversations path, the sync state to the state path. The
       session folder is read only.
ChangeLog:
  Initial implementation
  Added from __future__ annotations (Python 3.9). Each transcript is scrubbed of credentials and
  scanned for PHI before it is written; a PHI hit means nothing is written and a short record
  (file name, reason, no content) goes to quarantine.log in the state folder. A corrupt state
  file is reported and replaced by an empty one, and the state write is atomic.
Usage:
  python3 sync_conversations.py [--full] [--sessions-dir DIR]
  --full          Re-convert all sessions regardless of prior state
  --sessions-dir  Folder of session files. Default: CLAUDE_CONFIG_DIR/projects/<this vault>.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import get_path, file_value, NotSetUp  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_write_scan  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────

CLAUDE_SESSIONS_DIR = None
CONVERSATIONS_DIR = None
STATE_FILE = None
STATE_NAME = "sync_conversations_state.json"
USER_LABEL = "U"
ASSISTANT_LABEL = "C"


def project_slug(path) -> str:
    """Claude Code's folder name for a project path: every character that is not a letter or digit becomes a dash."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def default_sessions_dir() -> Path:
    """The Claude Code folder for the current vault.

    A `sessions` line in the paths file wins. Otherwise it is
    CLAUDE_CONFIG_DIR/projects/<vault path with every non letter or digit as a dash>.
    """
    chosen = file_value("sessions")
    if chosen is not None:
        return chosen
    base = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if not base:
        raise NotSetUp("not set up: pass --sessions-dir or set CLAUDE_CONFIG_DIR")
    return Path(base).expanduser() / "projects" / project_slug(get_path("vault"))


def configure(sessions_dir=None, conversations_dir=None, state_dir=None) -> None:
    """Set the three folders. With no arguments they come from the path loader."""
    global CLAUDE_SESSIONS_DIR, CONVERSATIONS_DIR, STATE_FILE
    CLAUDE_SESSIONS_DIR = Path(sessions_dir) if sessions_dir is not None else default_sessions_dir()
    CONVERSATIONS_DIR = Path(conversations_dir) if conversations_dir is not None else get_path("conversations")
    state_root = Path(state_dir) if state_dir is not None else get_path("state")
    STATE_FILE = state_root / STATE_NAME

MONTH_NAMES = {
    1: "01-January", 2: "02-February", 3: "03-March", 4: "04-April",
    5: "05-May", 6: "06-June", 7: "07-July", 8: "08-August",
    9: "09-September", 10: "10-October", 11: "11-November", 12: "12-December",
}

# Minimum characters for a message to be worth including
MIN_MSG_CHARS = 10

# ── Filters ───────────────────────────────────────────────────────────────────

def is_skill_content(text: str) -> bool:
    """Detect injected skill file content, starts with '# /' heading."""
    return text.startswith("# /") and "\n**Role:**" in text[:200]


def is_system_continuation(text: str) -> bool:
    """Detect context-window continuation summary injected by Claude Code."""
    return text.startswith("This session is being continued from a previous conversation")


def is_command_invocation(text: str) -> bool:
    """Detect slash command XML tags injected by Claude Code."""
    return text.startswith("<command-message>") or text.startswith("<command-name>")


def clean_user_text(text: str) -> str:
    """Strip system-injected tags from user message text."""
    # Remove <ide_opened_file>...</ide_opened_file> blocks
    text = re.sub(r"<ide_opened_file>.*?</ide_opened_file>", "", text, flags=re.DOTALL)
    # Remove <system-reminder>...</system-reminder> blocks
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
    # Remove <ide_selection>...</ide_selection> blocks
    text = re.sub(r"<ide_selection>.*?</ide_selection>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_user_text(content) -> str | None:
    """Extract clean user text from message content (str or list of blocks)."""
    if isinstance(content, str):
        text = content.strip()
        if is_command_invocation(text) or is_system_continuation(text):
            return None
        cleaned = clean_user_text(text)
        return cleaned if len(cleaned) >= MIN_MSG_CHARS else None

    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = block.get("text", "").strip()
            if not text:
                continue
            if is_skill_content(text) or is_command_invocation(text) or is_system_continuation(text):
                continue
            cleaned = clean_user_text(text)
            if cleaned:
                parts.append(cleaned)
        combined = "\n\n".join(parts).strip()
        return combined if len(combined) >= MIN_MSG_CHARS else None

    return None


def extract_assistant_text(content) -> str | None:
    """Extract clean assistant text, skip thinking blocks, tool calls."""
    if not isinstance(content, list):
        return None
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text", "").strip()
        if text and len(text) >= MIN_MSG_CHARS:
            parts.append(text)
    combined = "\n\n".join(parts).strip()
    return combined if len(combined) >= MIN_MSG_CHARS else None

# ── JSONL parser ──────────────────────────────────────────────────────────────

def parse_session(jsonl_path: Path) -> dict | None:
    """
    Parse a JSONL session file into a structured session dict.
    Returns None if session has no substantive content.
    """
    turns: list[dict] = []
    ai_title: str = ""
    first_ts: datetime | None = None

    with open(jsonl_path, encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            record_type = obj.get("type")
            ts_str = obj.get("timestamp", "")

            # Parse timestamp
            ts: datetime | None = None
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if first_ts is None:
                        first_ts = ts
                except ValueError:
                    pass

            if record_type == "ai-title":
                ai_title = obj.get("aiTitle", "")

            elif record_type == "user":
                content = obj.get("message", {}).get("content", "")
                text = extract_user_text(content)
                if text and ts:
                    turns.append({"role": "user", "ts": ts, "text": text})

            elif record_type == "assistant":
                content = obj.get("message", {}).get("content", [])
                text = extract_assistant_text(content)
                if text and ts:
                    turns.append({"role": "assistant", "ts": ts, "text": text})

    if not turns or first_ts is None:
        return None

    return {
        "session_id": jsonl_path.stem,
        "title": ai_title or "Session",
        "first_ts": first_ts,
        "turns": turns,
    }

# ── Markdown writer ───────────────────────────────────────────────────────────

def session_to_markdown(session: dict) -> str:
    first_ts: datetime = session["first_ts"]
    date_str = first_ts.astimezone().strftime("%Y-%m-%d")
    title = session["title"]
    session_id = session["session_id"][:8]

    lines: list[str] = [
        f"# {date_str}, {title}",
        f"",
        f"**Session ID:** {session_id}",
        f"",
        f"---",
        f"",
    ]

    for turn in session["turns"]:
        ts_local = turn["ts"].astimezone()
        time_str = ts_local.strftime("%H:%M")
        role_label = USER_LABEL if turn["role"] == "user" else ASSISTANT_LABEL
        text = turn["text"]

        lines.append(f"**[{time_str}]** {role_label}: {text}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def output_path(session: dict) -> Path:
    first_ts: datetime = session["first_ts"].astimezone()
    year = str(first_ts.year)
    month_folder = MONTH_NAMES[first_ts.month]
    date_str = first_ts.strftime("%Y-%m-%d")
    filename = f"{date_str}-auto-{session['session_id'][:8]}.md"
    return CONVERSATIONS_DIR / year / month_folder / filename

# ── State management ──────────────────────────────────────────────────────────

def load_state() -> dict:
    """The saved state, or {} when missing or corrupt (a corrupt file prints a warning)."""
    return vault_write_scan.load_json_state(STATE_FILE)


def save_state(state: dict) -> None:
    vault_write_scan.write_json_atomic(STATE_FILE, state)


def quarantine_log() -> Path:
    return STATE_FILE.parent / "quarantine.log"

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Re-convert all sessions")
    parser.add_argument("--sessions-dir", type=Path, default=None, help="Folder of session files")
    args = parser.parse_args()
    try:
        configure(sessions_dir=args.sessions_dir)
    except NotSetUp:
        print("not set up", file=sys.stderr)
        sys.exit(2)

    if not CLAUDE_SESSIONS_DIR.exists():
        print(f"Sessions directory not found")
        sys.exit(1)

    state = {} if args.full else load_state()
    jsonl_files = sorted(CLAUDE_SESSIONS_DIR.glob("*.jsonl"))

    converted = 0
    skipped = 0
    empty = 0
    errors = 0
    quarantined = 0
    t_start = time.time()

    for jsonl_path in jsonl_files:
        file_key = jsonl_path.name
        mtime = str(jsonl_path.stat().st_mtime)

        if not args.full and state.get(file_key) == mtime:
            skipped += 1
            continue

        try:
            session = parse_session(jsonl_path)
        except Exception as e:
            print(f"  ERROR {file_key}: {e}")
            errors += 1
            state[file_key] = mtime
            continue

        if session is None:
            empty += 1
            state[file_key] = mtime
            continue

        scan = vault_write_scan.scan_or_none(session_to_markdown(session))
        if scan is None:
            print(f"  ERROR {file_key}: scan could not run, not written")
            errors += 1
            continue
        if scan.quarantine:
            vault_write_scan.record_quarantine(quarantine_log(), file_key, scan.reason())
            print(f"  QUARANTINED {file_key}: {scan.reason()}")
            quarantined += 1
            state[file_key] = mtime
            continue

        out_path = output_path(session)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(scan.text, encoding="utf-8")

        state[file_key] = mtime
        converted += 1
        print(f"  {out_path.name}")

    save_state(state)

    elapsed = round(time.time() - t_start, 1)
    print(f"\nDone in {elapsed}s")
    print(f"  Converted : {converted}")
    print(f"  Skipped   : {skipped} (unchanged)")
    print(f"  Empty     : {empty} (no substantive content)")
    print(f"  Errors    : {errors}")
    print(f"  Quarantined : {quarantined} (PHI found, not written)")


if __name__ == "__main__":
    main()
