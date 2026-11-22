"""Tests for hooks/gate_rules.py.

Scope: Status line reading and the per-skill rule checks for arch, dev and qa,
using the dotfiles values (spec APPROVED, design DESIGN_APPROVED, validation
DOCUMENTED or VALIDATED). Synthetic text only, fake ids like T-001.
Ticket: n/a

ChangeLog:
  - Moved from dated approval lines to Status lines. Date, dash and Unicode
    digit tests removed because no date is read any more.
  - Initial version: parser tests 1 to 9 plus per-skill rule tests.
  - fence, line split, BOM and no Status echo regression tests.
"""
from __future__ import annotations

import os
import sys
import unittest

HOOKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

import gate_rules as gr  # noqa: E402  (path setup must come first)

STATE_TEMPLATE = "# T-001 state\nStatus: {0}\n"
FENCE = "```"
SPEC_OK = "Status: APPROVED"


def state(value: str) -> str:
    return STATE_TEMPLATE.format(value)


def spec_allows(text: str) -> bool:
    """True if arch accepts this text as the spec (state fixed to SPEC_APPROVED)."""
    return gr.check_arch(text, state("SPEC_APPROVED")).ok


class SpecStatusLineTests(unittest.TestCase):
    """Ported from the old approval line parser tests, now on `Status: APPROVED`."""

    def test_1_status_approved_passes(self) -> None:
        self.assertTrue(spec_allows(SPEC_OK))

    def test_3_placeholder_fails(self) -> None:
        self.assertFalse(spec_allows("Status: [APPROVED]"))
        self.assertFalse(spec_allows("Status: APPROVED | DRAFT"))
        self.assertFalse(spec_allows("Status:"))

    def test_4_old_dated_approval_line_no_longer_counts(self) -> None:
        self.assertFalse(spec_allows("Approved - 2026-11-01"))
        self.assertFalse(spec_allows("# Spec\nApproved \u2014 2026-11-01\n"))

    def test_5_fenced_block_does_not_count(self) -> None:
        text = "{0}\n{1}\n{0}\n".format(FENCE, SPEC_OK)
        self.assertFalse(spec_allows(text))
        tilde = "~~~\n{0}\n~~~\n".format(SPEC_OK)
        self.assertFalse(spec_allows(tilde))

    def test_5b_line_after_closed_fence_counts(self) -> None:
        text = "{0}\ncode\n{0}\n{1}\n".format(FENCE, SPEC_OK)
        self.assertTrue(spec_allows(text))

    def test_6_trailing_spaces_pass_extra_text_fails(self) -> None:
        self.assertTrue(spec_allows(SPEC_OK + "   "))
        self.assertFalse(spec_allows(SPEC_OK + " by me"))
        self.assertFalse(spec_allows("Note: " + SPEC_OK))

    def test_9_crlf_passes(self) -> None:
        text = "# Title\r\n{0}\r\nmore\r\n".format(SPEC_OK)
        self.assertTrue(spec_allows(text))

    def test_validation_and_design_use_their_own_values(self) -> None:
        self.assertFalse(gr.check_dev("Status: APPROVED\n", state("IN_DEV")).ok)
        self.assertFalse(gr.check_dev("Status: DESIGN_COMPLETE\n", state("IN_DEV")).ok)
        self.assertTrue(gr.check_dev("Status: DESIGN_APPROVED\n", state("IN_DEV")).ok)


class FenceTrackingTests(unittest.TestCase):
    def counts(self, *lines: str) -> bool:
        return spec_allows("\n".join(lines) + "\n")

    def test_mixed_marker_kinds_do_not_toggle(self) -> None:
        self.assertFalse(self.counts(FENCE, SPEC_OK, "~~~"))
        self.assertFalse(self.counts("~~~", SPEC_OK, FENCE))

    def test_longer_outer_fence_holds_shorter_fence_line(self) -> None:
        self.assertFalse(self.counts(FENCE + "`", FENCE, SPEC_OK, FENCE + "`"))

    def test_closing_line_with_info_text_does_not_close(self) -> None:
        self.assertFalse(self.counts(FENCE, FENCE + "python", SPEC_OK, FENCE))

    def test_closing_line_with_more_markers_closes(self) -> None:
        self.assertTrue(self.counts(FENCE, "code", FENCE + "`", SPEC_OK))

    def test_opening_fence_may_carry_info_text(self) -> None:
        self.assertFalse(self.counts(FENCE + "python", SPEC_OK, FENCE))

    def test_four_space_indent_is_not_a_fence(self) -> None:
        self.assertTrue(self.counts("    " + FENCE, SPEC_OK))

    def test_backtick_line_with_backtick_in_info_is_not_a_fence(self) -> None:
        self.assertTrue(self.counts(FENCE + "a`b", SPEC_OK))

    def test_status_after_mixed_fences_stays_hidden(self) -> None:
        text = "{0}\n~~~\nStatus: ROUTED\n".format(FENCE)
        self.assertFalse(gr.read_status(text).ok)


