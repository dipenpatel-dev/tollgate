#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests that the read-only git guard denies git diff --no-index and the implicit form
       (two paths outside the repo), and still allows ordinary git diff forms
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Run: python3 -m unittest tests/hooks/test_git_readonly_no_index.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(REPO, "hooks")


def run_guard(command: str, cwd: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}})
    return subprocess.run([os.path.join(HOOKS, "git_readonly_guard.sh")], input=payload,
                          capture_output=True, text=True, cwd=cwd)


def verdict(command: str, cwd: str) -> str:
    proc = run_guard(command, cwd)
    if proc.returncode != 0:
        return "exit%d" % proc.returncode
    if not proc.stdout.strip():
        return ""
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


class NoIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = os.path.join(cls.tmp.name, "repo")
        cls.outside = os.path.join(cls.tmp.name, "outside")
        os.makedirs(cls.repo)
        os.makedirs(cls.outside)
        subprocess.run(["git", "-C", cls.repo, "init", "-q"], check=True)
        with open(os.path.join(cls.repo, "a.txt"), "w", encoding="utf-8") as fh:
            fh.write("one\n")
        with open(os.path.join(cls.outside, "note.txt"), "w", encoding="utf-8") as fh:
            fh.write("synthetic\n")
        cls.note = os.path.join(cls.outside, "note.txt")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_no_index_flag_is_denied(self) -> None:
        for command in ("git diff --no-index /dev/null %s" % self.note,
                        "git diff --no-index=1 /dev/null x",
                        "git diff --no-in /dev/null x",
                        "git diff --no-inde /dev/null x",
                        "git diff --stat --no-index a b",
                        "git -C %s diff --no-index /dev/null x" % self.repo,
                        "sh -c 'git diff --no-index /dev/null x'",
                        "echo hi && git diff --no-index /dev/null x"):
            self.assertEqual(verdict(command, self.repo), "deny", command)

    def test_two_paths_outside_the_repo_are_denied(self) -> None:
        for command in ("git diff /dev/null %s" % self.note,
                        "git diff %s %s" % (self.note, self.note),
                        "git diff ~/.ssh/id_x ~/.ssh/id_y",
                        "git diff $HOME/.env /dev/null",
                        "git diff -- /dev/null %s" % self.note):
            self.assertEqual(verdict(command, self.repo), "deny", command)

    def test_outside_a_repo_two_paths_are_denied(self) -> None:
        self.assertEqual(verdict("git diff a b", self.outside), "deny")

    def test_ordinary_diff_stays_allowed(self) -> None:
        for command in ("git diff", "git diff --stat", "git diff HEAD~1", "git diff --cached --name-only",
                        "git diff HEAD~1 HEAD", "git diff main..feature", "git diff -- a.txt",
                        "git diff HEAD -- a.txt", "git diff a.txt a.txt", "git diff --no-color",
                        "git diff --no-prefix", "git diff --no-renames", "git diff %s" % self.note,
                        "git log --no-merges", "git status"):
            self.assertEqual(verdict(command, self.repo), "", command)

    def test_unreadable_payload_still_blocks(self) -> None:
        proc = subprocess.run([os.path.join(HOOKS, "git_readonly_guard.sh")], input="not json",
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
