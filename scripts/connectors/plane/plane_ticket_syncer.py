# Module:      plane syncer.py
# Description: The sync command: sends the state file, the status and new session text of one ticket to its Plane card.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       plane sync sync; every send is guarded by the ledger and by the secret scan
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from connectors.plane.plane_comment_builder import (
    build_dev_extras,
    build_spec_extras,
    comment_key,
    cut_to_limit,
    extract_markdown_section,
    find_secret_pattern,
    markdown_to_html,
    read_new_session_text,
)
from connectors.plane.plane_sync_ledger import SyncLedger, ledger_path, load_ledger, save_ledger
from connectors.plane.plane_sync_settings import PlaneSyncSettings
from connectors.plane.plane_work_item_client import PlaneWorkItemClient
from connectors.plane.vault_ticket_files import (
    VaultTicketState,
    normalize_status_word,
    read_state_file,
    parse_ticket_id,
    session_log_files,
    ticket_folder,
    ticket_id_gate,
)

EXIT_OK = 0
EXIT_STOPPED = 2
STATE_SHA_PREFIX = "state-sha: "
EXTRAS_SPEC = "spec"
EXTRAS_DEV = "dev"
CURRENT_STATE_HEADING = "Current state"
PARTS_JOINER = "\n\n"
JOINER_LENGTH = len(PARTS_JOINER)
MAX_FIT_ROUNDS = 5
FIT_SAFETY = 0.95
NOTE_KEY_PREFIX = "note|"


@dataclass
class _Context:
    settings: PlaneSyncSettings
    client: PlaneWorkItemClient
    folder: Path
    ledger_file: Path
    ledger: SyncLedger
    state: VaultTicketState
    ticket_id: str
    sha: str
    emit: Callable[[str], None]


@dataclass
class _Result:
    description: str = "same"
    status: str = "same"
    comment: str = "none"
    cut: str = "no"
    first_sync: str = "no"
    unknown_word: str | None = None


def _stop(ctx: _Context, message: str) -> int:
    ctx.emit(f"stopped | {message}")
    return EXIT_STOPPED


def _first_sync_ledger(
    client: PlaneWorkItemClient, project_key: str,
    folder: Path, ticket_id: str, number: int, from_start: bool,
) -> SyncLedger | None:
    project = next((p for p in client.list_projects() if p.project_key == project_key), None)
    if project is None:
        return None
    card = next(
        (i for i in client.list_work_items(project.project_id)
         if i.external_id == ticket_id and i.number == number),
        None,
    )
    if card is None:
        return None
    offsets: dict[str, int] = {}
    if not from_start:
        for path in session_log_files(folder, ticket_id):
            offsets[path.name] = len(path.read_text(encoding="utf-8"))
    return SyncLedger(ticket_id, project.project_id, card.work_item_id, card.number, None, None, offsets, [])


def _sync_description(ctx: _Context, result: _Result) -> int | None:
    ledger = ctx.ledger
    if ledger.description_sha == ctx.sha:
        return None
    state = ctx.state
    hit = find_secret_pattern(state.title + state.body_text, ctx.settings.secret_patterns)
    if hit is not None:
        return _stop(ctx, f"secret pattern {hit} in description; nothing sent")
    html = markdown_to_html(state.body_text) + f"<p>{STATE_SHA_PREFIX}{ctx.sha}</p>"
    ctx.client.update_work_item(
        ledger.project_id, ledger.work_item_id, {"description_html": html, "name": state.title}
    )
    ledger.description_sha = ctx.sha
    save_ledger(ctx.ledger_file, ledger)
    result.description = "updated"
    return None


def _status_comment_text(ctx: _Context, old: str, word: str, board: str) -> str:
    text = f"Status: {old} to {word} (board: {board}) (generated)"
    if word in ctx.settings.blocked_words:
        section = extract_markdown_section(ctx.state.body_text, CURRENT_STATE_HEADING)
        text += f"\n\nCurrent state:\n\n{section}"
    return text


