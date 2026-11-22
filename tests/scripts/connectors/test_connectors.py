#!/usr/bin/env python3
"""Connector framework tests CON-01 to CON-04, plus secret store checks.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove a connector is off until first use, and never leaks a key.
Change log:
  - First version.
"""
import contextlib
import io
import os
import pathlib
import subprocess
import sys
import unittest
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from connector_helpers import MockClient, FakeSecretStore, assert_no_network
from throwaway_home import throwaway_home
import fake_connector
from connectors import registry, connect, secret_store


def fake_secret():
    return "tgfake-" + uuid.uuid4().hex


def env_with(env):
    return dict(env, TOLLGATE_NONINTERACTIVE="1")


class Base(unittest.TestCase):
    def setUp(self):
        self.cm = throwaway_home()
        self.home, self.env = self.cm.__enter__()
        self.env = env_with(self.env)
        self.store = FakeSecretStore()
        self.mock = MockClient()
        registry.set_store(self.store)
        registry.set_http_factory(lambda: self.mock)
        self.secret = fake_secret()

    def tearDown(self):
        registry.set_store(None)
        registry.set_http_factory(None)
        self.cm.__exit__(None, None, None)

    def turn_on(self, address="https://fake.invalid"):
        self.addCleanup(lambda: None)
        os.environ["TG_TEST_KEY"] = self.secret
        try:
            code = connect.main(["on", "fakeconn", "--address", address,
                                 "--key-from-env", "TG_TEST_KEY"], env=self.env)
        finally:
            del os.environ["TG_TEST_KEY"]
        return code

    def run_fake_main(self):
        old = os.environ.copy()
        os.environ.update(self.env)
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err), \
                    contextlib.redirect_stdout(io.StringIO()):
                try:
                    code = registry.run_cli(fake_connector.main)
                except SystemExit as e:
                    code = e.code
            return code, err.getvalue()
        finally:
            os.environ.clear()
            os.environ.update(old)


