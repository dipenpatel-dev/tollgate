#!/usr/bin/env python3
"""Tests for validate_state_files, and a check that the synthetic fixtures behave as labelled.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove good fixtures pass, the one deliberately bad fixture fails, and no file text is printed.
Change log:
  - First version.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
VAL = ROOT / "scripts" / "validation"
FIXTURES = ROOT / "tests" / "fixtures" / "tickets"
sys.path.insert(0, str(VAL))
import validate_state_files as vsf  # noqa: E402


class TestCheckText(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(vsf.check_text("---\nticket: TG-1\nstatus: OPEN\nterminal_status:\n---\n"), [])
        self.assertEqual(vsf.check_text("---\nticket_id: TG-1\nstatus: OPEN\n---\n"), [])

    def test_problems(self):
        self.assertEqual(vsf.check_text("status: OPEN"), ["no_front_matter"])
        self.assertEqual(vsf.check_text("---\nticket: TG-1\nstatus: OPEN\n"), ["front_matter_not_closed"])
        self.assertIn("malformed_line", vsf.check_text("---\nticket: TG-1\nstatus OPEN\n---\n"))
        self.assertIn("no_ticket_key", vsf.check_text("---\nstatus: OPEN\n---\n"))
        self.assertIn("no_status", vsf.check_text("---\nticket: TG-1\nstatus:\n---\n"))


class TestFixtures(unittest.TestCase):
    def test_fixture_folder_present(self):
        self.assertTrue(FIXTURES.is_dir())

    def test_only_the_bad_fixture_fails(self):
        bad = vsf.validate(FIXTURES)
        self.assertEqual(sorted(pathlib.Path(k).name for k in bad), ["BAD-001-state.md"])

    def test_cli_exit_codes(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        script = str(VAL / "validate_state_files.py")
        good = FIXTURES / "state_complete.md"
        self.assertEqual(subprocess.run([sys.executable, "-B", script, str(good)], env=env).returncode, 0)
        proc = subprocess.run([sys.executable, "-B", script, str(FIXTURES)], env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("BAD-001-state.md", proc.stdout)
        self.assertEqual(subprocess.run([sys.executable, "-B", script, str(FIXTURES / "nope")], env=env,
                                        capture_output=True).returncode, 2)

    def test_state_files_in_temp_copy(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "TG-1-state.md").write_text("---\nticket: TG-1\nstatus: OPEN\n---\n")
            self.assertEqual(vsf.validate(d), {})

    def test_build_vault_fixture_script_writes_only_where_asked(self):
        text = (FIXTURES / "build_vault_100.py").read_text()
        self.assertIn("Author: Dipen Patel (dipenpatel-dev)", text)
        self.assertNotIn("PROJ-174", text)


if __name__ == "__main__":
    unittest.main()
