#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: the Python-too-old message in install.sh, and TOLLGATE_PYTHON in tests/hooks/run.sh and tests/e2e/run.sh
Ticket: none
ChangeLog:
  - Created.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def old_python_dir(tmp: str, minor: int = 11) -> str:
    """A folder holding a python3 that reports 3.<minor>."""
    folder = os.path.join(tmp, "oldpy")
    os.makedirs(folder)
    path = os.path.join(folder, "python3")
    with open(path, "w") as fh:
        fh.write(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then echo "Python 3.%d.0"; exit 0; fi\n'
            'if [ "$1" = "-c" ]; then\n'
            '  case "$2" in\n'
            "    *'sys.exit(0 if'*) exit 1 ;;\n"
            '    *) echo "3.%d"; exit 0 ;;\n'
            "  esac\n"
            "fi\nexit 1\n" % (minor, minor)
        )
    os.chmod(path, 0o755)
    return folder


class InstallerPythonMessage(unittest.TestCase):
    def test_message_is_os_neutral_and_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = os.path.join(tmp, "home")
            os.makedirs(home)
            env = {"HOME": home, "PATH": old_python_dir(tmp) + ":/usr/bin:/bin", "TERM": "dumb"}
            run = subprocess.run(["/bin/bash", os.path.join(REPO, "install.sh"), "--non-interactive"],
                                 env=env, capture_output=True, text=True)
        out = run.stdout + run.stderr
        self.assertEqual(1, run.returncode, out)
        self.assertIn("Tollgate needs Python 3.12 or newer, found 3.11", out)
        self.assertIn("python3 --version", out)
        self.assertRegex(out, r"first on (your )?PATH")
        self.assertIn("brew install python@3.12", out)
        self.assertRegex(out, r"Linux:")


class TestRunnersHonorTollgatePython(unittest.TestCase):
    def _header(self, rel: str) -> str:
        with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
            text = fh.read()
        m = re.search(r"# Python 3\.12 is the minimum\..*?\n(?=\w+=|\n)", text, re.S)
        self.assertIsNotNone(m, rel)
        return m.group(0)

    def _run(self, rel: str, extra_env: dict) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            folder = old_python_dir(tmp)
            env = {"PATH": "/usr/bin:/bin", **extra_env(folder)}
            script = self._header(rel) + '\necho "FIRST=$(command -v python3)"\n'
            run = subprocess.run(["/bin/bash", "-c", script], env=env, capture_output=True, text=True)
            return folder + "\n" + run.stdout + run.stderr

    def test_both_runners_prepend_the_folder_and_warn_when_old(self):
        for rel in ("tests/hooks/run.sh", "tests/e2e/run.sh"):
            out = self._run(rel, lambda f: {"TOLLGATE_PYTHON": os.path.join(f, "python3")})
            folder = out.splitlines()[0]
            self.assertIn("FIRST=" + os.path.join(folder, "python3"), out, rel)
            self.assertIn("older than 3.12", out, rel)


if __name__ == "__main__":
    unittest.main()
