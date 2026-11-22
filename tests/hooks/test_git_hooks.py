#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests for the git and PR guard hooks (git_commit_guard.sh, git_push_guard.sh,
       git_ask_before_run.py, co_authored_by_check.sh, guard_worktree_remove.sh,
       gh_pr_create_detect.py)
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Run: python3 -m unittest tests/hooks/test_git_hooks.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(REPO, "hooks")
ATTRIBUTION = "Co-Authored" + "-By: Example Bot <bot@example.invalid>"


def run(script: str, stdin: str, env: dict | None = None, cwd: str | None = None):
    base = {k: v for k, v in os.environ.items() if not k.startswith("TOLLGATE_")}
    return subprocess.run([os.path.join(HOOKS, script)], input=stdin, capture_output=True,
                          text=True, env={**base, **(env or {})}, cwd=cwd)


def bash_payload(command: str, cwd: str = ".") -> str:
    return json.dumps({"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}})


def decision(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)["hookSpecificOutput"]


def write_file(path: str, text: str) -> None:
    with open(path, "w") as handle:
        handle.write(text)


def git(repo: str, *args: str) -> None:
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})


class RepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "r")
        os.mkdir(self.repo)
        git(self.repo, "init", "-q", "-b", "main")
        write_file(os.path.join(self.repo, "a.txt"), "x")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "first")

    def tearDown(self) -> None:
        self.tmp.cleanup()


class SchemaTests(RepoCase):
    def test_HOK_02_commit_guard_returns_ask_schema(self) -> None:
        proc = run("git_commit_guard.sh", bash_payload('git commit -m "msg"', self.repo))
        self.assertEqual(proc.returncode, 0)
        out = decision(proc)
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("draft message: msg", out["permissionDecisionReason"])

    def test_HOK_02_push_guard_returns_ask_schema(self) -> None:
        proc = run("git_push_guard.sh", bash_payload("git push origin feature/x", self.repo))
        self.assertEqual(proc.returncode, 0)
        out = decision(proc)
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "ask")

    def test_HOK_02_guards_silent_on_other_commands(self) -> None:
        for script in ("git_commit_guard.sh", "git_push_guard.sh"):
            proc = run(script, bash_payload("git status", self.repo))
            self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def test_HOK_02_guards_fail_closed_on_bad_input(self) -> None:
        for script in ("git_commit_guard.sh", "git_push_guard.sh", "git_readonly_guard.sh",
                       "co_authored_by_check.sh", "guard_worktree_remove.sh"):
            for raw in ("not json", "", "[]"):
                proc = run(script, raw)
                self.assertEqual((proc.returncode, proc.stdout), (2, ""), (script, raw))
                self.assertNotEqual(proc.stderr.strip(), "", script)

    def test_HOK_02_co_author_returns_deny_schema(self) -> None:
        proc = run("co_authored_by_check.sh", bash_payload(f'git commit -m "x\n\n{ATTRIBUTION}"'))
        self.assertEqual(proc.returncode, 0)
        out = decision(proc)
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")

    def test_HOK_02_pr_detect_yes_no(self) -> None:
        def detect(cmd: str) -> str:
            return run("gh_pr_create_detect.py", cmd).stdout
        self.assertEqual(detect("gh pr " + "create --title x"), "yes")
        self.assertEqual(detect("bash -c 'gh pr " + "create'"), "yes")
        self.assertEqual(detect('git commit -m "run gh pr ' + 'create later"'), "no")
        self.assertEqual(detect("gh pr list"), "no")


