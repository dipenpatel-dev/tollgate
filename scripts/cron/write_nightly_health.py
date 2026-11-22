#!/usr/bin/env python3
# Module:      write_nightly_health.py
# Description: Parse the nightly step results, write nightly-health.json into the state
#              folder, and (only with --notify) show a desktop notification on failure.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Nightly health file
# Version:     1.0
# ChangeLog:
#   Initial version
"""Usage: write_nightly_health.py [--notify] name:PASS name:FAIL:exit_code ...

Exit code is 0 unless the state folder cannot be resolved (2) or written (1).
"""
import argparse
import json
import logging
import pathlib
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

HEALTH_NAME = "nightly-health.json"
NOTIFICATION_TITLE = "Nightly index"
NOTIFICATION_BODY = "The nightly index failed. Check the log."


def parse_args(args):
    """Parse 'name:PASS' or 'name:FAIL:exit_code' positional args."""
    steps = []
    for arg in args:
        parts = arg.split(":", 2)
        if len(parts) < 2:
            log.warning("Skipping malformed arg: %r", arg)
            continue
        entry = {"name": parts[0], "status": parts[1]}
        if len(parts) == 3:
            try:
                entry["exit_code"] = int(parts[2])
            except ValueError:
                log.warning("Non-integer exit_code in arg: %r", arg)
        steps.append(entry)
    return steps


def compute_overall(steps):
    if not steps:
        return "FAIL"
    return "PASS" if all(s["status"] == "PASS" for s in steps) else "FAIL"


def write_health(health_path, steps, overall):
    payload = {
        "last_run": datetime.now().astimezone().isoformat(timespec="seconds"),
        "overall": overall,
        "steps": steps,
    }
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def fire_notification():
    script = 'display notification "{}" with title "{}"'.format(NOTIFICATION_BODY, NOTIFICATION_TITLE)
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        log.error("notification failed: %s", type(exc).__name__)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--notify", action="store_true", help="Show a desktop notification on failure.")
    parser.add_argument("steps", nargs="*")
    args = parser.parse_args(argv)
    if not args.steps:
        log.warning("No step results provided, writing an empty FAIL health file")
    try:
        health_path = get_path("state") / HEALTH_NAME
    except NotSetUp:
        print("not set up", file=sys.stderr)
        return 2
    steps = parse_args(args.steps)
    overall = compute_overall(steps)
    try:
        write_health(health_path, steps, overall)
    except OSError as exc:
        log.error("could not write the health file: %s", type(exc).__name__)
        return 1
    if overall == "FAIL" and args.notify:
        fire_notification()
    return 0


if __name__ == "__main__":
    sys.exit(main())