class TextHandlingTests(unittest.TestCase):
    def test_line_separator_does_not_split_lines(self) -> None:
        text = "x" + chr(0x2028) + SPEC_OK + "\n"
        self.assertFalse(spec_allows(text))
        self.assertEqual(gr.read_status("Status: IN_DEV" + chr(0x2028) + "Status: ROUTED\n").value,
                         "IN_DEV" + chr(0x2028) + "Status: ROUTED")

    def test_lone_carriage_return_does_not_split(self) -> None:
        self.assertFalse(spec_allows("x\r" + SPEC_OK + "\n"))

    def test_bom_does_not_hide_first_line(self) -> None:
        self.assertEqual(gr.read_status("﻿Status: IN_DEV\n").value, "IN_DEV")
        self.assertEqual(gr.read_status(b"\xef\xbb\xbfStatus: IN_DEV\n").value, "IN_DEV")
        design = b"\xef\xbb\xbfStatus: DESIGN_APPROVED\n"
        self.assertTrue(gr.check_dev(design, state("IN_DEV")).ok)


class StatusTests(unittest.TestCase):
    def test_reads_first_status_value(self) -> None:
        result = gr.read_status("# T-001\nStatus: SPEC_APPROVED  \nbody\n")
        self.assertTrue(result.ok)
        self.assertEqual(result.value, "SPEC_APPROVED")

    def test_7_two_different_status_lines_malformed(self) -> None:
        result = gr.read_status("Status: IN_DEV\nStatus: ROUTED\n")
        self.assertFalse(result.ok)

    def test_7b_same_value_twice_is_fine(self) -> None:
        self.assertTrue(gr.read_status("Status: IN_DEV\nStatus: IN_DEV\n").ok)

    def test_8_empty_no_status_and_bad_bytes_malformed(self) -> None:
        self.assertFalse(gr.read_status("").ok)
        self.assertFalse(gr.read_status("   \n").ok)
        self.assertFalse(gr.read_status("# T-001\nno status here\n").ok)
        self.assertFalse(gr.read_status(b"Status: IN_DEV\n\xff\xfe").ok)
        self.assertFalse(gr.read_status(None).ok)
        self.assertFalse(gr.read_status("Status:\n").ok)

    def test_bytes_input_accepted(self) -> None:
        self.assertEqual(gr.read_status(b"Status: IN_DEV\n").value, "IN_DEV")

    def test_9_crlf_status(self) -> None:
        self.assertEqual(gr.read_status("Status: IN_DEV\r\nx\r\n").value, "IN_DEV")

    def test_status_in_fence_ignored(self) -> None:
        text = "{0}\nStatus: ROUTED\n{0}\nStatus: IN_DEV\n".format(FENCE)
        self.assertEqual(gr.read_status(text).value, "IN_DEV")

    def test_indented_status_is_not_top_level(self) -> None:
        self.assertFalse(gr.read_status("  Status: IN_DEV\n").ok)


class ArchRuleTests(unittest.TestCase):
    def test_status_approved_form_with_state_allows(self) -> None:
        result = gr.check_arch(state("APPROVED"), state("SPEC_APPROVED"))
        self.assertTrue(result.ok)

    def test_missing_spec_blocks_and_names_it(self) -> None:
        result = gr.check_arch(None, state("SPEC_APPROVED"))
        self.assertFalse(result.ok)
        self.assertIn("spec.md", result.reason)

    def test_spec_without_status_line_blocks(self) -> None:
        result = gr.check_arch("# Spec\nno status\n", state("SPEC_APPROVED"))
        self.assertFalse(result.ok)
        self.assertIn("spec.md", result.reason)

    def test_unapproved_spec_blocks(self) -> None:
        result = gr.check_arch(state("DRAFT"), state("SPEC_APPROVED"))
        self.assertFalse(result.ok)
        self.assertIn("Status: APPROVED", result.reason)

    def test_lowercase_approved_status_does_not_count(self) -> None:
        self.assertFalse(gr.check_arch(state("approved"), state("SPEC_APPROVED")).ok)

    def test_wrong_state_blocks(self) -> None:
        result = gr.check_arch(state("APPROVED"), state("ROUTED"))
        self.assertFalse(result.ok)
        self.assertIn("SPEC_APPROVED", result.reason)

    def test_missing_state_blocks(self) -> None:
        result = gr.check_arch(state("APPROVED"), None)
        self.assertFalse(result.ok)
        self.assertIn("state file", result.reason)


