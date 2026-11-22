# Module:      cli.py
# Description: Command line for the plane connector: create, sync and drift. First use goes through the connector framework.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       argument parsing, connector setup check, confirmation for create, exit codes; one emit function writes every output line
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Mapping, Sequence

from connectors import registry
from connectors.plane.plane_drift_checker import run_drift
from connectors.plane.plane_sync_ledger import PlaneSyncLedgerError
from connectors.plane.plane_sync_settings import (
    PlaneAddressError,
    PlaneSyncConfigError,
    PlaneSyncSettings,
    default_settings_path,
    load_settings,
)
from connectors.plane.plane_ticket_syncer import EXTRAS_DEV, EXTRAS_SPEC, run_sync
from connectors.plane.plane_work_item_client import PlaneApiError, PlaneWorkItemClient
from connectors.plane.vault_ticket_creator import run_create
from connectors.plane.vault_ticket_files import VaultTicketError, safe_text, skip_line, ticket_id_gate
from connectors.secret_store import SecretStoreError
from core.paths import NotSetUp, get_path

CONNECTOR_NAME = "plane"
EXIT_CONFIG = 1
EXIT_LEDGER = 2
EXIT_STOPPED = 2
EXIT_PLANE = 3
TICKETS_PATH_KEY = "tickets"
STATE_PATH_KEY = "state"
STATE_SUBFOLDER = "plane"
WORK_TYPES = ("feature", "fix", "research")
COMMAND_CREATE = "create"
COMMAND_SYNC = "sync"
COMMAND_DRIFT = "drift"
YES_ANSWERS = ("y", "yes")

_ACTIVE: dict[str, object] = {"settings": None, "insecure": False}


def emit(line: str) -> None:
    """Write one output line to standard output."""
    sys.stdout.write(line + "\n")


def _build_client(address: str, key: str, http: object) -> PlaneWorkItemClient:
    """The factory the framework calls. The settings come from the run that registered it."""
    settings = _ACTIVE["settings"]
    if not isinstance(settings, PlaneSyncSettings):
        raise PlaneSyncConfigError("settings were not loaded")
    return PlaneWorkItemClient(
        address, settings.workspace_slug, key, http,
        allow_insecure_http=bool(_ACTIVE["insecure"]),
        external_source=settings.external_source_name,
        min_seconds_between_calls=settings.min_seconds_between_calls,
        timeout_seconds=settings.http_timeout_seconds,
        page_size=settings.page_size,
    )


