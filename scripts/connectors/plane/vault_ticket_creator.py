# Module:      vault_ticket_creator.py
# Description: The create command. Makes the Plane card first, then the vault folder, state file and ledger.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       plane sync create; no file or folder is written before the card exists
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

from pathlib import Path
from typing import Callable

from connectors.plane.plane_comment_builder import find_secret_pattern
from connectors.plane.plane_sync_ledger import PlaneSyncLedgerError, SyncLedger, ledger_path, save_ledger
from connectors.plane.plane_sync_settings import PlaneSyncSettings, PrefixRow
from connectors.plane.plane_work_item_client import PlaneWorkItemClient, PlaneWorkItemRecord
from connectors.plane.vault_ticket_files import (
    VaultFolderExistsError,
    VaultTicketError,
    format_ticket_id,
    highest_local_ticket_number,
    normalize_status_word,
    parse_state_text,
    render_initial_state_file,
    skip_line,
    ticket_folder,
    write_new_ticket_folder,
)

EXIT_OK = 0
EXIT_STOPPED = 2
MAX_TITLE_LENGTH = 255
PLACEHOLDER_TICKET_NUMBER = 0
DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "plane_ticket_state_template.md"


def _stop(emit: Callable[[str], None], text: str) -> int:
    emit(f"stopped | {text}")
    return EXIT_STOPPED


def _check_inputs(template_text: str, row: PrefixRow, prefix: str, fields: dict[str, str]) -> str | None:
    """Render and parse the state file with a placeholder number. Return the problem, or None."""
    if len(fields["title"]) > MAX_TITLE_LENGTH:
        return f"title is longer than {MAX_TITLE_LENGTH} characters"
    try:
        sample = render_initial_state_file(
            template_text, ticket_id=format_ticket_id(prefix, PLACEHOLDER_TICKET_NUMBER, row), **fields
        )
        parsed = parse_state_text(sample, "new state file")
    except VaultTicketError as error:
        return str(error)
    if parsed.title != fields["title"]:
        return "title does not read back equal"
    return None


def _find_or_create_card(
    settings: PlaneSyncSettings,
    client: PlaneWorkItemClient,
    project_id: str,
    *,
    title: str,
    local_highest: int,
    expected_id: str,
    emit: Callable[[str], None],
) -> PlaneWorkItemRecord | None:
    """Adopt a half-finished card, or pass the number guard and create one. None means stopped."""
    items = client.list_work_items(project_id)
    plane_highest = max((item.number for item in items), default=0)
    candidates = [
        item for item in items
        if item.name == title and item.external_id in (None, "", expected_id)
    ]
    if len(candidates) > 1:
        numbers = ", ".join(str(item.number) for item in candidates)
        _stop(emit, f"several cards match the title: {numbers}")
        return None
    if candidates:
        card = candidates[0]
        if card.number == plane_highest and card.number == local_highest + 1:
            return card
        _stop(emit, f"card {card.number} matches the title but Plane highest {plane_highest}, local highest {local_highest}")
        return None
    if plane_highest != local_highest:
        _stop(emit, f"Plane highest {plane_highest}, local highest {local_highest}")
        return None
    state_ids = client.list_state_ids(project_id)
    if settings.new_ticket_board_status not in state_ids:
        _stop(emit, f"board status {settings.new_ticket_board_status} not found")
        return None
    return client.create_work_item(
        project_id, name=title, state_id=state_ids[settings.new_ticket_board_status]
    )


def _write_ledger(
    state_root: Path, card: PlaneWorkItemRecord, project_id: str, ticket_id: str, state_text: str,
) -> None:
    status_word = normalize_status_word(parse_state_text(state_text, ticket_id).status_word)
    ledger = SyncLedger(
        ticket_id=ticket_id, project_id=project_id, work_item_id=card.work_item_id,
        number=card.number, description_sha=None, status_word=status_word,
        session_offsets={}, posted_keys=[],
    )
    save_ledger(ledger_path(state_root, ticket_id), ledger)


