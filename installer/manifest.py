#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: the owned-entries manifest. Records what Tollgate installed into ~/.claude so an
       update can remove what upstream dropped and --uninstall can remove only Tollgate's own files.
Ticket: none
ChangeLog:
  - Option parsing uses parse_intermixed_args: on python 3.9 the command names after the options were
    rejected as unrecognized arguments, which stopped the installer.
  - Created.

Manifest file: ~/.claude/tollgate/manifest.json, a JSON object with these keys:
  version      the Tollgate version that wrote it
  commands     file names (not paths) of the command files Tollgate installed into ~/.claude/commands
  hooks        identities of the hook entries Tollgate added to settings.json (written by merge_settings.py)
  permissions  {allow|ask|deny|additionalDirectories: [rules Tollgate added]} (written by merge_settings.py)
  env          settings.json env names Tollgate set (written by merge_settings.py)
  cron         names of scheduled jobs Tollgate created

A rename is a remove plus an add: the old file name is in the manifest, the new list no longer holds it,
so the old file is moved to a backup folder and the new one is installed. Nothing else is ever removed.

Usage:
  manifest.py sync-commands --manifest FILE --commands-dir DIR --backup-dir DIR [--version V] NAME...
  manifest.py uninstall-commands --manifest FILE --commands-dir DIR --backup-dir DIR
  manifest.py set-list --manifest FILE --key KEY [VALUE...]
  manifest.py get-list --manifest FILE --key KEY
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

KEEP_REMOVED_BACKUPS = 3


def load(path: str) -> dict:
    try:
        with open(path) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path: str, data: dict) -> bool:
    """Write only when the content changes. Returns True when the file was written."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    try:
        with open(path) as fh:
            if fh.read() == text:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return True


def safe_name(name: str) -> bool:
    """A command file name: no folder part, ends in .md, not hidden."""
    return bool(name) and name == os.path.basename(name) and name.endswith(".md") and not name.startswith(".")


def prune_siblings(path: str, keep: int = KEEP_REMOVED_BACKUPS) -> None:
    """Keep only the newest `keep` folders beside `path` (and path itself counts)."""
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        return
    dirs = sorted(d for d in os.listdir(parent) if os.path.isdir(os.path.join(parent, d)))
    for old in dirs[:-keep] if len(dirs) > keep else []:
        shutil.rmtree(os.path.join(parent, old), ignore_errors=True)


def remove_files(names: list[str], commands_dir: str, backup_dir: str) -> list[str]:
    """Move each named command file into backup_dir. Returns the names that were moved."""
    moved = []
    for name in names:
        if not safe_name(name):
            continue
        src = os.path.join(commands_dir, name)
        if not os.path.isfile(src) and not os.path.islink(src):
            continue
        os.makedirs(backup_dir, exist_ok=True)
        shutil.move(src, os.path.join(backup_dir, name))
        moved.append(name)
    if moved:
        prune_siblings(backup_dir)
    return moved


def sync_commands(manifest: str, commands_dir: str, backup_dir: str, names: list[str], version: str) -> int:
    data = load(manifest)
    old = [n for n in data.get("commands", []) if isinstance(n, str)]
    new = sorted(set(names))
    stale = [n for n in old if n not in new]
    for name in remove_files(stale, commands_dir, backup_dir):
        print(f"  Removed command dropped upstream: {name} (copy in {backup_dir})")
    data["commands"] = new
    if version:
        data["version"] = version
    save(manifest, data)
    return 0


def uninstall_commands(manifest: str, commands_dir: str, backup_dir: str) -> int:
    data = load(manifest)
    for name in remove_files([n for n in data.get("commands", []) if isinstance(n, str)], commands_dir, backup_dir):
        print(f"  Removed command: {name} (copy in {backup_dir})")
    data["commands"] = []
    save(manifest, data)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="manifest.py")
    ap.add_argument("action", choices=["sync-commands", "uninstall-commands", "set-list", "get-list"])
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--commands-dir")
    ap.add_argument("--backup-dir")
    ap.add_argument("--version", default="")
    ap.add_argument("--key")
    ap.add_argument("values", nargs="*")
    args = ap.parse_intermixed_args(argv[1:])   # python 3.9 parse_args drops names that follow options
    if args.action == "sync-commands":
        return sync_commands(args.manifest, args.commands_dir, args.backup_dir, args.values, args.version)
    if args.action == "uninstall-commands":
        return uninstall_commands(args.manifest, args.commands_dir, args.backup_dir)
    data = load(args.manifest)
    if args.action == "get-list":
        print("\n".join(str(v) for v in data.get(args.key, [])))
        return 0
    data[args.key] = sorted(set(args.values))
    save(args.manifest, data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