registry.register(CONNECTOR_NAME, _build_client)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plane")
    parser.add_argument("--settings", default=None, help="settings file; default sits next to the paths file")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser(COMMAND_CREATE)
    create.add_argument("--prefix", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--priority", required=True)
    create.add_argument("--scope", required=True)
    create.add_argument("--repo", required=True)
    create.add_argument("--type", required=True, choices=WORK_TYPES, dest="work_type")
    create.add_argument("--yes", action="store_true", help="confirm without a terminal")
    sync = commands.add_parser(COMMAND_SYNC)
    sync.add_argument("ticket_id")
    sync.add_argument("--extras", choices=(EXTRAS_SPEC, EXTRAS_DEV), default=None)
    sync.add_argument("--from-start", action="store_true", dest="from_start")
    drift = commands.add_parser(COMMAND_DRIFT)
    drift.add_argument("ticket_ids", nargs="+")
    return parser


def _tokenless_outcome(
    args: argparse.Namespace, settings: PlaneSyncSettings, out: Callable[[str], None]
) -> int | None:
    """Decide what needs no card call: an unmapped prefix or a bad id. None means the run goes on."""
    if args.command == COMMAND_CREATE and args.prefix not in settings.prefix_table:
        out(skip_line(args.prefix))
        return EXIT_STOPPED
    ids = [args.ticket_id] if args.command == COMMAND_SYNC else getattr(args, "ticket_ids", None)
    gates = [ticket_id_gate(settings.prefix_table, ticket_id) for ticket_id in ids or []]
    if not gates or None in gates:
        return None
    for line, _ in gates:
        out(line)
    return max(code for _, code in gates)


def _confirmed(
    args: argparse.Namespace, settings: PlaneSyncSettings, env: Mapping[str, str] | None,
    confirm: Callable[[str], str] | None, out: Callable[[str], None],
) -> bool:
    """create always asks. A terminal answers y or n; with no terminal only --yes lets it run."""
    if args.yes:
        return True
    if not registry.interactive(env):
        out("stopped | create changes Plane and the vault; no terminal, so pass --yes to confirm")
        return False
    project = settings.prefix_table[args.prefix].project_key
    question = f'Create a card "{safe_text(args.title)}" in project {project} and a ticket folder? [y/N] '
    ask = confirm if confirm is not None else input
    if ask(question).strip().lower() in YES_ANSWERS:
        return True
    out("stopped | create was not confirmed")
    return False


def _roots(tickets_root: Path | None, state_root: Path | None) -> tuple[Path, Path]:
    tickets = tickets_root if tickets_root is not None else get_path(TICKETS_PATH_KEY)
    state = state_root if state_root is not None else get_path(STATE_PATH_KEY) / STATE_SUBFOLDER
    return tickets, state


def _dispatch(
    args: argparse.Namespace, settings: PlaneSyncSettings, client: PlaneWorkItemClient,
    roots: tuple[Path, Path], out: Callable[[str], None],
) -> int:
    tickets_root, state_root = roots
    if args.command == COMMAND_SYNC:
        return run_sync(
            settings, client, tickets_root, state_root, ticket_id=args.ticket_id,
            extras=args.extras, emit=out, from_start=args.from_start,
        )
    if args.command == COMMAND_DRIFT:
        return run_drift(settings, client, tickets_root, ticket_ids=args.ticket_ids, emit=out)
    return run_create(
        settings, client, tickets_root, state_root,
        prefix=args.prefix, title=args.title, priority=args.priority, scope=args.scope,
        repo=args.repo, work_type=args.work_type, today=date.today().isoformat(), emit=out,
    )


def _run(
    args: argparse.Namespace, env: Mapping[str, str] | None, settings: PlaneSyncSettings | None,
    roots_given: tuple[Path | None, Path | None], out: Callable[[str], None],
    allow_insecure_http: bool, confirm: Callable[[str], str] | None,
) -> int:
    if not registry.is_on(CONNECTOR_NAME, env) and not registry.interactive(env):
        raise NotSetUp(registry.how_to_set_up(CONNECTOR_NAME))
    if settings is None:
        path = Path(args.settings) if args.settings else default_settings_path(env)
        settings = load_settings(path, env if env is not None else os.environ)
    outcome = _tokenless_outcome(args, settings, out)
    if outcome is not None:
        return outcome
    _ACTIVE.update(settings=settings, insecure=allow_insecure_http)
    client = registry.ensure(CONNECTOR_NAME, env)
    if args.command == COMMAND_CREATE and not _confirmed(args, settings, env, confirm, out):
        return EXIT_STOPPED
    return _dispatch(args, settings, client, _roots(*roots_given), out)


def main(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    settings: PlaneSyncSettings | None = None,
    tickets_root: Path | None = None,
    state_root: Path | None = None,
    out: Callable[[str], None] = emit,
    allow_insecure_http: bool = False,
    confirm: Callable[[str], str] | None = None,
) -> int:
    """Run one command. The keyword arguments let tests point at a stub and temporary folders."""
    try:
        args = _build_parser().parse_args(list(argv))
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else 0
    try:
        return _run(args, env, settings, (tickets_root, state_root), out, allow_insecure_http, confirm)
    except (NotSetUp, SecretStoreError) as error:
        sys.stderr.write(str(error) + "\n")
        return EXIT_STOPPED
    except PlaneApiError as error:
        out(f"stopped | {error}")
        return EXIT_PLANE
    except PlaneSyncLedgerError as error:
        out(f"stopped | {error}")
        return EXIT_LEDGER
    except PlaneAddressError as error:
        out(f"stopped | {error}")
        return EXIT_CONFIG
    except PlaneSyncConfigError as error:
        out(f"stopped | settings problem: {error}")
        return EXIT_CONFIG
    except VaultTicketError as error:
        out(f"stopped | {error}")
        return EXIT_CONFIG
