#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests that the Write/Edit and Bash guards protect Tollgate's own files, and that the
       gate override Bash guard catches names built from pieces
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Run: python3 -m unittest tests/hooks/test_self_protection.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(REPO, "hooks")
WRITE_GUARD = os.path.join(HOOKS, "pre-tool-write-guard-path.sh")
BASH_GUARD = os.path.join(HOOKS, "pre-tool-bash-guard-code-dir.py")
OVERRIDE_GUARD = os.path.join(HOOKS, "pre-tool-bash-guard-gate-override.py")
OVERRIDE = "over" + "ride"


def run(hook: str, stdin: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([hook], input=stdin, capture_output=True, text=True, env=env)


def is_deny(proc: subprocess.CompletedProcess) -> bool:
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    try:
        out = json.loads(proc.stdout)["hookSpecificOutput"]
    except (ValueError, KeyError):
        return False
    return out["permissionDecision"] == "deny"


class Home(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.realpath(self.tmp.name)
        self.repo = os.path.join(self.home, "tollgate-repo")
        os.makedirs(os.path.join(self.repo, "hooks"))
        os.makedirs(os.path.join(self.home, ".claude"))
        os.makedirs(os.path.join(self.home, ".tollgate", "state"))
        self.env = {**os.environ, "HOME": self.home, "TOLLGATE_HOME": self.repo}
        self.env.pop("TOLLGATE_CODE_DIR", None)

    def p(self, *parts: str) -> str:
        return os.path.join(self.home, *parts)


class WriteGuardProtectsOwnFiles(Home):
    def write(self, path: str, key: str = "file_path") -> subprocess.CompletedProcess:
        return run(WRITE_GUARD, json.dumps({"tool_name": "Write", "tool_input": {key: path}}), self.env)

    def test_protected_paths_are_denied(self) -> None:
        cases = [self.p(".claude", "settings.json"), self.p(".claude", "credentials.sh"),
                 self.p(".tollgate", "config.json"), self.p(".tollgate", "state", "a.log"),
                 self.p(".zshrc"), self.p(".bashrc"), self.p(".bash_profile"), self.p(".profile"),
                 os.path.join(self.repo, "hooks", "x.py"), os.path.join(self.repo, "settings.json"),
                 self.p(".ZSHRC"), self.p(".Claude", "Settings.JSON"), self.p(".TOLLGATE", "x")]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(is_deny(self.write(case)))

    def test_symlink_to_protected_file_is_denied(self) -> None:
        link = self.p("innocent.txt")
        os.symlink(self.p(".zshrc"), link)
        self.assertTrue(is_deny(self.write(link)))

    def test_notebook_path_is_checked(self) -> None:
        self.assertTrue(is_deny(self.write(self.p(".zshrc"), key="notebook_path")))

    def test_ordinary_paths_are_allowed(self) -> None:
        for case in [self.p("project", "notes.md"), self.p(".claude", "other.md"),
                     self.p(".tollgatefoo"), os.path.join(self.repo, "docs", "a.md")]:
            with self.subTest(case=case):
                proc = self.write(case)
                self.assertEqual(proc.returncode, 0)
                self.assertFalse(is_deny(proc))

    def test_missing_helper_blocks(self) -> None:
        lone = os.path.join(self.home, "lone-hooks")
        os.makedirs(lone)
        copy = os.path.join(lone, "pre-tool-write-guard-path.sh")
        shutil.copy(WRITE_GUARD, copy)
        proc = run(copy, json.dumps({"tool_input": {"file_path": self.p("a")}}), self.env)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("BLOCKED", proc.stderr)


class BashGuardProtectsOwnFiles(Home):
    def bash(self, command: str) -> subprocess.CompletedProcess:
        return run(BASH_GUARD, json.dumps({"tool_name": "Bash", "cwd": self.home,
                                           "tool_input": {"command": command}}), self.env)

    def test_write_commands_are_denied(self) -> None:
        h = self.home
        cases = [
            "echo x > %s/.zshrc" % h, "echo x >> ~/.bashrc", "echo x>$HOME/.profile",
            "echo x | tee %s/.claude/settings.json" % h, "cp /tmp/a %s/.claude/credentials.sh" % h,
            "mv /tmp/a ~/.bash_profile", "rm -rf ~/.tollgate", "rm %s/.tollgate/state/a" % h,
            "sed -i s/a/b/ ~/.zshrc", "sed -i.bak s/a/b/ $HOME/.zshrc",
            "echo x > $TOLLGATE_HOME/hooks/scrub_secrets.py", "touch %s/hooks/new.py" % self.repo,
            "cp /tmp/a ${TOLLGATE_HOME}/settings.json", "ln -s /tmp/a ~/.zshrc",
            "echo X > ~/.ZSHRC", "chmod 777 ~/.claude/credentials.sh",
            "python3 -c \"open('%s/.zshrc','w').write('x')\"" % h,
            "python3 -c \"open('x/.tollgate/config.json','a').write('x')\"",
            "node -e \"require('fs').writeFileSync(process.env.HOME+'/.bashrc','x')\"",
            "bash -c 'echo x > ~/.zshrc'", "cd ~ && echo x > .zshrc",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(is_deny(self.bash(case)), case)

    def test_reads_and_ordinary_commands_are_allowed(self) -> None:
        h = self.home
        cases = [
            "cat ~/.zshrc", "grep alias %s/.bashrc" % h, "ls -la ~/.tollgate", "cat %s/.claude/settings.json" % h,
            "cp ~/.zshrc /tmp/backup", "diff ~/.zshrc /tmp/a", "git status", "echo x > /tmp/x.txt",
            "python3 -c \"print(open('%s/.zshrc').read())\"" % h, "ls %s/hooks" % self.repo,
            "cat %s/hooks/scrub_secrets.py > /tmp/copy.py" % self.repo,
        ]
        for case in cases:
            with self.subTest(case=case):
                proc = self.bash(case)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stdout.strip(), "")

    def test_bad_payload_fails_closed(self) -> None:
        self.assertEqual(run(BASH_GUARD, "not json", self.env).returncode, 2)


class TollgateConfigFolderIsProtected(Home):
    """The installer's ~/.claude/tollgate folder and tollgate-config, and files named by env vars."""

    def write(self, path: str, env: dict) -> subprocess.CompletedProcess:
        return run(WRITE_GUARD, json.dumps({"tool_name": "Write", "tool_input": {"file_path": path}}), env)

    def bash(self, command: str, env: dict) -> subprocess.CompletedProcess:
        return run(BASH_GUARD, json.dumps({"tool_name": "Bash", "cwd": self.home,
                                           "tool_input": {"command": command}}), env)

    def test_write_and_redirect_to_config_paths_are_denied(self) -> None:
        for rel in (".claude/tollgate/connectors.yaml", ".claude/tollgate/paths.yaml", ".claude/tollgate-config"):
            with self.subTest(rel=rel):
                self.assertTrue(is_deny(self.write(self.p(*rel.split("/")), self.env)))
                self.assertTrue(is_deny(self.bash("echo x > %s/%s" % (self.home, rel), self.env)))

    def test_reads_stay_allowed(self) -> None:
        for rel in (".claude/tollgate/connectors.yaml", ".claude/tollgate-config"):
            proc = self.bash("cat %s/%s" % (self.home, rel), self.env)
            self.assertEqual((proc.returncode, proc.stdout.strip()), (0, ""))

    def test_env_named_files_are_protected(self) -> None:
        for var in ("TOLLGATE_CONNECTORS", "TOLLGATE_PATHS", "TOLLGATE_CONFIG"):
            target = self.p("elsewhere", var.lower() + ".yaml")
            env = {**self.env, var: target}
            with self.subTest(var=var):
                self.assertTrue(is_deny(self.write(target, env)))
                self.assertTrue(is_deny(self.write(target.upper(), env)))
                self.assertTrue(is_deny(self.bash("echo x >> " + target, env)))
                self.assertFalse(is_deny(self.write(self.p("elsewhere", "other.yaml"), env)))


class ChainedCommandsAreSplit(Home):
    """A protected write after any separator, including newline and CR, is denied."""

    def bash(self, command: str) -> subprocess.CompletedProcess:
        return run(BASH_GUARD, json.dumps({"tool_name": "Bash", "cwd": self.home,
                                           "tool_input": {"command": command}}), self.env)

    def test_each_separator_denies(self) -> None:
        rm = "rm $HOME/.zshrc"
        for sep in ("\n", "\r\n", "\r", ";", "&&", "||", "|", "&", ";\n"):
            with self.subTest(sep=repr(sep)):
                self.assertTrue(is_deny(self.bash("echo hi" + sep + rm)))
        for body in ("echo $(%s)", "echo `%s`", 'echo "$(%s)"', 'echo "`%s`"'):
            with self.subTest(body=body):
                self.assertTrue(is_deny(self.bash(body % rm)))

    def test_newline_applies_to_code_dir_too(self) -> None:
        code = self.p("code")
        os.makedirs(code)
        self.env["TOLLGATE_CODE_DIR"] = code
        self.assertTrue(is_deny(self.bash("echo hi\nrm %s/a.py" % code)))

    def test_quoted_newlines_and_plain_chains_are_allowed(self) -> None:
        for cmd in ("echo 'a\nrm ~/.zshrc'", 'echo "a\nb" > /tmp/x', "echo hi\nls\ncat ~/.zshrc",
                    "echo $(date) && echo `date`"):
            with self.subTest(cmd=cmd):
                proc = self.bash(cmd)
                self.assertEqual((proc.returncode, proc.stdout.strip()), (0, ""))


class OverrideNameTricks(unittest.TestCase):
    def check(self, command: str) -> subprocess.CompletedProcess:
        return run(OVERRIDE_GUARD, json.dumps({"tool_input": {"command": command}}), dict(os.environ))

    def test_built_names_are_denied(self) -> None:
        cases = [
            'cp a ./a-gate-"%s".md' % OVERRIDE,
            "cp a ./a-gate-'%s'.md" % OVERRIDE,
            "cp a ./a-\"gate\"-%s.md" % OVERRIDE,
            "X=%s; echo x > a-gate-$X.md" % OVERRIDE,
            "echo x > a-gate-${X}.md",
            "echo x > a-gate-$(echo %s).md" % OVERRIDE,
            "echo x > a-gate-`echo %s`.md" % OVERRIDE,
            "touch a-gate-{%s,x}.md" % OVERRIDE,
            "touch a-gate-overrid[e].md",
            "echo x > a-gate-*.md",
            "rm a-gate-ov*.md",
            "python3 -c \"open('a-gate-'+'%s.md','w')\"" % OVERRIDE,
            "python3 -c \"open('a-gate-'+'ov'+'erride.md','w').write('x')\"",
            "node -e \"require('fs').writeFileSync('a-gate-'+'%s.md','x')\"" % OVERRIDE,
            "perl -e 'open(F,\">a-gate-\".\"%s.md\")'" % OVERRIDE,
            "python3 <<EOF\nopen('a-gate-'+'%s.md','w')\nEOF" % OVERRIDE,
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(is_deny(self.check(case)), case)

    def test_normal_commands_are_allowed(self) -> None:
        cases = [
            "git log --oneline -5",
            "ls a-gate-%s.md" % OVERRIDE,
            "cat T-001-gate-%s.md" % OVERRIDE,
            "grep -r gate- docs",
            "ls a-gate-*.md",
            "echo \"gate-check passed\" > /tmp/out.txt",
            "python3 -c \"print('gate-check')\"",
            "rm /tmp/*.md",
        ]
        for case in cases:
            with self.subTest(case=case):
                proc = self.check(case)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
