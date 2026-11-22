#!/usr/bin/env python3
"""
module_name: validate_state_files.py
description: Checks that ticket state files have a well-formed front matter block with a
             ticket key and a status. Prints file names and reasons only, never file text.
             Used to prove the sample fixtures stay valid and to check a folder of real state files.
             The source repo held an empty validation config folder, so this is the only
             validation helper; domain validators stay out of Tollgate.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial front matter validator.
usage:
  validate_state_files.py FOLDER_OR_FILE      exit 0 all valid, 1 some invalid, 2 bad path
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

KEY_FIELDS = ("ticket", "ticket_id")
LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:(\s.*)?$")


def check_text(text: str) -> list:
    """Return a list of reason codes. Empty means valid."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ["no_front_matter"]
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return ["front_matter_not_closed"]
    fields, reasons = {}, []
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith(("#", "-")) or raw.startswith(" "):
            continue
        if not LINE.match(raw):
            reasons.append("malformed_line")
            continue
        key, _sep, value = raw.partition(":")
        fields[key] = value.strip()
    if not any(fields.get(k) for k in KEY_FIELDS):
        reasons.append("no_ticket_key")
    if not fields.get("status"):
        reasons.append("no_status")
    return reasons


def find_state_files(path: pathlib.Path) -> list:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.md") if "state" in p.name)


def validate(path) -> dict:
    """Return {file path: [reasons]} for every state file that is invalid."""
    bad = {}
    for file in find_state_files(pathlib.Path(path)):
        try:
            reasons = check_text(file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            reasons = ["unreadable"]
        if reasons:
            bad[str(file)] = reasons
    return bad


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate ticket state file front matter.")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    if not pathlib.Path(args.path).exists():
        print("No such path", file=sys.stderr)
        return 2
    bad = validate(args.path)
    for file, reasons in bad.items():
        print(f"{pathlib.Path(file).name}: {', '.join(reasons)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
