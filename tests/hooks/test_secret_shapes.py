#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests that the secret scanners catch the shapes added after the first release, in all four
       places that hold patterns (scrub_secrets.py both modes, scrub_text, post-tool-bash-scan-secrets.py,
       pre-commit-secrets), and that ordinary text is left alone
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Run: python3 tests/hooks/test_secret_shapes.py
Every secret-shaped string is built by concatenation at run time, so none sits in the source.
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

import scrub_secrets  # noqa: E402

A = "Ab1Cd2Ef3G"  # ten characters of mixed filler


def fakes() -> dict[str, str]:
    """label -> a synthetic value of that shape."""
    return {
        "AWS_ACCESS_KEY": "KEY_" + "AK" + "IA" + "ABCDEFGH12345678",
        "OPENAI_KEY": "sk-" + "proj-" + A * 3,
        "STRIPE_KEY": "sk_" + "live_" + A * 2,
        "STRIPE_RK": "rk_" + "live_" + A * 2,
        "GOOGLE_API_KEY": "AI" + "za" + "Sy" + A * 3 + "abc",
        "NPM_TOKEN": "npm" + "_" + A * 3 + "abcdef",
        "HUGGINGFACE_TOKEN": "hf" + "_" + A * 3 + "abcd",
        "GITLAB_TOKEN": "gl" + "pat-" + A * 2,
        "SENDGRID_KEY": "S" + "G." + A + A + "." + A + A,
        "JWT": "ey" + "Jhbgci" + A + "." + "ey" + "Jzdwi" + A + "." + A + "sig",
        "URL_CREDENTIAL": "postgres" + "://" + "appuser" + ":" + "hunter22xyz" + "@" + "db.example.invalid/x",
        "SLACK_WEBHOOK": "https://" + "hooks.slack" + ".com/services/" + "T0" + "AAAAAAA/B0" + "BBBBBBB/" + A * 2,
        "CURL_CREDENTIAL": "curl -u " + "appuser" + ":" + "hunter22xyz" + " https://x.example.invalid",
        "BEARER_TOKEN": "curl -H 'Authorization: Bear" + "er " + A * 3 + "1' https://x.example.invalid",
    }


def run(script: str, payload: object) -> subprocess.CompletedProcess:
    return subprocess.run([os.path.join(HOOKS, script)], input=json.dumps(payload), capture_output=True, text=True)


def pre(tool: str, **tool_input: object) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}


def deny_text(proc: subprocess.CompletedProcess) -> str:
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return ""
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    return out["permissionDecisionReason"]