class TestCon(Base):
    def test_con01_not_set_up(self):
        with assert_no_network():
            code, err = self.run_fake_main()
        self.assertNotIn(code, (0, None))
        self.assertIn("fakeconn: not set up", err)
        self.assertIn("connect.py on fakeconn", err)
        self.assertEqual(self.mock.calls, [])
        self.assertFalse(os.path.exists(self.env["TOLLGATE_CONNECTORS"]))

    def test_con01_subprocess_exit_code(self):
        r = subprocess.run([sys.executable, "-B", str(HERE / "fake_connector.py")],
                           env=self.env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fakeconn: not set up", r.stderr)

    def test_con02_first_use_stores_secret_nowhere_on_disk(self):
        with assert_no_network():
            self.assertEqual(self.turn_on(), 0)
        self.assertTrue(self.store.asked_to_store("fakeconn"))
        self.assertEqual(self.store.get("fakeconn"), self.secret)
        needle = self.secret.encode()
        roots = [ROOT, pathlib.Path(self.home)]
        for root in roots:
            for dp, dn, fn in os.walk(root):
                dn[:] = [d for d in dn if d != ".git"]
                for f in fn:
                    p = os.path.join(dp, f)
                    try:
                        with open(p, "rb") as fh:
                            data = fh.read()
                    except OSError:
                        continue
                    self.assertNotIn(needle, data, p)
        with open(self.env["TOLLGATE_CONNECTORS"]) as fh:
            text = fh.read()
        self.assertIn("fakeconn", text)
        self.assertIn("https://fake.invalid", text)

    def test_con02_key_from_stdin(self):
        code = connect.main(["on", "fakeconn", "--address", "https://a.invalid",
                             "--key-stdin"], stdin=io.StringIO(self.secret + "\n"),
                            env=self.env)
        self.assertEqual(code, 0)
        self.assertEqual(self.store.get("fakeconn"), self.secret)

    def test_con02_noninteractive_without_key_refuses(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = connect.main(["on", "fakeconn", "--address", "https://a.invalid"],
                                env=self.env)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.store.stored_names(), [])

    def test_con03_on_survives_restart_and_reaches_client(self):
        self.turn_on()
        # a "restart": the in-process state is dropped; only the file and store remain
        registry._FACTORIES.clear()
        import importlib
        importlib.reload(fake_connector)
        os.environ.update(self.env)
        try:
            client = registry.require("fakeconn")
            client.ping()
        finally:
            for k in self.env:
                os.environ.pop(k, None)
        self.assertEqual(len(self.mock.calls), 1)
        self.assertEqual(self.mock.calls[0]["url"], "https://fake.invalid/ping")
        self.assertEqual(registry.load_state(self.env)["fakeconn"],
                         {"address": "https://fake.invalid", "on": True})

    def test_con04_off_returns_to_not_set_up(self):
        self.turn_on()
        self.assertEqual(connect.main(["off", "fakeconn"], env=self.env), 0)
        self.assertIsNone(self.store.get("fakeconn"))
        with assert_no_network():
            code, err = self.run_fake_main()
        self.assertNotIn(code, (0, None))
        self.assertIn("fakeconn: not set up", err)
        self.assertEqual(self.mock.calls, [])

    def test_status(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(connect.main(["status", "fakeconn"], env=self.env), 1)
            self.turn_on()
            self.assertEqual(connect.main(["status", "fakeconn"], env=self.env), 0)
        self.assertIn("fakeconn: not set up", out.getvalue())
        self.assertIn("fakeconn: on", out.getvalue())

    def test_ensure_first_use_in_terminal(self):
        answers = {"address": lambda m: "https://t.invalid", "key": lambda m: self.secret}
        env = dict(self.env)
        env["TOLLGATE_NONINTERACTIVE"] = "0"
        orig = registry.interactive
        registry.interactive = lambda e=None: True
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                client = registry.ensure("fakeconn", env=env, prompt=answers)
        finally:
            registry.interactive = orig
        client.ping()
        self.assertEqual(self.mock.calls[0]["url"], "https://t.invalid/ping")


class TestSecretStores(unittest.TestCase):
    class Recorder:
        def __init__(self, rc=0, out=""):
            self.calls, self.rc, self.out = [], rc, out

        def __call__(self, argv, **kw):
            self.calls.append((argv, kw))
            return subprocess.CompletedProcess(argv, self.rc, self.out, "")

    def test_keychain_secret_not_in_arguments(self):
        s = fake_secret()
        rec = self.Recorder()
        secret_store.MacKeychainStore(run=rec).set("x", s)
        argv, kw = rec.calls[0]
        self.assertNotIn(s, " ".join(argv))
        self.assertIn(s, kw["input"])

    def test_keychain_rejects_unsafe_value(self):
        with self.assertRaises(secret_store.SecretStoreError):
            secret_store.MacKeychainStore(run=self.Recorder()).set("x", 'a"b')

    def test_secret_tool_secret_on_stdin(self):
        s = fake_secret()
        rec = self.Recorder()
        secret_store.SecretToolStore(run=rec).set("x", s)
        argv, kw = rec.calls[0]
        self.assertNotIn(s, " ".join(argv))
        self.assertEqual(kw["input"], s)

    def test_get_returns_value_or_none(self):
        self.assertEqual(secret_store.MacKeychainStore(
            run=self.Recorder(0, "abc\n")).get("x"), "abc")
        self.assertIsNone(secret_store.MacKeychainStore(
            run=self.Recorder(44)).get("x"))

    def test_no_tool_refuses_never_plain_file(self):
        st = secret_store.default_store(system="Linux", which=lambda n: None)
        with self.assertRaises(secret_store.NoSecretStore) as cm:
            st.set("x", "v")
        self.assertIn("plain file", str(cm.exception))
        self.assertIsInstance(
            secret_store.default_store(system="Windows", which=lambda n: "x"),
            secret_store.RefusingStore)

    def test_default_store_choice(self):
        self.assertIsInstance(
            secret_store.default_store(system="Darwin", which=lambda n: "/x"),
            secret_store.MacKeychainStore)
        self.assertIsInstance(
            secret_store.default_store(system="Linux", which=lambda n: "/x"),
            secret_store.SecretToolStore)

    def test_memory_store(self):
        m = secret_store.MemoryStore()
        m.set("a", "1")
        self.assertEqual(m.get("a"), "1")
        m.delete("a")
        self.assertIsNone(m.get("a"))


if __name__ == "__main__":
    unittest.main()
