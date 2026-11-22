# Module:      vault_ticket_files.py
# Description: Reads ticket state files, scans ticket folders, and writes a new ticket folder in the vault.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       plane sync vault side; write_new_ticket_folder is the only writer and is create-only
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from connectors.plane.plane_sync_settings import PrefixRow
from core.paths import iter_ticket_folders, ticket_folder as find_ticket_folder

FRONTMATTER_FENCE = "---"
STATE_FILE_SUFFIX = "-state.md"
SESSION_FILE_INFIX = "-session-"
PLACEHOLDER_PATTERN = re.compile(r"\{([a-z_]+)\}")
STATUS_SPLIT_PATTERN = re.compile(r"\s+[\(\-]")
SAFE_WORD_PATTERN = re.compile(r"[A-Za-z0-9_\-]+")
TICKET_ID_PATTERN = re.compile(r"([A-Za-z]+)-([0-9]+)")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
SAFE_TEXT_LIMIT = 80
EXIT_OK = 0
EXIT_STOPPED = 2


class VaultTicketError(RuntimeError):
    """Raised when a ticket file or folder cannot be read or written."""


class VaultFolderExistsError(VaultTicketError):
    """Raised when the folder for a new ticket already exists."""


@dataclass(frozen=True)
class VaultTicketState:
    ticket_id: str
    title: str
    status_word: str
    body_text: str
    raw_text: str
    state_path: Path


def parse_ticket_id(ticket_id: str) -> tuple[str, int] | None:
    """Split an id such as PROJ-339 into its prefix and number. None when the text is not a ticket id."""
    match = TICKET_ID_PATTERN.fullmatch(ticket_id)
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def safe_text(text: str, limit: int = SAFE_TEXT_LIMIT) -> str:
    """Remove control characters and newlines and cap the length, so the text is safe to print."""
    return CONTROL_CHARACTERS.sub("", text)[:limit]


def skip_line(prefix: str) -> str:
    return f"skip | prefix {prefix} has no Plane project in the settings"


def ticket_id_gate(prefix_table: Mapping[str, PrefixRow], ticket_id: str) -> tuple[str, int] | None:
    """Return (output line, exit code) when the id must not reach Plane, or None for a mapped ticket id."""
    parsed = parse_ticket_id(ticket_id)
    if parsed is None:
        return f"stopped | not a ticket id: {safe_text(ticket_id)}", EXIT_STOPPED
    if parsed[0] not in prefix_table:
        return skip_line(parsed[0]), EXIT_OK
    return None


def format_ticket_id(prefix: str, number: int, row: PrefixRow) -> str:
    return f"{prefix}-{number:0{row.number_width}d}"


def ticket_folder(ticket_id: str, tickets_root: Path) -> Path:
    """The folder of one ticket, flat or under its prefix folder.

    An existing ticket is found through the shared path helper. For a ticket that does not exist
    yet, the new folder goes under the prefix folder when the vault already has one, else flat.
    """
    found = find_ticket_folder(ticket_id, tickets_root)
    if found is not None:
        return found
    prefix = ticket_id.split("-", 1)[0]
    if tickets_root.is_dir():
        for child in sorted(tickets_root.iterdir()):
            if child.is_dir() and child.name.upper() == prefix.upper() and child.name.isalpha():
                return child / ticket_id
    return tickets_root / ticket_id


