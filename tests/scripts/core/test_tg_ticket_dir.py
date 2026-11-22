"""
module_name: test_tg_ticket_dir.py
description: Tests for the tg_ticket_dir command.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial test.
"""
import os
import pathlib
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests" / "harness"))

from throwaway_home import throwaway_home  # noqa: E402

TG_TICKET_DIR = str(REPO / "scripts" / "core" / "tg_ticket_dir")


def run_cli(env, *args):
    return subprocess.run([sys.executable, "-B", TG_TICKET_DIR, *args],
                          capture_output=True, text=True, env=env)


def tickets_root(env):
    root = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
    root.mkdir(parents=True, exist_ok=True)
    return root


class TgTicketDirCli(unittest.TestCase):
    def test_prints_nested_folder(self):
        with throwaway_home() as (home, env):
            root = tickets_root(env)
            (root / "PROJ" / "PROJ-312").mkdir(parents=True)
            proc = run_cli(env, "PROJ-312")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(os.path.realpath(proc.stdout.strip()),
                             os.path.realpath(str(root / "PROJ" / "PROJ-312")))
            self.assertEqual(proc.stderr, "")

    def test_prints_flat_folder(self):
        with throwaway_home() as (home, env):
            root = tickets_root(env)
            (root / "T-1").mkdir()
            proc = run_cli(env, "T-1")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(os.path.realpath(proc.stdout.strip()),
                             os.path.realpath(str(root / "T-1")))

    def test_missing_ticket_exits_1_with_not_found(self):
        with throwaway_home() as (home, env):
            tickets_root(env)
            proc = run_cli(env, "PROJ-9")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not found", proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_bad_key_is_not_found(self):
        with throwaway_home() as (home, env):
            tickets_root(env)
            proc = run_cli(env, "../etc")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not found", proc.stderr)

    def test_not_set_up_exits_1(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_KNOWLEDGE")
            proc = run_cli(env, "PROJ-1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not set up", proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_usage_error_with_no_or_extra_arguments(self):
        with throwaway_home() as (home, env):
            for args in ((), ("PROJ-1", "PROJ-2")):
                proc = run_cli(env, *args)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("usage", proc.stderr)


if __name__ == "__main__":
    unittest.main()
