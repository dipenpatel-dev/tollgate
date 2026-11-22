#!/usr/bin/env python3
# Module: vault_query.py
# Description: Ticket board CLI. Reads the tickets folder and prints the board, sprint, work in progress, blocked tickets or one ticket.
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: vault_query CLI, read only
# ChangeLog: initial

from pathlib import Path
import re
import os
import sys
import argparse
import datetime
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp, ticket_folder, iter_ticket_folders  # noqa: E402


INTERNAL_ENUM: frozenset[str] = frozenset({
    "BACKLOG", "OPEN", "PARKED", "SPEC_APPROVED", "DESIGN_COMPLETE",
    "DEV_COMPLETE", "SUPPORT_COMPLETE", "QA_BLOCKED", "QA_APPROVED",
    "SHIPPED", "SUPERSEDED", "CANCELLED",
})
TERMINAL_SET: frozenset[str] = frozenset({"SHIPPED", "SUPERSEDED", "CANCELLED"})
ACTIVE_SET: frozenset[str] = frozenset({
    "OPEN", "SPEC_APPROVED", "DESIGN_COMPLETE",
    "DEV_COMPLETE", "SUPPORT_COMPLETE", "QA_BLOCKED", "QA_APPROVED",
})
ENUM_DISPLAY_ORDER: list[str] = [
    "OPEN", "BACKLOG", "PARKED", "SPEC_APPROVED", "DESIGN_COMPLETE",
    "DEV_COMPLETE", "SUPPORT_COMPLETE", "QA_BLOCKED", "QA_APPROVED",
    "SHIPPED", "SUPERSEDED", "CANCELLED",
]
VAULT_CONFIG_FILENAME = "vault-config.yaml"
BOARD_MAPPINGS_DIRNAME = "board-mappings"
DEFAULT_STANDALONE = "T"
MISSING_CONFIG_MSG = "treating the ticket prefix as the only standalone prefix"
STATE_FILE_SUFFIX = "-state.md"
IN_PROGRESS_FILENAME = "tickets-in-progress.md"
ON_ABSENT_REJECT: str = "reject"
ON_ABSENT_WARN: str = "warn"


def _strip_quotes(val: str) -> str:
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
        return val[1:-1]
    return val


def _collect_indented(lines: list[str], start: int) -> tuple[Any, int]:
    collected = []
    i = start
    while i < len(lines):
        ln = lines[i]
        if not ln.startswith("  "):
            break
        collected.append(ln)
        i += 1
    consumed = i - start
    if not collected:
        return ("", 0)
    first = collected[0].strip()
    if first.startswith("- "):
        items = [
            _strip_quotes(ln.strip()[2:])
            for ln in collected
            if ln.strip().startswith("- ")
        ]
        return (items, consumed)
    result: dict[str, str] = {}
    for ln in collected:
        if ":" in ln:
            k, _, v = ln.partition(":")
            result[k.strip()] = _strip_quotes(v.strip())
    return (result, consumed)


