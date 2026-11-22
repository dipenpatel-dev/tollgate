#!/usr/bin/env python3
"""secrets_tool tests: no value ever reaches stdout, stderr, a file or an argument list.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove list shows names only, set never echoes, a missing secret store
         refuses with no plain-file fallback, and cleanup needs --confirm.
Change log:
  - First version. Ideas from the old keychain test: round trip, empty value, missing entry.
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
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from connector_helpers import FakeSecretStore
from throwaway_home import throwaway_home
from connectors import registry, secret_store
from connectors.data import secrets_tool as st

TOOL = ROOT / "scripts" / "connectors" / "data" / "secrets_tool.py"


class Base(unittest.TestCase):
    def setUp(self):
        self.cm = throwaway_home()
        self.home, self.env = self.cm.__enter__()
        self._old = os.environ.copy()
        os.environ.update(self.env)
        self.store = FakeSecretStore()
        registry.set_store(self.store)
        self.value = "tgfake-" + uuid.uuid4().hex

    def tearDown(self):
        registry.set_store(None)
        os.environ.clear()
        os.environ.update(self._old)
        self.cm.__exit__(None, None, None)

    def run_tool(self, argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = st.main(argv, stdin=io.StringIO(stdin), env=self.env)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def set_it(self, name="alpha"):
        return self.run_tool(["set", name, "--stdin"], self.value + "\n")


class TestTool(Base):
    def test_set_stores_value_and_prints_no_value(self):
        code, out, err = self.set_it()
        self.assertEqual(code, 0)
        self.assertEqual(self.store.get("alpha"), self.value)
        self.assertNotIn(self.value, out + err)
        self.assertIn("alpha: saved", out)

    def test_list_names_only(self):
        self.set_it("alpha")
        self.set_it("beta")
        code, out, err = self.run_tool(["list"])
        self.assertEqual(code, 0)
        self.assertEqual(out.split(), ["alpha", "beta"])
        self.assertNotIn(self.value, out + err)

    def test_no_value_in_any_file(self):
        self.set_it()
        needle = self.value.encode()
        for root in (ROOT, pathlib.Path(self.home)):
            for dp, dn, fn in os.walk(root):
                dn[:] = [d for d in dn if d != ".git"]
                for f in fn:
                    try:
                        with open(os.path.join(dp, f), "rb") as fh:
                            self.assertNotIn(needle, fh.read(), f)
                    except OSError:
                        pass
        idx = st._index_path(self.env)
        self.assertTrue(idx.exists())
        self.assertIn("alpha", idx.read_text())

    def test_value_cannot_be_an_argument(self):
        code, out, err = self.run_tool(["set", "alpha", self.value])
        self.assertEqual(code, 2)
        self.assertNotIn(self.value, out + err)
        self.assertIsNone(self.store.get("alpha"))

    def test_value_reaches_store_not_argv(self):
        calls = []

        def run(argv, **kw):
            calls.append((argv, kw))
            return subprocess.CompletedProcess(argv, 0, "", "")
        registry.set_store(secret_store.SecretToolStore(run=run))
        self.assertEqual(self.set_it()[0], 0)
        argv, kw = calls[0]
        self.assertNotIn(self.value, " ".join(argv))
        self.assertEqual(kw["input"], self.value)

    def test_empty_value_refused(self):
        code, _, err = self.run_tool(["set", "alpha", "--stdin"], "\n")
        self.assertEqual(code, 1)
        self.assertIn("empty", err)
        self.assertEqual(self.store.stored_names(), [])

    def test_no_terminal_without_stdin_flag_refuses(self):
        code, _, err = self.run_tool(["set", "alpha"])
        self.assertEqual(code, 1)
        self.assertIn("--stdin", err)

    def test_bad_name_refused(self):
        for bad in ("a b", "a/b", "", "x" * 65):
            code, _, _ = self.run_tool(["set", bad, "--stdin"], "v\n") if bad else (1, "", "")
            self.assertEqual(code, 1)

    def test_delete(self):
        self.set_it()
        code, out, _ = self.run_tool(["delete", "alpha"])
        self.assertEqual(code, 0)
        self.assertIsNone(self.store.get("alpha"))
        self.assertNotIn("alpha", self.run_tool(["list"])[1].split())

    def test_cleanup_needs_confirm(self):
        self.set_it("a1")
        self.set_it("a2")
        code, out, _ = self.run_tool(["cleanup", "a1", "a2"])
        self.assertEqual(code, 1)
        self.assertEqual(self.store.stored_names(), ["a1", "a2"])
        self.assertIn("would delete", out)
        code, out, _ = self.run_tool(["cleanup", "a1", "--confirm"])
        self.assertEqual(code, 0)
        self.assertEqual(self.store.stored_names(), ["a2"])

    def test_cleanup_deletes_only_named(self):
        self.set_it("keep")
        self.set_it("drop")
        self.run_tool(["cleanup", "drop", "--confirm"])
        self.assertEqual(self.store.stored_names(), ["keep"])
        self.assertEqual(self.run_tool(["list"])[1].split(), ["keep"])

    def test_connector_key_names_are_protected(self):
        registry.save_state({"fakeconn": {"address": "https://x.invalid", "on": True}}, self.env)
        self.store.set("fakeconn", "x")
        for argv in (["delete", "fakeconn"], ["cleanup", "fakeconn", "--confirm"]):
            code, _, err = self.run_tool(argv)
            self.assertEqual(code, 1)
            self.assertIn("connect.py", err)
        self.assertEqual(self.store.get("fakeconn"), "x")


class TestNoStore(Base):
    def test_every_command_refuses_in_process(self):
        registry.set_store(secret_store.RefusingStore())
        for argv in (["list"], ["set", "a", "--stdin"], ["delete", "a"],
                     ["cleanup", "a", "--confirm"]):
            code, out, err = self.run_tool(argv, self.value + "\n")
            self.assertEqual(code, 1, argv)
            self.assertIn("plain file", err)
            self.assertNotIn(self.value, out + err)
        self.assertFalse(st._index_path(self.env).exists())

    def test_subprocess_with_no_tools_refuses_and_writes_nothing(self):
        env = dict(self.env, PATH="")
        r = subprocess.run([sys.executable, "-B", str(TOOL), "set", "a", "--stdin"],
                           input=self.value + "\n", env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no secret store", r.stderr)
        self.assertNotIn(self.value, r.stdout + r.stderr)
        self.assertFalse(st._index_path(self.env).exists())


if __name__ == "__main__":
    unittest.main()
