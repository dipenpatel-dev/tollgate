"""Gate tests GAT-01 to GAT-04 for the Status line gate.

Scope: runs the real gate hook and the real write guard as subprocesses against
a throwaway vault in a temp dir. Status lines are written by hand in the
fixtures, because the commands that write them are built separately. Fake
ticket T-001 only, no real data.
Ticket: n/a

ChangeLog:
  - Fixed tg- names: GAT-04 now checks tg-arch is gated, a leftover TOLLGATE_SKILL_PREFIX is ignored and
    bare or other-prefix names are not gated.
  - Initial version: GAT-01 arch gate, GAT-02 full chain, GAT-03 override file
    rules, GAT-04 the fixed tg- command names.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import tempfile
import unittest
from typing import Dict, Optional

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(TESTS_DIR, "..", ".."))
HOOK = os.path.join(REPO, "hooks", "pre-prompt-expansion-check-gates.py")
WRITE_GUARD = os.path.join(REPO, "hooks", "pre-tool-write-guard-path.sh")
KEY = "T-001"
TIMEOUT_SECONDS = 30
TODAY = datetime.date.today()
COMMAND_PREFIX = "tg-"


def command(skill: str) -> str:
    return COMMAND_PREFIX + skill


def payload(name: str, args: str = KEY) -> str:
    return json.dumps({
        "command_name": name,
        "command_args": args,
        "command_source": "user",
        "cwd": "/tmp/example",
        "expansion_type": "slash_command",
        "hook_event_name": "UserPromptExpansion",
        "prompt": "/{0} {1}".format(name, args),
    })


class GateVault(unittest.TestCase):
    """A throwaway vault under a throwaway home, with a helper to run the hook."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.join(self._tmp.name, "home")
        self.vault = os.path.join(self._tmp.name, "vault")
        self.ticket_dir = os.path.join(self.vault, "02-tickets", KEY)
        os.makedirs(self.ticket_dir)
        os.makedirs(self.home)
        self.log = os.path.join(self.home, "gate.log")

    def put(self, suffix: str, text: str) -> str:
        path = os.path.join(self.ticket_dir, "{0}-{1}.md".format(KEY, suffix))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def set_status(self, suffix: str, status: str) -> None:
        self.put(suffix, "# {0} {1}\nStatus: {2}\n".format(KEY, suffix, status))

    def gate(self, skill: str, name: Optional[str] = None, **extra_env: str):
        """Run the hook for `tg-<skill>`, or for the exact command `name`. extra_env adds env values."""
        env = {k: v for k, v in os.environ.items() if k != "TOLLGATE_SKILL_PREFIX"}
        env.update({"HOME": self.home, "TOLLGATE_KNOWLEDGE": self.vault, "TOLLGATE_HOME": str(REPO),
                    "TOLLGATE_GATE_LOG": self.log})
        env.update(extra_env)
        return subprocess.run([HOOK], input=payload(name or command(skill)), capture_output=True, text=True,
                              env=env, timeout=TIMEOUT_SECONDS)

    def log_text(self) -> str:
        with open(self.log, encoding="utf-8") as handle:
            return handle.read()

    def is_blocked(self, result: subprocess.CompletedProcess) -> bool:
        self.assertEqual(result.returncode, 0)
        if not result.stdout.strip():
            return False
        self.assertEqual(json.loads(result.stdout)["decision"], "block")
        return True


class GAT01ArchNeedsSpecStatus(GateVault):
    def test_gat_01_arch_blocked_without_spec_status_allowed_with_it(self) -> None:
        self.set_status("state", "SPEC_APPROVED")
        self.put("spec", "# spec\nno status line here\n")
        result = self.gate("arch")
        self.assertTrue(self.is_blocked(result))
        self.assertIn("spec.md", json.loads(result.stdout)["reason"])
        self.put("spec", "# spec\nStatus: APPROVED\n")
        self.assertFalse(self.is_blocked(self.gate("arch")))

    def test_gat_01b_missing_spec_file_blocks(self) -> None:
        self.set_status("state", "SPEC_APPROVED")
        self.assertTrue(self.is_blocked(self.gate("arch")))

    def test_gat_01c_old_dated_approval_line_does_not_open_the_gate(self) -> None:
        self.set_status("state", "SPEC_APPROVED")
        self.put("spec", "# spec\nApproved - {0}\n".format(TODAY.isoformat()))
        self.assertTrue(self.is_blocked(self.gate("arch")))


