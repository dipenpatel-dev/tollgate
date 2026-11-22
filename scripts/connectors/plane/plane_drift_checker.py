# Module:      plane_drift_checker.py
# Description: The drift command: compares the Plane card of each ticket with its vault state file and prints each mismatch.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       plane sync drift; read only, sends no write call
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Sequence

from connectors.plane.plane_comment_builder import comment_key
from connectors.plane.plane_sync_settings import PlaneSyncSettings
from connectors.plane.plane_work_item_client import PlaneWorkItemClient, PlaneWorkItemRecord
from connectors.plane.vault_ticket_files import (
    VaultTicketState,
    parse_ticket_id,
    read_state_file,
    safe_text,
    ticket_folder,
    ticket_id_gate,
)

EXIT_OK = 0
EXIT_MISMATCH = 2
STATE_SHA_PATTERN = re.compile(r"state-sha: ([0-9a-f]{12})")


def _description_line(
    client: PlaneWorkItemClient, project_id: str, card: PlaneWorkItemRecord,
    state: VaultTicketState, ticket_id: str,
) -> str | None:
    description = client.get_work_item(project_id, card.work_item_id).description_html
    if description is None:
        return f"description_unreadable | {ticket_id} | the read returned no description"
    found = STATE_SHA_PATTERN.findall(description)
    card_sha = found[-1] if found else "none"
    file_sha = comment_key(state.raw_text)
    if card_sha != file_sha:
        return f"wrong_description | {ticket_id} | card {card_sha} file {file_sha}"
    return None


def _card_lines(
    client: PlaneWorkItemClient, project_id: str, cards: Sequence[PlaneWorkItemRecord],
    state: VaultTicketState, ticket_id: str, number: int,
) -> list[str]:
    card = next((c for c in cards if c.external_id == ticket_id), None)
    if card is None:
        return [f"missing_card | {ticket_id} | no card with that id"]
    lines: list[str] = []
    if card.number != number:
        lines.append(f"wrong_number | {ticket_id} | card {card.number} vault {number}")
    if card.name != state.title:
        lines.append(f'wrong_name | {ticket_id} | card "{safe_text(card.name)}" vault "{state.title}"')
    description_line = _description_line(client, project_id, card, state, ticket_id)
    if description_line is not None:
        lines.append(description_line)
    return lines


def _drift_one(
    settings: PlaneSyncSettings, client: PlaneWorkItemClient, tickets_root: Path, ticket_id: str,
    projects: dict[str, str], cards_by_key: dict[str, list[PlaneWorkItemRecord]], emit: Callable[[str], None],
) -> int:
    """Check one ticket id. Returns how many mismatch lines it printed."""
    gate = ticket_id_gate(settings.prefix_table, ticket_id)
    if gate is not None:
        emit(gate[0])
        return 1 if gate[1] != EXIT_OK else 0
    prefix, number = parse_ticket_id(ticket_id) or ("", 0)
    row = settings.prefix_table[prefix]
    state = read_state_file(ticket_folder(ticket_id, tickets_root), ticket_id)
    project_id = projects.get(row.project_key)
    if project_id is None:
        emit(f"missing_card | {ticket_id} | no card with that id")
        return 1
    if row.project_key not in cards_by_key:
        cards_by_key[row.project_key] = client.list_work_items(project_id)
    lines = _card_lines(client, project_id, cards_by_key[row.project_key], state, ticket_id, number)
    for line in lines:
        emit(line)
    return len(lines)


def run_drift(
    settings: PlaneSyncSettings,
    client: PlaneWorkItemClient,
    tickets_root: Path,
    *,
    ticket_ids: Sequence[str],
    emit: Callable[[str], None],
) -> int:
    """Print one line per mismatch between cards and state files. Returns 0 when none, else 2."""
    projects = {p.project_key: p.project_id for p in client.list_projects()}
    cards_by_key: dict[str, list[PlaneWorkItemRecord]] = {}
    mismatches = sum(
        _drift_one(settings, client, tickets_root, ticket_id, projects, cards_by_key, emit)
        for ticket_id in ticket_ids
    )
    return EXIT_MISMATCH if mismatches else EXIT_OK