def _project_id(client: PlaneWorkItemClient, row: PrefixRow) -> str | None:
    for project in client.list_projects():
        if project.project_key == row.project_key:
            return project.project_id
    return None


def _read_template(settings: PlaneSyncSettings) -> str:
    """The ticket state template: the file named in the settings, else the one shipped next to this module."""
    template_path = Path(settings.template_path).expanduser() if settings.template_path else DEFAULT_TEMPLATE
    try:
        return template_path.read_text(encoding="utf-8")
    except OSError:
        raise VaultTicketError(f"template {template_path.name} cannot be read") from None


def _finish_create(
    settings: PlaneSyncSettings, client: PlaneWorkItemClient, tickets_root: Path, state_root: Path,
    row: PrefixRow, project_id: str, card: PlaneWorkItemRecord, state_text_for: Callable[[str], str],
    prefix: str, emit: Callable[[str], None],
) -> int:
    ticket_id = format_ticket_id(prefix, card.number, row)
    client.update_work_item(
        project_id, card.work_item_id,
        {"external_id": ticket_id, "external_source": settings.external_source_name},
    )
    state_text = state_text_for(ticket_id)
    try:
        _write_ledger(state_root, card, project_id, ticket_id, state_text)
        write_new_ticket_folder(ticket_folder(ticket_id, tickets_root), state_text, ticket_id)
    except VaultFolderExistsError:
        return _stop(emit, f"folder for {ticket_id} exists; card {card.number} kept")
    except (VaultTicketError, PlaneSyncLedgerError) as error:
        return _stop(emit, f"{error}; card {card.number} kept")
    emit(f"created | {ticket_id} | card {card.number}")
    return EXIT_OK


def _create_checked(
    settings: PlaneSyncSettings, client: PlaneWorkItemClient, tickets_root: Path, state_root: Path,
    row: PrefixRow, prefix: str, fields: dict[str, str], template: str, emit: Callable[[str], None],
) -> int:
    hit = find_secret_pattern(fields["title"], settings.secret_patterns)
    if hit is not None:
        return _stop(emit, f"secret pattern {hit} in title; nothing sent")
    problem = _check_inputs(template, row, prefix, fields)
    if problem is not None:
        return _stop(emit, f"title cannot be stored: {problem}")
    local_highest = highest_local_ticket_number(row, tickets_root)
    project_id = _project_id(client, row)
    if project_id is None:
        return _stop(emit, f"Plane project {row.project_key} not found")
    expected_id = format_ticket_id(prefix, local_highest + 1, row)
    card = _find_or_create_card(settings, client, project_id, title=fields["title"],
                                local_highest=local_highest, expected_id=expected_id, emit=emit)
    if card is None:
        return EXIT_STOPPED
    return _finish_create(
        settings, client, tickets_root, state_root, row, project_id, card,
        lambda ticket_id: render_initial_state_file(template, ticket_id=ticket_id, **fields),
        prefix, emit,
    )


def run_create(
    settings: PlaneSyncSettings,
    client: PlaneWorkItemClient,
    tickets_root: Path,
    state_root: Path,
    *,
    prefix: str,
    title: str,
    priority: str,
    scope: str,
    repo: str,
    work_type: str,
    today: str,
    emit: Callable[[str], None],
    template_text: str | None = None,
) -> int:
    """Create the card, then the vault files. Returns 0 on success, 2 when stopped."""
    row = settings.prefix_table.get(prefix)
    if row is None:
        emit(skip_line(prefix))
        return EXIT_STOPPED
    template = template_text if template_text is not None else _read_template(settings)
    fields = {"title": title, "priority": priority, "scope": scope, "repo": repo,
              "work_type": work_type, "today": today}
    return _create_checked(settings, client, tickets_root, state_root, row, prefix, fields, template, emit)
