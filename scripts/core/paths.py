"""
module_name: paths.py
description: Path loader. Resolves logical folder names to real paths from the paths file and environment.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.1.0
change_log:
  1.1.0: vault_git_mode() reads the vault_git setting (none, local, remote) and detects it when the line is missing or bad.
  1.0.1: whiteboard added to the knowledge subfolders so the installer creates it and the backfill finds it.
  1.0.0: Initial path loader.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess


class NotSetUp(Exception):
    """Raised when a path cannot be resolved because setup is not done."""


_ENV_PATHS = "TOLLGATE_PATHS"
_ENV_KNOWLEDGE = "TOLLGATE_KNOWLEDGE"
_ENV_STATE = "TOLLGATE_STATE_DIR"
_ENV_CODE = "TOLLGATE_CODE_DIR"

# The one table that names the vault folders. Every script, hook and the installer takes
# folder names from here (or from a line of the same name in the paths file). Nothing else
# may hold a folder name. To change the layout, change this table or add a line to the paths file.
LAYOUT = {
    "landing": "00-landing",
    "system_map": "01-system-map",
    "tickets": "02-tickets",
    "knowledge": "03-knowledge-base",
    "education": "04-education",
    "conversations": "05-conversations",
    "chat_threads": "06-chat-threads",
    "reference": "08-reference",
    "memory": "memory",
    "output": "output",
}
# Folders the installer creates inside a layout folder: (layout key, subfolder names).
LAYOUT_SUBDIRS = (
    ("system_map", ("clients", "pipelines", "architecture", "data-model", "platform-learning")),
    ("knowledge", ("decisions", "learnings", "patterns", "whiteboard")),
)
# name -> folder name under the vault. "vault" names are joined onto the vault folder.
_VAULT_CHILDREN = dict(LAYOUT, meetings="meetings", references="references")
_HOME_CHILDREN = {
    "cache": "cache",
    "logs": "logs",
    "index": "index",
}
NAMES = ("vault",) + tuple(_VAULT_CHILDREN) + ("state", "cache", "logs", "index", "repos", "standards")


def _expand(value: str) -> pathlib.Path:
    return pathlib.Path(os.path.expandvars(os.path.expanduser(value.strip()))).expanduser()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _read_file(env=None) -> dict:
    """Read simple `name: path` lines from the paths file. Missing file gives {}."""
    location = (env if env is not None else os.environ).get(_ENV_PATHS, "").strip()
    if not location:
        return {}
    file = _expand(location)
    try:
        text = file.read_text()
    except OSError:
        return {}
    found: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        name, _, value = line.partition(":")
        value = value.split(" #")[0]
        value = _unquote(value)
        if name.strip() and value:
            found[name.strip()] = value
    return found


def _tg_home() -> pathlib.Path:
    return pathlib.Path(os.path.expanduser("~")) / ".tollgate"


def _default(name: str, explicit: dict, env=None) -> pathlib.Path:
    environ = env if env is not None else os.environ
    if name == "vault":
        raise NotSetUp("not set up: " + _ENV_KNOWLEDGE + " is not set")
    if name in _VAULT_CHILDREN:
        return get_path("vault", env) / _VAULT_CHILDREN[name]
    if name == "state":
        value = environ.get(_ENV_STATE, "").strip()
        return _expand(value) if value else _tg_home() / "state"
    if name in _HOME_CHILDREN:
        return _tg_home() / _HOME_CHILDREN[name]
    if name == "repos":
        value = environ.get(_ENV_CODE, "").strip()
        if value:
            return _expand(value)
        raise NotSetUp("not set up: " + _ENV_CODE + " is not set")
    if name == "standards":
        # No default. Unset means the optional standards collection is off.
        raise NotSetUp("not set up: no `standards` line in the paths file")
    raise KeyError("unknown path name: " + name)


def get_path(name: str, env=None) -> pathlib.Path:
    """Return the folder for a logical name. Raises NotSetUp if it cannot be resolved.

    env is an optional mapping used in place of os.environ (the hooks pass their own).
    """
    environ = env if env is not None else os.environ
    explicit = _read_file(env)
    if name in explicit:
        return _expand(explicit[name])
    if name == "vault":
        value = environ.get(_ENV_KNOWLEDGE, "").strip()
        if value:
            return _expand(value)
    return _default(name, explicit, env)


def file_value(name: str, env=None):
    """Return the folder a paths-file line gives for a name, or None when there is no such line.

    For names that are not in NAMES (for example `sessions`), which get_path does not know.
    """
    explicit = _read_file(env)
    return _expand(explicit[name]) if name in explicit else None


VAULT_GIT_MODES = ("none", "local", "remote")


def detect_vault_git(vault) -> str:
    """Guess the vault git mode from the vault folder: no .git is none, no remote is local, else remote."""
    vault = pathlib.Path(vault)
    if not (vault / ".git").exists():
        return "none"
    try:
        done = subprocess.run(["git", "-C", str(vault), "remote"], capture_output=True,
                              universal_newlines=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return "local"
    if done.returncode == 0 and done.stdout.strip():
        return "remote"
    return "local"


def vault_git_mode(env=None) -> str:
    """Return how the vault is saved: none, local or remote.

    The `vault_git` line of the paths file wins. A missing or bad value is detected from the vault
    folder (see detect_vault_git). Raises NotSetUp when detection is needed and there is no vault.
    """
    value = _read_file(env).get("vault_git", "").strip().lower()
    if value in VAULT_GIT_MODES:
        return value
    return detect_vault_git(get_path("vault", env))


def get_all() -> dict:
    """Return every name that resolves. Names that cannot resolve are left out."""
    result: dict = {}
    for name in NAMES:
        try:
            result[name] = get_path(name)
        except NotSetUp:
            continue
    return result


def folder_name(key: str, env=None) -> str:
    """Return the folder name (relative to the vault) for a layout key such as `tickets`.

    A paths-file line for the key wins. A path inside the vault gives its relative name. A line
    outside the vault gives the last part, so name comparisons still work.
    """
    if key not in _VAULT_CHILDREN:
        raise KeyError("unknown layout name: " + key)
    explicit = _read_file(env)
    if key in explicit:
        chosen = _expand(explicit[key])
        try:
            return chosen.relative_to(get_path("vault", env)).as_posix()
        except (ValueError, NotSetUp):
            return chosen.name
    return _VAULT_CHILDREN[key]


_TICKET_KEY = re.compile(r"^[A-Za-z]+-[0-9]+$")
_TICKET_PREFIX = re.compile(r"^[A-Za-z]+$")


def _inside(root: pathlib.Path, path: pathlib.Path) -> bool:
    """True when the real location of path is at or below the real location of root."""
    try:
        real_root = os.path.realpath(str(root))
        real_path = os.path.realpath(str(path))
        return os.path.commonpath([real_root, real_path]) == real_root
    except ValueError:
        return False


def _ticket_root(tickets_root, env=None) -> pathlib.Path:
    return pathlib.Path(tickets_root) if tickets_root is not None else get_path("tickets", env)


def ticket_prefix_depth(parts) -> int:
    """Return 1 when a path below the tickets folder starts with a prefix folder, else 0.

    parts are the path parts after the tickets folder name, for example ("PROJ", "PROJ-312", "PROJ-312-state.md").
    A prefix level is a letters-only folder followed by a ticket key folder with the same letters,
    and at least one more part (a file) after that. Flat paths such as ("PROJ-312", "PROJ-312-state.md") give 0.
    """
    if len(parts) < 3:
        return 0
    first, second = parts[0], parts[1]
    if (_TICKET_PREFIX.match(first) and _TICKET_KEY.match(second)
            and second.split("-", 1)[0].upper() == first.upper()):
        return 1
    return 0


def ticket_folder(key: str, tickets_root=None, env=None):
    """Return the folder of one ticket, or None.

    A vault keeps tickets flat (`<tickets>/KEY`) or by prefix (`<tickets>/PREFIX/KEY`, PREFIX being
    the letters before the hyphen, matched without regard to case). Flat is tried first. A key that
    is not letters, a hyphen and digits is refused, and so is a folder whose real location is
    outside the tickets folder. tickets_root defaults to the tickets path from the loader.
    """
    if not isinstance(key, str) or not _TICKET_KEY.match(key):
        return None
    root = _ticket_root(tickets_root, env)
    flat = root / key
    if flat.is_dir() and _inside(root, flat):
        return flat
    prefix = key.split("-", 1)[0].upper()
    try:
        names = sorted(os.listdir(str(root)))
    except OSError:
        return None
    for name in names:
        if name.upper() != prefix:
            continue
        nested = root / name / key
        if nested.is_dir() and _inside(root, nested):
            return nested
    return None


def iter_ticket_folders(tickets_root=None, env=None):
    """Yield every ticket folder, flat or under a prefix folder, sorted by path.

    Only folders named like a ticket key are yielded, and only when their real location is inside
    the tickets folder. A prefix folder is a folder named with letters only.
    """
    root = _ticket_root(tickets_root, env)
    try:
        names = sorted(os.listdir(str(root)))
    except OSError:
        return
    for name in names:
        child = root / name
        if not child.is_dir() or not _inside(root, child):
            continue
        if _TICKET_KEY.match(name):
            yield child
        elif _TICKET_PREFIX.match(name):
            try:
                inner = sorted(os.listdir(str(child)))
            except OSError:
                continue
            for sub in inner:
                nested = child / sub
                if (_TICKET_KEY.match(sub) and sub.split("-", 1)[0].upper() == name.upper()
                        and nested.is_dir() and _inside(root, nested)):
                    yield nested


def subdir_prefixes(layout_key: str, names, env=None) -> tuple:
    """Return `<layout folder>/<name>/` for each name the layout lists under layout_key.

    A name the layout does not list under that key is left out, so a scan never names a folder
    the installer does not create.
    """
    listed = set()
    for key, subs in LAYOUT_SUBDIRS:
        if key == layout_key:
            listed.update(subs)
    base = folder_name(layout_key, env)
    return tuple(base + "/" + name + "/" for name in names if name in listed)


def layout_dirs() -> list:
    """Every vault folder the installer creates, as names relative to the vault."""
    names = [folder_name(key) for key in LAYOUT]
    for key, subs in LAYOUT_SUBDIRS:
        names.extend(folder_name(key) + "/" + sub for sub in subs)
    return names


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["layout"]:
        for line in ("%s: %s" % (key, name) for key, name in LAYOUT.items()):
            print(line)
    elif sys.argv[1:] == ["dirs"]:
        print("\n".join(layout_dirs()))
    else:
        sys.stderr.write("usage: paths.py layout | dirs\n")
        sys.exit(2)
