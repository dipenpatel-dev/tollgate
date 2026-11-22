#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests for the vault frontmatter hook, the vault doc standard check, the claim hook
ChangeLog:
  - Removed the ValidateForWrite tests (hook dropped).
  - Created.

Run: python3 -m unittest tests/hooks/test_vault_hooks.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(REPO, "hooks")
GOOD_FM = "---\nstatus: ACTIVE\ntype: ticket_spec\n---\nBody\n"
BAD_FM = "---\nstatus: active\n---\nBody\n"


def run(script: str, stdin: str, env: dict | None = None, args: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([os.path.join(HOOKS, script)] + (args or []), input=stdin, capture_output=True,
                          text=True, env={**os.environ, **(env or {})})


def write(path: str, content: str) -> str:
    return json.dumps({"tool_name": "Write", "tool_input": {"file_path": path, "content": content}})


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = os.path.join(os.path.realpath(self.tmp.name), "vault")
        os.makedirs(self.vault)
        self.env = {"TOLLGATE_KNOWLEDGE": self.vault}

    def tearDown(self) -> None:
        self.tmp.cleanup()


class VaultFrontmatter(Base):
    def test_HOK_02_block_schema(self) -> None:
        result = run("pre_tool_write_vault_frontmatter.py", write(os.path.join(self.vault, "a.md"), BAD_FM), self.env)
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        self.assertIn("ALL_CAPS", out["permissionDecisionReason"])

    def test_allow_good_frontmatter(self) -> None:
        result = run("pre_tool_write_vault_frontmatter.py", write(os.path.join(self.vault, "a.md"), GOOD_FM), self.env)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_outside_vault_and_unset_variable_allow(self) -> None:
        outside = os.path.join(self.tmp.name, "other.md")
        self.assertEqual(run("pre_tool_write_vault_frontmatter.py", write(outside, BAD_FM), self.env).stdout, "")
        unset = {"TOLLGATE_KNOWLEDGE": ""}
        self.assertEqual(run("pre_tool_write_vault_frontmatter.py", write(os.path.join(self.vault, "a.md"), BAD_FM), unset).stdout, "")

    def test_empty_string_sentinel_blocked(self) -> None:
        content = "---\nowner: \"\"\n---\nx\n"
        result = run("pre_tool_write_vault_frontmatter.py", write(os.path.join(self.vault, "a.md"), content), self.env)
        self.assertIn("deny", result.stdout)


class ClaimHook(Base):
    def test_HOK_02_block_schema(self) -> None:
        result = run("pre_tool_write_scan_claims.py", write("/x/n.md", "The job is DONE.\n"))
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        self.assertIn("line 1", out["permissionDecisionReason"])

    def test_allow_cited_claim_and_non_markdown(self) -> None:
        self.assertEqual(run("pre_tool_write_scan_claims.py", write("/x/n.md", "DONE (source: ci run)\n")).stdout, "")
        self.assertEqual(run("pre_tool_write_scan_claims.py", write("/x/n.py", "DONE = 1\n")).stdout, "")

    def test_fenced_code_is_not_scanned(self) -> None:
        self.assertEqual(run("pre_tool_write_scan_claims.py", write("/x/n.md", "```\nDONE\n```\n")).stdout, "")


class VaultDocStandard(Base):
    def post(self, path: str) -> subprocess.CompletedProcess:
        return run("vault_doc_standard_check.sh", json.dumps({"tool_name": "Write", "tool_input": {"file_path": path}}), self.env)

    def test_HOK_02_missing_frontmatter_reminder_schema(self) -> None:
        path = os.path.join(self.vault, "a.md")
        Path(path).write_text("no frontmatter\n")
        out = json.loads(self.post(path).stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PostToolUse")
        self.assertIn("no YAML frontmatter", out["additionalContext"])

    def test_complete_frontmatter_is_silent(self) -> None:
        path = os.path.join(self.vault, "b.md")
        Path(path).write_text("---\ndoc_type: note\nstatus: ACTIVE\ndate: 2026-01-01\nlast_updated: 2026-01-01\ntags: []\nlinks: []\n---\nx\n")
        self.assertEqual(self.post(path).stdout, "")

    def test_incomplete_names_missing_field_and_outside_is_silent(self) -> None:
        path = os.path.join(self.vault, "c.md")
        Path(path).write_text("---\nstatus: ACTIVE\n---\nx\n")
        self.assertIn("doc_type", json.loads(self.post(path).stdout)["hookSpecificOutput"]["additionalContext"])
        outside = os.path.join(self.tmp.name, "o.md")
        Path(outside).write_text("plain\n")
        self.assertEqual(self.post(outside).stdout, "")


if __name__ == "__main__":
    unittest.main()