def _post_status_comment(ctx: _Context, text: str, old: str, word: str) -> None:
    key = comment_key(f"status|{old}|{word}|{ctx.sha}")
    ledger = ctx.ledger
    if key in ledger.posted_keys:
        return
    ctx.client.post_comment(ledger.project_id, ledger.work_item_id, markdown_to_html(text), key)
    ledger.posted_keys.append(key)
    save_ledger(ctx.ledger_file, ledger)


def _move_card(ctx: _Context, word: str, board: str, target: str) -> int | None:
    ledger = ctx.ledger
    if ledger.status_word is None:
        card = ctx.client.get_work_item(ledger.project_id, ledger.work_item_id)
        if card.state_id != target:
            ctx.client.update_work_item(ledger.project_id, ledger.work_item_id, {"state": target})
        return None
    old = ledger.status_word
    text = _status_comment_text(ctx, old, word, board)
    hit = find_secret_pattern(text, ctx.settings.secret_patterns)
    if hit is not None:
        return _stop(ctx, f"secret pattern {hit} in status comment; nothing sent")
    ctx.client.update_work_item(ledger.project_id, ledger.work_item_id, {"state": target})
    _post_status_comment(ctx, text, old, word)
    return None


def _sync_status(ctx: _Context, result: _Result) -> int | None:
    word = normalize_status_word(ctx.state.status_word)
    ledger = ctx.ledger
    if word == ledger.status_word:
        return None
    board = ctx.settings.status_map.get(word)
    if board is None:
        result.status = f"unknown:{word}"
        result.unknown_word = word
        return None
    target = ctx.client.list_state_ids(ledger.project_id).get(board)
    if target is None:
        return _stop(ctx, f"board status {board} not found in Plane")
    stopped = _move_card(ctx, word, board, target)
    if stopped is not None:
        return stopped
    ledger.status_word = word
    save_ledger(ctx.ledger_file, ledger)
    result.status = "moved"
    return None


