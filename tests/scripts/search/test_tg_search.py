"""
module_name: test_tg_search.py
description: Tests for scripts/search/tg-search: which script each tool name runs, argument and stdin
             pass-through, exit codes, the Python choice, and the bad-tool message. A fake python
             (a shell script named by TOLLGATE_PYTHON) records what it is given, so nothing real runs.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version.
"""
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
WRAPPER = ROOT / "scripts" / "search" / "tg-search"
SEARCH = ROOT / "scripts" / "search"
TOOLS = {"query": "query_index.py", "ground": "ground.py",
         "reference": "reference_query.py", "add": "reference_add.py", "health": "vault_health.py"}

FAKE_PY = """#!/bin/sh
{ echo "SCRIPT=$1"; shift; for a in "$@"; do echo "ARG=$a"; done; echo "STDIN=$(cat)"; } > "$FAKE_OUT"
exit "${FAKE_EXIT:-0}"
"""


class TgSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tg-search-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.fake = os.path.join(self.tmp, "fakepy")
        with open(self.fake, "w") as fh:
            fh.write(FAKE_PY)
        os.chmod(self.fake, os.stat(self.fake).st_mode | stat.S_IXUSR)
        self.out = os.path.join(self.tmp, "out.txt")

    def run_wrapper(self, *args, stdin="", exit_code=0, python=None, extra=None):
        env = {k: v for k, v in os.environ.items() if k not in ("TOLLGATE_PYTHON", "TOLLGATE_PATHS")}
        env.update({"TOLLGATE_PYTHON": python or self.fake, "FAKE_OUT": self.out,
                    "FAKE_EXIT": str(exit_code), "HOME": self.tmp})
        env.update(extra or {})
        return subprocess.run([str(WRAPPER), *args], input=stdin, capture_output=True, text=True,
                              env=env, timeout=30)

    def recorded(self):
        with open(self.out) as fh:
            return fh.read().splitlines()

    def test_each_tool_runs_its_script_next_to_the_wrapper(self):
        for tool, script in TOOLS.items():
            result = self.run_wrapper(tool)
            self.assertEqual(result.returncode, 0, tool)
            self.assertEqual(self.recorded()[0], "SCRIPT=%s" % (SEARCH / script), tool)

    def test_arguments_pass_through_unchanged(self):
        self.run_wrapper("query", "two words", "--top", "5", "")
        lines = self.recorded()
        self.assertEqual([l for l in lines if l.startswith("ARG=")],
                         ["ARG=two words", "ARG=--top", "ARG=5", "ARG="])

    def test_stdin_is_passed_through(self):
        self.run_wrapper("ground", stdin="a claim to check\n")
        self.assertIn("STDIN=a claim to check", self.recorded())

    def test_exit_code_is_preserved(self):
        for code in (0, 1, 3, 42):
            self.assertEqual(self.run_wrapper("health", exit_code=code).returncode, code)

    def test_unknown_tool_prints_usage_and_exits_2(self):
        result = self.run_wrapper("frobnicate")
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: tg-search", result.stderr)
        self.assertIn("frobnicate", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse(os.path.exists(self.out))

    def test_no_arguments_prints_usage_and_exits_2(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: tg-search", result.stderr)

    def test_script_name_is_not_accepted_as_a_tool(self):
        self.assertEqual(self.run_wrapper("query_index.py").returncode, 2)

    def test_works_from_another_folder(self):
        result = subprocess.run([str(WRAPPER), "query", "x"], cwd=self.tmp, input="", capture_output=True, text=True,
                                env={**os.environ, "TOLLGATE_PYTHON": self.fake, "FAKE_OUT": self.out},
                                timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.recorded()[0], "SCRIPT=%s" % (SEARCH / "query_index.py"))

    def test_python_falls_back_to_the_venv_then_python3(self):
        # TOLLGATE_PYTHON not executable: the wrapper must not use it. The venv lives in the state folder.
        state = os.path.join(self.tmp, "state")
        venv_bin = os.path.join(state, "venv", "bin")
        os.makedirs(venv_bin)
        shutil.copy(self.fake, os.path.join(venv_bin, "python3"))
        paths = os.path.join(self.tmp, "paths.yaml")
        with open(paths, "w") as fh:
            fh.write("state: %s\n" % state)
        result = self.run_wrapper("health", python=os.path.join(self.tmp, "missing"),
                                  extra={"TOLLGATE_PATHS": paths})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded()[0], "SCRIPT=%s" % (SEARCH / "vault_health.py"))

    def test_wrapper_is_executable_and_has_a_header(self):
        self.assertTrue(os.access(WRAPPER, os.X_OK))
        head = WRAPPER.read_text().splitlines()[:20]
        self.assertTrue(any(line.startswith("# Author:") for line in head))
        self.assertTrue(any("ChangeLog" in line for line in head))


if __name__ == "__main__":
    unittest.main()