class GAT02FullChain(GateVault):
    def test_gat_02_spec_arch_dev_qa_end_to_end(self) -> None:
        # Entry point: spec is never gated.
        self.set_status("state", "ROUTED")
        self.assertFalse(self.is_blocked(self.gate("spec")))
        # arch is blocked until the spec is approved.
        self.assertTrue(self.is_blocked(self.gate("arch")))
        self.set_status("spec", "APPROVED")
        self.set_status("state", "SPEC_APPROVED")
        self.assertFalse(self.is_blocked(self.gate("arch")))
        # dev is blocked while the design is only complete, not approved.
        self.set_status("design", "DESIGN_COMPLETE")
        self.set_status("state", "DESIGN_COMPLETE")
        self.assertTrue(self.is_blocked(self.gate("dev")))
        # The owner approves the design, so dev may start (first block).
        self.set_status("design", "DESIGN_APPROVED")
        self.set_status("state", "DESIGN_APPROVED")
        self.assertFalse(self.is_blocked(self.gate("dev")))
        # Later block: state IN_DEV still passes dev, but qa is still blocked.
        self.set_status("state", "IN_DEV")
        self.assertFalse(self.is_blocked(self.gate("dev")))
        self.assertTrue(self.is_blocked(self.gate("qa")))
        # Final block applied, validation file documented.
        self.set_status("state", "DEV_COMPLETE")
        self.assertTrue(self.is_blocked(self.gate("qa")), "validation file still missing")
        self.set_status("edge-case-validation", "DOCUMENTED")
        self.assertFalse(self.is_blocked(self.gate("qa")))
        # The legacy VALIDATED value also passes.
        self.set_status("edge-case-validation", "VALIDATED")
        self.assertFalse(self.is_blocked(self.gate("qa")))
        # qa approved afterwards: qa blocks a rerun that skipped dev completion.
        self.set_status("state", "QA_APPROVED")
        self.assertTrue(self.is_blocked(self.gate("qa")))


class GAT03OverrideFile(GateVault):
    def override_line(self, skill: str = "arch") -> str:
        return "Override: {0} {1} owner decision\n".format(skill, TODAY.isoformat())

    def model_write(self, path: str, tool: str = "Write") -> subprocess.CompletedProcess:
        body = json.dumps({"tool_name": tool, "session_id": "s1", "tool_input": {"file_path": path}})
        env = {**os.environ, "HOME": self.home}
        env.pop("TOLLGATE_CODE_DIR", None)
        return subprocess.run([WRITE_GUARD], input=body, capture_output=True, text=True,
                              env=env, timeout=TIMEOUT_SECONDS)

    def test_gat_03_owner_created_override_opens_the_gate(self) -> None:
        self.set_status("state", "ROUTED")
        self.assertTrue(self.is_blocked(self.gate("arch")))
        # The owner creates the file from a terminal (a plain file write here).
        self.put("gate-override", self.override_line())
        self.assertFalse(self.is_blocked(self.gate("arch")))
        self.assertIn("override arch T-001", self.log_text())
        # It covers one skill only.
        self.assertTrue(self.is_blocked(self.gate("dev")))

    def test_gat_03b_model_write_to_override_file_is_blocked(self) -> None:
        target = os.path.join(self.ticket_dir, "{0}-gate-override.md".format(KEY))
        for tool in ("Write", "Edit", "MultiEdit"):
            result = self.model_write(target, tool)
            self.assertIn("deny", result.stdout, tool)
            self.assertIn("terminal", result.stdout, tool)
        self.assertFalse(os.path.exists(target))

    def test_gat_03c_blocked_write_means_no_override_and_gate_stays_shut(self) -> None:
        self.set_status("state", "ROUTED")
        target = os.path.join(self.ticket_dir, "{0}-gate-override.md".format(KEY))
        self.assertIn("deny", self.model_write(target).stdout)
        self.assertTrue(self.is_blocked(self.gate("arch")))

    def test_gat_03d_expired_override_does_not_count(self) -> None:
        self.set_status("state", "ROUTED")
        old = TODAY - datetime.timedelta(days=1)
        self.put("gate-override", "Override: arch {0} stale\n".format(old.isoformat()))
        self.assertTrue(self.is_blocked(self.gate("arch")))


class GAT04FixedNames(GateVault):
    def test_gat_04_tg_names_are_gated_and_name_the_tg_spec_command(self) -> None:
        self.set_status("state", "ROUTED")
        result = self.gate("arch")
        self.assertTrue(self.is_blocked(result))
        reason = json.loads(result.stdout)["reason"]
        self.assertIn("/tg-spec {0}".format(KEY), reason)
        self.set_status("spec", "APPROVED")
        self.set_status("state", "SPEC_APPROVED")
        self.assertFalse(self.is_blocked(self.gate("arch")))

    def test_gat_04b_old_prefix_variable_is_ignored(self) -> None:
        self.set_status("state", "ROUTED")
        for value in ("tg", "", "my-team", "tg-"):
            self.assertTrue(self.is_blocked(self.gate("arch", TOLLGATE_SKILL_PREFIX=value)), repr(value))
        self.assertTrue(self.is_blocked(self.gate("arch")))

    def test_gat_04c_other_names_are_not_gated(self) -> None:
        self.set_status("state", "ROUTED")
        for name in ("zz-arch", "arch", "dev", "qa", "my-team-arch", "close", "tg-spec", "tg-architect"):
            result = self.gate("arch", name=name, TOLLGATE_SKILL_PREFIX="my-team")
            self.assertEqual(result.stdout.strip(), "", name)


if __name__ == "__main__":
    unittest.main()
