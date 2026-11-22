#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: shared helpers for the read before write guard (pattern, state dir, session log path)
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Used by pre-tool-write-require-read.py and post-tool-read-record.py.
Env:
  GUARD_REGEX         regex for guarded paths (default: names ending in -state.md)
  TOLLGATE_STATE_DIR   state directory (default: $HOME/.tollgate/state); a `state` line in the paths
                       file wins when the path loader can be imported through TOLLGATE_HOME
"""

from __future__ import annotations

import os
import re
import sys

DEFAULT_GUARD_REGEX = r"-state\.md$"
DEFAULT_STATE_SUBPATH = os.path.join(".tollgate", "state")
READ_LOG_SUBDIR = "read_log"
UNKNOWN_SESSION = "unknown"
UNSAFE_SESSION_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def guard_pattern() -> re.Pattern:
    """Compile GUARD_REGEX, falling back to the default when unset or empty."""
    return re.compile(os.environ.get("GUARD_REGEX") or DEFAULT_GUARD_REGEX)


def _loader_state_dir() -> str:
    """The state folder from the path loader (paths file, then TOLLGATE_STATE_DIR), or "" when unavailable."""
    home = os.environ.get("TOLLGATE_HOME", "")
    if not home:
        return ""
    scripts = os.path.join(home, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from core import paths  # type: ignore
        return str(paths.get_path("state"))
    except Exception:
        return ""


def state_dir() -> str:
    """Directory that holds per session read logs."""
    loaded = _loader_state_dir()
    if loaded:
        return loaded
    configured = os.environ.get("TOLLGATE_STATE_DIR")
    return configured or os.path.join(os.path.expanduser("~"), DEFAULT_STATE_SUBPATH)


def read_log_path(session_id: str) -> str:
    """Path of the read log for one session, with the id made filename safe."""
    safe = UNSAFE_SESSION_CHARS.sub("_", session_id or "") or UNKNOWN_SESSION
    return os.path.join(state_dir(), READ_LOG_SUBDIR, safe + ".log")


def normalize(path: str) -> str:
    """Resolve symlinks and relative parts so reads and writes compare equal."""
    return os.path.realpath(os.path.expanduser(path))
