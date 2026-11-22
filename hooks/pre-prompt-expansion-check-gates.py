#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: block the arch, dev and qa chain skills when the earlier `Status:` lines are missing
Ticket: n/a
ChangeLog:
  - Gates the fixed command names tg-arch, tg-dev and tg-qa. TOLLGATE_SKILL_PREFIX is no longer read
    (an old value in the environment is ignored), and the hook no longer allows because it is unset.
  - Also runs as a PreToolUse hook on the Skill tool, so a skill the model calls itself is gated
    the same way as one the user types (a typed slash command only reaches UserPromptExpansion).
    The skill name is tool_input.skill and the arguments are tool_input.args. A block there is a
    permissionDecision deny.
  - Fails closed. A payload that cannot be read exits 2. An internal error while checking a
    gated skill (arch, dev, qa) blocks it. An internal error on any other command still allows
    (and logs fail_open) so a broken gate cannot lock every slash command.
  - A gated skill with a ticket id but no ticket folder, or with TOLLGATE_KNOWLEDGE unset, no
    longer allows silently: it still allows, but prints {"systemMessage": "..."} so the user sees
    that the gate did not check anything. (A block was not chosen: an id-like word such as UTF-8
    would lock the user out, and a vault laid out by prefix folder would block every real ticket.)
  - Gate reads `Status:` lines (dotfiles format), not dated approval lines. (Earlier: an empty
    TOLLGATE_SKILL_PREFIX gated the bare commands arch, dev and qa and an unset one allowed;
    replaced by the fixed tg-arch, tg-dev and tg-qa names above.)
  - First ticket token with a vault folder wins, ids are case insensitive and
    uppercased, override reader hardened, unreadable files reported apart.
  - Override reader also refuses a file that is not a regular file.
  - Created.

Trigger: UserPromptExpansion (typed slash command) and PreToolUse on the Skill tool (model call)
Action: read command_name and command_args. If the name is `tg-arch`, `tg-dev` or `tg-qa`
and the arguments hold a ticket id, check the state file and artifacts
under the tickets folder from the path loader ({KEY} inside it) with the rules in gate_rules.py. On a failed
check, print {"decision": "block", "reason": "..."} on stdout and exit 0.
A dated override file {KEY}-gate-override.md with a line `Override: <skill> YYYY-MM-DD <reason>`
lets one skill through on that date only; every use is logged.
Reads only, so no locking. On an internal error: a gated skill is blocked, any other command
is allowed. One line goes to the log file (TOLLGATE_GATE_LOG, default gate_check.log in the state folder from the path loader, else ~/.tollgate/state)
and a warning goes to stderr. A payload that is not a JSON object exits 2.
When the gate cannot check (ticket folder not found, or TOLLGATE_KNOWLEDGE unset) it allows and
prints one {"systemMessage": ...} warning line that says what is wrong.
Block messages name paths and expected lines, never file contents.
The override reader ignores fenced lines, refuses a symlinked or non-regular override file and strips a BOM.
An unreadable artifact (permission denied) is reported apart from a missing one.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import stat
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

COMMAND_PREFIX = "tg-"
KNOWLEDGE_ENV = "TOLLGATE_KNOWLEDGE"
LOG_ENV = "TOLLGATE_GATE_LOG"
DEFAULT_LOG = os.path.join("~", ".tollgate", "state", "gate_check.log")
HOME_ENV = "TOLLGATE_HOME"
TICKET_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+$", re.IGNORECASE)
TOKEN_PUNCTUATION = ",.;:!?()[]{}<>\"'`"
OVERRIDE_RE = re.compile(r"^Override: (\S+) ([0-9]{4}-[0-9]{2}-[0-9]{2}) (\S.*)$")
DATE_FORMAT = "%Y-%m-%d"
CHAIN_SKILLS = ("ticket", "support", "spec", "arch", "dev", "qa")
GATED_SKILLS = ("arch", "dev", "qa")
RUN_FIRST = {"arch": "spec", "dev": "arch", "qa": "dev"}
FILE_SUFFIXES = {
    "state file": "state",
    "spec.md": "spec",
    "design.md": "design",
    "edge-case-validation.md": "edge-case-validation",
}
OVERRIDE_SUFFIX = "gate-override"
LOG_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
MAX_LOG_DETAIL = 200

logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(message)s")
LOGGER = logging.getLogger("tollgate_gate_check")


