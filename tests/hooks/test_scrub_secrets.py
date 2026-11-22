#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests for scrub_secrets.py (both modes), scrub_secrets.sh and the variable registry
ChangeLog:
  - Created.

Run: python3 -m unittest tests/hooks/test_scrub_secrets.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(REPO, "hooks")


def fake_github_token() -> str:
    return "gh" + "p_" + "A1b2C3d4E5" * 4


def fake_anthropic_key() -> str:
    return "sk-" + "ant-" + "api03-" + "Zz9Yy8Xx7W" * 3


def run(script: str, payload: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([os.path.join(HOOKS, script)], input=json.dumps(payload), capture_output=True,
                          text=True, env={**os.environ, **(env or {})})


def pre(tool: str, **tool_input: object) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}


class ScrubSecretsPre(unittest.TestCase):
    def decision(self, result: subprocess.CompletedProcess) -> dict | None:
        self.assertEqual(result.returncode, 0)
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)["hookSpecificOutput"]

    def test_HOK_02_deny_schema(self) -> None:
        out = self.decision(run("scrub_secrets.py", pre("Bash", command="echo " + fake_github_token())))
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertTrue(out["permissionDecisionReason"])

    def test_HOK_03_blocks_fake_key_written_to_file(self) -> None:
        cases = (
            ("Write", {"file_path": "/x/a.txt", "content": "key=" + fake_anthropic_key()}),
            ("Edit", {"file_path": "/x/a.txt", "new_string": fake_anthropic_key()}),
            ("MultiEdit", {"file_path": "/x/a.txt", "edits": [{"new_string": fake_anthropic_key()}]}),
        )
        for tool, args in cases:
            out = self.decision(run("scrub_secrets.py", pre(tool, **args)))
            self.assertEqual(out["permissionDecision"], "deny", tool)
            self.assertNotIn(fake_anthropic_key(), out["permissionDecisionReason"])

    def test_HOK_03_blocks_fake_key_in_command(self) -> None:
        out = self.decision(run("scrub_secrets.py", pre("Bash", command="curl -H 'x: " + fake_github_token() + "' host")))
        self.assertEqual(out["permissionDecision"], "deny")

    def test_blocks_literal_export_but_not_variable(self) -> None:
        bad = self.decision(run("scrub_secrets.py", pre("Bash", command="export MY_API_TOKEN=abcdefgh12345")))
        self.assertEqual(bad["permissionDecision"], "deny")
        self.assertIsNone(self.decision(run("scrub_secrets.py", pre("Bash", command="export MY_API_TOKEN=$(pass show x)"))))

    def test_allows_clean_write_and_command(self) -> None:
        self.assertIsNone(self.decision(run("scrub_secrets.py", pre("Write", file_path="/x/a.txt", content="hello"))))
        self.assertIsNone(self.decision(run("scrub_secrets.py", pre("Bash", command="ls -la"))))

    def test_bad_input_fails_closed(self) -> None:
        for raw in ("not json", "", "[]"):
            result = subprocess.run([os.path.join(HOOKS, "scrub_secrets.py")], input=raw, capture_output=True, text=True)
            self.assertEqual((result.returncode, result.stdout), (2, ""), raw)
            self.assertIn("fails closed", result.stderr)

    def test_registry_name_blocks_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = os.path.join(tmp, "reg.txt")
            with open(reg, "w") as fh:
                fh.write("EXAMPLE_DB_PASS  # comment\n")
            env = {"SCRUB_REGISTRY_PATH": reg}
            out = self.decision(run("scrub_secrets.py", pre("Bash", command="run EXAMPLE_DB_PASS=hunter2hunter2"), env))
            self.assertEqual(out["permissionDecision"], "deny")
            self.assertIsNone(self.decision(run("scrub_secrets.py", pre("Bash", command="run OTHER_NAME=hunter2hunter2"), env)))


class ScrubSecretsPost(unittest.TestCase):
    def post(self, tool: str, response: object) -> subprocess.CompletedProcess:
        return run("scrub_secrets.py", {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_response": response})

    def test_HOK_02_post_schema_and_redaction(self) -> None:
        token = fake_github_token()
        result = self.post("Bash", {"stdout": "found " + token, "stderr": ""})
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PostToolUse")
        self.assertIn("[REDACTED:GITHUB_TOKEN]", out["additionalContext"])
        self.assertNotIn(token, out["additionalContext"])

    def test_clean_output_is_silent(self) -> None:
        self.assertEqual(self.post("Bash", {"stdout": "all good"}).stdout, "")

    def test_denylisted_tool_is_silent(self) -> None:
        self.assertEqual(self.post("Write", {"stdout": fake_github_token()}).stdout, "")

    def test_shell_wrapper_runs_same_logic(self) -> None:
        result = run("scrub_secrets.sh", pre("Bash", command="echo " + fake_github_token()))
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
