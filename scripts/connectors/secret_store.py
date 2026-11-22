#!/usr/bin/env python3
"""Secret store interface and the default stores for macOS and Linux.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Keep connector keys in the user's own secret store, never in a file.
Change log:
  - First version: SecretStore interface, Keychain, secret-tool, in-memory fake.

A key never goes into an argument list. The Keychain store sends its command
on stdin through `security -i`. The Linux store sends the key on stdin.
If neither tool exists, the default store refuses. There is no plain-file store.
"""
import getpass
import platform
import re
import shutil
import subprocess

SERVICE_PREFIX = "tollgate-"


class SecretStoreError(Exception):
    pass


class NoSecretStore(SecretStoreError):
    pass


class SecretStore:
    """Interface: set, get, delete. Names are connector names."""

    def set(self, name, value):
        raise NotImplementedError

    def get(self, name):
        raise NotImplementedError

    def delete(self, name):
        raise NotImplementedError


NAME_RE = re.compile(r"\A[a-z0-9][a-z0-9_-]{0,63}\Z")


def check_name(name):
    """Refuse a connector name that is not plain lowercase letters, digits, - or _."""
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise SecretStoreError("a connector name is lowercase letters, digits, "
                               "dashes and underscores only, and starts with a "
                               "letter or digit")


def _service(name):
    check_name(name)
    return SERVICE_PREFIX + name


def _account():
    try:
        return getpass.getuser()
    except Exception:
        return "tollgate"


class MacKeychainStore(SecretStore):
    def __init__(self, run=subprocess.run):
        self._run = run

    def set(self, name, value):
        if any(c in value for c in ('"', "\\", "\n", "\r", "\0")):
            raise SecretStoreError(
                "the key has a quote, backslash or line break, which the "
                "Keychain command cannot take safely; use a plain token")
        # `security -i` reads commands from stdin, so the key is never an argument.
        line = ('add-generic-password -a "%s" -s "%s" -U -w "%s"\n'
                % (_account(), _service(name), value))
        r = self._run(["security", "-i"], input=line, text=True,
                      capture_output=True)
        if r.returncode != 0:
            raise SecretStoreError("Keychain refused to save the key for " + name)

    def get(self, name):
        r = self._run(["security", "find-generic-password", "-a", _account(),
                       "-s", _service(name), "-w"], text=True,
                      capture_output=True)
        if r.returncode != 0:
            return None
        return r.stdout.rstrip("\n")

    def delete(self, name):
        self._run(["security", "delete-generic-password", "-a", _account(),
                   "-s", _service(name)], text=True, capture_output=True)


class SecretToolStore(SecretStore):
    def __init__(self, run=subprocess.run):
        self._run = run

    def _attrs(self, name):
        return ["service", _service(name), "account", _account()]

    def set(self, name, value):
        r = self._run(["secret-tool", "store", "--label=" + _service(name)]
                      + self._attrs(name), input=value, text=True,
                      capture_output=True)
        if r.returncode != 0:
            raise SecretStoreError("secret-tool refused to save the key for " + name)

    def get(self, name):
        r = self._run(["secret-tool", "lookup"] + self._attrs(name),
                      text=True, capture_output=True)
        if r.returncode != 0 or not r.stdout:
            return None
        return r.stdout

    def delete(self, name):
        self._run(["secret-tool", "clear"] + self._attrs(name),
                  text=True, capture_output=True)


class MemoryStore(SecretStore):
    """In-memory fake for tests. Nothing touches disk."""

    def __init__(self):
        self._data = {}

    def set(self, name, value):
        self._data[name] = value

    def get(self, name):
        return self._data.get(name)

    def delete(self, name):
        self._data.pop(name, None)


class RefusingStore(SecretStore):
    """Used when no secret store exists. Every call refuses."""

    MESSAGE = ("no secret store found (macOS Keychain or Linux secret-tool). "
               "Tollgate will not keep a key in a plain file. "
               "Install secret-tool, then try again.")

    def set(self, name, value):
        raise NoSecretStore(self.MESSAGE)

    def get(self, name):
        raise NoSecretStore(self.MESSAGE)

    def delete(self, name):
        raise NoSecretStore(self.MESSAGE)


def default_store(system=None, which=shutil.which):
    system = system or platform.system()
    if system == "Darwin" and which("security"):
        return MacKeychainStore()
    if system == "Linux" and which("secret-tool"):
        return SecretToolStore()
    return RefusingStore()
