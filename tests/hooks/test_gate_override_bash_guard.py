#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: tests for hooks/pre-tool-bash-guard-gate-override.py
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Run: python3 -m unittest tests/hooks/test_gate_override_bash_guard.py
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOK = os.path.join(REPO, "hooks", "pre-tool-bash-guard-gate-override.py")
P = "$TOLLGATE_KNOWLEDGE/02-tickets/T-001/T-001-gate-override.md"


def run(stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run([HOOK], input=stdin, capture_output=True, text=True)


def cmd(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def denied(proc: subprocess.CompletedProcess) -> bool:
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"] == "deny" and out["hookEventName"] == "PreToolUse"


class GateOverrideBashGuard(unittest.TestCase):
    def test_write_commands_are_denied(self):
        cases = [
            'echo "Override: arch 2026-01-01 x" > ' + P,
            'echo "Override: arch 2026-01-01 x" >> ' + P,
            "printf 'Override: arch 2026-01-01 x' | tee " + P,
            "cp /tmp/a " + P,
            "mv /tmp/a " + P,
            "dd if=/tmp/a of=" + P,
            "install -m 644 /tmp/a " + P,
            "ln -s /tmp/a " + P,
            "touch " + P,
            "truncate -s 0 " + P,
            "sed -i s/a/b/ " + P,
            "python3 -c \"open('T-001-gate-override.md','w').write('x')\"",
            "cd d && echo hi>T-001-gate-override.md",
            "cat /tmp/a >T-001-gate-override.md",
            "rm " + P,
            "printf x > T-001-GATE-OVERRIDE.MD",
            "echo x > t-001-Gate-Override.md",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(denied(run(cmd(case))))

    def test_reads_are_allowed(self):
        cases = [
            "cat " + P,
            "ls " + P,
            "grep Override " + P,
            "head -n 3 " + P,
            "cat " + P + " 2>&1",
            "cat " + P + " 2>/dev/null",
            "ls -la $TOLLGATE_KNOWLEDGE/02-tickets/T-001/",
        ]
        for case in cases:
            with self.subTest(case=case):
                proc = run(cmd(case))
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout.strip(), "")

    def test_unrelated_commands_with_write_verbs_are_allowed(self):
        for case in ["echo hello > /tmp/x.txt", "cp a b", "python3 -c 'print(1)'", "git status"]:
            with self.subTest(case=case):
                self.assertEqual(run(cmd(case)).stdout.strip(), "")

    def test_unreadable_payload_fails_closed(self):
        for bad in ["", "not json", "[]"]:
            with self.subTest(bad=bad):
                proc = run(bad)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("fails closed", proc.stderr)

    def test_readable_payload_without_a_command_is_allowed(self):
        for bad in [json.dumps({"tool_input": None}),
                    json.dumps({"tool_input": {"command": 5}}), json.dumps({})]:
            with self.subTest(bad=bad):
                proc = run(bad)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout.strip(), "")

    def test_deny_shape_matches_other_bash_hooks(self):
        out = json.loads(run(cmd("echo x > T-001-gate-override.md")).stdout)
        self.assertEqual(set(out), {"hookSpecificOutput"})
        self.assertEqual(set(out["hookSpecificOutput"]),
                         {"hookEventName", "permissionDecision", "permissionDecisionReason"})


if __name__ == "__main__":
    unittest.main()