def highest_local_ticket_number(row: PrefixRow, tickets_root: Path) -> int:
    if not tickets_root.is_dir():
        return 0
    pattern = re.compile(row.ticket_pattern)
    highest = 0
    for child in iter_ticket_folders(tickets_root):
        match = pattern.match(child.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def _split_frontmatter(text: str, source_name: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    fences = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == FRONTMATTER_FENCE]
    if len(fences) < 2:
        raise VaultTicketError(f"{source_name}: frontmatter is missing")
    return "".join(lines[fences[0] + 1:fences[1]]), "".join(lines[fences[1] + 1:])


PLAIN_NON_TEXT = re.compile(r"^(?:[-+]?\d+(?:\.\d+)?|true|false|null|~)$", re.IGNORECASE)
KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(?:\s+(.*))?$")
BODY_STATUS_LINE = re.compile(r"^Status:[ \t]*(\S.*)$")
FENCE_LINE = re.compile(r"^(`{3,}|~{3,})")


def _scalar(raw: str) -> object:
    """Read one frontmatter value: a JSON string, a quoted string, plain text, or a non-text scalar."""
    value = raw.strip()
    if value.startswith('"'):
        return json.loads(value)
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return None if PLAIN_NON_TEXT.match(value) else value


def _read_front(front_text: str, source_name: str) -> dict[str, object]:
    """A small reader for flat key: value frontmatter. Nested lines are skipped."""
    front: dict[str, object] = {}
    for line in front_text.splitlines():
        if not line.strip() or line.startswith(("#", " ", "\t", "-")):
            continue
        match = KEY_LINE.match(line)
        if match is None:
            raise VaultTicketError(f"{source_name}: frontmatter is not valid")
        try:
            front[match.group(1)] = _scalar(match.group(2) or "")
        except ValueError:
            raise VaultTicketError(f"{source_name}: frontmatter is not valid") from None
    return front


def _body_status(body_text: str) -> str | None:
    """The first Status line at column one outside fenced code, or None."""
    fence: str | None = None
    for line in body_text.splitlines():
        marker = FENCE_LINE.match(line)
        if marker and fence is None:
            fence = marker.group(1)[0]
        elif marker and marker.group(1)[0] == fence:
            fence = None
        elif fence is None and BODY_STATUS_LINE.match(line):
            return BODY_STATUS_LINE.match(line).group(1).strip()  # type: ignore[union-attr]
    return None


def parse_state_text(text: str, source_name: str) -> VaultTicketState:
    front_text, body_text = _split_frontmatter(text, source_name)
    front = _read_front(front_text, source_name)
    if not isinstance(front.get("title"), str):
        raise VaultTicketError(f"{source_name}: key title is missing or not text")
    status = front.get("status") if isinstance(front.get("status"), str) else _body_status(body_text)
    if not isinstance(status, str):
        raise VaultTicketError(f"{source_name}: key status is missing or not text")
    ticket_value = front.get("ticket")
    return VaultTicketState(
        ticket_id=ticket_value if isinstance(ticket_value, str) else "",
        title=str(front["title"]),
        status_word=status,
        body_text=body_text,
        raw_text=text,
        state_path=Path(source_name),
    )


def read_state_file(folder: Path, ticket_id: str) -> VaultTicketState:
    path = folder / f"{ticket_id}{STATE_FILE_SUFFIX}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        raise VaultTicketError(f"state file {path.name} cannot be read") from None
    state = parse_state_text(text, path.name)
    return VaultTicketState(
        ticket_id=state.ticket_id,
        title=state.title,
        status_word=state.status_word,
        body_text=state.body_text,
        raw_text=state.raw_text,
        state_path=path,
    )


def normalize_status_word(raw: str) -> str:
    head = STATUS_SPLIT_PATTERN.split(raw.strip(), maxsplit=1)[0]
    return head.upper().replace(" ", "_").replace("-", "_")


def render_initial_state_file(
    template_text: str,
    *,
    ticket_id: str,
    title: str,
    priority: str,
    scope: str,
    repo: str,
    work_type: str,
    today: str,
) -> str:
    for label, value in (("priority", priority), ("work_type", work_type)):
        if not SAFE_WORD_PATTERN.fullmatch(value):
            raise VaultTicketError(f"{label} holds characters that cannot be stored")
    values: Mapping[str, str] = {
        "ticket_id": ticket_id,
        "title": json.dumps(title),
        "priority": priority,
        "scope": json.dumps(scope),
        "repo": json.dumps(repo),
        "work_type": work_type,
        "today": today,
    }

    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise VaultTicketError(f"template placeholder {name} has no value")
        return values[name]

    return PLACEHOLDER_PATTERN.sub(fill, template_text)


def _remove_partial_folder(folder: Path, state_path: Path) -> None:
    state_path.unlink(missing_ok=True)
    folder.rmdir()


def write_new_ticket_folder(folder: Path, state_text: str, ticket_id: str) -> Path:
    state_path = folder / f"{ticket_id}{STATE_FILE_SUFFIX}"
    try:
        folder.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise VaultFolderExistsError(f"folder for {ticket_id} exists") from None
    except OSError:
        raise VaultTicketError(f"folder for {ticket_id} cannot be created") from None
    try:
        with state_path.open("x", encoding="utf-8") as handle:
            handle.write(state_text)
    except OSError:
        _remove_partial_folder(folder, state_path)
        raise VaultTicketError(f"state file for {ticket_id} cannot be written") from None
    return state_path


def session_log_files(folder: Path, ticket_id: str) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(folder.glob(f"{ticket_id}{SESSION_FILE_INFIX}*.md"), key=lambda path: path.name)
