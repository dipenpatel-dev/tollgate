#!/usr/bin/env python3
# Module:      ticket_state_check.py
# Description: Checks one ticket folder under the tickets path. It reads the state, spec,
#              design and validation files and flags a missing file or field that the gate
#              and the commands rely on: a single first Status line in each file, a state
#              value from the allowed list, and last_block_applied once dev has started.
#              It reads only. It imports the gate rules so the two never disagree.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Ticket state files, read only
# Version:     1.0
# ChangeLog:
#   Initial version
"""Usage:
    ticket_state_check.py KEY [--tickets-dir DIR] [--json]

Exit codes: 0 no problems, 1 at least one problem, 2 not set up or ticket folder missing.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "hooks"))

from core.paths import get_path, NotSetUp, ticket_folder  # noqa: E402
import gate_rules  # noqa: E402

# Every value a state file may hold (docs/gate-lines.md). The four named in the gate rules
# come from that module; the others are written by the ticket, support, spec and qa commands.
VALID_STATES = (
    "ROUTED",
    "SUPPORT_COMPLETE",
    "RESOLVED_TIER_1",
    "ENHANCEMENT_PROPOSED",
    gate_rules.STATE_SPEC_APPROVED,
    "DESIGN_COMPLETE",
    gate_rules.STATE_DESIGN_APPROVED,
    gate_rules.STATE_IN_DEV,
    gate_rules.STATE_DEV_COMPLETE,
    "QA_BLOCKED",
    "QA_APPROVED",
)
# States from which each artifact must exist with its own accepted Status value.
SPEC_STATES = (
    gate_rules.STATE_SPEC_APPROVED, "DESIGN_COMPLETE", gate_rules.STATE_DESIGN_APPROVED,
    gate_rules.STATE_IN_DEV, gate_rules.STATE_DEV_COMPLETE, "QA_BLOCKED", "QA_APPROVED",
)
DESIGN_STATES = (
    gate_rules.STATE_DESIGN_APPROVED, gate_rules.STATE_IN_DEV,
    gate_rules.STATE_DEV_COMPLETE, "QA_BLOCKED", "QA_APPROVED",
)
VALIDATION_STATES = (gate_rules.STATE_DEV_COMPLETE, "QA_BLOCKED", "QA_APPROVED")
BLOCK_STATES = (gate_rules.STATE_IN_DEV, gate_rules.STATE_DEV_COMPLETE, "QA_BLOCKED", "QA_APPROVED")
BLOCK_KEY = "last_block_applied"
BLOCK_VALUE = re.compile(r"^(none|B-\d{2})$")
KEY_PATTERN = re.compile(r"^[A-Za-z]+-\d+$")

EXIT_OK, EXIT_PROBLEM, EXIT_SETUP = 0, 1, 2


def _read(path):
    try:
        return path.read_bytes()
    except OSError:
        return None


def _first_content_line(text):
    """Return (line number, text) of the first line that is not blank, front matter or a heading."""
    in_front = False
    for number, line in enumerate(gate_rules.split_lines(text), start=1):
        stripped = line.strip()
        if number == 1 and stripped == "---":
            in_front = True
            continue
        if in_front:
            if stripped == "---":
                in_front = False
            continue
        if not stripped or stripped.startswith("#"):
            continue
        return number, stripped
    return 0, ""


def _last_block(text):
    for line in gate_rules.lines_outside_fences(text):
        match = re.match(r"^\s*(?:[-*]\s*)?%s\s*:\s*(.*)$" % BLOCK_KEY, line)
        if match:
            return match.group(1).strip().strip("`")
    return None


def _check_artifact(findings, folder, key, suffix, allowed, label):
    path = folder / "{}-{}".format(key, suffix)
    data = _read(path)
    if data is None:
        findings.append(("error", "MISSING_FILE", "{} file {}-{} is missing".format(label, key, suffix)))
        return
    status = gate_rules.read_status(data)
    if not status.ok:
        findings.append(("error", "BAD_STATUS", "{} file: {}".format(label, status.reason)))
    elif status.value not in allowed:
        findings.append(("error", "WRONG_STATUS", "{} file needs Status: {}".format(label, " or ".join(allowed))))


def check_ticket(folder, key):
    """Return a list of (level, code, message) findings for a ticket folder."""
    findings = []
    state_path = folder / "{}-state.md".format(key)
    data = _read(state_path)
    if data is None:
        findings.append(("error", "MISSING_FILE", "state file {}-state.md is missing".format(key)))
        return findings
    text = gate_rules.decode_text(data)
    status = gate_rules.read_status(data)
    if not status.ok:
        findings.append(("error", "BAD_STATUS", "state file: {}".format(status.reason)))
        return findings
    if status.value not in VALID_STATES:
        findings.append(("error", "UNKNOWN_STATE", "state file holds a Status value that is not allowed"))
        return findings
    number, first = _first_content_line(text)
    if not first.startswith(gate_rules.STATUS_PREFIX) and not first.startswith("## Skill Handoff"):
        findings.append(("warn", "STATUS_NOT_FIRST", "the Status line is not the first line of content"))
    state = status.value
    if state in BLOCK_STATES:
        block = _last_block(text)
        if block is None:
            findings.append(("error", "MISSING_FIELD", "state file has no {} line".format(BLOCK_KEY)))
        elif not BLOCK_VALUE.match(block):
            findings.append(("error", "BAD_FIELD", "{} must be none or B-NN".format(BLOCK_KEY)))
    if state in SPEC_STATES:
        _check_artifact(findings, folder, key, "spec.md", (gate_rules.SPEC_APPROVED_STATUS,), "spec")
    if state in DESIGN_STATES:
        _check_artifact(findings, folder, key, "design.md", (gate_rules.DESIGN_APPROVED_STATUS,), "design")
    if state in VALIDATION_STATES:
        _check_artifact(findings, folder, key, "edge-case-validation.md",
                        gate_rules.VALIDATION_STATUSES, "validation")
    return findings


def build_parser():
    parser = argparse.ArgumentParser(description="Check one ticket folder for the fields the gate relies on.")
    parser.add_argument("key", help="Ticket key, for example T-001.")
    parser.add_argument("--tickets-dir", type=pathlib.Path, default=None,
                        help="Tickets folder. Default: the tickets path from the path loader.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not KEY_PATTERN.match(args.key):
        print("not a ticket key: {}".format(args.key), file=sys.stderr)
        return EXIT_SETUP
    try:
        tickets = args.tickets_dir if args.tickets_dir else get_path("tickets")
    except NotSetUp:
        print("not set up", file=sys.stderr)
        return EXIT_SETUP
    folder = ticket_folder(args.key, pathlib.Path(tickets))
    if folder is None:
        print("ticket folder not found: {}".format(args.key), file=sys.stderr)
        return EXIT_SETUP
    findings = check_ticket(folder, args.key)
    problems = [f for f in findings if f[0] == "error"]
    if args.json:
        print(json.dumps({"ticket": args.key, "ok": not problems,
                          "findings": [{"level": a, "code": b, "message": c} for a, b, c in findings]},
                         indent=2))
    elif not findings:
        print("{}: ok".format(args.key))
    else:
        for level, code, message in findings:
            print("{} {} {}: {}".format(level.upper(), code, args.key, message))
    return EXIT_PROBLEM if problems else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