def _parse_yaml_lines(lines: list[str], source: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if line[0] in (" ", "\t"):
            i += 1
            continue
        if ":" not in line:
            raise ValueError(f"Malformed YAML in {source}: no colon in top-level line {line!r}")
        key, _, raw_val = line.partition(":")
        key = key.strip()
        raw_val = raw_val.strip()
        if raw_val:
            result[key] = _strip_quotes(raw_val)
            i += 1
        else:
            value, consumed = _collect_indented(lines, i + 1)
            result[key] = value
            i += 1 + consumed
    return result


def parse_frontmatter(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    delimiters = [i for i, ln in enumerate(lines) if ln.strip() == "---"]
    if len(delimiters) < 2:
        return {}
    block = lines[delimiters[0] + 1 : delimiters[1]]
    return _parse_yaml_lines(block, path)


def parse_yaml_config(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return _parse_yaml_lines(lines, path)


def load_vault_config(tickets_dir: Path) -> tuple[dict[str, str], list[str]]:
    config_path = tickets_dir / VAULT_CONFIG_FILENAME
    errors: list[str] = []
    if not config_path.exists():
        errors.append(
            f"vault-config.yaml not found at {config_path}; {MISSING_CONFIG_MSG}"
        )
        return ({}, errors)
    try:
        config = parse_yaml_config(config_path)
    except ValueError as exc:
        errors.append(f"vault-config.yaml malformed: {exc}")
        return ({}, errors)
    return (dict(config), errors)


def load_board_mappings(mappings_dir: Path) -> dict[str, dict]:
    mappings: dict[str, dict] = {}
    if not mappings_dir.exists():
        return mappings
    for yaml_file in sorted(mappings_dir.glob("*.yaml")):
        try:
            data = parse_yaml_config(yaml_file)
            board_id = data.get("board_id", yaml_file.stem)
            mappings[str(board_id)] = data
        except ValueError:
            pass
    return mappings


def _resolve_standalone_status(raw_status: str) -> tuple[str, list[str]]:
    normalized = raw_status.upper()
    if normalized not in INTERNAL_ENUM:
        return (
            "INVALID",
            [f"status {raw_status!r} not in enum: {sorted(INTERNAL_ENUM)}"],
        )
    return (normalized, [])


def _resolve_external_status(
    ticket_id: str,
    raw_status: str,
    mapping: dict,
) -> tuple[str, list[str]]:
    tokens = raw_status.split()
    if len(tokens) > 1 and tokens[0].upper() == "SHIPPED":
        return (
            "SHIPPED",
            [f"SHIPPED_WITH_EMBEDDED_DATE: {ticket_id} raw_status={raw_status!r}"],
        )
    status_map = mapping.get("status_map", {})
    on_absent = mapping.get("on_absent", ON_ABSENT_WARN)
    if raw_status in status_map:
        return (status_map[raw_status], [])
    if on_absent == ON_ABSENT_REJECT:
        return (
            "INVALID",
            [f"status {raw_status!r} absent from board map; on_absent=reject"],
        )
    return (
        "UNRESOLVED",
        [f"status {raw_status!r} unmapped for {ticket_id}; on_absent=warn"],
    )


def resolve_prefix_and_status(
    ticket_id: str,
    raw_status: str,
    standalone_prefixes: frozenset[str],
    board_mappings: dict[str, dict],
) -> tuple[str, list[str]]:
    prefix = ticket_id.split("-")[0]
    if prefix in standalone_prefixes:
        return _resolve_standalone_status(raw_status)
    for mapping in board_mappings.values():
        patterns = mapping.get("prefix_patterns", [])
        if prefix in patterns:
            return _resolve_external_status(ticket_id, raw_status, mapping)
    return (
        "UNRESOLVED",
        [f"prefix {prefix!r} has no board mapping; ticket={ticket_id}"],
    )


def validate_invariants(ticket_id: str, fields: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    status = str(fields.get("status", ""))
    raw_ts = fields.get("terminal_status") or ""
    terminal_status = str(raw_ts).strip()
    ts_empty = not terminal_status

    if status in TERMINAL_SET and ts_empty:
        violations.append(
            f"TYPE_A_VIOLATION: {ticket_id} status={status!r} but terminal_status is empty"
        )
    if status not in TERMINAL_SET and not ts_empty:
        violations.append(
            f"TYPE_B_VIOLATION: {ticket_id} status={status!r} but terminal_status={terminal_status!r}"
        )
    if status in TERMINAL_SET and not ts_empty:
        first_token = terminal_status.split()[0]
        if first_token != status:
            violations.append(
                f"TERMINAL_MISMATCH: {ticket_id} status={status!r} "
                f"but terminal_status starts with {first_token!r}"
            )
    return violations


def _process_ticket_folder(
    folder: Path,
    standalone_prefixes: frozenset[str],
    board_mappings: dict[str, dict],
) -> tuple[Optional[dict], Optional[dict]]:
    folder_name = folder.name
    state_path = folder / f"{folder_name}{STATE_FILE_SUFFIX}"
    if not state_path.exists():
        return None, {"ticket_id": folder_name, "path": str(folder), "error_type": "absent"}
    try:
        fields = parse_frontmatter(state_path)
    except ValueError as exc:
        return None, {
            "ticket_id": folder_name,
            "path": str(state_path),
            "error_type": "malformed",
            "detail": str(exc),
        }
    ticket_id = str(fields.get("ticket_id", folder_name))
    raw_status = str(fields.get("status", ""))
    resolved_status, resolve_errors = resolve_prefix_and_status(
        ticket_id, raw_status, standalone_prefixes, board_mappings
    )
    invariant_violations = validate_invariants(ticket_id, fields)
    return {
        "ticket_id": ticket_id,
        "status": resolved_status,
        "fields": fields,
        "errors": resolve_errors + invariant_violations,
    }, None


def scan_tickets(
    tickets_dir: Path,
    standalone_prefixes: frozenset[str],
    board_mappings: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    tickets: list[dict] = []
    errors: list[dict] = []
    for item in iter_ticket_folders(tickets_dir):
        ticket, error = _process_ticket_folder(item, standalone_prefixes, board_mappings)
        if error is not None:
            errors.append(error)
        else:
            tickets.append(ticket)
    return tickets, errors


def load_in_progress_list(vault_root: Path) -> set[str]:
    ip_path = vault_root / IN_PROGRESS_FILENAME
    if not ip_path.exists():
        return set()
    text = ip_path.read_text(encoding="utf-8")
    return set(re.findall(r"[A-Z][A-Z0-9]*-[0-9]+|[a-z]+-[0-9]+", text))


def detect_drift(tickets: list[dict], in_progress_ids: set[str]) -> list[dict]:
    drift: list[dict] = []
    for t in tickets:
        if t["status"] == "SHIPPED" and t["ticket_id"] in in_progress_ids:
            drift.append({
                "ticket_id": t["ticket_id"],
                "detail": "status=SHIPPED but appears in in-progress list",
            })
    return drift


def cmd_board(
    tickets_dir: Path,
    vault_root: Path,
    standalone_prefixes: frozenset[str],
    board_mappings: dict[str, dict],
) -> None:
    tickets, errors = scan_tickets(tickets_dir, standalone_prefixes, board_mappings)
    in_progress_ids = load_in_progress_list(vault_root)
    drift = detect_drift(tickets, in_progress_ids)
    groups: dict[str, list[str]] = {s: [] for s in ENUM_DISPLAY_ORDER}
    for t in tickets:
        if t["status"] in groups:
            groups[t["status"]].append(t["ticket_id"])
    for status in ENUM_DISPLAY_ORDER:
        print(f"\n[{status}]")
        for tid in groups[status]:
            print(f"  {tid}")
    print("\n[DRIFT]")
    for d in drift:
        print(f"  {d['ticket_id']}: {d['detail']}")
    print("\n[ERRORS]")
    for e in errors:
        print(f"  {e['ticket_id']} ({e['error_type']}): {e.get('path', '')}")


def cmd_sprint(
    tickets_dir: Path,
    standalone_prefixes: frozenset[str],
    board_mappings: dict[str, dict],
) -> None:
    sprints_dir = tickets_dir / "sprints"
    if not sprints_dir.exists():
        print(f"ERROR: sprints directory not found at {sprints_dir}")
        return
    sprint_files = sorted(sprints_dir.glob("*.md"))
    if not sprint_files:
        print(f"ERROR: no sprint files found in {sprints_dir}")
        return
    tickets, _ = scan_tickets(tickets_dir, standalone_prefixes, board_mappings)
    status_by_id = {t["ticket_id"]: t["status"] for t in tickets}
    for sf in sprint_files:
        fields = parse_frontmatter(sf)
        missing = [f for f in ["sprint_id", "start_date", "end_date", "tickets"] if f not in fields]
        if missing:
            print(f"ERROR: {sf.name} missing fields: {missing}")
            continue
        print(f"\nSprint: {fields['sprint_id']}")
        print(f"  {fields['start_date']} to {fields['end_date']}")
        for tid in fields["tickets"]:
            print(f"  {tid}: {status_by_id.get(tid, 'UNKNOWN')}")


def cmd_wip(
    tickets_dir: Path,
    standalone_prefixes: frozenset[str],
    board_mappings: dict[str, dict],
) -> None:
    tickets, _ = scan_tickets(tickets_dir, standalone_prefixes, board_mappings)
    active = [t for t in tickets if t["status"] in ACTIVE_SET]
    if not active:
        print("no active tickets")
        return
    groups: dict[str, list[str]] = {}
    for t in active:
        ticket_type = str(t["fields"].get("type", "untyped"))
        groups.setdefault(ticket_type, []).append(t["ticket_id"])
    for ticket_type, ids in sorted(groups.items()):
        print(f"\n[{ticket_type}]")
        for tid in ids:
            print(f"  {tid}")


def cmd_blocked(
    tickets_dir: Path,
    standalone_prefixes: frozenset[str],
    board_mappings: dict[str, dict],
) -> None:
    tickets, _ = scan_tickets(tickets_dir, standalone_prefixes, board_mappings)
    status_by_id = {t["ticket_id"]: t["status"] for t in tickets}
    blocked: list[tuple[str, str]] = []
    unknown: list[tuple[str, str]] = []
    for t in tickets:
        deps = t["fields"].get("depends_on", [])
        if not deps:
            continue
        if isinstance(deps, str):
            deps = [deps]
        for raw_dep in deps:
            dep_id = raw_dep.strip()
            if not dep_id:
                continue
            if dep_id in status_by_id:
                if status_by_id[dep_id] not in TERMINAL_SET:
                    blocked.append((t["ticket_id"], dep_id))
            else:
                unknown.append((t["ticket_id"], dep_id))
    print("[BLOCKED]")
    for ticket_id, dep_id in blocked:
        print(f"  {ticket_id} blocked by {dep_id}")
    print("\n[DEPENDENCY_UNKNOWN]")
    for ticket_id, dep_id in unknown:
        print(f"  {ticket_id} depends on {dep_id} (no state file)")


def _find_most_recent_session_log(ticket_dir: Path) -> Optional[Path]:
    date_re = re.compile(r"-session-(\d{4}-\d{2}-\d{2})\.md$")
    dated = []
    for f in ticket_dir.glob("*-session-????-??-??.md"):
        m = date_re.search(f.name)
        if m:
            dated.append((m.group(1), f))
    if not dated:
        return None
    dated.sort(key=lambda x: x[0])
    return dated[-1][1]


def cmd_ticket(
    ticket_id: str,
    tickets_dir: Path,
    standalone_prefixes: frozenset[str],
    board_mappings: dict[str, dict],
) -> None:
    ticket_dir = ticket_folder(ticket_id, tickets_dir)
    if ticket_dir is None:
        print(f"ERROR: ticket directory not found: {ticket_id}")
        return
    state_path = ticket_dir / f"{ticket_id}{STATE_FILE_SUFFIX}"
    if not state_path.exists():
        print(f"ERROR: state file not found for {ticket_id}")
        return
    fields = parse_frontmatter(state_path)
    for k, v in fields.items():
        print(f"{k}: {v}")
    log_path = _find_most_recent_session_log(ticket_dir)
    if log_path is None:
        print("no session log found")
        return
    print(log_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="vault_query: ticket board CLI")
    parser.add_argument("--tickets-dir", type=Path, default=None, dest="tickets_dir",
                        help="Tickets folder. Default: the tickets path from the path loader.")
    parser.add_argument("--vault-root", type=Path, default=None, dest="vault_root")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("board")
    sub.add_parser("sprint")
    sub.add_parser("wip")
    sub.add_parser("blocked")
    ticket_sub = sub.add_parser("ticket")
    ticket_sub.add_argument("ticket_id")
    args = parser.parse_args()
    if args.tickets_dir is not None:
        tickets_dir: Path = args.tickets_dir
    else:
        try:
            tickets_dir = get_path("tickets")
        except NotSetUp:
            print("not set up", file=sys.stderr)
            sys.exit(2)
    vault_root: Path = args.vault_root if args.vault_root else tickets_dir.parent
    if not tickets_dir.exists():
        print(f"ERROR: tickets directory not found: {tickets_dir}", file=sys.stderr)
        sys.exit(1)
    config, config_errors = load_vault_config(tickets_dir)
    for err in config_errors:
        print(err, file=sys.stderr)
    local_prefix = config.get("local_prefix", "")
    standalone_prefixes = frozenset(
        {DEFAULT_STANDALONE} | ({local_prefix} if local_prefix else set())
    )
    board_mappings = load_board_mappings(tickets_dir / BOARD_MAPPINGS_DIRNAME)
    if args.command == "board":
        cmd_board(tickets_dir, vault_root, standalone_prefixes, board_mappings)
    elif args.command == "sprint":
        cmd_sprint(tickets_dir, standalone_prefixes, board_mappings)
    elif args.command == "wip":
        cmd_wip(tickets_dir, standalone_prefixes, board_mappings)
    elif args.command == "blocked":
        cmd_blocked(tickets_dir, standalone_prefixes, board_mappings)
    elif args.command == "ticket":
        cmd_ticket(args.ticket_id, tickets_dir, standalone_prefixes, board_mappings)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
