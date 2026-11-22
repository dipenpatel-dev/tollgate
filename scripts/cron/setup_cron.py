#!/usr/bin/env python3
# Module:      setup_cron.py
# Description: Create a scheduled job (a macOS launchd job file) from the generic template.
#              It writes only one file, inside the home folder given with --home, under
#              Library/LaunchAgents. It never loads the job unless --yes-install-job is
#              given. With --dry-run it prints the file and the folder and writes nothing.
#              The launcher program (launchctl) can be replaced with --launcher, which the
#              tests use so that the real launchd is never called.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Scheduled job setup
# Version:     1.0
# ChangeLog:
#   Initial version
"""Usage:
    setup_cron.py --home DIR (--job nightly-index|weekly-reminder | --program PATH)
                  [--label NAME] [--hour H] [--minute M] [--weekday 0-6] [--arg X ...]
                  [--dry-run] [--yes-install-job] [--launcher PATH] [--remove]

Without --yes-install-job the job file is written but not loaded, and the text says so.
Exit codes: 0 done, 1 refused, 2 bad arguments or not set up.
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "launchd" / "job.plist.template"
AGENTS_SUBPATH = ("Library", "LaunchAgents")
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
# Variables copied into the job so it finds the same folders. Names and paths only, never a secret.
# The job still resolves every folder through the path loader at run time, and a `vault:` line in the
# paths file wins over the copied TOLLGATE_KNOWLEDGE. nightly_index.sh stops with a clear message
# when the vault folder it was given no longer exists.
CARRIED_VARIABLES = ("TOLLGATE_HOME", "TOLLGATE_PATHS", "TOLLGATE_KNOWLEDGE", "TOLLGATE_STATE_DIR",
                     "TOLLGATE_CODE_DIR", "TOLLGATE_PYTHON", "CLAUDE_CONFIG_DIR")
BASE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

JOBS = {
    "nightly-index": {"script": "nightly_index.sh", "args": ["--notify"], "hour": 2, "minute": 0, "weekday": None},
    "weekly-reminder": {"script": "think_calibrate_reminder.sh", "args": [], "hour": 9, "minute": 0, "weekday": 0},
}


def build_parser():
    p = argparse.ArgumentParser(description="Create a scheduled job file from the template.")
    p.add_argument("--home", required=True, type=pathlib.Path,
                   help="Home folder to write into. Only Library/LaunchAgents below it is touched.")
    p.add_argument("--job", choices=sorted(JOBS), help="A ready made job.")
    p.add_argument("--program", type=pathlib.Path, help="Program to run (instead of --job).")
    p.add_argument("--arg", action="append", default=[], help="Argument for the program (repeatable).")
    p.add_argument("--label", help="Job name. Default: tg-job-<job>.")
    p.add_argument("--hour", type=int)
    p.add_argument("--minute", type=int)
    p.add_argument("--weekday", type=int, help="0 is Sunday. Leave out for every day.")
    p.add_argument("--dry-run", action="store_true", help="Print what would be written; write nothing.")
    p.add_argument("--yes-install-job", action="store_true", help="Also load the job (needed to really schedule it).")
    p.add_argument("--launcher", default="launchctl", help="Program used to load or unload the job.")
    p.add_argument("--remove", action="store_true", help="Remove the job file (and unload it with --yes-install-job).")
    return p


def settings(args):
    """Resolve program, arguments, label and schedule from the flags."""
    job = JOBS.get(args.job) if args.job else None
    if job is None and args.program is None:
        raise ValueError("give --job or --program")
    if job is not None:
        program = pathlib.Path(__file__).resolve().parent / job["script"]
        program_args = list(job["args"]) + list(args.arg)
        hour = job["hour"] if args.hour is None else args.hour
        minute = job["minute"] if args.minute is None else args.minute
        weekday = job["weekday"] if args.weekday is None else args.weekday
        label = args.label or "tg-job-" + args.job
    else:
        program, program_args = args.program, list(args.arg)
        hour = 2 if args.hour is None else args.hour
        minute = 0 if args.minute is None else args.minute
        weekday = args.weekday
        label = args.label or "tg-job-" + re.sub(r"\W+", "-", program.stem)
    if not LABEL_PATTERN.match(label):
        raise ValueError("bad label")
    if not (0 <= hour <= 23 and 0 <= minute <= 59) or (weekday is not None and not 0 <= weekday <= 6):
        raise ValueError("bad time")
    return label, program, program_args, hour, minute, weekday


def render(label, program, program_args, hour, minute, weekday, log_file, env):
    """Fill the template. All values are XML escaped."""
    arguments = "\n".join("        <string>{}</string>".format(escape(str(a)))
                          for a in ["/bin/bash", str(program)] + list(program_args))
    schedule = []
    if weekday is not None:
        schedule.append("        <key>Weekday</key>\n        <integer>{}</integer>".format(weekday))
    schedule.append("        <key>Hour</key>\n        <integer>{}</integer>".format(hour))
    schedule.append("        <key>Minute</key>\n        <integer>{}</integer>".format(minute))
    environment = "\n".join("        <key>{}</key>\n        <string>{}</string>".format(escape(k), escape(v))
                            for k, v in env)
    text = TEMPLATE.read_text(encoding="utf-8")
    for marker, value in (("@LABEL@", escape(label)), ("@PROGRAM_ARGUMENTS@", arguments),
                          ("@SCHEDULE@", "\n".join(schedule)), ("@ENVIRONMENT@", environment),
                          ("@LOG_FILE@", escape(str(log_file)))):
        text = text.replace(marker, value)
    return text


def inside(child, parent):
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        label, program, program_args, hour, minute, weekday = settings(args)
    except ValueError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    home = args.home
    if not home.is_dir():
        print("error: --home is not a folder", file=sys.stderr)
        return 2
    agents = home.joinpath(*AGENTS_SUBPATH)
    plist = agents / (label + ".plist")
    if not inside(agents, home):
        print("refused: the job folder would be outside --home", file=sys.stderr)
        return 1

    if args.remove:
        print("{}: remove {}".format("dry run" if args.dry_run else "remove", plist))
        if args.dry_run:
            return 0
        if args.yes_install_job and plist.exists():
            subprocess.run([args.launcher, "bootout", "gui/{}".format(os.getuid()), str(plist)],
                           capture_output=True, text=True)
        if plist.exists():
            plist.unlink()
        return 0

    try:
        log_file = get_path("logs") / (label + ".log")
    except NotSetUp:
        print("not set up", file=sys.stderr)
        return 2
    env = [("PATH", BASE_PATH)] + [(k, os.environ[k]) for k in CARRIED_VARIABLES if os.environ.get(k)]
    text = render(label, program, program_args, hour, minute, weekday, log_file, env)

    if args.dry_run:
        print("dry run. Nothing is written and nothing is loaded.")
        print("would write: {}".format(plist))
        print("would load:  {}".format("yes (--yes-install-job given)" if args.yes_install_job else "no"))
        print(text)
        return 0

    agents.mkdir(parents=True, exist_ok=True)
    plist.write_text(text, encoding="utf-8")
    print("wrote: {}".format(plist))
    print("note: the job keeps the folder variables as they are now. If the vault moves, add a `vault:` "
          "line to the paths file or run this script again.")
    if not args.yes_install_job:
        print("not loaded. Add --yes-install-job to load the job.")
        return 0
    if args.launcher == "launchctl" and home.resolve() != pathlib.Path(os.environ.get("HOME", "")).resolve():
        print("refused: the real launcher only loads a job from the real home folder", file=sys.stderr)
        return 1
    proc = subprocess.run([args.launcher, "bootstrap", "gui/{}".format(os.getuid()), str(plist)],
                          capture_output=True, text=True)
    print("loaded" if proc.returncode == 0 else "load failed (exit {})".format(proc.returncode))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
