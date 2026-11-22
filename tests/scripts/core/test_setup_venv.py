"""
module_name: test_setup_venv.py
description: Tests the Python version check in setup_venv.sh (minimum 3.12).
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial test.
"""
import os
import pathlib
import stat
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
SETUP_VENV = str(REPO / "scripts" / "core" / "setup_venv.sh")


def fake_python(folder, minor):
    """A base python that reports 3.<minor> for -c checks and fails `-m venv`."""
    path = pathlib.Path(folder) / "fakepy"
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-c" ]; then\n'
        "  case \"$2\" in\n"
        "    *print*) echo 3.%d; exit 0 ;;\n" % minor
        + "    *) [ %d -ge 12 ] && exit 0 || exit 1 ;;\n" % minor
        + "  esac\n"
        "fi\n"
        'echo "$@" >> "$0.calls"\n'
        "exit 7\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


class SetupVenvVersionCheck(unittest.TestCase):
    def run_script(self, minor, extra=(), premade=False):
        with tempfile.TemporaryDirectory() as tmp:
            venv = os.path.join(tmp, "venv")
            marker = os.path.join(venv, "marker.txt")
            if premade:
                os.makedirs(venv)
                pathlib.Path(marker).write_text("keep me")
            fake = fake_python(tmp, minor)
            env = dict(os.environ, TOLLGATE_BASE_PYTHON=fake, PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run(["bash", SETUP_VENV, "--venv", venv, *extra],
                                    capture_output=True, text=True, env=env)
            calls_file = pathlib.Path(fake + ".calls")
            calls = calls_file.read_text() if calls_file.exists() else ""
            return result, os.path.exists(venv), os.path.exists(marker), calls

    def test_old_python_is_refused_before_anything_is_made(self):
        result, made, _, calls = self.run_script(11)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Tollgate needs Python 3.12 or newer, found 3.11", result.stderr)
        self.assertFalse(made)
        self.assertEqual(calls, "")

    def test_python_312_reaches_venv_creation(self):
        result, _, _, calls = self.run_script(12)
        self.assertNotIn("Tollgate needs Python", result.stderr)
        self.assertIn("creating venv", result.stdout)
        self.assertIn("-m venv", calls)             # the fake python was asked to build the venv
        self.assertNotEqual(result.returncode, 0)   # and it cannot, so the script stops there

    def test_force_with_old_python_deletes_nothing(self):
        result, made, marker_kept, calls = self.run_script(11, extra=("--force",), premade=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Tollgate needs Python 3.12 or newer, found 3.11", result.stderr)
        self.assertTrue(made)
        self.assertTrue(marker_kept)                # the check runs before rm -rf
        self.assertEqual(calls, "")


if __name__ == "__main__":
    unittest.main()
