"""Tests for hooks/pre-prompt-expansion-check-gates.py.

Scope: UserPromptExpansion payloads against synthetic ticket folders in a temp
dir. Fake ids like T-001, no real data. Runs the hook as a subprocess.
Ticket: n/a

ChangeLog:
  - Fixed tg- command names (tg-arch, tg-dev, tg-qa); TOLLGATE_SKILL_PREFIX is not read. Test 21 now
    proves a leftover prefix variable is ignored and bare arch, dev, qa are not gated.
  - Q-08: tests 19b, 20b, 20d now expect a visible "Gate not checked" warning (still an
    allow, never a block) instead of empty output. Added tests 19c, 19d.
  - Moved to Status lines (spec APPROVED, design DESIGN_APPROVED, validation
    DOCUMENTED); test 13 and 16 reworded, DESIGN_COMPLETE state now blocks dev.
  - Initial version: design tests 10 to 26.
  - ticket token choice, lowercase ids, override hardening, unreadable files,
    no Status echo.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from typing import Dict, List, Optional

HOOKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "pre-prompt-expansion-check-gates")
HOOK = os.path.join(HOOKS_DIR, "pre-prompt-expansion-check-gates.py")
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

from state_file_io import write_state_atomic  # noqa: E402  (path setup must come first)

PREFIX = "tg"
KEY = "T-001"
TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)
SECRET_MARKER = "UNIQUE_BODY_MARKER_7431"
CONCURRENT_RUNS = 12
CONCURRENT_WRITES = 150
TIMEOUT_SECONDS = 30


def state(value: str) -> str:
    return "# {0} state\nStatus: {1}\n{2}\n".format(KEY, value, SECRET_MARKER)


def spec_doc() -> str:
    return "# spec\nStatus: APPROVED\n{0}\n".format(SECRET_MARKER)


def design_doc() -> str:
    return "# design\nStatus: DESIGN_APPROVED\n{0}\n".format(SECRET_MARKER)


def validation_doc() -> str:
    return "# validation\nStatus: DOCUMENTED\n"


def payload(skill: str, args: str = KEY, name: Optional[str] = None) -> str:
    return json.dumps({
        "command_name": name or "{0}-{1}".format(PREFIX, skill),
        "command_args": args,
        "command_source": "user",
        "cwd": "/tmp/example",
        "expansion_type": "slash_command",
        "hook_event_name": "UserPromptExpansion",
        "prompt": "/{0}-{1} {2}".format(PREFIX, skill, args),
    })


class GateHookBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.vault = os.path.join(self._tmp.name, "vault")
        self.ticket_dir = os.path.join(self.vault, "02-tickets", KEY)
        os.makedirs(self.ticket_dir)
        self.log = os.path.join(self._tmp.name, "logs", "gate.log")
        self.env = {
            "TOLLGATE_KNOWLEDGE": self.vault,
            "TOLLGATE_HOME": os.path.dirname(HOOKS_DIR),
            "TOLLGATE_GATE_LOG": self.log,
        }

    def put(self, suffix: str, text: str) -> str:
        path = os.path.join(self.ticket_dir, "{0}-{1}.md".format(KEY, suffix))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_hook(self, stdin: str, drop: Optional[List[str]] = None, **extra: str):
        env = {k: v for k, v in os.environ.items() if k not in (drop or [])}
        env.update({k: v for k, v in self.env.items() if k not in (drop or [])})
        env.update(extra)
        return subprocess.run([HOOK], input=stdin, capture_output=True, text=True,
                              env=env, timeout=TIMEOUT_SECONDS)

    def run_with_broken_rules(self, stdin: str) -> subprocess.CompletedProcess:
        script = (
            "import importlib.util, sys\n"
            "sys.path.insert(0, {0!r})\n"
            "import gate_rules\n"
            "def boom(*a, **k):\n"
            "    raise RuntimeError('forced')\n"
            "gate_rules.check_arch = boom\n"
            "spec = importlib.util.spec_from_file_location('hook', {1!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "sys.exit(mod.main())\n"
        ).format(HOOKS_DIR, HOOK)
        env = {**os.environ, **self.env}
        return subprocess.run([sys.executable, "-c", script], input=stdin,
                              capture_output=True, text=True, env=env, timeout=TIMEOUT_SECONDS)

    def blocked(self, result: subprocess.CompletedProcess) -> Dict[str, str]:
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["decision"], "block")
        return data

    def allowed(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def warned(self, result: subprocess.CompletedProcess, *words: str) -> None:
        """Allowed, but with one visible warning that says what is wrong."""
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertNotIn("decision", data)
        self.assertIn("Gate not checked", data["systemMessage"])
        for word in words:
            self.assertIn(word, data["systemMessage"])

    def log_text(self) -> str:
        if not os.path.exists(self.log):
            return ""
        with open(self.log, encoding="utf-8") as handle:
            return handle.read()

    def good_chain(self, status: str) -> None:
        self.put("spec", spec_doc())
        self.put("design", design_doc())
        self.put("edge-case-validation", validation_doc())
        self.put("state", state(status))


class ArchTests(GateHookBase):
    def test_10_arch_approved_spec_and_state_allowed(self) -> None:
        self.put("spec", spec_doc())
        self.put("state", state("SPEC_APPROVED"))
        self.allowed(self.run_hook(payload("arch")))

    def test_11_arch_missing_spec_blocks_and_names_path(self) -> None:
        self.put("state", state("SPEC_APPROVED"))
        data = self.blocked(self.run_hook(payload("arch")))
        self.assertIn(os.path.join(self.ticket_dir, "T-001-spec.md"), data["reason"])
        self.assertIn("/tg-spec T-001", data["reason"])

    def test_12_arch_state_routed_blocks(self) -> None:
        self.put("spec", spec_doc())
        self.put("state", state("ROUTED"))
        reason = self.blocked(self.run_hook(payload("arch")))["reason"]
        self.assertIn("SPEC_APPROVED", reason)
        self.assertNotIn("ROUTED", reason)


class DevTests(GateHookBase):
    def test_13_dev_without_approval_blocks_then_design_approved_allows(self) -> None:
        self.put("design", "# design\nStatus: DESIGN_COMPLETE\n")
        self.put("state", state("DESIGN_APPROVED"))
        self.blocked(self.run_hook(payload("dev")))
        self.put("design", design_doc())
        self.allowed(self.run_hook(payload("dev")))

    def test_13b_dev_with_state_design_complete_blocks(self) -> None:
        self.put("design", design_doc())
        self.put("state", state("DESIGN_COMPLETE"))
        self.blocked(self.run_hook(payload("dev")))

    def test_14_dev_in_dev_with_approved_design_allowed(self) -> None:
        self.put("design", design_doc())
        self.put("state", state("IN_DEV"))
        self.allowed(self.run_hook(payload("dev")))


class QaTests(GateHookBase):
    def test_15_qa_all_good_allowed(self) -> None:
        self.good_chain("DEV_COMPLETE")
        self.allowed(self.run_hook(payload("qa")))

    def test_16_qa_validation_status_missing_blocks(self) -> None:
        self.good_chain("DEV_COMPLETE")
        self.put("edge-case-validation", "# validation\nno status line\n")
        data = self.blocked(self.run_hook(payload("qa")))
        self.assertIn("edge-case-validation.md", data["reason"])

    def test_17_qa_state_in_dev_blocks(self) -> None:
        self.good_chain("IN_DEV")
        reason = self.blocked(self.run_hook(payload("qa")))["reason"]
        self.assertIn("DEV_COMPLETE", reason)
        self.assertNotIn("IN_DEV", reason)


class AllowPathTests(GateHookBase):
    def test_18_entry_points_and_unrelated_commands_allowed_silently(self) -> None:
        for name in ("tg-ticket", "tg-support", "tg-spec", "other-skill", "close"):
            self.allowed(self.run_hook(payload("spec", name=name)))
        self.assertEqual(self.log_text(), "")

    def test_19_no_ticket_id_allowed_and_logged(self) -> None:
        self.allowed(self.run_hook(payload("arch", args="no id here")))
        self.assertIn("no ticket id", self.log_text())

    def test_19b_unset_knowledge_dir_allowed_and_logged(self) -> None:
        self.warned(self.run_hook(payload("arch"), drop=["TOLLGATE_KNOWLEDGE"]),
                    "TOLLGATE_KNOWLEDGE is not set")
        self.assertIn("allow", self.log_text())

    def test_19c_missing_ticket_folder_warns_for_arch_dev_qa(self) -> None:
        for skill in ("arch", "dev", "qa"):
            self.warned(self.run_hook(payload(skill, args="T-777")), "T-777", "02-tickets")

    def test_19d_no_warning_when_there_is_no_ticket_id_or_folder_found(self) -> None:
        self.allowed(self.run_hook(payload("arch", args="no id here")))
        self.put("state", state("ROUTED"))
        self.blocked(self.run_hook(payload("arch")))

    def test_20_traversal_token_is_not_a_ticket_id(self) -> None:
        outside = os.path.join(self.vault, "02-tickets", "..", "secret")
        os.makedirs(outside)
        for args in ("../secret", "T-001/../../x", "a/b"):
            self.allowed(self.run_hook(payload("arch", args=args)))
        self.assertIn("no ticket id", self.log_text())

    def test_20b_symlinked_ticket_folder_outside_vault_allowed_and_logged(self) -> None:
        outside = os.path.join(self._tmp.name, "elsewhere")
        os.makedirs(outside)
        link_key = "T-002"
        os.symlink(outside, os.path.join(self.vault, "02-tickets", link_key))
        self.warned(self.run_hook(payload("arch", args=link_key)), link_key)
        self.assertIn("no ticket id", self.log_text())

    def test_20f_trailing_punctuation_does_not_skip_the_gate(self) -> None:
        self.put("state", state("ROUTED"))
        for args in ("T-001,", "(T-001)", "T-001.", "'T-001';"):
            self.blocked(self.run_hook(payload("arch", args=args)))

    def test_20g_symlinked_folder_does_not_hide_a_later_real_ticket(self) -> None:
        self.put("state", state("ROUTED"))
        outside = os.path.join(self._tmp.name, "elsewhere")
        os.makedirs(outside)
        os.symlink(outside, os.path.join(self.vault, "02-tickets", "T-002"))
        self.blocked(self.run_hook(payload("arch", args="T-002 T-001")))

    def test_20c_first_token_with_a_folder_is_used(self) -> None:
        self.put("state", state("ROUTED"))
        self.blocked(self.run_hook(payload("arch", args="UTF-8 T-001")))
        self.blocked(self.run_hook(payload("arch", args="T-001 UTF-8")))

    def test_20d_token_without_a_folder_is_no_ticket(self) -> None:
        self.put("state", state("ROUTED"))
        self.warned(self.run_hook(payload("arch", args="UTF-8")), "UTF-8")
        self.assertIn("no ticket id", self.log_text())

    def test_20e_lowercase_id_still_gated(self) -> None:
        self.put("state", state("ROUTED"))
        self.blocked(self.run_hook(payload("arch", args="t-001")))

    def test_21_old_prefix_variable_is_ignored(self) -> None:
        """tg- is fixed: a leftover TOLLGATE_SKILL_PREFIX (set, empty or absent) changes nothing."""
        self.put("state", state("ROUTED"))
        for value in ("ex", "", "zz-"):
            self.blocked(self.run_hook(payload("arch"), TOLLGATE_SKILL_PREFIX=value))
        self.blocked(self.run_hook(payload("arch"), drop=["TOLLGATE_SKILL_PREFIX"]))
        self.allowed(self.run_hook(payload("arch", name="ex-arch"), TOLLGATE_SKILL_PREFIX="ex"))

    def test_21b_other_names_allowed(self) -> None:
        self.put("state", state("ROUTED"))
        for name in ("zz-qa", "tgqa", "tg-qa-extra", "qa", "arch", "dev"):
            self.allowed(self.run_hook(payload("qa", name=name)))


class NestedLayoutTests(GateHookBase):
    """Tickets kept as 02-tickets/PREFIX/KEY, the layout of a real vault."""

    def nest(self, folder_name: str) -> None:
        """Move the ticket folder under 02-tickets/<folder_name>/."""
        parent = os.path.join(self.vault, "02-tickets", folder_name)
        os.makedirs(parent)
        nested = os.path.join(parent, KEY)
        os.rename(self.ticket_dir, nested)
        self.ticket_dir = nested

    def test_27_nested_folder_is_found_and_blocks_with_its_path(self) -> None:
        self.nest("T")
        self.put("state", state("SPEC_APPROVED"))
        data = self.blocked(self.run_hook(payload("arch")))
        self.assertIn(os.path.join(self.vault, "02-tickets", "T", KEY, "T-001-spec.md"), data["reason"])

    def test_27b_nested_folder_with_good_files_is_allowed(self) -> None:
        self.nest("T")
        self.put("spec", spec_doc())
        self.put("state", state("SPEC_APPROVED"))
        self.allowed(self.run_hook(payload("arch")))

    def test_27c_prefix_folder_case_does_not_matter(self) -> None:
        self.nest("t")
        self.put("state", state("ROUTED"))
        self.blocked(self.run_hook(payload("arch")))

    def test_27f_gate_follows_a_tickets_folder_renamed_in_the_paths_file(self) -> None:
        renamed = os.path.join(self.vault, "work-items")
        os.makedirs(os.path.join(renamed, KEY))
        paths_file = os.path.join(self._tmp.name, "paths.yaml")
        with open(paths_file, "w", encoding="utf-8") as handle:
            handle.write("tickets: {0}\n".format(renamed))
        with open(os.path.join(renamed, KEY, "{0}-state.md".format(KEY)), "w", encoding="utf-8") as handle:
            handle.write(state("ROUTED"))
        data = self.blocked(self.run_hook(payload("arch"), TOLLGATE_PATHS=paths_file))
        self.assertIn(os.path.join(renamed, KEY), data["reason"])

    def test_27h_gate_log_goes_to_the_state_folder_of_the_paths_file(self) -> None:
        state_dir = os.path.join(self._tmp.name, "moved-state")
        paths_file = os.path.join(self._tmp.name, "paths.yaml")
        with open(paths_file, "w", encoding="utf-8") as handle:
            handle.write("state: {0}\n".format(state_dir))
        self.put("state", state("ROUTED"))
        env = {k: v for k, v in os.environ.items() if k != "TOLLGATE_STATE_DIR"}
        env.update({k: v for k, v in self.env.items() if k != "TOLLGATE_GATE_LOG"})
        env.update({"TOLLGATE_PATHS": paths_file, "HOME": self._tmp.name})
        result = subprocess.run([HOOK], input=payload("arch"), capture_output=True, text=True,
                                env=env, timeout=TIMEOUT_SECONDS)
        self.blocked(result)
        log_file = os.path.join(state_dir, "gate_check.log")
        self.assertTrue(os.path.exists(log_file))
        with open(log_file, encoding="utf-8") as handle:
            self.assertIn("block arch T-001", handle.read())
        self.assertFalse(os.path.exists(os.path.join(self._tmp.name, ".tollgate")))

    def test_27i_gate_log_falls_back_to_the_old_default_without_the_loader(self) -> None:
        self.put("state", state("ROUTED"))
        env = {k: v for k, v in os.environ.items() if k not in ("TOLLGATE_STATE_DIR", "TOLLGATE_PATHS")}
        env.update({k: v for k, v in self.env.items() if k not in ("TOLLGATE_GATE_LOG", "TOLLGATE_HOME")})
        env["HOME"] = self._tmp.name
        subprocess.run([HOOK], input=payload("arch"), capture_output=True, text=True, env=env,
                       timeout=TIMEOUT_SECONDS)
        self.assertTrue(os.path.exists(os.path.join(self._tmp.name, ".tollgate", "state", "gate_check.log")))

    def test_27g_gate_warns_when_the_path_loader_cannot_be_found(self) -> None:
        self.warned(self.run_hook(payload("arch"), drop=["TOLLGATE_HOME"]), "TOLLGATE_HOME is not set")

    def test_27d_flat_folder_wins_over_nested(self) -> None:
        self.put("state", state("ROUTED"))
        os.makedirs(os.path.join(self.vault, "02-tickets", "T", KEY))
        data = self.blocked(self.run_hook(payload("arch")))
        self.assertIn(os.path.join(self.vault, "02-tickets", KEY), data["reason"])

    def test_27e_nested_symlink_outside_the_vault_is_ignored(self) -> None:
        outside = os.path.join(self._tmp.name, "outside")
        os.makedirs(outside)
        os.rmdir(self.ticket_dir)
        os.makedirs(os.path.join(self.vault, "02-tickets", "T"))
        os.symlink(outside, os.path.join(self.vault, "02-tickets", "T", KEY))
        self.warned(self.run_hook(payload("arch")), KEY)


class FailOpenTests(GateHookBase):
    def assert_failed_open(self, result: subprocess.CompletedProcess) -> None:
        self.allowed(result)
        self.assertNotEqual(result.stderr.strip(), "")
        self.assertIn("fail_open", self.log_text())

    def assert_failed_closed(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")
        self.assertNotEqual(result.stderr.strip(), "")
        self.assertIn("fail_closed", self.log_text())

    def test_22_bad_json_fails_closed(self) -> None:
        self.assert_failed_closed(self.run_hook("{not json"))

    def test_22b_non_object_json_fails_closed(self) -> None:
        self.assert_failed_closed(self.run_hook("[1, 2]"))

    def test_23_exception_inside_rules_blocks_a_gated_skill(self) -> None:
        self.put("spec", spec_doc())
        self.put("state", state("SPEC_APPROVED"))
        data = self.blocked(self.run_with_broken_rules(payload("arch")))
        self.assertIn("RuntimeError", data["reason"])
        self.assertIn("fail_closed", self.log_text())

    def test_23b_exception_for_a_non_gated_command_still_allows(self) -> None:
        self.put("spec", spec_doc())
        self.put("state", state("SPEC_APPROVED"))
        script = (
            "import importlib.util, sys\n"
            "sys.path.insert(0, {0!r})\n"
            "spec = importlib.util.spec_from_file_location('hook', {1!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "def boom(*a, **k):\n"
            "    raise RuntimeError('forced')\n"
            "mod.evaluate = boom\n"
            "sys.exit(mod.main())\n"
        ).format(HOOKS_DIR, HOOK)
        env = {**os.environ, **self.env}
        result = subprocess.run([sys.executable, "-c", script], input=payload("status"),
                                capture_output=True, text=True, env=env, timeout=TIMEOUT_SECONDS)
        self.assert_failed_open(result)


def skill_payload(skill: str, args: str = KEY, tool: str = "Skill") -> str:
    """A PreToolUse payload for a model-invoked skill (the Skill tool)."""
    return json.dumps({
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"skill": skill, "args": args},
        "cwd": "/tmp/example",
    })


class SkillToolTests(GateHookBase):
    """The gate also runs on the Skill tool, so a skill the model calls itself is gated too."""

    def denied(self, result: subprocess.CompletedProcess) -> Dict[str, str]:
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        return out

    def test_30_model_called_gated_skill_is_denied_when_status_missing(self) -> None:
        self.put("state", state("ROUTED"))
        out = self.denied(self.run_hook(skill_payload("{0}-arch".format(PREFIX))))
        self.assertIn(KEY, out["permissionDecisionReason"])

    def test_30b_model_called_gated_skill_is_allowed_when_chain_is_ready(self) -> None:
        self.put("spec", spec_doc())
        self.put("state", state("SPEC_APPROVED"))
        self.allowed(self.run_hook(skill_payload("{0}-arch".format(PREFIX))))

    def test_30c_leading_slash_in_skill_name_is_ignored(self) -> None:
        self.put("state", state("ROUTED"))
        self.denied(self.run_hook(skill_payload("/{0}-dev".format(PREFIX))))

    def test_30d_other_skills_and_other_tools_are_not_gated(self) -> None:
        self.put("state", state("ROUTED"))
        self.allowed(self.run_hook(skill_payload("status")))
        self.allowed(self.run_hook(skill_payload("{0}-arch".format(PREFIX), tool="Bash")))

    def test_30e_override_lets_a_model_called_skill_through(self) -> None:
        self.put("state", state("ROUTED"))
        self.put("gate-override", "Override: arch {0} hotfix\n".format(TODAY.isoformat()))
        self.allowed(self.run_hook(skill_payload("{0}-arch".format(PREFIX))))

    def test_30f_internal_error_for_a_gated_model_call_is_denied(self) -> None:
        self.put("spec", spec_doc())
        self.put("state", state("SPEC_APPROVED"))
        result = self.run_with_broken_rules(skill_payload("{0}-arch".format(PREFIX)))
        self.assertIn("RuntimeError", self.denied(result)["permissionDecisionReason"])

    def test_30g_unreadable_skill_payload_exits_2(self) -> None:
        self.assertEqual(self.run_hook("{not json").returncode, 2)


class OverrideTests(GateHookBase):
    def setUp(self) -> None:
        super().setUp()
        self.put("state", state("ROUTED"))

    def override(self, skill: str = "arch", date: datetime.date = TODAY, reason: str = "hotfix") -> None:
        self.put("gate-override", "Override: {0} {1} {2}\n".format(skill, date.isoformat(), reason))

    def test_24_valid_override_allows_and_logs(self) -> None:
        self.override()
        self.allowed(self.run_hook(payload("arch")))
        self.assertIn("override arch T-001", self.log_text())

    def test_24b_wrong_skill_blocks(self) -> None:
        self.override(skill="dev")
        self.blocked(self.run_hook(payload("arch")))

    def test_24c_yesterday_blocks(self) -> None:
        self.override(date=YESTERDAY)
        self.blocked(self.run_hook(payload("arch")))

    def test_24d_no_reason_blocks(self) -> None:
        self.put("gate-override", "Override: arch {0}\n".format(TODAY.isoformat()))
        self.blocked(self.run_hook(payload("arch")))
        self.put("gate-override", "Override: arch {0}   \n".format(TODAY.isoformat()))
        self.blocked(self.run_hook(payload("arch")))


class OverrideHardeningTests(GateHookBase):
    def setUp(self) -> None:
        super().setUp()
        self.put("state", state("ROUTED"))
        self.line = "Override: arch {0} hotfix".format(TODAY.isoformat())

    def test_24e_override_inside_a_fence_is_ignored(self) -> None:
        self.put("gate-override", "```\n{0}\n```\n".format(self.line))
        self.blocked(self.run_hook(payload("arch")))
        self.put("gate-override", "~~~\n{0}\n```\n".format(self.line))
        self.blocked(self.run_hook(payload("arch")))

    def test_24f_override_after_a_closed_fence_counts(self) -> None:
        self.put("gate-override", "```\ncode\n```\n{0}\n".format(self.line))
        self.allowed(self.run_hook(payload("arch")))

    def test_24g_symlinked_override_is_refused_and_logged(self) -> None:
        real = os.path.join(self._tmp.name, "real-override.md")
        with open(real, "w", encoding="utf-8") as handle:
            handle.write(self.line + "\n")
        os.symlink(real, os.path.join(self.ticket_dir, "T-001-gate-override.md"))
        self.blocked(self.run_hook(payload("arch")))
        self.assertIn("override_refused", self.log_text())

    def test_24j_non_regular_override_is_refused_and_does_not_hang(self) -> None:
        fifo = os.path.join(self.ticket_dir, "T-001-gate-override.md")
        os.mkfifo(fifo)
        try:
            result = self.run_hook_short(payload("arch"))
        finally:
            os.unlink(fifo)
        self.blocked(result)
        self.assertIn("not a regular file", self.log_text())

    def run_hook_short(self, stdin: str) -> subprocess.CompletedProcess:
        env = {**os.environ, **self.env}
        try:
            return subprocess.run([HOOK], input=stdin, capture_output=True, text=True,
                                  env=env, timeout=5)
        except subprocess.TimeoutExpired:
            self.fail("the gate hook hung reading a named pipe as an override file")

    def test_24h_bom_before_override_line_still_counts(self) -> None:
        self.put("gate-override", "\ufeff" + self.line + "\n")
        self.allowed(self.run_hook(payload("arch")))

    def test_24i_unicode_digit_date_does_not_count(self) -> None:
        wide = "".join(chr(0xFF10 + int(ch)) if ch.isdigit() else ch for ch in TODAY.isoformat())
        self.put("gate-override", "Override: arch {0} hotfix\n".format(wide))
        self.blocked(self.run_hook(payload("arch")))


class UnreadableFileTests(GateHookBase):
    def test_27_permission_denied_is_reported_apart_from_missing(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root can read any file")
        self.put("spec", spec_doc())
        state_path = self.put("state", state("SPEC_APPROVED"))
        os.chmod(state_path, 0)
        self.addCleanup(os.chmod, state_path, 0o600)
        reason = self.blocked(self.run_hook(payload("arch")))["reason"]
        self.assertIn("permission denied", reason)
        self.assertIn(state_path, reason)
        self.assertIn("unreadable", self.log_text())

    def test_27b_missing_file_is_not_called_unreadable(self) -> None:
        self.put("spec", spec_doc())
        reason = self.blocked(self.run_hook(payload("arch")))["reason"]
        self.assertNotIn("permission denied", reason)


class ConcurrencyAndLeakTests(GateHookBase):
    def test_25_reader_never_sees_a_half_written_state_file(self) -> None:
        self.put("spec", spec_doc())
        state_path = self.put("state", state("SPEC_APPROVED"))
        stop = threading.Event()

        def writer() -> None:
            for index in range(CONCURRENT_WRITES):
                if stop.is_set():
                    return
                write_state_atomic(state_path, state("SPEC_APPROVED") + "x" * (index % 50))

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            results = [self.run_hook(payload("arch")) for _ in range(CONCURRENT_RUNS)]
        finally:
            stop.set()
            thread.join()
        for result in results:
            self.allowed(result)

    def test_26_block_message_never_prints_file_contents(self) -> None:
        self.put("spec", "# spec\n{0}\n".format(SECRET_MARKER))
        self.put("state", state("ROUTED"))
        result = self.run_hook(payload("arch"))
        self.blocked(result)
        self.assertNotIn(SECRET_MARKER, result.stdout)
        self.assertNotIn(SECRET_MARKER, result.stderr)
        self.assertNotIn(SECRET_MARKER, self.log_text())

    def test_26b_block_message_never_prints_the_status_value(self) -> None:
        self.put("spec", spec_doc())
        self.put("state", state("UNIQUE_STATUS_VALUE_55"))
        result = self.run_hook(payload("arch"))
        self.blocked(result)
        self.assertNotIn("UNIQUE_STATUS_VALUE_55", result.stdout)
        self.assertNotIn("UNIQUE_STATUS_VALUE_55", self.log_text())


class FixtureTests(GateHookBase):
    def test_fixture_payload_shape_is_handled(self) -> None:
        with open(os.path.join(FIXTURE_DIR, "tc-01-typed-arch.json"), encoding="utf-8") as handle:
            text = handle.read()
        data = json.loads(text)
        self.assertEqual(data["hook_event_name"], "UserPromptExpansion")
        # The recorded fixture still carries the old example prefix; the shape is what is under test.
        data["command_name"] = "tg-" + data["command_name"].split("-", 1)[1]
        self.put("state", state("ROUTED"))
        self.blocked(self.run_hook(json.dumps(data)))


if __name__ == "__main__":
    unittest.main()