def _read_optional(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _extras(ctx: _Context, kind: str | None) -> tuple[str, str | None]:
    if kind is None:
        return "", None
    names = [f"{ctx.ticket_id}-spec.md", f"{ctx.ticket_id}-design.md"]
    if kind == EXTRAS_DEV:
        names = [f"{ctx.ticket_id}-edge-case-validation.md"]
    texts = [_read_optional(ctx.folder / name) for name in names]
    notes = [f"(extras: {n} not found)" for n, t in zip(names, texts) if t is None]
    present = [t or "" for t in texts]
    if kind == EXTRAS_DEV:
        built = build_dev_extras(present[0]) if texts[0] is not None else ""
    else:
        built = build_spec_extras(*present) if texts[0] is not None else ""
    text = PARTS_JOINER.join(part for part in [built, *notes] if part)
    if notes:
        return text, comment_key(NOTE_KEY_PREFIX + text)
    digest = comment_key("".join(present))
    return text, comment_key(f"extras|{kind}|{digest}")


def _join_parts(session_text: str, extras_text: str, limit: int, pointer: str) -> str:
    """Cut each part to fit a markdown limit; the extras keep at most half when there is session text."""
    extras_part = cut_to_limit(extras_text, limit // 2 if session_text else limit, pointer)
    session_part = session_text
    if session_text:
        budget = limit - len(extras_part) - JOINER_LENGTH if extras_part else limit
        session_part = cut_to_limit(session_text, budget, pointer)
    return PARTS_JOINER.join(part for part in (session_part, extras_part) if part)


def _compose_html(ctx: _Context, session_text: str, extras_text: str, res: _Result) -> str:
    """Return the comment HTML, at most comment_max_chars long. Shrinks the markdown until the HTML fits."""
    limit = ctx.settings.comment_max_chars
    pointer = f"(cut; full text in the {ctx.ticket_id} files in the vault)"
    whole = PARTS_JOINER.join(part for part in (session_text, extras_text) if part)
    markdown_limit = limit
    for _ in range(MAX_FIT_ROUNDS):
        body = _join_parts(session_text, extras_text, markdown_limit, pointer)
        html = markdown_to_html(body)
        if len(html) <= limit:
            res.cut = "yes" if body != whole else res.cut
            return html
        markdown_limit = max(0, int(markdown_limit * limit * FIT_SAFETY / len(html)))
    res.cut = "yes"
    return markdown_to_html(pointer)


def _post_comment(
    ctx: _Context, html: str, session_key: str | None, extras_key: str | None, new_offsets: dict[str, int]
) -> None:
    ledger = ctx.ledger
    external_id = session_key or extras_key or comment_key(html)
    ctx.client.post_comment(ledger.project_id, ledger.work_item_id, html, external_id)
    ledger.posted_keys.extend(key for key in (session_key, extras_key) if key)
    ledger.session_offsets = new_offsets
    save_ledger(ctx.ledger_file, ledger)


def _sync_comment(ctx: _Context, result: _Result, extras: str | None) -> int | None:
    ledger = ctx.ledger
    session_text, new_offsets = read_new_session_text(ctx.folder, ctx.ticket_id, ledger.session_offsets)
    extras_text, extras_key = _extras(ctx, extras)
    if extras_key in ledger.posted_keys:
        extras_text, extras_key = "", None
    session_key = comment_key(session_text) if session_text else None
    if session_key in ledger.posted_keys:
        session_text, session_key = "", None
    if not session_text and not extras_text:
        ledger.session_offsets = new_offsets
        save_ledger(ctx.ledger_file, ledger)
        return None
    hit = find_secret_pattern(session_text + extras_text, ctx.settings.secret_patterns)
    if hit is not None:
        return _stop(ctx, f"secret pattern {hit} in comment text; nothing posted")
    html = _compose_html(ctx, session_text, extras_text, result)
    _post_comment(ctx, html, session_key, extras_key, new_offsets)
    result.comment = "posted"
    return None


def _summary(ticket_id: str, result: _Result) -> str:
    return (
        f"synced | {ticket_id} | description={result.description} status={result.status} "
        f"comment={result.comment} cut={result.cut} first_sync={result.first_sync}"
    )


def _open_ledger(
    client: PlaneWorkItemClient, folder: Path, ledger_file: Path,
    project_key: str, ticket_id: str, number: int, from_start: bool,
) -> tuple[SyncLedger | None, bool]:
    existing = load_ledger(ledger_file)
    if existing is not None:
        return existing, False
    created = _first_sync_ledger(client, project_key, folder, ticket_id, number, from_start)
    if created is not None:
        save_ledger(ledger_file, created)
    return created, True


def _run_steps(ctx: _Context, extras: str | None, first_sync: bool) -> int:
    result = _Result(first_sync="yes" if first_sync else "no")
    stopped = _sync_description(ctx, result)
    if stopped is None:
        stopped = _sync_status(ctx, result)
    if stopped is None:
        stopped = _sync_comment(ctx, result, extras)
    if stopped is not None:
        return stopped
    ctx.emit(_summary(ctx.ticket_id, result))
    return EXIT_STOPPED if result.unknown_word else EXIT_OK


def run_sync(
    settings: PlaneSyncSettings,
    client: PlaneWorkItemClient,
    tickets_root: Path,
    state_root: Path,
    *,
    ticket_id: str,
    extras: str | None,
    emit: Callable[[str], None],
    from_start: bool = False,
) -> int:
    """Send what changed for one ticket to its Plane card. Returns 0, or 2 when something was stopped or unknown."""
    gate = ticket_id_gate(settings.prefix_table, ticket_id)
    if gate is not None:
        emit(gate[0])
        return gate[1]
    prefix, number = parse_ticket_id(ticket_id) or ("", 0)
    row = settings.prefix_table[prefix]
    folder = ticket_folder(ticket_id, tickets_root)
    state = read_state_file(folder, ticket_id)
    ledger_file = ledger_path(state_root, ticket_id)
    if from_start and ledger_file.exists():
        emit("stopped | --from-start is valid only when the ticket has no ledger")
        return EXIT_STOPPED
    ledger, first_sync = _open_ledger(
        client, folder, ledger_file, row.project_key, ticket_id, number, from_start
    )
    if ledger is None:
        emit(f"stopped | no card for {ticket_id}")
        return EXIT_STOPPED
    ctx = _Context(settings, client, folder, ledger_file, ledger, state, ticket_id, comment_key(state.raw_text), emit)
    return _run_steps(ctx, extras, first_sync)
