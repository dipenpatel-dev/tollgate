#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests for the review security fixes: the git read guard and permission list, the git
       commit and push command parser, the secret command guard additions, the Plane key shape in
       the secret scanners, fail closed shell hooks, the Skill matcher and onFailure wiring.
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Run: python3 -m unittest tests/hooks/test_security_fixes.py
All keys here are obviously fake and are built at run time so no real shape sits in the source.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(REPO, "hooks")
sys.path.insert(0, HOOKS)

import git_ask_before_run as gar  # noqa: E402


def run(script: str, stdin: str, env: dict | None = None, cwd: str | None = None):
    base = {k: v for k, v in os.environ.items() if not k.startswith("TOLLGATE_")}
    return subprocess.run([os.path.join(HOOKS, script)], input=stdin, capture_output=True,
                          text=True, env={**base, **(env or {})}, cwd=cwd)


def bash_payload(command: str, cwd: str = ".") -> str:
    return json.dumps({"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}})


def decision(proc: subprocess.CompletedProcess) -> str:
    if not proc.stdout.strip():
        return ""
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def fake_plane_key() -> str:
    return "plane_" + "api_" + "FAKEFAKEFAKEFAKEFAKE12345"


def fake_json_member(name: str = "api_key") -> str:
    return '{"%s": "%s"}' % (name, "FAKE" * 6)


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
        with open(os.path.join(self.repo, "a.txt"), "w") as handle:
            handle.write("x")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "first")

    def tearDown(self) -> None:
        self.tmp.cleanup()


class PushParserTests(RepoCase):
    """Each form that used to slip past the push guard is now seen (item 7)."""

    FORMS = (
        "git -c k=v push origin main",
        "git --no-pager push origin main",
        "git -C {repo} push origin main",
        "git --git-dir={repo}/.git --work-tree={repo} push origin main",
        "/usr/bin/git push origin main",
        "env git push origin main",
        "env -u FOO A=1 git push origin main",
        "(git push origin main)",
        "sh -c 'git push origin main'",
        "bash -c \"cd /tmp && git push origin main\"",
        "bash -lc 'git push origin main'",
        "VAR=1 git push origin main",
        "A=1 B=2 /usr/bin/git -c k=v push origin main",
        "echo hi; git push origin main",
        "true && git push origin main",
        "echo $(git push origin main)",
        "echo \"$(git push origin main)\"",
        "sudo git push origin main",
        "eval 'git push origin main'",
        "{ git push origin main; }",
        "time git push origin main",
        "nohup git push origin main",
        "env -S \"git push origin main\"",
        "env --split-string=\"git push origin main\"",
        "env -S 'git push origin main'",
        "env -i -S 'git push origin main'",
    )

    def push(self, command: str, env: dict | None = None):
        return run("git_push_guard.sh", bash_payload(command, self.repo), env=env)

    def test_every_form_is_denied_on_a_protected_branch(self) -> None:
        for form in self.FORMS:
            command = form.replace("{repo}", self.repo)
            self.assertEqual(decision(self.push(command)), "deny", command)

    def test_every_form_asks_on_a_feature_branch(self) -> None:
        for form in self.FORMS:
            command = form.replace("{repo}", self.repo).replace("origin main", "origin feature/x")
            self.assertEqual(decision(self.push(command)), "ask", command)

    def test_not_a_push_is_ignored(self) -> None:
        for command in ("git status", "echo git push", "echo 'git push origin main'",
                        "git -c k=v status", "git log --oneline", "cat push", "gitpush"):
            self.assertEqual(self.push(command).stdout, "", command)

    def test_unbalanced_quote_still_detects_push(self) -> None:
        self.assertEqual(decision(self.push("git push origin main 'oops")), "deny")

    def test_dash_c_path_sets_the_repo(self) -> None:
        calls = gar.git_calls(f"git -c a=b -C {self.repo} push origin x")
        self.assertEqual((calls[0].verb, calls[0].repo, calls[0].configs), ("push", self.repo, ["a=b"]))

    def test_commit_guard_sees_the_same_forms(self) -> None:
        for command in ("git -c k=v commit -m x", "env git commit -m x", "/usr/bin/git commit -m x",
                        "(git commit -m x)", "sh -c 'git commit -m x'", "VAR=1 git commit -m x"):
            proc = run("git_commit_guard.sh", bash_payload(command, self.repo))
            self.assertEqual(decision(proc), "ask", command)

    def test_co_author_check_sees_the_same_forms(self) -> None:
        line = "Co-Authored" + "-By: Bot <bot@example.invalid>"
        for command in ("git -c k=v commit -m '%s'" % line, "env git commit -m '%s'" % line,
                        "/usr/bin/git commit -m '%s'" % line, "sh -c \"git commit -m '%s'\"" % line):
            proc = run("co_authored_by_check.sh", bash_payload(command))
            self.assertEqual(decision(proc), "deny", command)


class ReadonlyGuardTests(unittest.TestCase):
    """The auto-approved git read commands cannot run code or write a file (item 1)."""

    def verdict(self, command: str) -> str:
        return decision(run("git_readonly_guard.sh", bash_payload(command)))

    def test_denied_forms(self) -> None:
        for command in (
            "git diff --output=/tmp/x",
            "git diff --output /tmp/x",
            "git log -p --output=/tmp/x",
            "git show --output=/tmp/x HEAD",
            "git diff --ext-diff",
            "git log --ext-diff -p",
            "git -c core.fsmonitor=/tmp/x status",
            "git -c diff.external=/tmp/x diff",
            "git --config-env=core.pager=EVIL log",
            "git config core.fsmonitor /tmp/x",
            "git config --global core.pager /tmp/x",
            "git config core.sshCommand 'sh -c x'",
            "git config diff.external /tmp/x",
            "git config diff.evil.textconv /tmp/x",
            "git config alias.st '!sh -c x'",
            "git config --add core.hooksPath /tmp/hooks",
            "git config set core.fsmonitor /tmp/x",
            "git config --local --replace-all core.editor /tmp/x",
            "env git -c core.pager=/tmp/x log",
            "sh -c 'git diff --output=/tmp/x'",
            "echo hi && git diff --output=/tmp/x",
        ):
            self.assertEqual(self.verdict(command), "deny", command)

    def test_allowed_forms(self) -> None:
        for command in (
            "git status", "git status --porcelain", "git log --oneline -5", "git diff", "git diff --stat HEAD~1",
            "git diff --cached --name-only", "git show HEAD --stat", "git config --get user.name",
            "git config user.name", "git config --list", "git config -l", "git config --get-regexp remote",
            "git config --get-all remote.origin.url", "git config get user.name", "git config list",
            "git -C /r log --oneline", "git config user.email 'me@example.invalid'",
            "git commit -m 'x'", "echo git diff --output=/tmp/x",
        ):
            self.assertEqual(self.verdict(command), "", command)

    def test_more_program_running_keys_are_denied(self) -> None:
        for key in ("difftool.x.cmd", "difftool.x.path", "mergetool.x.cmd", "mergetool.x.path",
                    "browser.x.cmd", "browser.x.path", "web.browser", "man.x.cmd", "man.x.path",
                    "interactive.diffFilter", "trailer.x.cmd", "trailer.x.command",
                    "core.alternateRefsCommand", "sequence.editor", "core.editor", "gpg.program",
                    "gpg.x.program"):
            self.assertEqual(self.verdict("git config %s /tmp/x" % key), "deny", key)

    def test_config_write_key_classifier(self) -> None:
        self.assertIsNone(gar.config_write_key(["--get", "a.b"]))
        self.assertIsNone(gar.config_write_key(["a.b"]))
        self.assertEqual(gar.config_write_key(["a.b", "v"]), "a.b")
        self.assertEqual(gar.config_write_key(["--unset", "a.b"]), "a.b")
        self.assertEqual(gar.config_write_key(["set", "a.b", "v"]), "a.b")
        self.assertIsNone(gar.config_write_key(["--file", "f", "--get", "a.b"]))

    def test_unreadable_payload_exits_2(self) -> None:
        self.assertEqual(run("git_readonly_guard.sh", "not json").returncode, 2)


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        with open(os.path.join(REPO, "settings.json"), encoding="utf-8") as handle:
            self.settings = json.load(handle)

    def test_git_config_is_not_blanket_approved(self) -> None:
        allow = self.settings["permissions"]["allow"]
        self.assertNotIn("Bash(git config:*)", allow)
        for rule in allow:
            if rule.startswith("Bash(git config"):
                self.assertTrue(any(flag in rule for flag in ("--get", "--list", " -l")), rule)

    def test_every_pre_tool_and_expansion_entry_sets_on_failure_block(self) -> None:
        for event in ("PreToolUse", "UserPromptExpansion"):
            for group in self.settings["hooks"][event]:
                for hook in group["hooks"]:
                    self.assertEqual(hook.get("onFailure"), "block", (event, hook["command"]))

    def test_no_matcher_names_multiedit(self) -> None:
        for event, groups in self.settings["hooks"].items():
            for group in groups:
                self.assertNotIn("MultiEdit", group.get("matcher", ""), event)

    def test_skill_matcher_runs_the_gate(self) -> None:
        groups = [g for g in self.settings["hooks"]["PreToolUse"] if g.get("matcher") == "Skill"]
        self.assertEqual(len(groups), 1)
        command = groups[0]["hooks"][0]["command"]
        self.assertIn("pre-prompt-expansion-check-gates.py", command)
        self.assertEqual(groups[0]["hooks"][0]["onFailure"], "block")

    def test_readonly_guard_is_wired(self) -> None:
        commands = [h["command"] for g in self.settings["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertTrue(any("git_readonly_guard.sh" in c for c in commands))


class SecretCommandGuardTests(unittest.TestCase):
    def verdict(self, command: str) -> int:
        return run("secret-command-guard.sh", bash_payload(command)).returncode

    def test_new_blocks(self) -> None:
        cred = "." + "aws/credentials"
        for command in (
            "security find-generic-password -s svc -g",
            "security find-generic-password -a me -s svc -w",
            "security find-internet-password -s host -wa me",
            "security dump-keychain",
            "security dump-keychain -d login.keychain",
            "cat ~/" + cred,
            "less ~/.netrc",
            "grep key ~/.netrc",
            "head -3 ~/.databrickscfg",
            "cat /proc/self/environ",
            "tr '\\0' '\\n' < /proc/self/environ",
            "python3 -c \"print(open('/home/u/" + cred + "').read())\"",
            "env",
            "/usr/bin/env",
            "env | sort",
            "/usr/bin/env | sort",
            "cd x && /usr/bin/env",
            "printenv",
            "/usr/bin/printenv HOME",
        ):
            self.assertEqual(self.verdict(command), 2, command)

    def test_still_allowed(self) -> None:
        for command in (
            "ls ~/.aws", "ls -la ~/.netrc", "env FOO=1 make", "/usr/bin/env python3 x.py",
            "security find-generic-password -s svc", "security list-keychains",
            "git status", "echo $HOME", "cat README.md",
        ):
            self.assertEqual(self.verdict(command), 0, command)

    def test_bad_payload_blocks(self) -> None:
        for raw in ("not json", "", "[]"):
            proc = run("secret-command-guard.sh", raw)
            self.assertEqual(proc.returncode, 2, raw)
            self.assertIn("could not read", proc.stderr)

    def test_readable_payload_without_command_is_allowed(self) -> None:
        self.assertEqual(run("secret-command-guard.sh", json.dumps({"tool_input": {}})).returncode, 0)
        self.assertEqual(run("secret-command-guard.sh", json.dumps({})).returncode, 0)

    def test_documented_as_a_speed_bump(self) -> None:
        with open(os.path.join(HOOKS, "secret-command-guard.sh"), encoding="utf-8") as handle:
            self.assertIn("SPEED BUMP", handle.read())


class ShellHooksFailClosed(unittest.TestCase):
    def test_bad_payload_blocks(self) -> None:
        for script in ("pre-tool-write-guard-path.sh", "co_authored_by_check.sh", "guard_worktree_remove.sh",
                       "secret-command-guard.sh"):
            for raw in ("not json", "", "[]"):
                proc = run(script, raw)
                self.assertEqual(proc.returncode, 2, (script, raw))

    def test_write_guard_allows_a_readable_payload_without_a_path(self) -> None:
        proc = run("pre-tool-write-guard-path.sh", json.dumps({"tool_input": {}}),
                   env={"TOLLGATE_CODE_DIR": "/nonexistent-code-dir"})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_python_policy_hooks_block_on_bad_payload(self) -> None:
        for script in ("pre-tool-bash-databricks-ask.py", "pre-tool-bash-guard-gate-override.py",
                       "pre_tool_write_scan_claims.py", "pre_tool_write_vault_frontmatter.py"):
            proc = run(script, "not json", env={"TOLLGATE_KNOWLEDGE": "/nonexistent-vault"})
            self.assertEqual(proc.returncode, 2, script)


class PlaneKeyShapeTests(unittest.TestCase):
    def pre(self, **tool_input) -> subprocess.CompletedProcess:
        tool = "Bash" if "command" in tool_input else "Write"
        return run("scrub_secrets.py", json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool,
                                                    "tool_input": tool_input}))

    def labels(self, proc: subprocess.CompletedProcess) -> str:
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertNotIn(fake_plane_key(), proc.stdout)
        return out["permissionDecisionReason"]

    def test_scrub_secrets_denies_plane_key_in_a_command_and_in_a_write(self) -> None:
        self.assertIn("PLANE_KEY", self.labels(self.pre(command="curl -H 'X-Api-Key: %s' x" % fake_plane_key())))
        self.assertIn("PLANE_KEY", self.labels(self.pre(file_path="/x/a.txt", content="k=" + fake_plane_key())))

    def test_scrub_secrets_denies_json_quoted_members(self) -> None:
        for name in ("api_key", "token", "secret", "API_KEY"):
            self.assertIn("JSON_CREDENTIAL", self.labels(self.pre(file_path="/x/a.json", content=fake_json_member(name))), name)

    def test_short_or_placeholder_values_are_not_flagged(self) -> None:
        for content in ('{"api_key": "short"}', '{"token": "<your token here>"}', '{"name": "' + "FAKE" * 6 + '"}',
                        "plane_api_ is the prefix", 'plane_api_key = os.environ["X"]'):
            self.assertEqual(self.pre(file_path="/x/a.json", content=content).stdout, "", content)

    def test_post_scrub_redacts_plane_key_and_json_member(self) -> None:
        for text in ("out: " + fake_plane_key(), fake_json_member()):
            payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_response": {"stdout": text}}
            proc = run("scrub_secrets.py", json.dumps(payload))
            context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("[REDACTED:", context)
            self.assertNotIn("FAKEFAKE", context)

    def test_post_tool_bash_scan_secrets_redacts_both_shapes(self) -> None:
        for text, label in (("out: " + fake_plane_key(), "PLANE_KEY"), (fake_json_member(), "JSON_CREDENTIAL")):
            payload = {"tool_name": "Bash", "tool_response": {"stdout": text}}
            proc = run("post-tool-bash-scan-secrets.py", json.dumps(payload))
            context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("[REDACTED:" + label + "]", context)

    def test_pre_commit_secrets_blocks_both_shapes(self) -> None:
        for text in ("k = " + fake_plane_key(), fake_json_member("token")):
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(["git", "init", "-q", "-b", "main", tmp], check=True, capture_output=True)
                with open(os.path.join(tmp, "f.txt"), "w") as handle:
                    handle.write(text + "\n")
                git(tmp, "add", "f.txt")
                proc = subprocess.run(["bash", os.path.join(HOOKS, "pre-commit-secrets")], cwd=tmp,
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1, text)

    def test_pre_commit_secrets_blocks_a_line_starting_with_plus_plus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", "-b", "main", tmp], check=True, capture_output=True)
            with open(os.path.join(tmp, "f.txt"), "w") as handle:
                handle.write("++TOKEN=" + fake_plane_key() + "\n")
            git(tmp, "add", "f.txt")
            proc = subprocess.run(["bash", os.path.join(HOOKS, "pre-commit-secrets")], cwd=tmp,
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stdout)

    def _staged_hook_exit(self, text: str) -> "subprocess.CompletedProcess[str]":
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", "-b", "main", tmp], check=True, capture_output=True)
            with open(os.path.join(tmp, "f.txt"), "w") as handle:
                handle.write(text + "\n")
            git(tmp, "add", "f.txt")
            return subprocess.run(["bash", os.path.join(HOOKS, "pre-commit-secrets")], cwd=tmp,
                                  capture_output=True, text=True)

    def test_pre_commit_secrets_blocks_a_private_key_header(self) -> None:
        # The pattern starts with dashes; without grep -e, BSD grep read it as an option and the check never ran.
        header = "-" * 5 + "BEGIN RSA " + "PRIVATE KEY" + "-" * 5
        proc = self._staged_hook_exit(header)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_pre_commit_secrets_blocks_an_added_line_that_looks_like_a_file_header(self) -> None:
        proc = self._staged_hook_exit("++ b/TOKEN=" + fake_plane_key())
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_pre_commit_secrets_allows_the_hook_file_itself(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", "-b", "main", tmp], check=True, capture_output=True)
            with open(os.path.join(HOOKS, "pre-commit-secrets"), encoding="utf-8") as src:
                with open(os.path.join(tmp, "hook.sh"), "w") as dst:
                    dst.write(src.read())
            git(tmp, "add", "hook.sh")
            proc = subprocess.run(["bash", os.path.join(HOOKS, "pre-commit-secrets")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout)


class PrePushRiskDocumented(unittest.TestCase):
    def test_header_and_docs_name_the_risk(self) -> None:
        with open(os.path.join(HOOKS, "git-pre-push"), encoding="utf-8") as handle:
            header = handle.read().split("set -uo pipefail")[0]
        self.assertIn("RISK", header)
        self.assertIn("bash -c", header)
        with open(os.path.join(REPO, "docs", "hooks.md"), encoding="utf-8") as handle:
            self.assertIn("TOLLGATE_PRE_PUSH_CMD", handle.read())


if __name__ == "__main__":
    unittest.main()
