#!/usr/bin/env python3
"""Test base for the comms connectors: routed mock client and run helpers.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Share setup between the per-connector tests. Synthetic data only.
Change log:
  - First version.
"""
import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import unittest
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from connector_helpers import MockClient, FakeSecretStore, assert_no_network  # noqa: E402,F401
from throwaway_home import throwaway_home  # noqa: E402
from connectors import registry, connect  # noqa: E402

FAKE_ADDRESS = "https://api.example.invalid"


def fake_secret():
    return "tgfake-" + uuid.uuid4().hex


def fake_slack_token():
    """A chat token shaped string, built from pieces so no token literal sits in this file."""
    return "xo" + "xb-" + "1234567890" + "-" + "abcdefghij"


def fake_credential():
    """A keyword style credential (the CREDENTIAL label), built from pieces."""
    return "pass" + "word=" + "Zz9Yy8Xx7Ww6Vv5Uu4"


class RoutedClient(MockClient):
    """Records calls; `handler(method, url, kwargs)` returns a JSON-able body."""

    def __init__(self, handler=None):
        super().__init__()
        self.handler = handler or (lambda m, u, k: {})

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        return {"status": 200, "body": json.dumps(self.handler(method, url, kwargs))}


class Base(unittest.TestCase):
    NAME = None
    MODULE = None  # imported module object

    def setUp(self):
        import importlib
        importlib.reload(self.MODULE)   # a restart test may have cleared the registry
        self.cm = throwaway_home()
        self.home, env = self.cm.__enter__()
        self.env = dict(env, TOLLGATE_NONINTERACTIVE="1")
        self.store = FakeSecretStore()
        self.mock = RoutedClient()
        registry.set_store(self.store)
        registry.set_http_factory(lambda: self.mock)
        self.secret = fake_secret()

    def tearDown(self):
        registry.set_store(None)
        registry.set_http_factory(None)
        self.cm.__exit__(None, None, None)

    def turn_on(self, key=None, address=FAKE_ADDRESS):
        os.environ["TG_TEST_KEY"] = key or self.secret
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return connect.main(["on", self.NAME, "--address", address,
                                     "--key-from-env", "TG_TEST_KEY"], env=self.env)
        finally:
            del os.environ["TG_TEST_KEY"]

    def run_main(self, argv=None, **extra):
        """Run the connector main through run_cli. Returns (code, out, err)."""
        old = os.environ.copy()
        os.environ.update(self.env)
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = registry.run_cli(lambda: self.MODULE.main(argv or [], **extra))
                except SystemExit as e:
                    code = e.code
            return code, out.getvalue(), err.getvalue()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def home_files(self):
        for dp, dn, fn in os.walk(self.home):
            for f in fn:
                yield pathlib.Path(dp, f)

    def read_json(self, *parts):
        return json.loads(pathlib.Path(self.home, *parts).read_text())

    def log_text(self):
        p = pathlib.Path(self.home, ".tollgate", "logs", "run_log.jsonl")
        return p.read_text() if p.exists() else ""

    def assert_text_absent(self, needle, texts):
        for t in texts:
            self.assertNotIn(needle, t)


def make_con_tests(base, argv_fn, extra_fn=None):
    """Return a TestCase class with CON-01 to CON-04 for one connector.

    argv_fn(test) gives the command line for a working run; extra_fn(test)
    gives keyword arguments for main (for example a fake process runner).
    """
    class Con(base):
        def run_ok(self):
            return self.run_main(argv_fn(self), **(extra_fn(self) if extra_fn else {}))

        def test_con01_not_set_up(self):
            with assert_no_network():
                code, out, err = self.run_ok()
            self.assertNotIn(code, (0, None))
            self.assertIn("%s: not set up" % self.NAME, err)
            self.assertIn("connect.py on %s" % self.NAME, err)
            self.assertEqual(self.mock.calls, [])
            self.assertFalse(os.path.exists(self.env["TOLLGATE_CONNECTORS"]))

        def test_con01_subprocess_exit_code(self):
            script = pathlib.Path(self.MODULE.__file__)
            r = subprocess.run([sys.executable, "-B", str(script)] + argv_fn(self),
                               env=self.env, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("%s: not set up" % self.NAME, r.stderr)

        def test_con02_first_use_secret_nowhere_on_disk(self):
            with assert_no_network():
                self.assertEqual(self.turn_on(), 0)
            self.assertTrue(self.store.asked_to_store(self.NAME))
            self.assertEqual(self.store.get(self.NAME), self.secret)
            needle = self.secret.encode()
            for root in (ROOT, pathlib.Path(self.home)):
                for dp, dn, fn in os.walk(root):
                    dn[:] = [d for d in dn if d != ".git"]
                    for f in fn:
                        try:
                            data = open(os.path.join(dp, f), "rb").read()
                        except OSError:
                            continue
                        self.assertNotIn(needle, data, os.path.join(dp, f))
            text = open(self.env["TOLLGATE_CONNECTORS"]).read()
            self.assertIn(self.NAME, text)
            self.assertIn(FAKE_ADDRESS, text)

        def test_con03_on_survives_restart_and_reaches_client(self):
            import importlib
            self.turn_on()
            registry._FACTORIES.clear()           # a restart: only file and store remain
            importlib.reload(self.MODULE)
            self.MODULE_RELOADED = True
            code, out, err = self.run_ok()
            self.assertIn(code, (0, None), err)
            self.assertEqual(registry.load_state(self.env)[self.NAME],
                             {"address": FAKE_ADDRESS, "on": True})
            self.reached_client()

        def test_con04_off_returns_to_not_set_up(self):
            self.turn_on()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(connect.main(["off", self.NAME], env=self.env), 0)
            self.assertIsNone(self.store.get(self.NAME))
            with assert_no_network():
                code, out, err = self.run_ok()
            self.assertNotIn(code, (0, None))
            self.assertIn("%s: not set up" % self.NAME, err)
            self.assertEqual(self.mock.calls, [])

    return Con
