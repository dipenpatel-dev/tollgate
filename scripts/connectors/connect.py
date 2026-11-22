#!/usr/bin/env python3
"""connect.py: turn a connector on or off, or show its status.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: The one command for connector setup.
Change log:
  - First version.

  connect.py on NAME [--address URL] [--key-from-env VAR | --key-stdin]
                     [--allow-host HOST]
  connect.py off NAME
  connect.py status [NAME]

In a terminal with no flags it asks for the address and key (the key is read
with no echo). Flags give the same result without a terminal.

A key is sent only to a host on the connector's built-in list. For a
self-hosted or enterprise host, run this yourself in a terminal with
`--allow-host HOST` (HOST or HOST:PORT); it is refused without a terminal.
"""
import argparse
import getpass
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from connectors import registry
from connectors.secret_store import SecretStoreError, check_name

NotSetUp = registry.NotSetUp


def first_use(name, env=None, prompt=None, address=None, settings=None,
              allow_hosts=None):
    """Ask for address and key, store the key, turn the connector on."""
    check_name(name)
    ask = prompt or {"address": lambda m: input(m),
                     "key": lambda m: getpass.getpass(m)}
    print("%s: not set up yet. Setting it up now." % name, file=sys.stderr)
    if not address:
        address = ask["address"]("Address for %s: " % name).strip()
    key = ask["key"]("Key for %s (hidden): " % name).strip()
    if not address or not key:
        raise NotSetUp("%s: setup needs both an address and a key" % name)
    try:
        registry.check_no_credentials(address)
    except ValueError as e:
        raise NotSetUp("%s: %s" % (name, e)) from None
    registry.turn_on(name, address, key, env, settings, allow_hosts)


def _read_key(args, stdin):
    if args.key_from_env:
        v = os.environ.get(args.key_from_env, "")
        if not v:
            raise NotSetUp("environment variable %s is empty or missing"
                           % args.key_from_env)
        return v.strip()
    if args.key_stdin:
        return stdin.read().strip()
    return None


def parse_sets(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise NotSetUp("--set needs KEY=VALUE, got '%s'" % it.split("=")[0])
        k, v = it.split("=", 1)
        out[k.strip()] = v
    return out


def cmd_on(args, stdin, env):
    settings = parse_sets(args.set)
    registry.check_settings(settings)    # refuse before anything is written
    allow = list(args.allow_host or [])
    if allow and not registry.interactive(env):
        raise NotSetUp("--allow-host is an owner step: run it yourself in a "
                       "terminal. It is refused when there is no terminal.")
    for h in allow:
        registry.normalize_allowed_host(h)   # refuse before anything is written
    key = _read_key(args, stdin)
    if key is None:
        if not registry.interactive(env):
            raise NotSetUp("%s: no terminal. Pass --address and either "
                           "--key-from-env VAR or --key-stdin" % args.name)
        first_use(args.name, env=env, address=args.address, settings=settings,
                  allow_hosts=allow)
    else:
        address = args.address or registry.load_state(env).get(
            args.name, {}).get("address")
        if not address or not key:
            raise NotSetUp("%s: pass --address URL and a non-empty key" % args.name)
        registry.turn_on(args.name, address, key, env, settings, allow)
    print("%s: on" % args.name)


def cmd_off(args, env):
    registry.turn_off(args.name, env)
    print("%s: off" % args.name)


def _print_settings(e):
    for k, v in sorted((e.get("settings") or {}).items()):
        print("  %s = %s" % (k, v))


def cmd_status(args, env):
    state = registry.load_state(env)
    names = [args.name] if args.name else sorted(state)
    if not names:
        print("no connectors set up")
    for n in names:
        e = state.get(n)
        if e and e.get("on"):
            addr = e.get("address", "")
            try:
                registry.check_no_credentials(addr)
            except ValueError:
                addr = "hidden: the saved address holds a login"
            print("%s: on (%s)" % (n, addr))
            _print_settings(e)
        elif e:
            print("%s: off" % n)
            _print_settings(e)
        else:
            print("%s: not set up" % n)
    return 0 if not args.name or (state.get(args.name) or {}).get("on") else 1


def main(argv=None, stdin=None, env=None):
    p = argparse.ArgumentParser(prog="connect.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    on = sub.add_parser("on")
    on.add_argument("name")
    on.add_argument("--address")
    on.add_argument("--allow-host", action="append", default=[], metavar="HOST")
    on.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    g = on.add_mutually_exclusive_group()
    g.add_argument("--key-from-env", metavar="VAR")
    g.add_argument("--key-stdin", action="store_true")
    off = sub.add_parser("off")
    off.add_argument("name")
    st = sub.add_parser("status")
    st.add_argument("name", nargs="?")
    args = p.parse_args(argv)
    try:
        if args.cmd == "on":
            cmd_on(args, stdin or sys.stdin, env)
        elif args.cmd == "off":
            cmd_off(args, env)
        else:
            return cmd_status(args, env)
    except (NotSetUp, SecretStoreError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