class DevRuleTests(unittest.TestCase):
    DESIGN = "Status: DESIGN_APPROVED\n"

    def test_allowed_states_with_approved_design(self) -> None:
        for value in ("DESIGN_APPROVED", "IN_DEV"):
            self.assertTrue(gr.check_dev(self.DESIGN, state(value)).ok, value)

    def test_design_complete_state_blocks(self) -> None:
        self.assertFalse(gr.check_dev(self.DESIGN, state("DESIGN_COMPLETE")).ok)

    def test_no_status_line_blocks(self) -> None:
        result = gr.check_dev("# Design\n", state("IN_DEV"))
        self.assertFalse(result.ok)
        self.assertIn("design.md", result.reason)
        self.assertIn("Status: DESIGN_APPROVED", result.reason)

    def test_missing_design_blocks(self) -> None:
        self.assertFalse(gr.check_dev(None, state("IN_DEV")).ok)

    def test_wrong_state_blocks(self) -> None:
        self.assertFalse(gr.check_dev(self.DESIGN, state("DEV_COMPLETE")).ok)

    def test_both_problems_reported(self) -> None:
        result = gr.check_dev("x", state("ROUTED"))
        self.assertIn("design.md", result.reason)
        self.assertIn("state file", result.reason)


class QaRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = state("DEV_COMPLETE")
        self.spec = "Status: APPROVED\n"
        self.design = "Status: DESIGN_APPROVED\n"
        self.validation = "Status: DOCUMENTED\n"

    def run_qa(self) -> gr.CheckResult:
        return gr.check_qa(self.state, self.spec, self.design, self.validation)

    def test_all_good_allows(self) -> None:
        self.assertTrue(self.run_qa().ok)

    def test_validated_value_also_allows(self) -> None:
        self.validation = "Status: VALIDATED\n"
        self.assertTrue(self.run_qa().ok)

    def test_validation_without_allowed_status_blocks(self) -> None:
        self.validation = "Status: PENDING\n"
        result = self.run_qa()
        self.assertFalse(result.ok)
        self.assertIn("edge-case-validation.md", result.reason)

    def test_validation_old_dated_line_alone_blocks(self) -> None:
        self.validation = "Validated - 2026-11-01\n"
        self.assertFalse(self.run_qa().ok)

    def test_in_dev_state_blocks(self) -> None:
        self.state = state("IN_DEV")
        self.assertFalse(self.run_qa().ok)

    def test_spec_status_not_approved_blocks(self) -> None:
        self.spec = state("DRAFT")
        result = self.run_qa()
        self.assertFalse(result.ok)
        self.assertIn("spec.md", result.reason)

    def test_missing_design_blocks(self) -> None:
        self.design = None
        self.assertIn("design.md", self.run_qa().reason)

    def test_reason_never_prints_the_status_value_from_the_file(self) -> None:
        for value in ("UNIQUE_STATUS_TEXT_9", "IN_DEV"):
            self.state = state(value)
            result = self.run_qa()
            self.assertFalse(result.ok)
            self.assertNotIn(value, result.reason)
            self.assertIn("DEV_COMPLETE", result.reason)
        arch = gr.check_arch(state("APPROVED"), state("UNIQUE_STATUS_TEXT_9"))
        self.assertNotIn("UNIQUE_STATUS_TEXT_9", arch.reason)
        self.spec = state("UNIQUE_STATUS_TEXT_9")
        self.assertNotIn("UNIQUE_STATUS_TEXT_9", self.run_qa().reason)

    def test_reason_never_contains_file_contents(self) -> None:
        secret = "UNIQUE_BODY_TEXT_12345"
        self.design = secret + "\n"
        self.validation = secret
        self.assertNotIn(secret, self.run_qa().reason)


if __name__ == "__main__":
    unittest.main()
