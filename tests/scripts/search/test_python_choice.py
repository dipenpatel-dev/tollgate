"""
module_name: test_python_choice.py
description: Which python rebuild.sh and nightly_index.sh run: TOLLGATE_PYTHON, then the state folder venv, then python3.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version.
"""
import os
import pathlib
import stat
import subprocess
import unittest

import support
from support import throwaway_home, write

CRON = support.ROOT / "scripts" / "cron" / "nightly_index.sh"
REBUILD = support.SEARCH / "rebuild.sh"


def stub(path, tag):
    """A fake python that prints which stub it is and exits 0."""
    write(path, f"#!/bin/sh\necho STUB-{tag}\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


class PythonChoice(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, self.env = self._home.__enter__()
        self.state = pathlib.Path(self.env["TOLLGATE_STATE_DIR"])
        self.env["PATH"] = "/usr/bin:/bin"

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def rebuild(self):
        return subprocess.run(["bash", str(REBUILD)], capture_output=True, text=True, env=self.env, timeout=60)

    def nightly_log(self):
        proc = subprocess.run(["bash", str(CRON), "--skip-index"], capture_output=True, text=True,
                              env=self.env, timeout=120)
        logs = list((pathlib.Path(self.home) / ".tollgate" / "logs" / "nightly").glob("*.log"))
        self.assertTrue(logs, proc.stdout + proc.stderr)
        return logs[0].read_text()

    def test_rebuild_prefers_tollgate_python(self):
        stub(self.state / "venv" / "bin" / "python3", "venv")
        self.env["TOLLGATE_PYTHON"] = str(stub(pathlib.Path(self.home) / "mine", "env"))
        self.assertEqual(self.rebuild().stdout.strip(), "STUB-env")

    def test_rebuild_uses_the_venv_when_no_variable(self):
        stub(self.state / "venv" / "bin" / "python3", "venv")
        proc = self.rebuild()
        self.assertEqual(proc.stdout.strip(), "STUB-venv")
        self.assertNotIn("no venv", proc.stderr)

    def test_rebuild_falls_back_to_python3_and_says_so(self):
        # the real python3 runs build_index.py here; only the log line matters
        self.assertIn("no venv found", self.rebuild().stderr)

    def test_nightly_prefers_tollgate_python(self):
        stub(self.state / "venv" / "bin" / "python3", "venv")
        self.env["TOLLGATE_PYTHON"] = str(stub(pathlib.Path(self.home) / "mine", "env"))
        text = self.nightly_log()
        self.assertIn("STUB-env", text)
        self.assertNotIn("STUB-venv", text)

    def test_nightly_uses_the_venv_when_no_variable(self):
        stub(self.state / "venv" / "bin" / "python3", "venv")
        text = self.nightly_log()
        self.assertIn("STUB-venv", text)
        self.assertNotIn("no venv found", text)

    def test_nightly_logs_a_line_when_there_is_no_venv(self):
        self.assertIn("no venv found", self.nightly_log())


if __name__ == "__main__":
    unittest.main()