def shared_paths(env: Optional[Dict[str, str]] = None) -> Any:
    """Return the path loader module (core.paths) found through TOLLGATE_HOME, or None.

    Never raises: a hook must keep working when the loader cannot be imported.
    """
    home = (env if env is not None else os.environ).get(HOME_ENV, "")
    if not home:
        return None
    scripts = os.path.join(home, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from core import paths  # type: ignore
        return paths
    except Exception:
        return None


def default_log_path() -> str:
    """The gate log when TOLLGATE_GATE_LOG is unset: the loader's state folder, else the old default."""
    loader = shared_paths()
    if loader is not None:
        try:
            return os.path.join(str(loader.get_path("state")), "gate_check.log")
        except Exception:
            pass
    return DEFAULT_LOG


def log_line(event: str, detail: str = "") -> None:
    """Append one line to the gate log. Never raises."""
    path = os.path.expanduser(os.environ.get(LOG_ENV) or default_log_path())
    stamp = datetime.datetime.now().strftime(LOG_TIME_FORMAT)
    text = "{0} {1} {2}".format(stamp, event, detail.replace("\n", " ")[:MAX_LOG_DETAIL])
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text.rstrip() + "\n")
    except OSError:
        LOGGER.warning("gate check: could not write log file")


def command_label(skill: str) -> str:
    """Return the typed command name for a skill: `tg-<skill>`."""
    return COMMAND_PREFIX + skill


def skill_from_command(command_name: str) -> Optional[str]:
    """Return the chain skill name for `tg-<skill>`, else None."""
    if not command_name.startswith(COMMAND_PREFIX):
        return None
    skill = command_name[len(COMMAND_PREFIX):]
    return skill if skill in CHAIN_SKILLS else None


def find_ticket_ids(command_args: str) -> List[str]:
    """Return every whitespace token that looks like a ticket id, uppercased, in order."""
    tokens = [token.strip(TOKEN_PUNCTUATION) for token in command_args.split()]
    return [token.upper() for token in tokens if TICKET_ID_RE.match(token)]


