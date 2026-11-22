#!/usr/bin/env python3
"""Connector test helpers: mock client, fake secret store, no-network check."""
import contextlib
import socket


class MockClient:
    """Records every request; returns canned responses. Makes no network call."""

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        return self.responses.get((method, url), {"status": 200, "body": {}})

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)


class FakeSecretStore:
    """Secret store interface that records what it was asked to store.

    Values stay in memory only. `requests` keeps the NAMES asked for, never
    the values, so a test can assert on behavior without echoing a secret.
    """

    def __init__(self):
        self._data = {}
        self.requests = []  # (action, name)

    def set(self, name, value):
        self.requests.append(("set", name))
        self._data[name] = value

    def get(self, name):
        self.requests.append(("get", name))
        return self._data.get(name)

    def delete(self, name):
        self.requests.append(("delete", name))
        self._data.pop(name, None)

    def stored_names(self):
        return sorted(self._data)

    def asked_to_store(self, name):
        return ("set", name) in self.requests


class NetworkAttempt(AssertionError):
    pass


@contextlib.contextmanager
def assert_no_network():
    """Fail the test if any code opens a socket connection inside the block."""
    attempts = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_gai = socket.getaddrinfo

    def blocked_connect(self, address, *a, **k):
        attempts.append(("connect", str(address)))
        raise NetworkAttempt("network call attempted: %r" % (address,))

    def blocked_connect_ex(self, address, *a, **k):
        attempts.append(("connect_ex", str(address)))
        raise NetworkAttempt("network call attempted: %r" % (address,))

    def blocked_gai(host, *a, **k):
        attempts.append(("getaddrinfo", str(host)))
        raise NetworkAttempt("dns lookup attempted: %r" % (host,))

    socket.socket.connect = blocked_connect
    socket.socket.connect_ex = blocked_connect_ex
    socket.getaddrinfo = blocked_gai
    try:
        yield attempts
    finally:
        socket.socket.connect = real_connect
        socket.socket.connect_ex = real_connect_ex
        socket.getaddrinfo = real_gai
    if attempts:
        raise NetworkAttempt("network attempts: %r" % (attempts,))


def _allow_invalid_test_hosts():
    """Let every test connector use fake `.invalid` hosts (never resolvable).

    Keeps a copy of the real host list in REAL_BUILTIN_HOSTS so a test of the
    host rules can put it back.
    """
    import copy
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))
    from connectors import registry
    global REAL_BUILTIN_HOSTS
    REAL_BUILTIN_HOSTS = copy.deepcopy(registry.BUILTIN_HOSTS)
    for name in ("fakeconn", "jira", "slack", "notion", "calendar",
                 "databricks", "plane"):
        registry.BUILTIN_HOSTS[name] = (tuple(registry.BUILTIN_HOSTS.get(name, ()))
                                        + (".invalid",))


REAL_BUILTIN_HOSTS = {}
_allow_invalid_test_hosts()
