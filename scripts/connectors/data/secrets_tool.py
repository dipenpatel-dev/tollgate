#!/usr/bin/env python3
"""secrets_tool: list, set, delete and clean up secrets in the user's secret store.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: A small command on top of scripts/connectors/secret_store.py. The user
         names every secret. This tool never prints a value, never writes a
         value to a file, and never puts a value in an argument list.
Change log:
  - First version.

  secrets_tool.py list
  secrets_tool.py set NAME            (value typed with no echo, or --stdin)
  secrets_tool.py delete NAME
  secrets_tool.py cleanup NAME [NAME ...] --confirm

With no secret store (no Keychain, no secret-tool) every command refuses.
There is no plain-file fallback. `list` shows names only. The names this tool
has set are kept in a names-only index file in the state folder (a store has
no way to list its own entries); the index never holds a value.
"""
import argparse
import getpass
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from connectors import registry
from connectors.secret_store import RefusingStore, SecretStoreError

NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
INDEX_FILE = "secret-names.json"


class ToolError(Exception):
    pass


def _store():
    store = registry.get_store()
    if isinstance(store, RefusingStore):
        raise ToolError(RefusingStore.MESSAGE)
    return store


def _index_path(env=None):
    env = os.environ if env is None else env
    state = env.get("TOLLGATE_STATE_DIR")
    if state:
        base = pathlib.Path(os.path.expanduser(state))
    else:
        from core.paths import get_path
        base = get_path("state")
    return base / INDEX_FILE


def _load_index(env=None):
    try:
        data = json.loads(_index_path(env).read_text())
    except (OSError, ValueError):
        return []
    return sorted(n for n in data if isinstance(n, str)) if isinstance(data, list) else []


def _save_index(names, env=None):
    p = _index_path(env)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(set(names)), indent=2) + "\n")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def _check_name(name):
    if not NAME_RE.match(name or ""):
        raise ToolError("a secret name uses letters, digits, dot, dash or underscore (1 to 64)")
    return name


def _connector_names(env=None):
    try:
        return set(registry.load_state(env))
    except Exception:
        return set()


def _guard_connector(name, env=None):
    if name in _connector_names(env):
        raise ToolError("%s is a connector key. Use connect.py on/off for it." % name)


def cmd_list(env=None):
    _store()
    names = _load_index(env)
    for n in names:
        print(n)
    if not names:
        print("no secrets set through this tool")
    return 0


def cmd_set(name, stdin, env=None):
    _check_name(name)
    store = _store()
    _guard_connector(name, env)
    if stdin is not None:
        value = stdin.read().strip()
    elif registry.interactive(env):
        value = getpass.getpass("Value for %s (hidden): " % name).strip()
    else:
        raise ToolError("no terminal. Pipe the value on stdin and pass --stdin")
    if not value:
        raise ToolError("the value is empty; nothing saved")
    store.set(name, value)
    value = None
    _save_index(_load_index(env) + [name], env)
    print("%s: saved" % name)
    return 0


def cmd_delete(name, env=None):
    _check_name(name)
    store = _store()
    _guard_connector(name, env)
    store.delete(name)
    _save_index([n for n in _load_index(env) if n != name], env)
    print("%s: deleted" % name)
    return 0


def cmd_cleanup(names, confirm, env=None):
    for n in names:
        _check_name(n)
    store = _store()
    for n in names:
        _guard_connector(n, env)
    if not confirm:
        print("would delete: " + ", ".join(names))
        print("nothing deleted. Pass --confirm to delete them.")
        return 1
    for n in names:
        store.delete(n)
    _save_index([n for n in _load_index(env) if n not in set(names)], env)
    print("deleted %d secret(s)" % len(names))
    return 0


def main(argv=None, stdin=None, env=None):
    p = argparse.ArgumentParser(prog="secrets_tool.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("set")
    s.add_argument("name")
    s.add_argument("--stdin", action="store_true", help="read the value from stdin")
    d = sub.add_parser("delete")
    d.add_argument("name")
    c = sub.add_parser("cleanup")
    c.add_argument("names", nargs="+")
    c.add_argument("--confirm", action="store_true")
    args, extra = p.parse_known_args(argv)
    if extra:
        # Never echo the extra words: one of them may be a value typed by mistake.
        print("secrets_tool.py: unexpected extra words. A value is never taken as "
              "an argument; use --stdin or the hidden prompt.", file=sys.stderr)
        sys.exit(2)
    try:
        if args.cmd == "list":
            return cmd_list(env)
        if args.cmd == "set":
            return cmd_set(args.name, (stdin or sys.stdin) if args.stdin else None, env)
        if args.cmd == "delete":
            return cmd_delete(args.name, env)
        return cmd_cleanup(args.names, args.confirm, env)
    except (ToolError, SecretStoreError) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
