#!/usr/bin/env python3
"""Connector hardening tests CON-Q06 and CON-Q07.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: A web address with a login in it is refused without echoing the
         password (Q-06). A hand-edited connectors file with wrong types never
         causes a traceback (Q-07).
Change log:
  - 2026-11-18 First version.
"""
import contextlib
import io
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from connector_helpers import MockClient, FakeSecretStore
from throwaway_home import throwaway_home
from connectors import registry, connect

PW = "hunter2-fakepw"


class Q06Credentials(unittest.TestCase):
    def setUp(self):
        self.cm = throwaway_home()
        self.home, self.env = self.cm.__enter__()
        self.env = dict(self.env, TOLLGATE_NONINTERACTIVE="1")
        self.store = FakeSecretStore()
        registry.set_store(self.store)
        registry.set_http_factory(lambda: MockClient())

    def tearDown(self):
        registry.set_store(None)
        registry.set_http_factory(None)
        self.cm.__exit__(None, None, None)

    def test_q06_url_with_login_is_refused_and_not_echoed(self):
        for url in ("https://user:%s@host.invalid" % PW,
                    "https://%s@host.invalid/path" % PW,
                    "https://:%s@host.invalid" % PW):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                import os
                os.environ["TG_Q06_KEY"] = "tgfake-key"
                try:
                    code = connect.main(["on", "fakeconn", "--address", url,
                                         "--key-from-env", "TG_Q06_KEY"], env=self.env)
                finally:
                    del os.environ["TG_Q06_KEY"]
            self.assertEqual(code, 1, url)
            self.assertIn("user name or password", err.getvalue())
            self.assertNotIn(PW, err.getvalue())
            self.assertFalse(registry.is_on("fakeconn", self.env))
            self.assertIsNone(self.store.get("fakeconn"))

    def test_q06_normal_address_still_accepted(self):
        registry.check_no_credentials("https://host.invalid/a?b=c@d")
        registry.check_address("https://host.invalid:8443/x")

    def test_q06_check_address_refuses_login_without_echo(self):
        with self.assertRaises(ValueError) as cm:
            registry.check_address("https://u:%s@host.invalid" % PW)
        self.assertNotIn(PW, str(cm.exception))

    def test_q06_status_hides_a_saved_login(self):
        p = pathlib.Path(self.env["TOLLGATE_CONNECTORS"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"fakeconn": {"on": true, "address": "https://u:%s@h.invalid"}}' % PW)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            connect.main(["status"], env=self.env)
        self.assertNotIn(PW, out.getvalue())


BAD_FILES = [
    "[]", "null", '"text"', "42", "{", "",
    '{"fakeconn": []}', '{"fakeconn": null}', '{"fakeconn": "str"}',
    '{"fakeconn": 5}',
    '{"fakeconn": {"on": true, "address": 5}}',
    '{"fakeconn": {"on": "yes", "address": "https://h.invalid"}}',
    '{"fakeconn": {"on": {"x": 1}}}',
    '{"fakeconn": {"on": true, "settings": "s"}}',
    '{"fakeconn": {"on": true, "settings": [1]}}',
    '{"fakeconn": {"on": true, "address": null, "settings": null}}',
]


class Q07MalformedFile(unittest.TestCase):
    def setUp(self):
        self.cm = throwaway_home()
        self.home, self.env = self.cm.__enter__()
        self.env = dict(self.env, TOLLGATE_NONINTERACTIVE="1")
        self.store = FakeSecretStore()
        registry.set_store(self.store)
        registry.set_http_factory(lambda: MockClient())

    def tearDown(self):
        registry.set_store(None)
        registry.set_http_factory(None)
        self.cm.__exit__(None, None, None)

    def _write(self, text):
        p = pathlib.Path(self.env["TOLLGATE_CONNECTORS"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def test_q07_no_traceback_for_any_malformed_file(self):
        for text in BAD_FILES:
            self._write(text)
            with self.subTest(file=text):
                registry.is_on("fakeconn", self.env)
                registry.get_settings("fakeconn", self.env)
                registry.set_settings("fakeconn", {"x": 1}, self.env)
                self._write(text)
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    connect.main(["status"], env=self.env)
                    connect.main(["status", "fakeconn"], env=self.env)
                    connect.main(["off", "fakeconn"], env=self.env)
                    self._write(text)
                    code = connect.main(["on", "fakeconn", "--address", "https://h.invalid",
                                         "--key-stdin"], stdin=io.StringIO("tgfake-key"),
                                        env=self.env)
                self.assertEqual(code, 0)

    def test_q07_wrong_typed_entry_reads_as_off(self):
        for text in ('{"fakeconn": "str"}', '{"fakeconn": {"on": "yes"}}',
                     '{"fakeconn": {"on": 1}}'):
            self._write(text)
            self.assertFalse(registry.is_on("fakeconn", self.env), text)


BAD_NAMES = ("my conn", "-bad", "a;b", 'a"b', "a$(x)", "../x", "", "UP", "slack\n")


class S5ConnectorName(unittest.TestCase):
    def setUp(self):
        self.cm = throwaway_home()
        self.home, self.env = self.cm.__enter__()
        self.env = dict(self.env, TOLLGATE_NONINTERACTIVE="1")
        self.store = FakeSecretStore()
        registry.set_store(self.store)
        self.calls = []

    def tearDown(self):
        registry.set_store(None)
        self.cm.__exit__(None, None, None)

    def _run(self, *a, **k):
        self.calls.append(a)
        raise AssertionError("security must not be called")

    def test_s5_keychain_store_refuses_bad_name_before_security(self):
        from connectors.secret_store import MacKeychainStore, SecretStoreError
        st = MacKeychainStore(run=self._run)
        for name in BAD_NAMES:
            for op in (lambda: st.set(name, "tgfake"), lambda: st.get(name),
                       lambda: st.delete(name)):
                with self.assertRaises(SecretStoreError):
                    op()
        self.assertEqual(self.calls, [])

    def test_s5_connect_on_and_off_refuse_bad_name_and_write_nothing(self):
        for name in ("my conn", "a;b", 'a"b'):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = connect.main(["on", name, "--address", "https://h.invalid",
                                     "--key-stdin"], stdin=io.StringIO("tgfake-key"),
                                    env=self.env)
                off = connect.main(["off", name], env=self.env)
            self.assertEqual((code, off), (1, 1), name)
            self.assertIn("connector name", err.getvalue())
        self.assertEqual(registry.load_state(self.env), {})

    def test_s5_plain_names_still_accepted(self):
        from connectors.secret_store import check_name
        for name in ("fakeconn", "databricks", "my-conn_2"):
            check_name(name)


if __name__ == "__main__":
    unittest.main()
