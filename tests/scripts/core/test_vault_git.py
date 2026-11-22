"""
module_name: test_vault_git.py
description: Tests for vault_git_mode and the tg_vault_git command.
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
sys.path.insert(0, str(REPO / "scripts"))

from throwaway_home import throwaway_home  # noqa: E402
from core import paths  # noqa: E402

TG_VAULT_GIT = str(REPO / "scripts" / "core" / "tg_vault_git")


def git(env, *args):
    full = dict(env)
    full.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    subprocess.run(["git", *args], check=True, capture_output=True, env=full)


def write_paths(env, text):
    pathlib.Path(env["TOLLGATE_PATHS"]).write_text(text)


def cli(env):
    return subprocess.run([sys.executable, "-B", TG_VAULT_GIT], capture_output=True, text=True, env=env)


class VaultGitMode(unittest.TestCase):
    def test_saved_value_wins_for_each_mode(self):
        with throwaway_home() as (home, env):
            for mode in ("none", "local", "remote"):
                write_paths(env, "vault_git: %s\n" % mode)
                self.assertEqual(paths.vault_git_mode(env), mode)

    def test_saved_value_wins_over_detection(self):
        with throwaway_home() as (home, env):
            git(env, "init", env["TOLLGATE_KNOWLEDGE"])
            write_paths(env, "vault_git: none\n")
            self.assertEqual(paths.vault_git_mode(env), "none")

    def test_missing_line_no_git_is_none(self):
        with throwaway_home() as (home, env):
            write_paths(env, "references: /x\n")
            self.assertEqual(paths.vault_git_mode(env), "none")

    def test_missing_line_git_without_remote_is_local(self):
        with throwaway_home() as (home, env):
            git(env, "init", env["TOLLGATE_KNOWLEDGE"])
            self.assertEqual(paths.vault_git_mode(env), "local")

    def test_missing_line_git_with_remote_is_remote(self):
        with throwaway_home() as (home, env):
            vault = env["TOLLGATE_KNOWLEDGE"]
            git(env, "init", vault)
            git(env, "-C", vault, "remote", "add", "origin", "https://example.invalid/v.git")
            self.assertEqual(paths.vault_git_mode(env), "remote")

    def test_bad_value_is_detected(self):
        with throwaway_home() as (home, env):
            vault = env["TOLLGATE_KNOWLEDGE"]
            write_paths(env, "vault_git: sometimes\n")
            self.assertEqual(paths.vault_git_mode(env), "none")
            git(env, "init", vault)
            self.assertEqual(paths.vault_git_mode(env), "local")

    def test_no_vault_raises(self):
        env = {"TOLLGATE_PATHS": "/nonexistent/paths.yaml"}
        with self.assertRaises(paths.NotSetUp):
            paths.vault_git_mode(env)


class VaultGitCli(unittest.TestCase):
    def test_prints_each_saved_mode(self):
        with throwaway_home() as (home, env):
            for mode in ("none", "local", "remote"):
                write_paths(env, "vault_git: %s\n" % mode)
                done = cli(env)
                self.assertEqual((done.returncode, done.stdout.strip()), (0, mode))

    def test_detects_when_line_missing(self):
        with throwaway_home() as (home, env):
            self.assertEqual(cli(env).stdout.strip(), "none")
            git(env, "init", env["TOLLGATE_KNOWLEDGE"])
            self.assertEqual(cli(env).stdout.strip(), "local")

    def test_bad_value_is_detected(self):
        with throwaway_home() as (home, env):
            write_paths(env, "vault_git: nope\n")
            self.assertEqual(cli(env).stdout.strip(), "none")

    def test_not_set_up_exits_1(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_KNOWLEDGE")
            done = cli(env)
            self.assertEqual(done.returncode, 1)
            self.assertIn("not set up", done.stderr)

    def test_extra_argument_exits_2(self):
        with throwaway_home() as (home, env):
            done = subprocess.run([sys.executable, "-B", TG_VAULT_GIT, "x"], capture_output=True, text=True, env=env)
            self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