def find_tickets_root(env: Dict[str, str]) -> Tuple[Optional[str], str]:
    """Return (tickets folder, "") from the path loader, or (None, reason) when it cannot be found.

    The loader lives in the Tollgate scripts folder, found through TOLLGATE_HOME. The folder name
    is never written in this hook: it comes from the paths file or the loader's single layout table.
    """
    home = env.get(HOME_ENV, "")
    if not home:
        return None, "{0} is not set, so the path loader cannot be found".format(HOME_ENV)
    scripts = os.path.join(home, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from core import paths  # type: ignore
        return str(paths.get_path("tickets", env)), ""
    except Exception as error:  # the loader raises NotSetUp when the vault is unknown
        return None, "the tickets folder could not be resolved ({0})".format(error)


def first_existing_ticket(candidates: List[str], tickets_root: str) -> Optional[str]:
    """Return the first candidate whose real folder sits under tickets_root, else None.

    A folder that is a symlink pointing outside tickets_root is skipped, so a planted link
    cannot hide a real ticket named later in the arguments.
    """
    for key in candidates:
        if ticket_folder(key, tickets_root):
            return key
    return None


def ticket_folder(key: str, tickets_root: str) -> Optional[str]:
    """Return the real folder of a ticket, or None.

    Uses the shared helper in the path loader when it can be imported; the code below is the
    fallback and also covers ids the helper refuses (a digit in the prefix).
    Looks flat first (`<tickets>/KEY`), then nested by the letters before the hyphen
    (`<tickets>/PREFIX/KEY`, the prefix folder matched without regard to case, so `ex`
    and `EX` both work). A folder that resolves outside tickets_root is ignored.
    """
    loader = shared_paths()
    if loader is not None and hasattr(loader, "ticket_folder"):
        try:
            shared = loader.ticket_folder(key, tickets_root)
        except Exception:
            shared = None
        if shared is not None:
            return str(shared)
    flat = os.path.join(tickets_root, key)
    if os.path.isdir(flat) and is_under(tickets_root, flat):
        return flat
    prefix = key.split("-", 1)[0]
    try:
        names = sorted(os.listdir(tickets_root))
    except OSError:
        return None
    for name in names:
        if name.upper() != prefix.upper():
            continue
        nested = os.path.join(tickets_root, name, key)
        if os.path.isdir(nested) and is_under(tickets_root, nested):
            return nested
    return None


def is_under(root: str, path: str) -> bool:
    """True if the resolved path sits at or below the resolved root."""
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(path)
    return os.path.commonpath([real_root, real_path]) == real_root


def try_read(tickets_root: str, path: str) -> Tuple[Optional[bytes], bool]:
    """Return (bytes or None, unreadable). Unreadable means permission denied."""
    if not is_under(tickets_root, path):
        return None, False
    try:
        with open(path, "rb") as handle:
            return handle.read(), False
    except PermissionError:
        return None, True
    except OSError:
        return None, False


def read_artifact(tickets_root: str, path: str) -> Optional[bytes]:
    """Read bytes from path if it resolves under tickets_root, else None."""
    return try_read(tickets_root, path)[0]


def ticket_file(ticket_dir: str, key: str, suffix: str) -> str:
    return os.path.join(ticket_dir, "{0}-{1}.md".format(key, suffix))


def override_valid(
    rules: Any, tickets_root: str, ticket_dir: str, key: str, skill: str, today: datetime.date
) -> bool:
    """True if the override file has `Override: <skill> <today> <reason>` outside fences.

    A symlinked override file is refused (and logged); so is anything that is not a regular file
    (a named pipe, device or folder, which could also hang the read), and one that is not UTF-8 text.
    """
    path = ticket_file(ticket_dir, key, OVERRIDE_SUFFIX)
    if os.path.islink(path):
        log_line("override_refused", "symlink {0}".format(key))
        return False
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return False
    if not stat.S_ISREG(mode):
        log_line("override_refused", "not a regular file {0}".format(key))
        return False
    text = rules.decode_text(read_artifact(tickets_root, path))
    if text is None:
        return False
    stamp = today.strftime(DATE_FORMAT)
    for line in rules.lines_outside_fences(text):
        match = OVERRIDE_RE.match(line.rstrip())
        if match and match.group(1) == skill and match.group(2) == stamp:
            return True
    return False


def run_check(rules: Any, skill: str, files: Dict[str, Optional[bytes]]) -> Any:
    """Apply the gate_rules check for one skill to the loaded files."""
    if skill == "arch":
        return rules.check_arch(files["spec"], files["state"])
    if skill == "dev":
        return rules.check_dev(files["design"], files["state"])
    return rules.check_qa(
        files["state"], files["spec"], files["design"], files["edge-case-validation"]
    )


def build_reason(
    reason: str, skill: str, key: str, ticket_dir: str,
    unreadable: Optional[List[str]] = None,
) -> str:
    """Compose the block message: reason, file paths named in it, next skill, override."""
    paths: List[str] = [
        ticket_file(ticket_dir, key, suffix)
        for name, suffix in FILE_SUFFIXES.items()
        if name in reason
    ]
    parts = ["Gate check blocked /{0} {1}: {2}.".format(command_label(skill), key, reason)]
    if paths:
        parts.append("Files checked: " + ", ".join(paths) + ".")
    if unreadable:
        parts.append("Not readable (permission denied, fix the file permissions): "
                     + ", ".join(unreadable) + ".")
    parts.append("Run /{0} {1} first.".format(command_label(RUN_FIRST[skill]), key))
    parts.append(
        "To override once, the owner adds `Override: {0} YYYY-MM-DD <reason>` (today's date) to {1}.".format(
            skill, ticket_file(ticket_dir, key, OVERRIDE_SUFFIX)
        )
    )
    return " ".join(parts)


def load_files(
    tickets_root: str, ticket_dir: str, key: str
) -> Tuple[Dict[str, Optional[bytes]], List[str]]:
    """Load the artifacts. Also return the paths that exist but are not readable."""
    files: Dict[str, Optional[bytes]] = {}
    unreadable: List[str] = []
    for suffix in FILE_SUFFIXES.values():
        path = ticket_file(ticket_dir, key, suffix)
        files[suffix], denied = try_read(tickets_root, path)
        if denied:
            unreadable.append(path)
    return files, unreadable


def not_checked_warning(skill: str, why: str) -> str:
    """One visible line saying the gate did not check this command, and why."""
    return "Gate not checked for /{0}: {1}. The command was allowed without a gate check.".format(
        command_label(skill), why
    )


def evaluate(
    payload: Dict[str, Any], env: Dict[str, str], today: datetime.date,
    warnings: Optional[List[str]] = None,
) -> Optional[str]:
    """Return a block message, or None to allow. May raise; the caller blocks a gated skill and lets any other prompt through.

    When the gate cannot check a gated skill that names a ticket, it still allows but appends
    a warning line to `warnings` so main can show it.
    """
    if warnings is None:
        warnings = []
    skill = skill_from_command(str(payload.get("command_name", "")))
    if skill not in GATED_SKILLS:
        return None
    candidates = find_ticket_ids(str(payload.get("command_args", "")))
    knowledge = env.get(KNOWLEDGE_ENV, "")
    if not candidates or not knowledge:
        log_line("allow", "no ticket id or {0} unset ({1})".format(KNOWLEDGE_ENV, skill))
        if candidates:
            warnings.append(not_checked_warning(
                skill, "{0} is not set, so ticket folders cannot be found".format(KNOWLEDGE_ENV)))
        return None
    tickets_root, why = find_tickets_root(env)
    if tickets_root is None:
        log_line("allow", "tickets folder not resolved ({0}): {1}".format(skill, why))
        if candidates:
            warnings.append(not_checked_warning(skill, why))
        return None
    key = first_existing_ticket(candidates, tickets_root)
    if key is None:
        log_line("allow", "no ticket id with a folder under {0} ({1})".format(tickets_root, skill))
        warnings.append(not_checked_warning(
            skill, "no ticket folder named {0} under {1}; check the ticket id and {2}".format(
                " or ".join(candidates), tickets_root, KNOWLEDGE_ENV)))
        return None
    ticket_dir = ticket_folder(key, tickets_root) or os.path.join(tickets_root, key)
    if not is_under(tickets_root, ticket_dir):
        log_line("allow", "ticket folder outside {0}".format(tickets_root))
        return None
    return decide(skill, key, tickets_root, ticket_dir, today)


def decide(
    skill: str, key: str, tickets_root: str, ticket_dir: str, today: datetime.date
) -> Optional[str]:
    """Check the override, then the gate rules. Return a block message or None."""
    import gate_rules

    if override_valid(gate_rules, tickets_root, ticket_dir, key, skill, today):
        log_line("override", "{0} {1}".format(skill, key))
        return None
    files, unreadable = load_files(tickets_root, ticket_dir, key)
    result = run_check(gate_rules, skill, files)
    if result.ok:
        return None
    log_line("block", "{0} {1}{2}".format(skill, key, " unreadable" if unreadable else ""))
    return build_reason(result.reason, skill, key, ticket_dir, unreadable)


def normalize_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Return (payload with command_name and command_args, is_pretool_call).

    A PreToolUse Skill payload carries the skill in tool_input.skill and arguments in tool_input.args.
    A PreToolUse payload for any other tool yields an empty command name, so nothing is gated.
    """
    if payload.get("hook_event_name") == "PreToolUse" or "tool_name" in payload:
        if payload.get("tool_name") != "Skill":
            return {"command_name": "", "command_args": ""}, True
        tool_input = payload.get("tool_input")
        tool_input = tool_input if isinstance(tool_input, dict) else {}
        name = str(tool_input.get("skill") or "").lstrip("/")
        return {"command_name": name, "command_args": str(tool_input.get("args") or "")}, True
    return payload, False


def is_gated_call(payload: Dict[str, Any], env: Dict[str, str]) -> bool:
    """True when the command is one of the gated chain skills (tg-arch, tg-dev, tg-qa)."""
    return skill_from_command(str(payload.get("command_name", ""))) in GATED_SKILLS


def parse_payload(raw: str) -> Dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("payload is not a JSON object")
    return data


def main(
    stdin_text: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    today: Optional[datetime.date] = None,
    emit: Callable[[str], None] = lambda text: sys.stdout.write(text + "\n"),
) -> int:
    """Run the hook. Returns 0 (a block is a JSON line on stdout) or 2 for an unreadable payload."""
    environment = dict(os.environ) if env is None else env
    try:
        raw = sys.stdin.read() if stdin_text is None else stdin_text
        payload, pretool = normalize_payload(parse_payload(raw))
    except Exception as error:  # fail closed: a payload that cannot be read is not allowed through
        log_line("fail_closed", "{0}: {1}".format(type(error).__name__, error))
        LOGGER.warning("gate check blocked (payload unreadable): %s", type(error).__name__)
        return 2
    warnings: List[str] = []
    try:
        message = evaluate(payload, environment, today or datetime.date.today(), warnings)
    except Exception as error:
        detail = "{0}: {1}".format(type(error).__name__, error)
        if is_gated_call(payload, environment):
            log_line("fail_closed", detail)
            LOGGER.warning("gate check failed for a gated skill, blocking: %s", type(error).__name__)
            message = "The gate check could not run ({0}), so this skill is blocked. See the gate log.".format(
                type(error).__name__)
        else:
            log_line("fail_open", detail)
            LOGGER.warning("gate check skipped (internal error, see gate log): %s", type(error).__name__)
            return 0
    if message:
        if pretool:
            emit(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }}))
        else:
            emit(json.dumps({"decision": "block", "reason": message}))
    elif warnings:
        emit(json.dumps({"systemMessage": " ".join(warnings)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
