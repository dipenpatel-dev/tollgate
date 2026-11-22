# Module:      test_plane_comment_builder.py
# Description: Tests for the comment builder: html, secret patterns, cut, session text, extras, and a scan of real session logs.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import tempfile
import unittest
from pathlib import Path

from connectors.plane.plane_comment_builder import (
    build_dev_extras,
    build_spec_extras,
    comment_key,
    cut_to_limit,
    extract_first_mermaid_block,
    extract_markdown_section,
    find_secret_pattern,
    markdown_to_html,
    read_new_session_text,
)
from plane_sync_test_support import FAKE_TOKEN, make_settings

PATTERNS = make_settings().secret_patterns
KEY_BLOCK = "-----BEGIN " + "RSA PRIVATE KEY-----"
ASSIGNMENT = "api_key = " + "abcd1234efgh5678"
SPEC = "# Spec\n\n## Requirements\nR-01 do it\n\n## Acceptance Criteria\nAC-01 works\n\n## Budget\nnone\n"
DESIGN = (
    "# D\n\n```mermaid\nflowchart TD\n    early --> x\n```\n\n## Implementation Plan\ntext\n\n"
    "### Data flow\n\n```mermaid\nflowchart TD\n    a --> b\n```\n"
)


class TestMarkdownAndSecrets(unittest.TestCase):
    def test_raw_html_is_shown_as_text(self) -> None:
        html = markdown_to_html("hello <script>alert(1)</script>\n\n**bold**")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_each_pattern_catches_its_case(self) -> None:
        self.assertEqual(find_secret_pattern(KEY_BLOCK, PATTERNS), "private_key_block")
        self.assertEqual(find_secret_pattern(ASSIGNMENT, PATTERNS), "named_secret_assignment")
        self.assertEqual(find_secret_pattern("value " + FAKE_TOKEN, PATTERNS), "long_mixed_token")

    def test_clean_text_has_no_hit(self) -> None:
        text = "Status moved. sha 0123456789ab, token budget is fine, T-339-session-2026-01-02.md"
        self.assertIsNone(find_secret_pattern(text, PATTERNS))
        self.assertIsNone(find_secret_pattern("anything", {}))

    def test_long_hyphenated_file_names_are_not_tokens(self) -> None:
        name = "T-209-qa-r2-report-2026-09-08-session-notes-final"
        self.assertIsNone(find_secret_pattern(name, PATTERNS))

    def test_first_matching_pattern_name_is_returned(self) -> None:
        patterns = {"first": "abc", "second": "abc"}
        self.assertEqual(find_secret_pattern("xabcx", patterns), "first")


class TestCutAndKey(unittest.TestCase):
    def test_text_within_the_limit_is_unchanged(self) -> None:
        self.assertEqual(cut_to_limit("abcde", 5, "ptr"), "abcde")

    def test_longer_text_is_cut_to_exactly_the_limit_with_the_pointer(self) -> None:
        cut = cut_to_limit("x" * 100, 50, "(cut; see vault)")
        self.assertEqual(len(cut), 50)
        self.assertTrue(cut.endswith("\n(cut; see vault)"))

    def test_tiny_limit_never_slices_from_the_end(self) -> None:
        self.assertEqual(cut_to_limit("x" * 100, 2, "pointer"), "\npointer")

    def test_comment_key_is_twelve_hex_and_stable(self) -> None:
        key = comment_key("hello")
        self.assertRegex(key, r"^[0-9a-f]{12}$")
        self.assertEqual(key, comment_key("hello"))
        self.assertNotEqual(key, comment_key("hello "))


class TestSessionText(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        (self.folder / "T-9-session-a.md").write_text("alpha text\n", encoding="utf-8")
        (self.folder / "T-9-session-b.md").write_text("beta text\n", encoding="utf-8")
        (self.folder / "T-9-state.md").write_text("not a session\n", encoding="utf-8")

    def test_all_text_is_read_with_file_headings_and_offsets(self) -> None:
        text, offsets = read_new_session_text(self.folder, "T-9", {})
        self.assertEqual(text, "### T-9-session-a.md\nalpha text\n\n\n### T-9-session-b.md\nbeta text\n")
        self.assertEqual(offsets, {"T-9-session-a.md": 11, "T-9-session-b.md": 10})

    def test_only_text_after_the_offset_is_returned(self) -> None:
        text, _ = read_new_session_text(self.folder, "T-9", {"T-9-session-a.md": 11})
        self.assertNotIn("alpha", text)
        self.assertIn("beta text", text)

    def test_nothing_new_gives_empty_text_and_same_offsets(self) -> None:
        text, offsets = read_new_session_text(
            self.folder, "T-9", {"T-9-session-a.md": 11, "T-9-session-b.md": 10}
        )
        self.assertEqual(text, "")
        self.assertEqual(offsets["T-9-session-b.md"], 10)

    def test_reading_writes_nothing(self) -> None:
        before = sorted(p.name for p in self.folder.iterdir())
        read_new_session_text(self.folder, "T-9", {})
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), before)


class TestExtras(unittest.TestCase):
    def test_section_runs_to_the_next_level_two_heading(self) -> None:
        section = extract_markdown_section(SPEC, "Requirements")
        self.assertEqual(section, "## Requirements\nR-01 do it")
        self.assertEqual(extract_markdown_section(SPEC, "Missing"), "")

    def test_mermaid_block_is_the_first_one_after_the_heading(self) -> None:
        block = extract_first_mermaid_block(DESIGN, "Implementation Plan")
        self.assertEqual(block, "```mermaid\nflowchart TD\n    a --> b\n```")
        self.assertEqual(extract_first_mermaid_block(DESIGN, "Nowhere"), "")

    def test_spec_extras_hold_requirements_criteria_and_diagram(self) -> None:
        extras = build_spec_extras(SPEC, DESIGN)
        for part in ("R-01 do it", "AC-01 works", "a --> b"):
            self.assertIn(part, extras)
        self.assertNotIn("early", extras)
        self.assertNotIn("Budget", extras)

    def test_a_missing_part_is_named(self) -> None:
        extras = build_spec_extras("# Spec\n", "# D\n")
        self.assertEqual(extras.count("(extras:"), 3)

    def test_dev_extras_drop_the_frontmatter(self) -> None:
        text = "---\nstatus: VALIDATED\n---\n# Results\nscenario 1 PASS\n"
        self.assertEqual(build_dev_extras(text), "# Results\nscenario 1 PASS")
        self.assertEqual(build_dev_extras("# Plain\nbody\n"), "# Plain\nbody")


if __name__ == "__main__":
    unittest.main()
