#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: shared list of Tollgate's own files that a model tool call must not write
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Lives in hooks/lib so it is a helper module, not a hook entry. Used by pre-tool-write-guard-path.sh (Write, Edit) and pre-tool-bash-guard-code-dir.py (Bash).
Protected: ~/.claude/settings.json, ~/.claude/credentials.sh, ~/.tollgate/, the shell profiles
(.zshrc, .bashrc, .bash_profile, .profile) in HOME, and the hooks folder and settings.json of the
Tollgate repo (found from this file's own location, TOLLGATE_HOME and CLAUDE_DOTFILES).
Method: every path is made absolute, symlinks are resolved, and the result is compared in lower
case so case-insensitive file systems cannot be used to slip past. The typed path and the
resolved path are both checked. Reads are never blocked here; callers only ask about writes.
Command line: `protected_paths.py <path>` exits 10 when the path is protected, 0 when it is not,
and 2 on any error (the caller blocks on 2, so the guard fails closed).
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple

PROTECTED_EXIT = 10
HOME_FILES = (".claude/settings.json", ".claude/credentials.sh", ".claude/tollgate-config",
              ".zshrc", ".bashrc", ".bash_profile", ".profile")
HOME_DIRS = (".tollgate", ".claude/tollgate")
REPO_FILES = ("settings.json",)
REPO_DIRS = ("hooks",)
ENV_HOME = "HOME"
ENV_REPO_VARS = ("TOLLGATE_HOME", "CLAUDE_DOTFILES")
ENV_FILE_VARS = ("TOLLGATE_CONNECTORS", "TOLLGATE_PATHS", "TOLLGATE_CONFIG")
EXPANDED_VARS = (ENV_HOME,) + ENV_REPO_VARS

Root = Tuple[str, bool]  # (lower case path, is_dir)


def _norm(path: str) -> str:
    return os.path.normpath(os.path.abspath(path)).lower()


def _real(path: str) -> str:
    return os.path.realpath(path).lower()


def _both(path: str) -> List[str]:
    """The typed (normalised) form and the symlink-resolved form, lower case, without duplicates."""
    forms = [_norm(path)]
    real = _real(path)
    if real not in forms:
        forms.append(real)
    return forms


def protected_roots(env: Optional[Dict[str, str]] = None) -> List[Root]:
    """All protected files and folders for this machine, typed and resolved forms."""
    env = os.environ if env is None else env
    home = env.get(ENV_HOME) or os.path.expanduser("~")
    repo_dirs = [os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))]
    repo_dirs += [env[name] for name in ENV_REPO_VARS if env.get(name)]
    roots: List[Root] = []
    for name in HOME_FILES:
        roots += [(form, False) for form in _both(os.path.join(home, name))]
    for name in HOME_DIRS:
        roots += [(form, True) for form in _both(os.path.join(home, name))]
    for name in ENV_FILE_VARS:
        roots += [(form, False) for form in _both(env[name])] if env.get(name) else []
    for repo in repo_dirs:
        for name in REPO_FILES:
            roots += [(form, False) for form in _both(os.path.join(repo, name))]
        for name in REPO_DIRS:
            roots += [(form, True) for form in _both(os.path.join(repo, name))]
    return roots


def dir_root(path: str) -> List[Root]:
    """A whole folder as protected roots (used for the read-only code directory)."""
    return [(form, True) for form in _both(path)]


def is_protected(path: str, roots: List[Root], cwd: Optional[str] = None) -> bool:
    """True when path is a protected file, or is or sits inside a protected folder."""
    if not path or path.startswith("-"):
        return False
    base = cwd or os.getcwd()
    full = os.path.join(base, os.path.expanduser(path))
    for form in _both(full):
        for root, is_dir in roots:
            if form == root or (is_dir and form.startswith(root.rstrip("/") + "/")):
                return True
    return False


def expand_vars(text: str, env: Optional[Dict[str, str]] = None) -> str:
    """Replace $NAME and ${NAME} for HOME, TOLLGATE_HOME and CLAUDE_DOTFILES with their values."""
    env = os.environ if env is None else env
    for name in EXPANDED_VARS:
        value = env.get(name) or (os.path.expanduser("~") if name == ENV_HOME else "")
        if value:
            text = text.replace("${%s}" % name, value).replace("$" + name, value)
    return text


def main(argv: List[str]) -> int:
    try:
        if len(argv) != 2:
            return 2
        return PROTECTED_EXIT if is_protected(argv[1], protected_roots()) else 0
    except Exception:
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