class PushGuardTests(RepoCase):
    def push(self, command: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return run("git_push_guard.sh", bash_payload(command, self.repo), env=env)

    def test_HOK_04_push_to_protected_branch_denied(self) -> None:
        for cmd in ("git push origin main", "git push origin HEAD:main",
                    "git push origin feature:refs/heads/main", "git push -u origin main",
                    "git push", "git push --all origin"):
            out = decision(self.push(cmd))
            self.assertEqual(out["permissionDecision"], "deny", cmd)
            self.assertIn("pull request", out["permissionDecisionReason"])

    def test_HOK_04_push_to_feature_branch_asks(self) -> None:
        out = decision(self.push("git push origin feature/x"))
        self.assertEqual(out["permissionDecision"], "ask")

    def test_HOK_04_protected_list_is_configurable(self) -> None:
        env = {"TOLLGATE_PROTECTED_BRANCHES": "release trunk"}
        self.assertEqual(decision(self.push("git push origin trunk", env))["permissionDecision"], "deny")
        self.assertEqual(decision(self.push("git push origin main", env))["permissionDecision"], "ask")

    def test_HOK_04_override_turns_deny_into_ask(self) -> None:
        env = {"TOLLGATE_ALLOW_PROTECTED_PUSH": "1"}
        self.assertEqual(decision(self.push("git push origin main", env))["permissionDecision"], "ask")

    def test_HOK_04_force_flag_warned(self) -> None:
        out = decision(self.push("git push --force origin feature/x"))
        self.assertIn("FORCE PUSH FLAG", out["permissionDecisionReason"])

    def test_HOK_04_chained_push_ignores_later_segment(self) -> None:
        out = decision(self.push("git push origin feature/x && echo main"))
        self.assertEqual(out["permissionDecision"], "ask")


class CommitGuardTests(RepoCase):
    def test_HOK_04_commit_guard_asks_and_lists_staged_files(self) -> None:
        write_file(os.path.join(self.repo, "b.txt"), "y")
        git(self.repo, "add", "b.txt")
        out = decision(run("git_commit_guard.sh", bash_payload('git commit -m "add b"', self.repo)))
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("b.txt", out["permissionDecisionReason"])

    def test_HOK_04_commit_guard_handles_dash_c(self) -> None:
        out = decision(run("git_commit_guard.sh", bash_payload(f'git -C {self.repo} commit -m "z"', "/")))
        self.assertIn(self.repo, out["permissionDecisionReason"])


class CoAuthorTests(unittest.TestCase):
    def check(self, command: str) -> subprocess.CompletedProcess:
        return run("co_authored_by_check.sh", bash_payload(command))

    def test_HOK_04_co_author_line_blocked(self) -> None:
        self.assertEqual(decision(self.check(f'git commit -m "x\n\n{ATTRIBUTION}"'))["permissionDecision"], "deny")
        self.assertEqual(decision(self.check(f'git -C /r commit -m "{ATTRIBUTION.lower()}"'))["permissionDecision"], "deny")

    def test_HOK_04_clean_commit_allowed(self) -> None:
        proc = self.check('git commit -m "plain message"')
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def test_HOK_04_non_commit_with_phrase_allowed(self) -> None:
        proc = self.check(f'echo "{ATTRIBUTION}"')
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))


class WorktreeRemoveTests(RepoCase):
    def make_worktree(self, merged: bool) -> str:
        path = os.path.join(self.tmp.name, "wt")
        git(self.repo, "worktree", "add", "-q", "-b", "feat", path)
        if not merged:
            write_file(os.path.join(path, "n.txt"), "n")
            git(path, "add", "n.txt")
            git(path, "commit", "-q", "-m", "work")
        return path

    def test_HOK_04_unmerged_worktree_remove_denied(self) -> None:
        path = self.make_worktree(merged=False)
        proc = run("guard_worktree_remove.sh", bash_payload(f"git worktree remove {path}", self.repo))
        out = decision(proc)
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("not merged to main", out["permissionDecisionReason"])

    def test_HOK_04_merged_worktree_remove_allowed(self) -> None:
        path = self.make_worktree(merged=True)
        proc = run("guard_worktree_remove.sh", bash_payload(f"git worktree remove {path}", self.repo))
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def test_HOK_04_base_branch_follows_protected_list(self) -> None:
        path = self.make_worktree(merged=False)
        git(self.repo, "branch", "trunk")
        proc = run("guard_worktree_remove.sh", bash_payload(f"git worktree remove {path}", self.repo),
                   env={"TOLLGATE_PROTECTED_BRANCHES": "trunk"})
        self.assertIn("not merged to trunk", decision(proc)["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