class PreScanShapes(unittest.TestCase):
    def test_each_shape_is_denied_in_a_bash_command(self) -> None:
        for label, value in fakes().items():
            command = value if value.startswith("curl") else "echo " + value
            reason = deny_text(run("scrub_secrets.py", pre("Bash", command=command)))
            self.assertTrue(reason, label)
            self.assertNotIn(value, reason, label)

    def test_each_shape_is_denied_in_a_file_write(self) -> None:
        for label, value in fakes().items():
            self.assertTrue(deny_text(run("scrub_secrets.py", pre("Write", file_path="/x/a.txt", content="v: " + value))), label)

    def test_label_names(self) -> None:
        for label, value in fakes().items():
            want = "STRIPE_KEY" if label == "STRIPE_RK" else label
            reason = deny_text(run("scrub_secrets.py", pre("Write", file_path="/x/a.txt", content="v: " + value)))
            self.assertIn(want, reason, label)

    def test_aws_key_after_an_underscore_is_caught(self) -> None:
        self.assertIn("AWS_ACCESS_KEY", deny_text(run("scrub_secrets.py", pre("Bash", command="export X=" + fakes()["AWS_ACCESS_KEY"]))))

    def test_assignment_in_written_text(self) -> None:
        for content in ('password = "' + "hunter22xyz" + '"', "db_token: '" + "abcd1234efgh" + "'",
                        '{"api_key": "' + "abcd1234efgh" + '"}', 'SECRET = "' + "s3cr3t-value-1" + '"'):
            reason = deny_text(run("scrub_secrets.py", pre("Write", file_path="/x/a.py", content=content)))
            self.assertIn("ASSIGNED_SECRET", reason, content)

    def test_zero_width_and_fullwidth_tricks_are_normalised(self) -> None:
        value = fakes()["STRIPE_KEY"]
        zero = value[:4] + "​" + value[4:]
        self.assertTrue(deny_text(run("scrub_secrets.py", pre("Bash", command="echo " + zero))))
        full = "".join(chr(ord(c) + 0xFEE0) if c == "_" else c for c in value)
        self.assertTrue(deny_text(run("scrub_secrets.py", pre("Bash", command="echo " + full))))

    def test_ordinary_text_is_allowed(self) -> None:
        for content in ('password = os.environ["X"]', 'password = "<your password>"', 'token = "${TOKEN}"',
                        'password = "changeme-please"', 'token_url = "https://example.invalid/oauth"',
                        "the key_name is sk-short", "see https://example.invalid/a:b/c", "git@github.com:me/repo.git",
                        "https://user:$PASS@host.example.invalid/x", "Authorization: Bearer <token>",
                        "curl -u $USER:$PASS https://x.example.invalid", "eyJ is a prefix",
                        "max_tokens = 4096", "postgres://user:pass@host.example.invalid/db", "sec" + 'ret = "UNIQUE_BODY' + '_TEXT_12345"',
                        'ANTHROPIC_KEY = "your-key-goes-here-ok"', 'secret_name = "db"', "ASSIGNED passwords are stored elsewhere"):
            self.assertEqual(deny_text(run("scrub_secrets.py", pre("Write", file_path="/x/a.md", content=content))), "", content)
        for command in ("git log --oneline", "ls -la", "curl https://example.invalid/api", "echo hello"):
            self.assertEqual(deny_text(run("scrub_secrets.py", pre("Bash", command=command))), "", command)

    def test_assignment_pattern_does_not_apply_to_commands(self) -> None:
        command = 'python3 -c "password = \\"' + "hunter22xyz" + '\\""'
        self.assertEqual(deny_text(run("scrub_secrets.py", pre("Bash", command=command))), "")

    def test_bad_payload_blocks(self) -> None:
        proc = subprocess.run([os.path.join(HOOKS, "scrub_secrets.py")], input="not json", capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


class PostAndHelperShapes(unittest.TestCase):
    def test_scrub_text_redacts_each_shape(self) -> None:
        for label, value in fakes().items():
            text, labels = scrub_secrets.scrub_text("out: " + value + " end")
            self.assertTrue(labels, label)
            self.assertIn("[REDACTED:", text, label)
            self.assertNotIn("hunter22xyz" if value.startswith("curl") else value, text, label)

    def test_scrub_text_keeps_placeholders_and_clean_text(self) -> None:
        for text in ("a [REDACTED:ANTHROPIC_KEY] b", "nothing here", "café ​ ok"):
            out, labels = scrub_secrets.scrub_text(text)
            self.assertEqual((out, labels), (text, []))

    def test_post_hooks_redact_each_shape(self) -> None:
        for script in ("scrub_secrets.py", "post-tool-bash-scan-secrets.py"):
            for label, value in fakes().items():
                payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_response": {"stdout": "out: " + value}}
                proc = run(script, payload)
                self.assertEqual(proc.returncode, 0, (script, label))
                context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
                self.assertIn("[REDACTED:", context, (script, label))

    def test_post_hook_catches_zero_width_split_key(self) -> None:
        value = fakes()["NPM_TOKEN"]
        payload = {"tool_name": "Bash", "tool_response": {"stdout": value[:6] + "‍" + value[6:]}}
        proc = run("post-tool-bash-scan-secrets.py", payload)
        self.assertIn("NPM_TOKEN", json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_post_hook_leaves_clean_output_alone(self) -> None:
        proc = run("post-tool-bash-scan-secrets.py", {"tool_name": "Bash", "tool_response": {"stdout": "all good\n"}})
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def test_post_hook_bad_payload_blocks(self) -> None:
        proc = subprocess.run([os.path.join(HOOKS, "post-tool-bash-scan-secrets.py")], input="x", capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


class PreCommitShapes(unittest.TestCase):
    def commit_status(self, text: str) -> int:
        with tempfile.TemporaryDirectory() as repo:
            env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
            subprocess.run(["git", "-C", repo, "init", "-q"], check=True, env=env)
            with open(os.path.join(repo, "f.txt"), "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            subprocess.run(["git", "-C", repo, "add", "f.txt"], check=True, env=env)
            return subprocess.run(["bash", os.path.join(HOOKS, "pre-commit-secrets")], cwd=repo, env=env,
                                  capture_output=True, text=True).returncode

    def test_blocks_each_added_shape(self) -> None:
        for label, value in fakes().items():
            if label in ("CURL_CREDENTIAL", "BEARER_TOKEN"):
                continue  # command shapes: the hook scans staged file text for value shapes only
            self.assertEqual(self.commit_status("v = " + value), 1, label)

    def test_allows_plain_text(self) -> None:
        for text in ("hello world", "https://user:$PASS@host.example.invalid/x", "git@github.com:me/repo.git",
                     "postgres://user:pass@host.example.invalid/db"):
            self.assertEqual(self.commit_status(text), 0, text)


if __name__ == "__main__":
    unittest.main()
