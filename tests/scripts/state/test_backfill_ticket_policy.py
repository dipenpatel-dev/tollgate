# Module:      test_backfill_ticket_policy.py
# Description: Tests for the earlier ticket policy core in backfill_vault_frontmatter.py:
#              the 14 kind rows chosen by file name, the terminal status test, the
#              placeholder test, block creation with its self check, and exact line
#              replacement with its self check, then the run planner, the approved
#              report check, the tree check, the run report, and the command line.
#              Every input is a synthetic byte string or a fixture vault built in a
#              pytest temp folder, so no test reaches the real vault. The 14 expected
#              rows are literals here. This file never reads the tool's policy table,
#              so a typo in the table cannot hide behind a copy of itself. An autouse
#              fixture makes the tool's default vault lookup raise.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Test classes: TestKindRows, TestKindRowsRoleByName, TestKindRowsLoadCheck,
#              TestTerminalStatus, TestTerminalStatusPlaceholder, TestCreateBlockEol,
#              TestCreateBlock, TestCreateBlockUnsafeTop, TestCreateBlockVerify,
#              TestReplaceLines, TestReplaceLinesVerify, TestLocalOnlyImports,
#              TestLocalOnlyRuntime, TestLocalOnlyStandards, TestLocalOnlyPython39 (B-01);
#              TestPlanRun1, TestPlanRun2, TestPlanRun3, TestApprovedReport, TestTreeClean,
#              TestRunWiring, TestRunCli, TestReportContract, TestAC01KindRows through
#              TestAC08ReportContent, TestS257ModeUnchanged (B-02). The B-02 classes run
#              the tool over fixture vaults: a git repository inside a pytest temp folder.
# Version:     1.2
# ChangeLog:
#   Initial implementation
#   Run planner, approved report, tree check, report, CLI tests
#   Spec Q2 change: session-notes.md is K10, not K9; exclusion tests

import ast
import difflib
import hashlib
import json
import logging
import os
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import minipytest as pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "state"))
import backfill_vault_frontmatter as tool  # noqa: E402

TOOL_PATH = Path(__file__).resolve().parents[3] / "scripts" / "state" / "backfill_vault_frontmatter.py"
THIS_PATH = Path(__file__).resolve()


def refuse_default_vault_root() -> Any:
    """Stand in for default_vault_root: a fallback to the real vault is a bug."""
    raise AssertionError("default_vault_root was called: a test would fall back to the real vault")


@pytest.fixture(autouse=True)
def forbid_real_vault_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the tool's default vault lookup raise for every test in this module."""
    monkeypatch.setattr(tool, "default_vault_root", refuse_default_vault_root)


LF = b"\n"
CRLF = b"\r\n"
FOLDER = "T-900"
CANARY = "CANARY_7Q2X_DO_NOT_LEAK"
ROLE_BY_NAME = "<role by name>"
FALLBACK_ROLE = "reference"

# Source: the spec, Policy Table, re-typed here as literals.
# Columns: kind id, catalog_type, doc_role, indexable, bare file names that must match.
# K1, K2, and K14 are matched by position or path shape, so their name lists are empty
# and each has its own test. K10 is matched by the folder name and by the one name below,
# the Jira summary that K9 must not take (Q2 change of 2026-10-06). K14 holds no values.
EXPECTED_ROWS: List[Tuple[str, Optional[str], Optional[str], Optional[bool], Tuple[str, ...]]] = [
    ("K1", "ticket", ROLE_BY_NAME, False, ()),
    ("K2", "ticket", "state", True, ()),
    ("K3", "ticket", "review", False, (
        "cursor.md", "cursor-review.md", "qa-cursor-pass-1.md", "arch-review-notes.md",
    )),
    ("K4", "ticket", "reference", False, (
        "Block_B-01-DIFF.md", "block_b-02-diff.md", "prompt-b01.md", "prompts.md",
        "starter-prompt-b01.md",
    )),
    ("K5", "ticket", "spec", True, ("spec.md", "pre-spec.md")),
    ("K6", "ticket", "design", True, ("design.md", "arch.md")),
    ("K7", "ticket", "qa", True, ("qa-findings.md", "qa-findings-r2.md")),
    ("K8", "ticket", "qa", True, ("edge-case-validation.md",)),
    ("K9", "ticket", "session_log", True, (
        "session.md", "session-2026-10-05.md", "session-notes-2026-10-05.md",
    )),
    ("K10", "ticket", "reference", True, ("session-notes.md",)),
    ("K11", "ticket", "reference", True, ("context.md", "diagrams.md")),
    ("K12", "ticket", "reference", True, ("shipped.md",)),
    ("K13", "ticket", "reference", True, (
        "handoff.md", "support-handoff.md", "notes.md", "plan.md", "jira-draft.md", "coord.md",
    )),
    ("K14", None, None, None, ()),
]
EXPECTED_ROW_COUNT = 14
NAME_CASES = [
    (row[0], row[1], row[2], row[3], name) for row in EXPECTED_ROWS for name in row[4]
]

# Names below a ticket folder that no row claims (K14), each with the reason it misses.
UNMATCHED_NAMES = [
    "T-900-qa-prompts.md",
    "random.md",
    "readme.md",
    "T-900-notes-extra.md",
    "T-900-spec-v2.md",
    "design-draft.md",
    "T-900-handoff-2.md",
    "context-old.md",
    "shipped-2.md",
    "T-900-state-backup.md",
    "T-901-spec.md",
    "T-9000-spec.md",
    "T-900-T-900-spec.md",
    "T-901.md",
    "Block_B-01.md",
    "Block_B-01-notes.md",
]
PATHS_OUTSIDE_THE_TABLE = [
    "00-landing/note.md",
    "02-tickets/loose.md",
    "02-tickets/spec.md",
    "02-tickets/T-900-state.md",
    "02-tickets/T-900/spec.txt",
    "02-tickets/T-900/spec",
    "02-tickets//spec.md",
    "02-tickets/T-900//spec.md",
    "02-tickets/T-900/./spec.md",
    "02-tickets/T-900/../spec.md",
    "02-tickets/T-900/",
    "03-knowledge-base/02-tickets/T-900/spec.md",
    "",
]
TERMINAL_VALUES = ("cancelled", "superseded", "dropped", "archived", "absorbed")


def ticket_path(name: str, folder: str = FOLDER) -> str:
    """Return the root relative path of a file directly inside a ticket folder."""
    return "02-tickets/{}/{}".format(folder, name)


def triple(row: Any) -> Tuple[str, str, bool]:
    """Return the three field values of a kind row as a plain tuple."""
    return (row.catalog_type, row.doc_role, row.indexable)


def row_id(rel: str) -> Optional[str]:
    """Return the kind id the tool gives a path, or None when it gives no row."""
    row = tool.kind_row_for(rel)
    return None if row is None else row.kind_id


def row_triple(rel: str) -> Optional[Tuple[str, str, bool]]:
    """Return the three field values the tool gives a path, or None when it gives no row."""
    row = tool.kind_row_for(rel)
    return None if row is None else triple(row)


def doc(lines: Sequence[str], eol: bytes = LF, body: Optional[bytes] = None) -> bytes:
    """Build a file: an opening delimiter, the lines, a closing delimiter, then the body.

    The default body is one line in the same line ending as the rest of the file.
    """
    block = b"".join(line.encode("utf-8") + eol for line in lines)
    tail = b"body" + eol if body is None else body
    return b"---" + eol + block + b"---" + eol + tail


def span_of(raw: bytes) -> Any:
    """Return the frontmatter span of raw, which must have one."""
    span = tool.split_frontmatter(raw)
    assert span is not None
    return span


def prepare(raw: bytes) -> Tuple[Any, Dict[str, Any]]:
    """Return the frontmatter span and parsed mapping of raw; both must exist."""
    span = tool.split_frontmatter(raw)
    assert span is not None
    parsed = tool.parse_block(span.block)
    assert parsed is not None
    return span, parsed


class TestKindRows:
    def test_the_literal_table_has_fourteen_rows_in_order(self) -> None:
        assert [row[0] for row in EXPECTED_ROWS] == ["K{}".format(n) for n in range(1, 15)]
        assert len(EXPECTED_ROWS) == EXPECTED_ROW_COUNT

    @pytest.mark.parametrize("kind_id,catalog_type,doc_role,indexable,name", NAME_CASES)
    def test_each_name_pattern_receives_its_row(
        self, kind_id: str, catalog_type: str, doc_role: str, indexable: bool, name: str
    ) -> None:
        prefixed = FOLDER + "-" + name
        for variant in (name, prefixed, name.upper(), prefixed.upper()):
            row = tool.kind_row_for(ticket_path(variant))
            assert row is not None, variant
            assert row.kind_id == kind_id, variant
            assert triple(row) == (catalog_type, doc_role, indexable), variant

    def test_the_state_row_takes_only_the_exact_file_at_depth_three(self) -> None:
        row = tool.kind_row_for("02-tickets/T-900/T-900-state.md")
        assert row is not None and row.kind_id == "K2"
        assert triple(row) == ("ticket", "state", True)
        assert row_id("02-tickets/T-900/notes/T-900-state.md") is None
        assert row_id("02-tickets/T-900/T-901-state.md") is None
        assert row_id("02-tickets/T-900/t-900-state.md") is None
        assert row_id("02-tickets/T-900/state.md") is None

    @pytest.mark.parametrize("name", ["T-900.md", "t-900.md", "T-900.MD"])
    def test_the_ticket_main_row_takes_the_folder_name(self, name: str) -> None:
        row = tool.kind_row_for(ticket_path(name))
        assert row is not None and row.kind_id == "K10"
        assert triple(row) == ("ticket", "reference", True)

    def test_a_file_named_for_another_ticket_is_not_the_ticket_main(self) -> None:
        assert row_id(ticket_path("T-901.md")) is None
        assert row_id(ticket_path("T-9000.md")) is None

    @pytest.mark.parametrize("name", UNMATCHED_NAMES)
    def test_an_unmatched_name_gets_no_row(self, name: str) -> None:
        assert tool.kind_row_for(ticket_path(name)) is None

    @pytest.mark.parametrize("rel", PATHS_OUTSIDE_THE_TABLE)
    def test_a_path_outside_a_ticket_folder_gets_no_row(self, rel: str) -> None:
        assert tool.kind_row_for(rel) is None

    def test_a_value_that_is_not_a_string_gets_no_row(self) -> None:
        assert tool.kind_row_for(None) is None  # type: ignore[arg-type]
        assert tool.kind_row_for(7) is None  # type: ignore[arg-type]

    def test_the_folder_prefix_needs_its_hyphen_and_is_removed_once(self) -> None:
        assert row_id(ticket_path("T-900-spec.md")) == "K5"
        assert row_id(ticket_path("t-900-spec.md")) == "K5"
        assert row_id(ticket_path("T-9000-spec.md")) is None
        assert row_id(ticket_path("T-900-T-900-spec.md")) is None

    def test_a_star_pattern_never_reuses_a_character_for_both_ends(self) -> None:
        assert tool._pattern_matches("ab*ba", FOLDER, "abba") is True
        assert tool._pattern_matches("ab*ba", FOLDER, "abxxba") is True
        assert tool._pattern_matches("ab*ba", FOLDER, "aba") is False
        assert tool._pattern_matches("ab*", FOLDER, "ab") is True
        assert tool._pattern_matches("ab", FOLDER, "abc") is False

    def test_the_first_matching_row_wins(self) -> None:
        assert row_id(ticket_path("cursor-prompt.md")) == "K3"
        assert row_id(ticket_path("arch-review.md")) == "K3"
        assert row_id(ticket_path("session-qa-findings.md")) == "K9"

    @pytest.mark.parametrize(
        "name", ["session-notes.md", "T-900-session-notes.md", "SESSION-NOTES.MD"]
    )
    def test_the_exact_session_notes_name_is_a_ticket_summary_not_a_session_log(
        self, name: str
    ) -> None:
        assert row_id(ticket_path(name)) == "K10"
        assert row_triple(ticket_path(name)) == ("ticket", "reference", True)

    @pytest.mark.parametrize(
        "name", ["session-notes-2026-10-05.md", "T-900-session-notes-2.md", "session-notes2.md"]
    )
    def test_a_dated_or_longer_session_notes_name_stays_a_session_log(self, name: str) -> None:
        assert row_id(ticket_path(name)) == "K9"
        assert row_triple(ticket_path(name)) == ("ticket", "session_log", True)

    def test_a_name_that_only_contains_session_notes_gets_no_row(self) -> None:
        assert row_id(ticket_path("my-session-notes.md")) is None

    @pytest.mark.parametrize(
        "folder,name,kind_id,expected",
        [
            ("cursor", "cursor.md", "K3", ("ticket", "review", False)),
            ("spec", "spec.md", "K5", ("ticket", "spec", True)),
            ("session", "session.md", "K9", ("ticket", "session_log", True)),
            ("notes", "notes.md", "K10", ("ticket", "reference", True)),
        ],
    )
    def test_a_name_that_two_rows_claim_goes_to_the_earlier_row(
        self, folder: str, name: str, kind_id: str, expected: Tuple[str, str, bool]
    ) -> None:
        rel = ticket_path(name, folder)
        assert row_id(rel) == kind_id
        assert row_triple(rel) == expected

    def test_an_archive_state_file_is_k1_not_k2(self) -> None:
        row = tool.kind_row_for("02-tickets/T-900/archive/T-900-state.md")
        assert row is not None and row.kind_id == "K1"
        assert triple(row) == ("ticket", "state", False)

    @pytest.mark.parametrize("folder", ["archive", "history", "Archive", "HISTORY"])
    @pytest.mark.parametrize(
        "name,role",
        [
            ("cursor-review.md", "review"),
            ("T-900-spec.md", "spec"),
            ("design.md", "design"),
            ("T-900-qa-findings.md", "qa"),
            ("T-900-session-1.md", "session_log"),
            ("T-900-session-notes.md", FALLBACK_ROLE),
            ("T-900-session-notes-2026-10-05.md", "session_log"),
            ("mystery-note.md", FALLBACK_ROLE),
        ],
    )
    def test_an_archive_file_takes_its_role_by_name_and_is_never_indexable(
        self, folder: str, name: str, role: str
    ) -> None:
        row = tool.kind_row_for("02-tickets/T-900/{}/{}".format(folder, name))
        assert row is not None and row.kind_id == "K1"
        assert triple(row) == ("ticket", role, False)

    def test_an_archive_folder_may_sit_at_any_depth_below_the_ticket(self) -> None:
        row = tool.kind_row_for("02-tickets/T-900/sub/deeper/history/spec.md")
        assert row is not None and row.kind_id == "K1"
        assert triple(row) == ("ticket", "spec", False)

    def test_only_a_folder_named_exactly_archive_or_history_makes_k1(self) -> None:
        assert row_id("02-tickets/T-900/archive.md") is None
        assert row_id("02-tickets/T-900/archive-old/spec.md") == "K5"
        assert row_id("02-tickets/T-900/old-archive/spec.md") == "K5"

    def test_the_archive_resolution_does_not_leak_into_other_rows(self) -> None:
        assert row_triple("02-tickets/T-900/archive/cursor.md") == ("ticket", "review", False)
        assert row_triple("02-tickets/T-900/archive/spec.md") == ("ticket", "spec", False)
        assert row_triple("02-tickets/T-900/spec.md") == ("ticket", "spec", True)

    def test_row_values_follow_the_row_and_apply_the_terminal_override(self) -> None:
        row = tool.kind_row_for(ticket_path("spec.md"))
        assert row is not None
        assert tool.row_values(row, {"status": "active"}) == tool.Values("ticket", "spec", True)
        assert tool.row_values(row, {}) == tool.Values("ticket", "spec", True)
        assert tool.row_values(row, {"status": "Archived"}) == tool.Values("ticket", "spec", False)

    def test_a_row_that_is_not_indexable_stays_false_for_every_status(self) -> None:
        row = tool.kind_row_for(ticket_path("cursor.md"))
        assert row is not None
        for status in ("active", "cancelled", None):
            assert tool.row_values(row, {"status": status}).indexable is False

    def test_row_values_never_raise_on_an_odd_mapping(self) -> None:
        row = tool.kind_row_for(ticket_path("spec.md"))
        assert row is not None
        assert tool.row_values(row, None) == tool.Values("ticket", "spec", True)  # type: ignore[arg-type]


class TestKindRowsRoleByName:
    @pytest.mark.parametrize("kind_id,catalog_type,doc_role,indexable,name", NAME_CASES)
    def test_each_name_pattern_gives_its_row_role(
        self, kind_id: str, catalog_type: str, doc_role: str, indexable: bool, name: str
    ) -> None:
        assert tool.role_by_name(ticket_path(FOLDER + "-" + name)) == doc_role
        assert tool.role_by_name(ticket_path(name)) == doc_role

    def test_the_state_test_is_loosened_to_any_name_ending_in_state(self) -> None:
        assert tool.role_by_name("02-tickets/T-900/archive/other-state.md") == "state"
        assert tool.role_by_name("02-tickets/T-900/archive/T-900-STATE.md") == "state"
        assert tool.role_by_name("02-tickets/T-900/T-900-state.md") == "state"

    def test_the_ticket_main_name_gives_reference(self) -> None:
        assert tool.role_by_name(ticket_path("T-900.md")) == FALLBACK_ROLE

    @pytest.mark.parametrize("name", ["state.md", "mystery.md", "T-901-spec.md"])
    def test_an_unknown_name_gives_reference(self, name: str) -> None:
        assert tool.role_by_name(ticket_path(name)) == FALLBACK_ROLE

    @pytest.mark.parametrize("rel", PATHS_OUTSIDE_THE_TABLE)
    def test_a_path_outside_a_ticket_folder_gives_reference(self, rel: str) -> None:
        assert tool.role_by_name(rel) == FALLBACK_ROLE

    def test_a_value_that_is_not_a_string_gives_reference(self) -> None:
        assert tool.role_by_name(None) == FALLBACK_ROLE  # type: ignore[arg-type]


class TestKindRowsLoadCheck:
    def test_the_check_runs_when_the_module_loads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        source = TOOL_PATH.read_text(encoding="utf-8")
        broken = source.replace('KindRow("K2", ', 'KindRow("K7", ', 1)
        assert broken != source
        module = types.ModuleType("broken_tool_for_load_check")
        monkeypatch.setitem(sys.modules, module.__name__, module)
        with pytest.raises(ValueError, match="KIND_ROWS_INVALID"):
            exec(compile(broken, module.__name__, "exec"), module.__dict__)

    @staticmethod
    def rows(*specs: Tuple[str, Tuple[str, ...]]) -> List[Any]:
        return [
            tool.KindRow(kind_id, "ticket", "reference", True, patterns)
            for kind_id, patterns in specs
        ]

    def test_ordered_ids_with_sound_patterns_pass(self) -> None:
        tool.check_kind_rows(self.rows(("K1", ()), ("K2", ("spec.md", "cursor*"))))

    @pytest.mark.parametrize(
        "specs",
        [
            (("K1", ()), ("K1", ())),
            (("K2", ()), ("K1", ())),
            (("K1", ()), ("K3", ())),
            (("X1", ()),),
            (("K1", ()), ("K2", ("Spec.md",))),
            (("K1", ()), ("K2", ("a*b*c",))),
        ],
    )
    def test_a_bad_table_raises_a_closed_code(self, specs: Tuple[Any, ...]) -> None:
        with pytest.raises(ValueError, match="KIND_ROWS_INVALID"):
            tool.check_kind_rows(self.rows(*specs))

    def test_an_exclusion_that_is_not_lowercase_raises_a_closed_code(self) -> None:
        rows = [
            tool.KindRow("K1", "ticket", "reference", True),
            tool.KindRow("K2", "ticket", "reference", True, exclusions=("Session-Notes.md",)),
        ]
        with pytest.raises(ValueError, match="KIND_ROWS_INVALID"):
            tool.check_kind_rows(rows)

    def test_a_lowercase_exclusion_passes(self) -> None:
        tool.check_kind_rows(
            [tool.KindRow("K1", "ticket", "reference", True, exclusions=("a.md",))]
        )

    def test_the_k9_row_excludes_the_ticket_summary_name_and_k10_takes_it(self) -> None:
        rows = {row.kind_id: row for row in tool.KIND_ROWS}
        assert rows["K9"].exclusions == ("session-notes.md",)
        assert "session-notes.md" in rows["K10"].patterns


class TestTerminalStatus:
    @pytest.mark.parametrize("value", TERMINAL_VALUES)
    def test_each_terminal_value_flips(self, value: str) -> None:
        assert tool.is_terminal_status({"status": value}) is True

    @pytest.mark.parametrize("value", TERMINAL_VALUES)
    def test_mixed_case_and_padding_do_not_hide_a_terminal_value(self, value: str) -> None:
        for variant in (value.upper(), value.title(), "  " + value + "  ", "\t" + value + "\n"):
            assert tool.is_terminal_status({"status": variant}) is True, repr(variant)

    @pytest.mark.parametrize(
        "value",
        [
            "active | archived",
            "parked",
            "closed",
            "shipped",
            "active",
            "",
            "   ",
            "archived.",
            "not archived",
            "cancelled by client",
            "archive",
        ],
    )
    def test_no_other_string_is_terminal(self, value: str) -> None:
        assert tool.is_terminal_status({"status": value}) is False

    @pytest.mark.parametrize("value", [None, True, False, 0, 1.5, ["archived"], {"x": "archived"}])
    def test_a_status_that_is_not_a_string_is_not_terminal(self, value: Any) -> None:
        assert tool.is_terminal_status({"status": value}) is False

    def test_a_missing_status_or_mapping_is_not_terminal(self) -> None:
        assert tool.is_terminal_status({}) is False
        assert tool.is_terminal_status({"state": "archived"}) is False
        assert tool.is_terminal_status(None) is False  # type: ignore[arg-type]
        assert tool.is_terminal_status(["archived"]) is False  # type: ignore[arg-type]

    def test_a_parsed_status_line_is_read_by_the_same_rule(self) -> None:
        _span, parsed = prepare(doc(["status: Cancelled", "indexable: true"]))
        assert tool.is_terminal_status(parsed) is True
        _span, parsed = prepare(doc(["status: active | archived"]))
        assert tool.is_terminal_status(parsed) is False

    def test_a_terminal_status_forces_the_resolved_row_not_indexable(self) -> None:
        for value in TERMINAL_VALUES:
            row = tool.kind_row_for(ticket_path("T-900-state.md"))
            assert row is not None
            assert tool.row_values(row, {"status": value}).indexable is False


class TestTerminalStatusPlaceholder:
    PLACEHOLDER = {"catalog_type": "unknown", "doc_role": "unknown", "indexable": False}

    def test_the_exact_placeholder_triple_is_a_placeholder(self) -> None:
        assert tool.is_placeholder(dict(self.PLACEHOLDER)) is True
        assert tool.is_placeholder(dict(self.PLACEHOLDER, indexed=None)) is True
        assert tool.is_placeholder(dict(self.PLACEHOLDER, title="x")) is True

    @pytest.mark.parametrize(
        "changes",
        [
            {"indexable": True},
            {"indexable": "false"},
            {"indexable": 0},
            {"indexable": None},
            {"catalog_type": "ticket"},
            {"catalog_type": "Unknown"},
            {"catalog_type": " unknown"},
            {"catalog_type": "unknown "},
            {"catalog_type": None},
            {"doc_role": "spec"},
            {"doc_role": "UNKNOWN"},
            {"doc_role": ["unknown"]},
        ],
    )
    def test_any_change_to_the_triple_is_not_a_placeholder(self, changes: Dict[str, Any]) -> None:
        assert tool.is_placeholder(dict(self.PLACEHOLDER, **changes)) is False

    @pytest.mark.parametrize("missing", ["catalog_type", "doc_role", "indexable"])
    def test_a_missing_triple_field_is_not_a_placeholder(self, missing: str) -> None:
        fm = dict(self.PLACEHOLDER)
        del fm[missing]
        assert tool.is_placeholder(fm) is False

    def test_a_hand_set_triple_is_not_a_placeholder(self) -> None:
        fm = {"catalog_type": "ticket", "doc_role": "spec", "indexable": True, "indexed": None}
        assert tool.is_placeholder(fm) is False

    def test_an_odd_mapping_is_not_a_placeholder(self) -> None:
        assert tool.is_placeholder({}) is False
        assert tool.is_placeholder(None) is False  # type: ignore[arg-type]
        assert tool.is_placeholder("unknown") is False  # type: ignore[arg-type]

    def test_a_parsed_placeholder_block_is_read_exactly(self) -> None:
        raw = doc(["catalog_type: unknown", "doc_role: unknown", "indexable: false", "indexed: null"])
        assert tool.is_placeholder(prepare(raw)[1]) is True
        quoted = doc(["catalog_type: unknown", "doc_role: unknown", 'indexable: "false"'])
        assert tool.is_placeholder(prepare(quoted)[1]) is False


class TestCreateBlockEol:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (b"# T\nline\n", LF),
            (b"# T\r\nline\r\n", CRLF),
            (b"# T\r\nline\n", CRLF),
            (b"# T\nline\r\n", LF),
            (b"# Single line, no ending", LF),
            (b"", LF),
            (b"\n# T\r\n", LF),
            (b"\r\n", CRLF),
            (b"a\rb", LF),
            (b"a\rb\r\n", CRLF),
            (b"one\r", LF),
        ],
    )
    def test_the_first_line_ending_decides(self, raw: bytes, expected: bytes) -> None:
        assert tool.choose_eol(raw) == expected


VALUES_SPEC = tool.Values("ticket", "spec", True)
VALUES_CURSOR = tool.Values("ticket", "review", False)
BLOCK_SPEC_LF = b"---\ncatalog_type: ticket\ndoc_role: spec\nindexable: true\nindexed: null\n---\n"
BLOCK_CURSOR_LF = (
    b"---\ncatalog_type: ticket\ndoc_role: review\nindexable: false\nindexed: null\n---\n"
)
FOUR_FIELD_LINES = [
    "catalog_type: ticket", "doc_role: spec", "indexable: true", "indexed: null",
]


def crlf(data: bytes) -> bytes:
    """Return data with every line feed written as a carriage return and line feed."""
    return data.replace(LF, CRLF)


class TestCreateBlock:
    def test_render_block_writes_the_four_fields_in_order_between_delimiters(self) -> None:
        assert tool.render_block(VALUES_SPEC, LF) == BLOCK_SPEC_LF
        assert tool.render_block(VALUES_CURSOR, LF) == BLOCK_CURSOR_LF

    def test_render_block_uses_the_given_line_ending_on_every_line(self) -> None:
        block = tool.render_block(VALUES_SPEC, CRLF)
        assert block == crlf(BLOCK_SPEC_LF)
        assert block.count(CRLF) == 6
        assert block.count(LF) == 6

    def test_indexed_is_rendered_as_null(self) -> None:
        assert b"indexed: null\n" in tool.render_block(VALUES_SPEC, LF)

    def test_create_block_puts_the_block_before_every_original_byte(self) -> None:
        raw = b"# Title\nbody\n"
        assert tool.create_block(raw, BLOCK_SPEC_LF) == BLOCK_SPEC_LF + raw

    @pytest.mark.parametrize(
        "raw",
        [
            b"# Title\nbody\n",
            b"# Title\r\nbody\r\n",
            b"# Single line, no ending",
            b"# Title\nbody with no trailing newline",
            b"# Title\n\xff\xfe\x00\x80 not utf 8 \xc3\x28\n",
            b"# T\r\nline\n",
            b"# T\nline\r\n",
            b"\n# Leading blank line\n",
            b"# Title\nline with NUL \x00 inside\n",
        ],
    )
    def test_a_created_block_passes_its_own_self_check(self, raw: bytes) -> None:
        eol = tool.choose_eol(raw)
        block = tool.render_block(VALUES_SPEC, eol)
        new_raw = tool.create_block(raw, block)
        assert tool.verify_create(raw, block, new_raw, VALUES_SPEC) is True
        assert new_raw[: len(block)] == block
        assert new_raw[len(block):] == raw

    def test_the_block_uses_the_file_first_line_ending_and_no_other(self) -> None:
        lf_file = b"# T\nline\r\n"
        new_raw = tool.create_block(lf_file, tool.render_block(VALUES_SPEC, tool.choose_eol(lf_file)))
        assert new_raw == BLOCK_SPEC_LF + lf_file
        crlf_file = b"# T\r\nline\n"
        block = tool.render_block(VALUES_SPEC, tool.choose_eol(crlf_file))
        assert tool.create_block(crlf_file, block) == crlf(BLOCK_SPEC_LF) + crlf_file

    def test_a_file_with_no_line_ending_gets_a_lf_block(self) -> None:
        raw = b"# Only line"
        block = tool.render_block(VALUES_SPEC, tool.choose_eol(raw))
        assert tool.create_block(raw, block) == BLOCK_SPEC_LF + raw


UNSAFE_TOPS = [
    pytest.param(b"", id="empty"),
    pytest.param(b"\xef\xbb\xbf# Title\n", id="utf8_bom"),
    pytest.param(b"\xff\xfe#\x00", id="utf16_little_endian_bom"),
    pytest.param(b"\xfe\xff\x00#", id="utf16_big_endian_bom"),
    pytest.param(b"---\nunclosed: yes\nbody\n", id="unclosed_frontmatter"),
    pytest.param(b"---\n", id="delimiter_line_only"),
    pytest.param(b"---", id="bare_delimiter"),
    pytest.param(b"----\ntext\n", id="long_rule"),
    pytest.param(b"---\r\nunclosed: yes\r\n", id="unclosed_crlf"),
    pytest.param(b"---\nkey: value\n---\nbody\n", id="existing_frontmatter"),
]


class TestCreateBlockUnsafeTop:
    @pytest.mark.parametrize("raw", UNSAFE_TOPS)
    def test_an_unsafe_top_is_refused(self, raw: bytes) -> None:
        assert tool.is_safe_top(raw) is False

    @pytest.mark.parametrize("raw", UNSAFE_TOPS)
    def test_the_self_check_refuses_a_block_over_an_unsafe_top(self, raw: bytes) -> None:
        block = tool.render_block(VALUES_SPEC, tool.choose_eol(raw))
        new_raw = tool.create_block(raw, block)
        assert tool.verify_create(raw, block, new_raw, VALUES_SPEC) is False

    @pytest.mark.parametrize(
        "raw",
        [b"# Title\n", b"\n# Title\n", b"-- two dashes\n", b" ---\n", b"text\n---\nmore\n", b"x"],
    )
    def test_an_ordinary_top_is_safe(self, raw: bytes) -> None:
        assert tool.is_safe_top(raw) is True


class TestCreateBlockVerify:
    RAW = b"# Title\nbody line\n"

    def build(self, raw: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
        data = self.RAW if raw is None else raw
        block = tool.render_block(VALUES_SPEC, tool.choose_eol(data))
        return data, block, tool.create_block(data, block)

    def test_new_bytes_that_drop_part_of_the_original_are_refused(self) -> None:
        raw, block, new_raw = self.build()
        assert tool.verify_create(raw, block, new_raw[:-1], VALUES_SPEC) is False
        assert tool.verify_create(raw, block, block, VALUES_SPEC) is False

    def test_new_bytes_with_an_extra_byte_are_refused(self) -> None:
        raw, block, new_raw = self.build()
        assert tool.verify_create(raw, block, new_raw + b"x", VALUES_SPEC) is False

    def test_a_changed_original_byte_is_refused(self) -> None:
        raw, block, new_raw = self.build()
        changed = new_raw[:-2] + b"X" + new_raw[-1:]
        assert len(changed) == len(new_raw)
        assert tool.verify_create(raw, block, changed, VALUES_SPEC) is False

    def test_a_same_length_edit_inside_the_block_is_refused(self) -> None:
        raw, block, _new_raw = self.build()
        neutral = block.replace(b"indexed: null", b"indexed: ~   ")
        assert len(neutral) == len(block)
        assert tool.verify_create(raw, block, neutral + raw, VALUES_SPEC) is False

    def test_a_block_in_the_wrong_line_ending_is_refused(self) -> None:
        raw = b"# Title\nbody\n"
        wrong = tool.render_block(VALUES_SPEC, CRLF)
        assert tool.verify_create(raw, wrong, wrong + raw, VALUES_SPEC) is False
        raw_crlf = b"# Title\r\nbody\r\n"
        wrong_lf = tool.render_block(VALUES_SPEC, LF)
        assert tool.verify_create(raw_crlf, wrong_lf, wrong_lf + raw_crlf, VALUES_SPEC) is False

    def test_a_block_with_no_closing_delimiter_cannot_borrow_a_later_rule(self) -> None:
        raw = b"# Title\n---\nbody\n"
        open_block = BLOCK_SPEC_LF[: -len(b"---\n")]
        assert tool.verify_create(raw, open_block, open_block + raw, VALUES_SPEC) is False

    def test_a_block_with_a_second_closing_line_is_refused(self) -> None:
        raw = b"# Title\nbody\n"
        doubled = BLOCK_SPEC_LF + b"---\n"
        assert tool.verify_create(raw, doubled, doubled + raw, VALUES_SPEC) is False

    def test_a_missing_block_is_refused(self) -> None:
        raw = b"# Title\nbody\n"
        assert tool.verify_create(raw, b"", raw, VALUES_SPEC) is False

    @pytest.mark.parametrize(
        "lines",
        [
            ["catalog_type: ticket", "doc_role: design", "indexable: true", "indexed: null"],
            ["catalog_type: ticket", "doc_role: spec", "indexable: false", "indexed: null"],
            ["catalog_type: reference", "doc_role: spec", "indexable: true", "indexed: null"],
            ["catalog_type: ticket", "doc_role: spec", "indexable: true", "indexed: yes"],
            ["catalog_type: ticket", "doc_role: spec", "indexable: 1", "indexed: null"],
            ["catalog_type: ticket", "doc_role: spec", 'indexable: "true"', "indexed: null"],
            ["catalog_type: ticket", "doc_role: spec", "indexable: true", 'indexed: "null"'],
            ["catalog_type: ticket", "doc_role: spec", "indexable: true"],
            FOUR_FIELD_LINES + ["extra: 1"],
            ["doc_role: spec", "catalog_type: ticket", "indexable: true", "indexed: null"],
            ["catalog_type: ticket", "doc_role: [spec", "indexable: true", "indexed: null"],
            ["catalog_type: &a [*a]", "doc_role: spec", "indexable: true", "indexed: null"],
            [],
        ],
    )
    def test_a_block_that_does_not_parse_to_the_four_exact_fields_is_refused(
        self, lines: List[str]
    ) -> None:
        raw = b"# Title\nbody\n"
        block = doc(lines, LF, b"")
        assert tool.verify_create(raw, block, block + raw, VALUES_SPEC) is False

    def test_a_value_that_would_inject_a_line_is_refused(self) -> None:
        raw = b"# Title\nbody\n"
        hostile = tool.Values("ticket\nextra: 1", "spec", True)
        block = tool.render_block(hostile, LF)
        assert tool.verify_create(raw, block, block + raw, hostile) is False

    def test_values_that_do_not_match_the_block_are_refused(self) -> None:
        raw, block, new_raw = self.build()
        assert tool.verify_create(raw, block, new_raw, VALUES_CURSOR) is False

    def test_odd_bytes_never_raise(self) -> None:
        for raw in (b"\x00", b"\xff" * 64, b"\r", b"\r\n\r\n", b"---\x00"):
            block = tool.render_block(VALUES_SPEC, tool.choose_eol(raw))
            assert tool.verify_create(raw, block, block + raw, VALUES_SPEC) in (True, False)


FLIP_LINES = ["catalog_type: ticket", "doc_role: state", "indexable: true", "indexed: null"]
FLIP_EDIT = [("indexable", "true", "false")]
FLIP_EXPECTED = {"indexable": False}
REWRITE_LINES = ["title: Example", "catalog_type: unknown", "doc_role: unknown", "indexable: false"]
REWRITE_EDITS = [
    ("catalog_type", "unknown", "ticket"),
    ("doc_role", "unknown", "spec"),
    ("indexable", "false", "true"),
]
REWRITE_EXPECTED = {"catalog_type": "ticket", "doc_role": "spec", "indexable": True}
NOTE_LINES = ["title: Example", "indexable: true", "note: kept"]


def changed_line_count(before: bytes, after: bytes) -> int:
    """Count the lines that differ between two files with the same number of lines."""
    old_lines = before.split(LF)
    new_lines = after.split(LF)
    assert len(old_lines) == len(new_lines)
    return sum(1 for old, new in zip(old_lines, new_lines) if old != new)


class TestReplaceLines:
    def test_field_line_span_returns_the_offsets_of_the_one_line(self) -> None:
        raw = doc(["a: 1", "indexable: true", "b: 2"])
        span, _ = prepare(raw)
        located = tool.field_line_span(span, "indexable")
        assert located == (9, 25)
        assert raw[9:25] == b"indexable: true\n"

    def test_field_line_span_keeps_the_carriage_return_in_the_line(self) -> None:
        raw = doc(["a: 1", "indexable: true", "b: 2"], CRLF)
        span, _ = prepare(raw)
        located = tool.field_line_span(span, "indexable")
        assert located == (11, 28)
        assert raw[11:28] == b"indexable: true\r\n"

    def test_field_line_span_finds_the_first_and_the_last_line_of_a_block(self) -> None:
        raw = doc(["indexable: true", "b: 2", "c: 3"])
        span, _ = prepare(raw)
        assert tool.field_line_span(span, "indexable") == (4, 20)
        assert tool.field_line_span(span, "c") == (25, 30)
        assert raw[25:30] == b"c: 3\n"

    @pytest.mark.parametrize(
        "lines",
        [
            ["a: 1", "b: 2"],
            ["indexable: true", "indexable: true"],
            ["indexable: true", "x: 1", "indexable: false"],
            ["parent:", "  indexable: true"],
            ['"indexable": true'],
            ["indexable_extra: true"],
            ["indexed: null"],
        ],
    )
    def test_a_field_line_is_found_only_when_exactly_one_column_zero_line_matches(
        self, lines: List[str]
    ) -> None:
        span, _ = prepare(doc(lines))
        assert tool.field_line_span(span, "indexable") is None

    def test_a_nested_line_with_the_same_name_is_ignored(self) -> None:
        raw = doc(["indexable: true", "nested:", "  indexable: false"])
        span, _ = prepare(raw)
        assert tool.field_line_span(span, "indexable") == (4, 20)

    @pytest.mark.parametrize("name", ["", "\ud800", "a\nb"])
    def test_an_unusable_name_gives_none_and_never_raises(self, name: str) -> None:
        raw = doc([": odd", "a: 1"])
        span = tool.split_frontmatter(raw)
        assert tool.field_line_span(span, name) is None

    def test_a_flip_replaces_one_line_and_leaves_every_other_byte(self) -> None:
        raw = doc(NOTE_LINES, LF, b"body\nmore\n")
        span, _ = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw == doc(["title: Example", "indexable: false", "note: kept"], LF, b"body\nmore\n")

    def test_a_flip_in_a_crlf_file_keeps_crlf(self) -> None:
        raw = doc(NOTE_LINES, CRLF)
        span, _ = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw == doc(["title: Example", "indexable: false", "note: kept"], CRLF)
        assert b"\n" not in new_raw.replace(CRLF, b"")

    def test_a_rewrite_replaces_exactly_the_three_named_lines(self) -> None:
        raw = doc(REWRITE_LINES, LF, b"body\n")
        span, _ = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, REWRITE_EDITS)
        expected = doc(
            ["title: Example", "catalog_type: ticket", "doc_role: spec", "indexable: true"],
            LF, b"body\n",
        )
        assert new_raw == expected
        assert changed_line_count(raw, new_raw) == 3

    def test_a_rewrite_to_a_false_row_replaces_two_lines_and_not_three(self) -> None:
        raw = doc(REWRITE_LINES)
        span, _ = prepare(raw)
        edits = REWRITE_EDITS[:2]
        new_raw = tool.replace_field_lines(raw, span, edits)
        assert new_raw is not None
        assert changed_line_count(raw, new_raw) == 2
        assert b"indexable: false\n" in new_raw

    def test_edits_given_in_any_order_give_the_same_bytes(self) -> None:
        raw = doc(REWRITE_LINES)
        span, _ = prepare(raw)
        forward = tool.replace_field_lines(raw, span, REWRITE_EDITS)
        backward = tool.replace_field_lines(raw, span, list(reversed(REWRITE_EDITS)))
        assert forward is not None and forward == backward

    @pytest.mark.parametrize(
        "line",
        [
            "indexable: True",
            'indexable: "true"',
            "indexable: 'true'",
            "indexable: true # keep",
            "indexable:  true",
            "indexable:true",
            "indexable: true ",
            "indexable: yes",
            "indexable : true",
            "indexable: false",
        ],
    )
    def test_a_flip_line_in_any_other_form_is_refused(self, line: str) -> None:
        raw = doc(["a: 1", line, "b: 2"])
        assert tool.replace_field_lines(raw, span_of(raw), FLIP_EDIT) is None

    def test_a_yaml_alias_of_the_old_value_is_refused(self) -> None:
        raw = doc(["indexable: no"])
        span, _ = prepare(raw)
        assert tool.replace_field_lines(raw, span, [("indexable", "false", "true")]) is None

    def test_two_indexable_lines_refuse_the_edit(self) -> None:
        raw = doc(["indexable: true", "b: 1", "indexable: true"])
        span, _ = prepare(raw)
        assert tool.replace_field_lines(raw, span, FLIP_EDIT) is None

    def test_a_missing_line_refuses_the_edit(self) -> None:
        raw = doc(["a: 1"])
        span, _ = prepare(raw)
        assert tool.replace_field_lines(raw, span, FLIP_EDIT) is None

    def test_one_refused_edit_refuses_the_whole_call(self) -> None:
        raw = doc(["title: Example", "indexable: true", "doc_role: spec"])
        span, _ = prepare(raw)
        edits = [("indexable", "true", "false"), ("doc_role", "unknown", "spec")]
        assert tool.replace_field_lines(raw, span, edits) is None

    def test_a_target_line_with_a_different_ending_than_the_file_is_refused(self) -> None:
        crlf_file = b"---\r\na: 1\r\nindexable: true\nb: 2\r\n---\r\nbody\r\n"
        span, _ = prepare(crlf_file)
        assert span.eol == CRLF
        assert tool.replace_field_lines(crlf_file, span, FLIP_EDIT) is None
        lf_file = b"---\nindexable: true\r\nb: 2\n---\nbody\n"
        span, _ = prepare(lf_file)
        assert span.eol == LF
        assert tool.replace_field_lines(lf_file, span, FLIP_EDIT) is None

    def test_no_edits_refuse(self) -> None:
        raw = doc(NOTE_LINES)
        span, _ = prepare(raw)
        assert tool.replace_field_lines(raw, span, []) is None

    def test_two_edits_on_one_line_refuse(self) -> None:
        raw = doc(NOTE_LINES)
        span, _ = prepare(raw)
        edits = [("indexable", "true", "false"), ("indexable", "true", "False")]
        assert tool.replace_field_lines(raw, span, edits) is None

    def test_an_edit_that_changes_nothing_refuses(self) -> None:
        raw = doc(NOTE_LINES)
        span, _ = prepare(raw)
        assert tool.replace_field_lines(raw, span, [("indexable", "true", "true")]) is None

    @pytest.mark.parametrize("new", ["false\nextra: 1", "false\r", "false\r\nextra: 1"])
    def test_a_new_value_with_a_line_break_refuses(self, new: str) -> None:
        raw = doc(NOTE_LINES)
        span, _ = prepare(raw)
        assert tool.replace_field_lines(raw, span, [("indexable", "true", new)]) is None

    @pytest.mark.parametrize(
        "edit",
        [
            ["indexable", "true", "false"],
            ("indexable", "true"),
            ("indexable", "true", "false", "extra"),
            ("indexable", True, "false"),
            ("indexable", "true", None),
            (None, "true", "false"),
            ("indexable", "true", "\ud800"),
            ("\ud800", "true", "false"),
            "indexable",
            None,
        ],
    )
    def test_a_malformed_edit_refuses_and_never_raises(self, edit: Any) -> None:
        raw = doc(NOTE_LINES)
        span, _ = prepare(raw)
        assert tool.replace_field_lines(raw, span, [edit]) is None

    def test_a_span_that_describes_other_bytes_is_refused(self) -> None:
        raw_a = doc(["indexable: true", "x: 1"])
        raw_b = doc(["indexable: true", "x: 2"])
        span_a, _ = prepare(raw_a)
        assert tool.replace_field_lines(raw_a, span_a, FLIP_EDIT) is not None
        assert tool.replace_field_lines(raw_b, span_a, FLIP_EDIT) is None

    def test_the_original_bytes_are_never_modified_in_place(self) -> None:
        raw = bytes(doc(NOTE_LINES))
        snapshot = bytes(raw)
        span, _ = prepare(raw)
        tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert raw == snapshot


def check_replace(
    raw: bytes, edits: Sequence[Tuple[str, str, str]], expected: Dict[str, Any]
) -> Tuple[bytes, bool]:
    """Replace, then run the self check with the file's own parsed mapping."""
    span, parsed = prepare(raw)
    new_raw = tool.replace_field_lines(raw, span, edits)
    assert new_raw is not None
    return new_raw, tool.verify_replace(raw, span, edits, new_raw, parsed, expected)


class TestReplaceLinesVerify:
    def test_a_flip_passes_its_own_self_check(self) -> None:
        assert check_replace(doc(NOTE_LINES), FLIP_EDIT, FLIP_EXPECTED)[1] is True

    def test_a_crlf_flip_passes_its_own_self_check(self) -> None:
        assert check_replace(doc(NOTE_LINES, CRLF), FLIP_EDIT, FLIP_EXPECTED)[1] is True

    def test_a_rewrite_passes_its_own_self_check(self) -> None:
        assert check_replace(doc(REWRITE_LINES), REWRITE_EDITS, REWRITE_EXPECTED)[1] is True

    def test_a_replace_that_touches_another_line_is_refused(self) -> None:
        raw = doc(NOTE_LINES)
        span, parsed = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw is not None
        for tampered in (
            new_raw.replace(b"note: kept", b"note: gone"),
            new_raw.replace(b"title: Example", b"title:  Example"),
            new_raw.replace(b"body\n", b"body!\n"),
            new_raw + b"tail\n",
            new_raw[:-1],
            LF + new_raw,
        ):
            assert tool.verify_replace(raw, span, FLIP_EDIT, tampered, parsed, FLIP_EXPECTED) is False

    def test_a_same_length_edit_that_parses_the_same_before_the_line_is_refused(self) -> None:
        raw = doc(["a:  1", "b: 2", "indexable: true"])
        span, parsed = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw is not None
        moved = new_raw.replace(b"a:  1\nb: 2", b"a: 1\nb:  2")
        assert len(moved) == len(new_raw) and moved != new_raw
        assert tool.verify_replace(raw, span, FLIP_EDIT, moved, parsed, FLIP_EXPECTED) is False

    def test_a_replace_that_changes_nothing_is_refused(self) -> None:
        raw = doc(NOTE_LINES)
        span, parsed = prepare(raw)
        assert tool.verify_replace(raw, span, FLIP_EDIT, raw, parsed, FLIP_EXPECTED) is False

    def test_a_replaced_line_that_lost_its_line_ending_style_is_refused(self) -> None:
        raw = doc(NOTE_LINES, CRLF)
        span, parsed = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw is not None
        lf_line = new_raw.replace(b"indexable: false\r\n", b"indexable: false\n")
        assert tool.verify_replace(raw, span, FLIP_EDIT, lf_line, parsed, FLIP_EXPECTED) is False

    def test_a_replaced_line_that_differs_from_the_plan_is_refused(self) -> None:
        raw = doc(NOTE_LINES)
        span, parsed = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw is not None
        same_meaning = new_raw.replace(b"indexable: false", b"indexable: False")
        assert tool.verify_replace(raw, span, FLIP_EDIT, same_meaning, parsed, FLIP_EXPECTED) is False

    def test_the_expected_values_must_match_by_type_and_value(self) -> None:
        raw = doc(NOTE_LINES)
        for wrong in ({"indexable": 0}, {"indexable": "false"}, {"indexable": True}):
            _new_raw, ok = check_replace(raw, FLIP_EDIT, wrong)
            assert ok is False, wrong

    def test_the_expected_keys_must_be_exactly_the_edited_fields(self) -> None:
        raw = doc(NOTE_LINES)
        _new_raw, extra = check_replace(raw, FLIP_EDIT, {"indexable": False, "note": "kept"})
        assert extra is False
        _new_raw, missing = check_replace(raw, [("indexable", "true", "True")], {})
        assert missing is False

    def test_a_mapping_that_differs_from_the_file_is_refused(self) -> None:
        raw = doc(NOTE_LINES)
        span, parsed = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw is not None
        changed = dict(parsed, title="Other")
        assert tool.verify_replace(raw, span, FLIP_EDIT, new_raw, changed, FLIP_EXPECTED) is False
        fewer = {key: value for key, value in parsed.items() if key != "note"}
        assert tool.verify_replace(raw, span, FLIP_EDIT, new_raw, fewer, FLIP_EXPECTED) is False

    def test_a_replacement_that_breaks_the_frontmatter_is_refused_before_any_comparison(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        raw = doc(NOTE_LINES)
        span, parsed = prepare(raw)
        edits = [("indexable", "true", "[unclosed")]
        new_raw = tool.replace_field_lines(raw, span, edits)
        assert new_raw is not None
        with caplog.at_level(logging.DEBUG, logger=tool.__name__):
            result = tool.verify_replace(raw, span, edits, new_raw, parsed, {"indexable": 1})
        assert result is False
        assert "comparison failed" not in " ".join(r.getMessage() for r in caplog.records)

    def test_edits_the_replacer_would_refuse_fail_the_self_check(self) -> None:
        raw = doc(["a: 1", "indexable: True"])
        span, parsed = prepare(raw)
        assert tool.verify_replace(raw, span, FLIP_EDIT, raw, parsed, FLIP_EXPECTED) is False
        assert tool.verify_replace(raw, span, [], raw, parsed, {}) is False

    def test_a_span_that_describes_other_bytes_fails_the_self_check(self) -> None:
        raw_a = doc(["indexable: true", "x: 1"])
        raw_b = doc(["indexable: true", "x: 2"])
        span_a, _ = prepare(raw_a)
        _span_b, parsed_b = prepare(raw_b)
        new_b = raw_b.replace(b"indexable: true", b"indexable: false")
        assert tool.verify_replace(raw_b, span_a, FLIP_EDIT, new_b, parsed_b, FLIP_EXPECTED) is False

    def test_a_mapping_that_is_not_a_dict_fails_without_raising(self) -> None:
        raw = doc(NOTE_LINES)
        span, parsed = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw is not None
        assert tool.verify_replace(raw, span, FLIP_EDIT, new_raw, None, FLIP_EXPECTED) is False  # type: ignore[arg-type]
        assert tool.verify_replace(raw, span, FLIP_EDIT, new_raw, parsed, None) is False  # type: ignore[arg-type]

    def test_a_comparison_that_raises_counts_as_a_failed_check(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        lines = ["loop: &loop [*loop]", "indexable: true", "note: " + CANARY]
        raw = doc(lines)
        span, parsed = prepare(raw)
        new_raw = tool.replace_field_lines(raw, span, FLIP_EDIT)
        assert new_raw is not None
        with caplog.at_level(logging.DEBUG, logger=tool.__name__):
            result = tool.verify_replace(raw, span, FLIP_EDIT, new_raw, parsed, FLIP_EXPECTED)
        assert result is False
        text = " ".join(record.getMessage() for record in caplog.records)
        assert "RecursionError" in text
        assert CANARY not in text


IMPORT_ALLOWLIST = frozenset(
    {
        "argparse", "dataclasses", "json", "logging", "os", "pathlib", "re", "shutil",
        "subprocess", "sys", "tempfile", "typing", "yaml", "core",
    }
)
FORBIDDEN_ROOTS = (
    "socket", "ssl", "http", "requests", "httpx", "anthropic", "openai", "torch",
    "transformers", "chromadb", "sentence_transformers", "ollama",
)
FORBIDDEN_DOTTED = ("urllib.request",)
MAX_FUNCTION_LINES = 40
HEADER_LABELS = (
    "# Module:", "# Description:", "# Author:", "# Date:", "# Scope:",
    "# ChangeLog:",
)
HEADER_SCAN_LINES = 40
UNFINISHED_MARKER = "TO" + "DO"


def import_violations(source: str) -> List[str]:
    """Return a note for every import, anywhere in source, outside the allowlist."""
    found: List[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = ["." * node.level + (node.module or "")]
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__":
            names = ["__import__"]
        else:
            continue
        found.extend(
            "line {}: {}".format(node.lineno, name)
            for name in names
            if name.split(".")[0] not in IMPORT_ALLOWLIST
        )
    return found


def missing_annotations(node: Any) -> List[str]:
    """Return the names of the return value and arguments of a function that lack a hint."""
    args = node.args
    every = args.posonlyargs + args.args + args.kwonlyargs
    every += [arg for arg in (args.vararg, args.kwarg) if arg is not None]
    gaps = [arg.arg for arg in every if arg.annotation is None and arg.arg not in ("self", "cls")]
    if node.returns is None:
        gaps.append("return")
    return gaps


def standards_violations(source: str) -> List[str]:
    """Return one note per function without hints, over the length limit, or per print call."""
    found: List[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if length > MAX_FUNCTION_LINES:
                found.append("{} is {} lines".format(node.name, length))
            gaps = missing_annotations(node)
            if gaps:
                found.append("{} lacks hints for {}".format(node.name, gaps))
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print":
            found.append("print call on line {}".format(node.lineno))
    return found


def header_violations(source: str) -> List[str]:
    """Return the header labels missing from the top of source, and any unfinished marker."""
    head = "\n".join(source.splitlines()[:HEADER_SCAN_LINES])
    found = ["missing {}".format(label) for label in HEADER_LABELS if label not in head]
    for number, line in enumerate(source.splitlines(), start=1):
        if UNFINISHED_MARKER in line:
            found.append("unfinished marker on line {}".format(number))
    return found


def function_source(total_lines: int) -> str:
    """Return a function named f whose definition spans exactly total_lines lines."""
    return "def f() -> None:\n" + "    x = 0\n" * (total_lines - 1)


def python39_violations(source: str) -> List[str]:
    """Return a note for each match statement and each vertical bar union in an annotation."""
    tree = ast.parse(source)
    found: List[str] = []
    annotations: List[Any] = []
    for node in ast.walk(tree):
        if type(node).__name__ == "Match":
            found.append("match statement on line {}".format(node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            every = args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]
            annotations += [arg.annotation for arg in every if arg is not None]
            annotations.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
    for annotation in [item for item in annotations if item is not None]:
        for inner in ast.walk(annotation):
            if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.BitOr):
                found.append("union with a vertical bar on line {}".format(inner.lineno))
    return found


class TestLocalOnlyImports:
    def test_the_tool_imports_only_the_allowlist(self) -> None:
        assert import_violations(TOOL_PATH.read_text(encoding="utf-8")) == []

    def test_the_check_flags_a_network_or_model_import_even_inside_a_function(self) -> None:
        sources = [
            "import socket\n",
            "from urllib import request\n",
            "import urllib.request\n",
            "def f() -> None:\n    import requests\n",
            "def f() -> None:\n    from anthropic import Anthropic\n",
            "from . import sibling\n",
            "x = __import__('socket')\n",
        ]
        for source in sources:
            assert import_violations(source) != [], source

    def test_the_check_accepts_an_allowed_import_anywhere(self) -> None:
        source = "import os\nfrom typing import Any\ndef f() -> None:\n    import core\n"
        assert import_violations(source) == []


RUNTIME_PROBE = """
import json, sys
sys.path.insert(0, {root!r})
{preload}
import backfill_vault_frontmatter
roots = {roots!r}
dotted = {dotted!r}
hits = sorted(
    name for name in sys.modules
    if name.split('.')[0] in roots or any(name == d or name.startswith(d + '.') for d in dotted)
)
sys.stdout.write(json.dumps(hits))
"""


def loaded_forbidden_modules(preload: str) -> List[str]:
    """Import the tool in a fresh interpreter and list the forbidden modules it loaded."""
    code = RUNTIME_PROBE.format(
        root=str(TOOL_PATH.parent), preload=preload,
        roots=FORBIDDEN_ROOTS, dotted=FORBIDDEN_DOTTED,
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        capture_output=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")[-300:]
    loaded: List[str] = json.loads(result.stdout.decode("utf-8"))
    return loaded


class TestLocalOnlyRuntime:
    def test_a_fresh_interpreter_loads_no_network_or_model_module(self) -> None:
        assert loaded_forbidden_modules("") == []

    def test_the_probe_does_see_a_forbidden_module_when_one_is_loaded(self) -> None:
        hits = loaded_forbidden_modules("import socket")
        assert "socket" in hits


class TestLocalOnlyStandards:
    @pytest.mark.parametrize("path", [TOOL_PATH, THIS_PATH], ids=["tool", "tests"])
    def test_functions_are_typed_short_and_never_print(self, path: Path) -> None:
        assert standards_violations(path.read_text(encoding="utf-8")) == []

    @pytest.mark.parametrize("path", [TOOL_PATH, THIS_PATH], ids=["tool", "tests"])
    def test_the_file_carries_the_header_block_and_no_unfinished_marker(self, path: Path) -> None:
        assert header_violations(path.read_text(encoding="utf-8")) == []

    def test_the_length_check_flags_a_function_one_line_over_the_limit(self) -> None:
        over = MAX_FUNCTION_LINES + 1
        assert standards_violations(function_source(over)) == ["f is {} lines".format(over)]
        assert standards_violations(function_source(MAX_FUNCTION_LINES)) == []

    def test_the_hint_check_flags_each_missing_hint(self) -> None:
        assert standards_violations("def f(a, b: int):\n    return 1\n") == [
            "f lacks hints for ['a', 'return']"
        ]
        assert standards_violations("class C:\n    def m(self, *rest, **kw) -> None:\n        pass\n") != []
        assert standards_violations("class C:\n    def m(self) -> None:\n        pass\n") == []

    def test_the_print_check_flags_a_print_call(self) -> None:
        assert standards_violations("def f() -> None:\n    print('x')\n") == ["print call on line 2"]

    def test_the_header_check_flags_a_missing_label_and_an_unfinished_marker(self) -> None:
        assert header_violations("# Module: x\n") != []
        full = "".join("{} x\n".format(label) for label in HEADER_LABELS)
        assert header_violations(full) == []
        assert header_violations(full + "# " + UNFINISHED_MARKER + " later\n") == [
            "unfinished marker on line {}".format(len(HEADER_LABELS) + 1)
        ]


class TestLocalOnlyPython39:
    @pytest.mark.parametrize("path", [TOOL_PATH, THIS_PATH], ids=["tool", "tests"])
    def test_no_match_statement_and_no_bar_union_in_an_annotation(self, path: Path) -> None:
        assert python39_violations(path.read_text(encoding="utf-8")) == []

    def test_the_check_flags_a_bar_union_in_each_annotation_position(self) -> None:
        sources = [
            "def f(x: int | None) -> None:\n    pass\n",
            "def f(x: int) -> str | None:\n    pass\n",
            "x: int | None = None\n",
            "def f(*a: int | str) -> None:\n    pass\n",
        ]
        for source in sources:
            assert python39_violations(source) != [], source

    def test_the_check_ignores_a_bar_outside_an_annotation(self) -> None:
        assert python39_violations("def f(a: int, b: int) -> int:\n    return a | b\n") == []

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="match needs Python 3.10 to parse")
    def test_the_check_flags_a_match_statement(self) -> None:
        source = "def f(x: int) -> int:\n    match x:\n        case 1:\n            return 1\n    return 0\n"
        assert python39_violations(source) != []


# ---------------------------------------------------------------------------
# Block B-02: fixture vaults, run helpers, and the run mode tests
# ---------------------------------------------------------------------------

GIT_LEAK_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX",
    "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE",
)
FIXTURE_USER = "Fixture User"
FIXTURE_EMAIL = "fixture@example.invalid"
FIXTURE_IGNORE_RULES = b"ignored/\n*.ignored.md\n"
FIXTURE_COMMIT_MESSAGE = "fixture commit"
GIT_DIR_NAME = ".git"
READ_ONLY_FILE_MODE = 0o444
TEMP_NAME_PREFIX = "backfill_vault_frontmatter_"
FATAL_PREFIX = "fatal precondition, nothing written: "
ALLOWED_GIT_COMMANDS = {"ls-files", "diff", "status"}
RUN_ADD_FLIP = 1
RUN_CREATE = 2
RUN_REWRITE = 3
ALL_RUNS = (RUN_ADD_FLIP, RUN_CREATE, RUN_REWRITE)
CLASS_NAMES = ("add", "create", "flip", "rewrite")
REPORT_KEYS = {
    "mode", "run", "tree", "counts", "by_class", "by_kind", "flips_by_status",
    "skipped_by_reason", "skipped", "writes", "complete_differs", "dispositions",
    "not_labeled", "exclusions",
}
COUNT_KEYS = {
    "scanned", "not_target", "classified", "already_complete", "written", "changed",
    "skipped", "result_true", "result_false",
}
WRITE_ENTRY_KEYS = {"path", "class", "kind", "added", "changes"}
NOT_LABELED = ["05-conversations", "06-chat-threads"]
S257_EXCLUSIONS = ["memory/"]
FOLDER_ABSENT_STATUS = "active"

# Source: the spec, Policy Table, as one fixture file per kind row, re-typed as
# literals. Columns: kind id, file name below 02-tickets/T-900, expected triple.
KIND_FIXTURES: List[Tuple[str, str, Tuple[str, str, bool]]] = [
    ("K1", "archive/T-900-spec.md", ("ticket", "spec", False)),
    ("K2", "T-900-state.md", ("ticket", "state", True)),
    ("K3", "cursor-review.md", ("ticket", "review", False)),
    ("K4", "prompt-b01.md", ("ticket", "reference", False)),
    ("K5", "spec.md", ("ticket", "spec", True)),
    ("K6", "design.md", ("ticket", "design", True)),
    ("K7", "qa-findings.md", ("ticket", "qa", True)),
    ("K8", "edge-case-validation.md", ("ticket", "qa", True)),
    ("K9", "session-2026-10-05.md", ("ticket", "session_log", True)),
    ("K10", "T-900.md", ("ticket", "reference", True)),
    ("K11", "context.md", ("ticket", "reference", True)),
    ("K12", "shipped.md", ("ticket", "reference", True)),
    ("K13", "handoff.md", ("ticket", "reference", True)),
]
UNMATCHED_FIXTURE = "scratch-notes.md"
SPEC_FIXTURE = "spec.md"
SPEC_TRIPLE = ("ticket", "spec", True)
REVIEW_FIXTURE = "cursor-review.md"
REVIEW_TRIPLE = ("ticket", "review", False)

KITCHEN_INCOMPLETE = doc(["title: Fixture", "status: active"])
KITCHEN_BARE = b"# Heading\nBody text.\n"
KITCHEN_PLACEHOLDER = doc([
    "title: Fixture", "doc_type: legacy-note", "catalog_type: unknown",
    "doc_role: unknown", "indexable: false", "indexed: null",
])
KITCHEN_CONTENT = {
    RUN_ADD_FLIP: KITCHEN_INCOMPLETE,
    RUN_CREATE: KITCHEN_BARE,
    RUN_REWRITE: KITCHEN_PLACEHOLDER,
}


def isolate_git(mp: pytest.MonkeyPatch, base: Path) -> None:
    """Make git read no user or system config and never search above base for a repository.

    The tool's own git calls inherit this process environment, so patching it here
    isolates both the fixture commands and the code under test.
    """
    home = base / "home"
    home.mkdir(exist_ok=True)
    for name in GIT_LEAK_VARS:
        mp.delenv(name, raising=False)
    mp.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    mp.setenv("GIT_CONFIG_NOSYSTEM", "1")
    mp.setenv("HOME", str(home))
    mp.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    mp.setenv("GIT_CEILING_DIRECTORIES", str(base))


class RunVault:
    """A throwaway vault folder under a pytest temp folder, backed by an isolated git repo."""

    def __init__(self, root: Path, out: Path) -> None:
        self.root = root
        self.out = out

    def git(self, *args: str) -> str:
        """Run one git command in the vault with a fixed identity and no signing or CRLF rewrite."""
        command = [
            "git", "-c", "user.name=" + FIXTURE_USER, "-c", "user.email=" + FIXTURE_EMAIL,
            "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args,
        ]
        done = subprocess.run(command, cwd=str(self.root), check=True, capture_output=True)
        return done.stdout.decode("utf-8", "replace")

    def init(self) -> None:
        """Create the folders, the repository, and an initial commit holding the ignore rules."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.out.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q")
        self.write(".gitignore", FIXTURE_IGNORE_RULES)
        self.commit_all()

    def write(self, rel: str, content: bytes, mode: Optional[int] = None) -> Path:
        """Write bytes at a vault relative path, creating folders, optionally setting the mode."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if mode is not None:
            path.chmod(mode)
        return path

    def read(self, rel: str) -> bytes:
        """Return the bytes of a vault relative path."""
        return (self.root / rel).read_bytes()

    def symlink(self, rel: str, target: str) -> Path:
        """Create a symlink at rel pointing at target."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        return path

    def commit_all(self) -> None:
        """Stage everything and commit. An empty commit is allowed so HEAD always exists."""
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", FIXTURE_COMMIT_MESSAGE)

    def status(self) -> str:
        """Return git status in the stable porcelain form."""
        return self.git("status", "--porcelain")


@pytest.fixture
def rv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunVault:
    """A fresh isolated git vault at tmp_path/vault, with an output folder beside it."""
    isolate_git(monkeypatch, tmp_path)
    vault = RunVault(tmp_path / "vault", tmp_path / "out")
    vault.init()
    return vault


def sha_of(raw: bytes) -> str:
    """Return the sha256 hex digest of raw."""
    return hashlib.sha256(raw).hexdigest()


def snapshot(root: Path) -> Dict[str, Tuple[str, int]]:
    """Content hash and st_mtime_ns of every regular file under root, skipping .git."""
    result: Dict[str, Tuple[str, int]] = {}
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [name for name in dirnames if name != GIT_DIR_NAME]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            result[str(path.relative_to(root))] = (sha_of(path.read_bytes()), path.stat().st_mtime_ns)
    return result


def hashes(root: Path, rels: Sequence[str]) -> Dict[str, str]:
    """Return the sha256 of each vault relative path, read through a link when it is one."""
    return {rel: sha_of((root / rel).read_bytes()) for rel in rels}


def four_lines(triple: Tuple[str, str, bool], eol: bytes = LF) -> bytes:
    """The four field lines a row gives a file, typed here and never read from the tool."""
    text = "catalog_type: {}\ndoc_role: {}\nindexable: {}\nindexed: null\n".format(
        triple[0], triple[1], "true" if triple[2] else "false"
    )
    return text.encode("utf-8").replace(LF, eol)


def expected_add(triple: Tuple[str, str, bool]) -> bytes:
    """A KITCHEN_INCOMPLETE file after an add: the four lines sit above the closing delimiter."""
    return b"---\ntitle: Fixture\nstatus: active\n" + four_lines(triple) + b"---\nbody\n"


def expected_create(triple: Tuple[str, str, bool]) -> bytes:
    """A KITCHEN_BARE file after a create: the block, then every original byte."""
    return b"---\n" + four_lines(triple) + b"---\n" + KITCHEN_BARE


def expected_rewrite(triple: Tuple[str, str, bool]) -> bytes:
    """A KITCHEN_PLACEHOLDER file after a rewrite: the three lines replaced, indexed untouched."""
    return b"---\ntitle: Fixture\ndoc_type: legacy-note\n" + four_lines(triple) + b"---\nbody\n"


EXPECTED_BY_RUN = {
    RUN_ADD_FLIP: expected_add,
    RUN_CREATE: expected_create,
    RUN_REWRITE: expected_rewrite,
}


def parse_front(raw: bytes) -> Dict[str, Any]:
    """Parse the frontmatter of file bytes without the tool. The file must start with a block."""
    lines = raw.decode("utf-8", "replace").splitlines(keepends=True)
    assert lines[0].rstrip("\r\n") == "---", "no opening delimiter"
    end = next(i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---")
    loaded = yaml.safe_load("".join(lines[1:end]))
    return loaded if loaded is not None else {}


def triple_of(raw: bytes) -> Tuple[Any, Any, Any]:
    """The catalog_type, doc_role, and indexable of a labeled file, with exact types checked."""
    front = parse_front(raw)
    assert all(name in front for name in ("catalog_type", "doc_role", "indexable", "indexed"))
    assert front["indexed"] is None
    assert isinstance(front["catalog_type"], str) and isinstance(front["doc_role"], str)
    assert isinstance(front["indexable"], bool)
    return front["catalog_type"], front["doc_role"], front["indexable"]


def build_kitchen(vault: RunVault, content: bytes) -> None:
    """Write one file per kind row and one unmatched file, all with the same content, and commit."""
    for _kind, name, _triple in KIND_FIXTURES:
        vault.write(ticket_path(name), content)
    vault.write(ticket_path(UNMATCHED_FIXTURE), content)
    vault.commit_all()


def preview(vault: RunVault, run: int) -> Dict[str, Any]:
    """Plan one run and return its report. Nothing is written."""
    return tool.run_policy(vault.root, run, False, None)


def as_approved(report: Dict[str, Any]) -> Dict[str, Any]:
    """Return the report as it would read back from a saved JSON file."""
    loaded: Dict[str, Any] = json.loads(json.dumps(report))
    return loaded


def apply_run(
    vault: RunVault, run: int, approved: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Apply one run against an approved report, by default the run's own fresh preview."""
    wanted = as_approved(preview(vault, run)) if approved is None else approved
    return tool.run_policy(vault.root, run, True, wanted)


def plan_one(vault: RunVault, rel: str, run: int) -> Any:
    """Plan one file for one run against a fresh git snapshot."""
    return tool.plan_run_file(vault.root, rel, tool.load_git_state(vault.root), run)


def skip_codes(report: Dict[str, Any]) -> Dict[str, str]:
    """Map each skipped path to its reason code."""
    return {entry["path"]: entry["reason"] for entry in report["skipped"]}


def write_entries(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Map each planned write path to its report entry."""
    return {entry["path"]: entry for entry in report["writes"]}


def cli_args(
    root: Path,
    run: Optional[int] = None,
    apply: bool = False,
    approved: Optional[Path] = None,
    report_path: Optional[Path] = None,
) -> List[str]:
    """Build the argument list for main. The vault root is always explicit."""
    args = ["--vault-root", str(root)]
    if run is not None:
        args.extend(["--run", str(run)])
    if apply:
        args.append("--apply")
    if approved is not None:
        args.extend(["--approved-report", str(approved)])
    if report_path is not None:
        args.extend(["--report-path", str(report_path)])
    return args


def run_main(
    capsys: pytest.CaptureFixture, args: List[str]
) -> Tuple[int, str, str]:
    """Run main and return the exit code with the raw stdout and stderr text."""
    code = tool.main(args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def save_preview(
    vault: RunVault, capsys: pytest.CaptureFixture, run: int, name: str = "approved.json"
) -> Path:
    """Run a preview through main, save its report, and return the report path."""
    path = vault.out / name
    code, _out, _err = run_main(capsys, cli_args(vault.root, run=run, report_path=path))
    assert code == 0
    return path


def fatal_messages(caplog: pytest.LogCaptureFixture) -> List[str]:
    """The ERROR messages logged by the tool."""
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]


def line_diff(before: bytes, after: bytes) -> Tuple[List[str], List[str]]:
    """Return (added lines, deleted lines) of a line level diff, each with its line ending."""
    old = before.decode("utf-8").splitlines(keepends=True)
    new = after.decode("utf-8").splitlines(keepends=True)
    added: List[str] = []
    deleted: List[str] = []
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            deleted.extend(old[old_start:old_end])
        if tag in ("replace", "insert"):
            added.extend(new[new_start:new_end])
    return added, deleted


class TestAC01KindRows:
    def test_each_fixture_file_receives_a_row(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        report = apply_run(rv, RUN_CREATE)
        for kind_id, name, triple in KIND_FIXTURES:
            assert rv.read(ticket_path(name)) == expected_create(triple), kind_id
        assert rv.read(ticket_path(UNMATCHED_FIXTURE)) == KITCHEN_BARE
        assert report["skipped_by_reason"] == {"NO_KIND_ROW": 1}
        assert report["counts"]["written"] == len(KIND_FIXTURES)

    def test_every_kind_id_is_covered_by_one_fixture(self) -> None:
        assert [item[0] for item in KIND_FIXTURES] == ["K{}".format(n) for n in range(1, 14)]


class TestAC02Triples:
    @pytest.mark.parametrize("run", ALL_RUNS)
    def test_each_row_matches_the_test_literals(self, rv: RunVault, run: int) -> None:
        build_kitchen(rv, KITCHEN_CONTENT[run])
        apply_run(rv, run)
        for kind_id, name, triple in KIND_FIXTURES:
            assert triple_of(rv.read(ticket_path(name))) == triple, kind_id
            assert rv.read(ticket_path(name)) == EXPECTED_BY_RUN[run](triple), kind_id
        assert rv.read(ticket_path(UNMATCHED_FIXTURE)) == KITCHEN_CONTENT[run]

    @pytest.mark.parametrize("run", ALL_RUNS)
    def test_the_indexed_field_is_null_and_never_a_string(self, rv: RunVault, run: int) -> None:
        build_kitchen(rv, KITCHEN_CONTENT[run])
        apply_run(rv, run)
        for _kind, name, _triple in KIND_FIXTURES:
            assert parse_front(rv.read(ticket_path(name)))["indexed"] is None


class TestAC03DiffStructure:
    def test_an_add_inserts_four_lines_and_deletes_none(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        apply_run(rv, RUN_ADD_FLIP)
        for _kind, name, triple in KIND_FIXTURES:
            added, deleted = line_diff(KITCHEN_INCOMPLETE, rv.read(ticket_path(name)))
            assert added == four_lines(triple).decode("utf-8").splitlines(keepends=True)
            assert deleted == []

    def test_a_create_inserts_six_lines_and_deletes_none(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        apply_run(rv, RUN_CREATE)
        for _kind, name, triple in KIND_FIXTURES:
            added, deleted = line_diff(KITCHEN_BARE, rv.read(ticket_path(name)))
            body = four_lines(triple).decode("utf-8").splitlines(keepends=True)
            assert added == ["---\n"] + body + ["---\n"]
            assert deleted == []

    def test_a_flip_replaces_exactly_one_line(self, rv: RunVault) -> None:
        raw = doc(["status: dropped", "catalog_type: ticket", "doc_role: spec",
                   "indexable: true", "indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        apply_run(rv, RUN_ADD_FLIP)
        added, deleted = line_diff(raw, rv.read(ticket_path("spec.md")))
        assert (added, deleted) == (["indexable: false\n"], ["indexable: true\n"])

    @pytest.mark.parametrize("name,triple,line_count", [
        ("spec.md", SPEC_TRIPLE, 3),
        (REVIEW_FIXTURE, REVIEW_TRIPLE, 2),
    ])
    def test_a_rewrite_replaces_three_lines_or_two_when_indexable_stays_false(
        self, rv: RunVault, name: str, triple: Tuple[str, str, bool], line_count: int
    ) -> None:
        rv.write(ticket_path(name), KITCHEN_PLACEHOLDER)
        rv.commit_all()
        apply_run(rv, RUN_REWRITE)
        added, deleted = line_diff(KITCHEN_PLACEHOLDER, rv.read(ticket_path(name)))
        assert len(added) == len(deleted) == line_count
        assert all(line.split(":")[0] in ("catalog_type", "doc_role", "indexable") for line in added + deleted)
        assert not any(line.startswith("indexed") for line in added + deleted)

    def test_a_replace_that_touches_another_line_is_refused(self) -> None:
        raw = doc(["status: cancelled", "title: Keep", "indexable: true"])
        span, fm = prepare(raw)
        edits = (("indexable", "true", "false"),)
        clean = raw.replace(b"indexable: true", b"indexable: false")
        touched = clean.replace(b"Keep", b"Lost")
        spaced = clean.replace(b"title: Keep\n", b"title: Keep \n")
        assert tool.verify_replace(raw, span, edits, touched, fm, {"indexable": False}) is False
        assert tool.verify_replace(raw, span, edits, spaced, fm, {"indexable": False}) is False
        assert tool.verify_replace(raw, span, edits, clean, fm, {"indexable": True}) is False
        assert tool.verify_replace(raw, span, edits, clean, fm, {"indexable": False}) is True

    def test_the_planner_refuses_a_flip_whose_bytes_touch_another_line(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw = doc(["status: cancelled", "catalog_type: ticket", "doc_role: spec",
                   "indexable: true", "indexed: null", "title: Keep"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        real = tool.replace_field_lines

        def greedy(raw_in: bytes, span: Any, edits: Sequence[Tuple[str, str, str]]) -> Optional[bytes]:
            result = real(raw_in, span, edits)
            return None if result is None else result.replace(b"Keep", b"Lost")

        monkeypatch.setattr(tool, "replace_field_lines", greedy)
        outcome = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert (outcome.kind, outcome.reason) == ("skipped", "VERIFY_FAILED")
        assert outcome.new_raw is None


class TestPlanRun1:
    def test_an_add_plans_the_four_lines_for_every_kind_row(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        for kind_id, name, triple in KIND_FIXTURES:
            out = plan_one(rv, ticket_path(name), RUN_ADD_FLIP)
            assert (out.kind, out.change_class, out.kind_id) == ("write", "add", kind_id)
            assert out.original == KITCHEN_INCOMPLETE
            assert out.new_raw == expected_add(triple), kind_id
            assert out.additions == {
                "catalog_type": triple[0], "doc_role": triple[1],
                "indexable": triple[2], "indexed": None,
            }
            assert out.changes == ()

    def test_an_add_keeps_present_fields_and_inserts_only_the_missing_ones(
        self, rv: RunVault
    ) -> None:
        raw = doc(["title: Fixture", "catalog_type: ticket", "indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert out.new_raw == doc(
            ["title: Fixture", "catalog_type: ticket", "indexed: null",
             "doc_role: spec", "indexable: true"]
        )
        assert out.additions == {"doc_role": "spec", "indexable": True}

    def test_a_present_indexed_value_is_never_touched(self, rv: RunVault) -> None:
        raw = doc(["title: Fixture", "indexed: 2026-09-01"])
        rv.write(ticket_path("design.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("design.md"), RUN_ADD_FLIP)
        assert list(out.additions) == ["catalog_type", "doc_role", "indexable"]
        assert out.new_raw is not None and b"indexed: 2026-09-01\n" in out.new_raw

    def test_a_terminal_status_file_without_indexable_gets_false(self, rv: RunVault) -> None:
        raw = doc(["title: Fixture", "status: cancelled"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert (out.change_class, out.additions["indexable"]) == ("add", False)
        assert out.new_raw == doc(
            ["title: Fixture", "status: cancelled", "catalog_type: ticket",
             "doc_role: spec", "indexable: false", "indexed: null"]
        )

    def test_a_terminal_status_file_that_already_reads_false_changes_nothing(
        self, rv: RunVault
    ) -> None:
        full = doc(["status: Cancelled", "catalog_type: ticket", "doc_role: spec",
                    "indexable: false", "indexed: null"])
        part = doc(["status: cancelled", "indexable: false"])
        rv.write(ticket_path("spec.md"), full)
        rv.write(ticket_path("design.md"), part)
        rv.commit_all()
        assert plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP).kind == "already_complete"
        out = plan_one(rv, ticket_path("design.md"), RUN_ADD_FLIP)
        assert out.change_class == "add" and "indexable" not in out.additions
        assert out.new_raw is not None and out.new_raw.count(b"indexable: false\n") == 1

    @pytest.mark.parametrize("lines,code", [
        (["title: Fixture", "doc_role: custom"], "CONFLICT_DOC_ROLE"),
        (["title: Fixture", "indexable: false"], "CONFLICT_INDEXABLE"),
        (["title: Fixture", "catalog_type: knowledge"], "CONFLICT_CATALOG_TYPE"),
        (["title: Fixture", "indexable: 1"], "CONFLICT_INDEXABLE"),
    ])
    def test_a_present_field_that_conflicts_with_its_row_skips_the_file(
        self, rv: RunVault, lines: List[str], code: str
    ) -> None:
        raw = doc(lines)
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert (out.kind, out.reason, out.new_raw) == ("skipped", code, None)
        assert rv.read(ticket_path("spec.md")) == raw

    def test_a_terminal_file_with_indexable_true_flips_one_line(self, rv: RunVault) -> None:
        raw = doc(["title: Fixture", "status: cancelled", "catalog_type: ticket",
                   "doc_role: spec", "indexable: true", "indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert out.new_raw == raw.replace(b"indexable: true", b"indexable: false")
        assert (out.change_class, out.kind_id, out.label) == ("flip", "K5", "cancelled")
        assert out.changes == (("indexable", "true", "false"),) and out.additions == {}

    @pytest.mark.parametrize("rel,kind_id", [
        ("00-landing/2026/09/weekly-1-1.md", "none"),
        ("02-tickets/T-900/T-900-state-backup.md", "none"),
        ("02-tickets/loose.md", "none"),
        ("02-tickets/T-900/cursor.md", "K3"),
    ])
    def test_a_flip_needs_no_kind_row(self, rv: RunVault, rel: str, kind_id: str) -> None:
        raw = doc(["status: archived", "catalog_type: ticket", "doc_role: reference",
                   "indexable: true", "indexed: null"])
        rv.write(rel, raw)
        rv.commit_all()
        out = plan_one(rv, rel, RUN_ADD_FLIP)
        assert (out.change_class, out.kind_id) == ("flip", kind_id)
        assert out.new_raw == raw.replace(b"indexable: true", b"indexable: false")

    def test_a_flip_outside_tickets_needs_no_other_field(self, rv: RunVault) -> None:
        raw = doc(["title: One on one", "status: archived", "indexable: true"])
        rv.write("00-landing/note.md", raw)
        rv.commit_all()
        out = plan_one(rv, "00-landing/note.md", RUN_ADD_FLIP)
        assert out.change_class == "flip" and out.label == "archived"

    @pytest.mark.parametrize("rel", ["05-conversations/log.md", "06-chat-threads/day.md"])
    def test_the_unlabeled_folders_never_flip(self, rv: RunVault, rel: str) -> None:
        raw = doc(["status: cancelled", "indexable: true"])
        rv.write(rel, raw)
        rv.commit_all()
        out = plan_one(rv, rel, RUN_ADD_FLIP)
        assert out.kind == "not_target" and out.new_raw is None

    def test_a_file_that_needs_both_an_add_and_a_flip_is_skipped(self, rv: RunVault) -> None:
        raw = doc(["status: cancelled", "indexable: true", "doc_role: spec"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert (out.kind, out.reason) == ("skipped", "MIXED_EDIT")
        assert out.new_raw is None and rv.read(ticket_path("spec.md")) == raw

    @pytest.mark.parametrize("variant", [
        ["indexable: True"],
        ['indexable: "true"'],
        ["indexable: 'true'"],
        ["indexable: true # keep"],
        ["indexable: true", "indexable: true"],
        ["indexable:  true"],
        ["indexable: yes"],
        ["indexable: true "],
    ])
    def test_a_flip_line_in_an_unaccepted_form_is_skipped(
        self, rv: RunVault, variant: List[str]
    ) -> None:
        raw = doc(["status: cancelled", "catalog_type: ticket", "doc_role: spec"]
                  + variant + ["indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert (out.kind, out.reason) == ("skipped", "UNEXPECTED_LINE_FORM")
        assert out.new_raw is None and rv.read(ticket_path("spec.md")) == raw

    def test_a_flip_and_an_add_keep_a_crlf_file_in_crlf(self, rv: RunVault) -> None:
        flip = doc(["status: cancelled", "catalog_type: ticket", "doc_role: spec",
                    "indexable: true", "indexed: null"], eol=CRLF)
        add = doc(["title: Fixture"], eol=CRLF)
        rv.write(ticket_path("spec.md"), flip)
        rv.write(ticket_path("design.md"), add)
        rv.commit_all()
        flipped = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP).new_raw
        added = plan_one(rv, ticket_path("design.md"), RUN_ADD_FLIP).new_raw
        assert flipped == flip.replace(b"indexable: true", b"indexable: false")
        assert added == doc(
            ["title: Fixture", "catalog_type: ticket", "doc_role: design",
             "indexable: true", "indexed: null"], eol=CRLF
        )

    def test_an_add_without_a_kind_row_is_skipped(self, rv: RunVault) -> None:
        rv.write(ticket_path(UNMATCHED_FIXTURE), KITCHEN_INCOMPLETE)
        rv.write("02-tickets/loose.md", KITCHEN_INCOMPLETE)
        rv.commit_all()
        for rel in (ticket_path(UNMATCHED_FIXTURE), "02-tickets/loose.md"):
            out = plan_one(rv, rel, RUN_ADD_FLIP)
            assert (out.kind, out.reason, out.new_raw) == ("skipped", "NO_KIND_ROW", None)

    def test_a_ticket_file_that_does_not_parse_is_skipped_and_other_folders_ignore_it(
        self, rv: RunVault
    ) -> None:
        broken = b"---\ntitle: [unclosed\n---\nbody\n"
        rv.write(ticket_path("spec.md"), broken)
        rv.write("00-landing/broken.md", broken)
        rv.commit_all()
        assert plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP).reason == "PARSE_ERROR"
        assert plan_one(rv, "00-landing/broken.md", RUN_ADD_FLIP).kind == "not_target"

    def test_run_one_leaves_bare_placeholder_and_complete_files_alone(self, rv: RunVault) -> None:
        full = doc(["catalog_type: ticket", "doc_role: spec", "indexable: true", "indexed: null"])
        rv.write(ticket_path("spec.md"), KITCHEN_BARE)
        rv.write(ticket_path("design.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path("qa-findings.md"), full)
        rv.commit_all()
        kinds = [plan_one(rv, ticket_path(name), RUN_ADD_FLIP).kind
                 for name in ("spec.md", "design.md", "qa-findings.md")]
        assert kinds == ["not_target", "already_complete", "already_complete"]

    def test_a_run_report_counts_the_resulting_indexable_values(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        report = preview(rv, RUN_ADD_FLIP)
        assert report["counts"]["written"] == 13
        assert (report["counts"]["result_true"], report["counts"]["result_false"]) == (10, 3)
        assert report["by_class"] == {"add": 13, "create": 0, "flip": 0, "rewrite": 0}
        assert report["by_kind"]["K3"] == {"add": 1, "create": 0, "flip": 0, "rewrite": 0}
        assert report["flips_by_status"] == {}

    def test_complete_differs_lists_only_hand_set_files_no_run_touches(self, rv: RunVault) -> None:
        hand = doc(["catalog_type: ticket", "doc_role: reference", "indexable: false", "indexed: null"])
        good = doc(["catalog_type: ticket", "doc_role: design", "indexable: true", "indexed: null"])
        flip = doc(["status: dropped", "catalog_type: ticket", "doc_role: qa",
                    "indexable: true", "indexed: null"])
        rv.write(ticket_path("spec.md"), hand)
        rv.write(ticket_path("design.md"), good)
        rv.write(ticket_path("qa-findings.md"), flip)
        rv.write(ticket_path("context.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path(UNMATCHED_FIXTURE), hand)
        rv.write("00-landing/outside.md", hand)
        rv.commit_all()
        for run in ALL_RUNS:
            report = preview(rv, run)
            assert report["complete_differs"] == [ticket_path("spec.md")], run


EOL_CASES: List[Tuple[str, bytes, bytes]] = [
    ("lf", b"# Heading\nBody text.\n", LF),
    ("crlf", b"# Heading\r\nBody text.\r\n", CRLF),
    ("crlf then lf", b"# Heading\r\nBody\nmore\n", CRLF),
    ("lf then crlf", b"# Heading\nBody\r\nmore\r\n", LF),
    ("one line, no ending", b"just text", LF),
    ("no trailing newline", b"# Heading\nbody", LF),
    ("not utf-8", b"# Heading\n\xff\xfe\x80 raw bytes\n", LF),
    ("carriage return only", b"text\r", LF),
]
UNSAFE_TOPS: List[Tuple[str, bytes]] = [
    ("empty", b""),
    ("utf-8 bom", b"\xef\xbb\xbf# Heading\n"),
    ("utf-16 le bom", b"\xff\xfe#\x00"),
    ("utf-16 be bom", b"\xfe\xff\x00#"),
    ("unclosed frontmatter", b"---\ntitle: Fixture\nno closing line\n"),
    ("horizontal rule", b"---\nText below a rule.\n"),
    ("rule with a space", b"--- \nText.\n"),
    ("four dashes", b"----\nText.\n"),
]


class TestPlanRun2:
    def test_a_create_plans_a_block_for_every_kind_row(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        for kind_id, name, triple in KIND_FIXTURES:
            out = plan_one(rv, ticket_path(name), RUN_CREATE)
            assert (out.kind, out.change_class, out.kind_id) == ("write", "create", kind_id)
            assert out.new_raw == expected_create(triple), kind_id
            assert out.additions == {
                "catalog_type": triple[0], "doc_role": triple[1],
                "indexable": triple[2], "indexed": None,
            }
            assert out.changes == () and out.label is None

    @pytest.mark.parametrize("case,raw,eol", EOL_CASES, ids=[case[0] for case in EOL_CASES])
    def test_the_block_uses_the_first_line_ending_and_keeps_every_original_byte(
        self, rv: RunVault, case: str, raw: bytes, eol: bytes
    ) -> None:
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_CREATE)
        block = b"---" + eol + four_lines(SPEC_TRIPLE, eol) + b"---" + eol
        assert out.new_raw == block + raw, case
        assert out.original == raw

    @pytest.mark.parametrize("case,raw", UNSAFE_TOPS, ids=[case[0] for case in UNSAFE_TOPS])
    def test_an_unsafe_top_is_skipped_and_stays_byte_identical(
        self, rv: RunVault, case: str, raw: bytes
    ) -> None:
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_CREATE)
        assert (out.kind, out.reason, out.new_raw) == ("skipped", "UNSAFE_TOP", None), case
        assert rv.read(ticket_path("spec.md")) == raw

    def test_unsafe_tops_are_not_written_on_apply(self, rv: RunVault) -> None:
        unsafe = [ticket_path("qa-findings-{}.md".format(n)) for n in range(len(UNSAFE_TOPS))]
        for rel, (_case, raw) in zip(unsafe, UNSAFE_TOPS):
            rv.write(rel, raw)
        rv.write(ticket_path("spec.md"), KITCHEN_BARE)
        rv.commit_all()
        before = hashes(rv.root, unsafe)
        report = apply_run(rv, RUN_CREATE)
        assert report["skipped_by_reason"] == {"UNSAFE_TOP": len(UNSAFE_TOPS)}
        assert report["counts"]["written"] == 1
        assert before == hashes(rv.root, list(before))

    def test_files_with_frontmatter_are_not_created_over(self, rv: RunVault) -> None:
        full = doc(["catalog_type: ticket", "doc_role: spec", "indexable: true", "indexed: null"])
        rv.write(ticket_path("spec.md"), KITCHEN_INCOMPLETE)
        rv.write(ticket_path("design.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path("qa-findings.md"), full)
        rv.commit_all()
        kinds = [plan_one(rv, ticket_path(name), RUN_CREATE).kind
                 for name in ("spec.md", "design.md", "qa-findings.md")]
        assert kinds == ["not_target", "already_complete", "already_complete"]

    @pytest.mark.parametrize("rel", [
        "00-landing/note.md", "03-knowledge-base/decisions/note.md",
        "05-conversations/log.md", "06-chat-threads/day.md", "01-system-map/spec.md",
    ])
    def test_a_bare_file_outside_the_ticket_folder_is_not_a_target(
        self, rv: RunVault, rel: str
    ) -> None:
        rv.write(rel, KITCHEN_BARE)
        rv.commit_all()
        for run in (RUN_CREATE, RUN_REWRITE):
            assert plan_one(rv, rel, run).kind == "not_target"

    def test_a_bare_file_without_a_kind_row_is_skipped(self, rv: RunVault) -> None:
        rv.write(ticket_path(UNMATCHED_FIXTURE), KITCHEN_BARE)
        rv.write("02-tickets/loose.md", KITCHEN_BARE)
        rv.commit_all()
        for rel in (ticket_path(UNMATCHED_FIXTURE), "02-tickets/loose.md"):
            out = plan_one(rv, rel, RUN_CREATE)
            assert (out.kind, out.reason, out.new_raw) == ("skipped", "NO_KIND_ROW", None)

    def test_a_ticket_file_that_does_not_parse_is_skipped(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), b"---\ntitle: [unclosed\n---\nbody\n")
        rv.commit_all()
        assert plan_one(rv, ticket_path("spec.md"), RUN_CREATE).reason == "PARSE_ERROR"

    def test_a_run_report_counts_creates_and_resulting_indexable_values(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        report = preview(rv, RUN_CREATE)
        assert (report["counts"]["written"], report["counts"]["changed"]) == (13, 0)
        assert (report["counts"]["result_true"], report["counts"]["result_false"]) == (10, 3)
        assert report["by_class"] == {"add": 0, "create": 13, "flip": 0, "rewrite": 0}
        assert report["dispositions"] == {}

    def test_the_state_file_gets_the_state_row_and_an_archive_state_file_does_not(
        self, rv: RunVault
    ) -> None:
        rv.write(ticket_path("T-900-state.md"), KITCHEN_BARE)
        rv.write(ticket_path("archive/T-900-state.md"), KITCHEN_BARE)
        rv.commit_all()
        top = plan_one(rv, ticket_path("T-900-state.md"), RUN_CREATE)
        archived = plan_one(rv, ticket_path("archive/T-900-state.md"), RUN_CREATE)
        assert (top.kind_id, archived.kind_id) == ("K2", "K1")
        assert archived.additions["doc_role"] == "state" and archived.additions["indexable"] is False


PLACEHOLDER_HEAD = ["title: Fixture", "doc_type: legacy-note"]
HAND_VARIANTS: List[Tuple[str, List[str]]] = [
    ("unknown with indexable true", ["catalog_type: unknown", "doc_role: unknown", "indexable: true"]),
    ("quoted false", ["catalog_type: unknown", "doc_role: unknown", 'indexable: "false"']),
    ("hand set triple", ["catalog_type: ticket", "doc_role: reference", "indexable: false"]),
    ("already the row", ["catalog_type: ticket", "doc_role: spec", "indexable: true"]),
    ("half placeholder", ["catalog_type: unknown", "doc_role: spec", "indexable: false"]),
    ("catalog only", ["catalog_type: unknown", "doc_role: reference", "indexable: false"]),
]
LINE_FORM_VARIANTS: List[Tuple[str, List[str]]] = [
    ("quoted unknown", ['catalog_type: "unknown"', "doc_role: unknown", "indexable: false"]),
    ("single quoted", ["catalog_type: unknown", "doc_role: 'unknown'", "indexable: false"]),
    ("capital false", ["catalog_type: unknown", "doc_role: unknown", "indexable: False"]),
    ("no as false", ["catalog_type: unknown", "doc_role: unknown", "indexable: no"]),
    ("trailing comment", ["catalog_type: unknown", "doc_role: unknown # old", "indexable: false"]),
    ("duplicate line", ["catalog_type: unknown", "doc_role: unknown", "indexable: false", "indexable: false"]),
]


class TestPlanRun3:
    def test_a_rewrite_replaces_the_placeholder_for_every_kind_row(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_PLACEHOLDER)
        for kind_id, name, triple in KIND_FIXTURES:
            out = plan_one(rv, ticket_path(name), RUN_REWRITE)
            assert (out.kind, out.change_class, out.kind_id) == ("write", "rewrite", kind_id)
            assert out.new_raw == expected_rewrite(triple), kind_id
            assert out.additions == {} and out.label == "legacy-note"
            wanted = [("catalog_type", "unknown", triple[0]), ("doc_role", "unknown", triple[1])]
            if triple[2]:
                wanted.append(("indexable", "false", "true"))
            assert out.changes == tuple(wanted), kind_id

    @pytest.mark.parametrize("case,lines", HAND_VARIANTS, ids=[case[0] for case in HAND_VARIANTS])
    def test_a_file_that_is_not_the_exact_placeholder_is_left_alone(
        self, rv: RunVault, case: str, lines: List[str]
    ) -> None:
        raw = doc(PLACEHOLDER_HEAD + lines + ["indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_REWRITE)
        assert (out.kind, out.new_raw, out.label) == ("already_complete", None, None), case
        assert rv.read(ticket_path("spec.md")) == raw

    @pytest.mark.parametrize("case,lines", LINE_FORM_VARIANTS, ids=[case[0] for case in LINE_FORM_VARIANTS])
    def test_a_placeholder_in_an_unaccepted_line_form_is_skipped_and_stays_left(
        self, rv: RunVault, case: str, lines: List[str]
    ) -> None:
        raw = doc(PLACEHOLDER_HEAD + lines + ["indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_REWRITE)
        assert (out.kind, out.reason, out.new_raw) == ("skipped", "UNEXPECTED_LINE_FORM", None), case
        assert out.label == "legacy-note" and rv.read(ticket_path("spec.md")) == raw

    def test_a_placeholder_without_a_kind_row_is_skipped_with_its_label(self, rv: RunVault) -> None:
        rv.write(ticket_path(UNMATCHED_FIXTURE), KITCHEN_PLACEHOLDER)
        no_type = doc(["title: Fixture", "catalog_type: unknown", "doc_role: unknown",
                       "indexable: false", "indexed: null"])
        rv.write(ticket_path("other-notes.md"), no_type)
        rv.commit_all()
        first = plan_one(rv, ticket_path(UNMATCHED_FIXTURE), RUN_REWRITE)
        second = plan_one(rv, ticket_path("other-notes.md"), RUN_REWRITE)
        assert (first.reason, first.label) == ("NO_KIND_ROW", "legacy-note")
        assert (second.reason, second.label) == ("NO_KIND_ROW", "none")

    @pytest.mark.parametrize("value,label", [
        ("legacy-note", "legacy-note"), ("12", "<non-string>"), ("[a, b]", "<non-string>"),
        ('"has space"', "<unprintable>"),
    ])
    def test_the_label_is_the_report_safe_doc_type(
        self, rv: RunVault, value: str, label: str
    ) -> None:
        raw = doc(["doc_type: " + value, "catalog_type: unknown", "doc_role: unknown",
                   "indexable: false", "indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        assert plan_one(rv, ticket_path("spec.md"), RUN_REWRITE).label == label

    def test_dispositions_count_resolved_and_left_per_label(self, rv: RunVault) -> None:
        other = doc(["doc_type: other-note", "catalog_type: unknown", "doc_role: unknown",
                     "indexable: false", "indexed: null"])
        rv.write(ticket_path("spec.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path("design.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path(UNMATCHED_FIXTURE), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path("odd-name.md"), other)
        rv.commit_all()
        report = preview(rv, RUN_REWRITE)
        assert report["dispositions"] == {
            "legacy-note": {"resolved": 2, "left": 1},
            "other-note": {"resolved": 0, "left": 1},
        }

    def test_dispositions_are_empty_in_the_other_runs(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path("design.md"), status_file("cancelled"))
        rv.write(ticket_path("qa-findings.md"), KITCHEN_BARE)
        rv.write(ticket_path(UNMATCHED_FIXTURE), KITCHEN_PLACEHOLDER)
        rv.commit_all()
        assert preview(rv, RUN_ADD_FLIP)["counts"]["changed"] == 1
        assert preview(rv, RUN_ADD_FLIP)["dispositions"] == {}
        assert preview(rv, RUN_CREATE)["dispositions"] == {}

    def test_a_terminal_status_makes_the_rewrite_keep_indexable_false(self, rv: RunVault) -> None:
        raw = doc(["status: cancelled", "catalog_type: unknown", "doc_role: unknown",
                   "indexable: false", "indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_REWRITE)
        assert out.changes == (("catalog_type", "unknown", "ticket"), ("doc_role", "unknown", "spec"))
        assert out.new_raw == doc(["status: cancelled", "catalog_type: ticket", "doc_role: spec",
                                   "indexable: false", "indexed: null"])

    def test_a_placeholder_outside_the_ticket_folder_is_not_a_target(self, rv: RunVault) -> None:
        rv.write("00-landing/note.md", KITCHEN_PLACEHOLDER)
        rv.commit_all()
        assert plan_one(rv, "00-landing/note.md", RUN_REWRITE).kind == "not_target"

    def test_a_rewrite_keeps_a_crlf_file_in_crlf_and_leaves_indexed_alone(self, rv: RunVault) -> None:
        raw = doc(["title: Fixture", "catalog_type: unknown", "doc_role: unknown",
                   "indexable: false", "indexed: 2026-09-01"], eol=CRLF)
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        out = plan_one(rv, ticket_path("spec.md"), RUN_REWRITE)
        assert out.new_raw == doc(["title: Fixture", "catalog_type: ticket", "doc_role: spec",
                                   "indexable: true", "indexed: 2026-09-01"], eol=CRLF)

    def test_a_placeholder_without_indexed_is_not_a_run_three_target(self, rv: RunVault) -> None:
        raw = doc(["title: Fixture", "catalog_type: unknown", "doc_role: unknown", "indexable: false"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        assert plan_one(rv, ticket_path("spec.md"), RUN_REWRITE).kind == "not_target"
        out = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert (out.kind, out.reason) == ("skipped", "CONFLICT_CATALOG_TYPE")

    def test_a_ticket_file_that_does_not_parse_is_skipped(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), b"---\ntitle: [unclosed\n---\nbody\n")
        rv.commit_all()
        assert plan_one(rv, ticket_path("spec.md"), RUN_REWRITE).reason == "PARSE_ERROR"


def planned(rel: str, change_class: str = "add", kind_id: str = "K5",
            additions: Optional[Dict[str, Any]] = None,
            changes: Tuple[Tuple[str, str, str], ...] = ()) -> Any:
    """Build a planned write by hand for approved report unit tests."""
    added = {"doc_role": "spec", "indexable": True} if additions is None else additions
    return tool.Outcome(
        rel, "write", additions=added, original=b"old", new_raw=b"new",
        change_class=change_class, kind_id=kind_id, changes=changes,
    )


def approved_entry(rel: str, change_class: str = "add", kind_id: str = "K5",
                   added: Optional[Dict[str, Any]] = None,
                   changes: Optional[List[List[str]]] = None) -> Dict[str, Any]:
    """The report entry a planned write must equal, typed here as a literal."""
    return {
        "path": rel, "class": change_class, "kind": kind_id,
        "added": {"doc_role": "spec", "indexable": True} if added is None else added,
        "changes": [] if changes is None else changes,
    }


def approved_report(entries: List[Any], run: int = RUN_ADD_FLIP, mode: str = "preview") -> Dict[str, Any]:
    """A minimal approved report holding the given write entries."""
    return {"mode": mode, "run": run, "writes": entries}


def write_json(path: Path, value: Any) -> Path:
    """Save value as a JSON file and return the path."""
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class TestApprovedReportUnapprovedEntries:
    def test_equal_entries_are_all_approved(self) -> None:
        outcomes = [planned("a.md"), planned("b.md", "flip", "none", {}, (("indexable", "true", "false"),))]
        report = approved_report([
            approved_entry("a.md"),
            approved_entry("b.md", "flip", "none", {}, [["indexable", "true", "false"]]),
        ])
        assert tool.unapproved_entries(outcomes, report) == []

    def test_a_planned_write_absent_from_the_report_is_returned(self) -> None:
        report = approved_report([approved_entry("a.md")])
        assert tool.unapproved_entries([planned("a.md"), planned("z.md"), planned("c.md")], report) == [
            "c.md", "z.md",
        ]

    @pytest.mark.parametrize("entry", [
        approved_entry("a.md", added={"doc_role": "design", "indexable": True}),
        approved_entry("a.md", added={"doc_role": "spec", "indexable": False}),
        approved_entry("a.md", added={"doc_role": "spec"}),
        approved_entry("a.md", change_class="create"),
        approved_entry("a.md", kind_id="K6"),
        approved_entry("a.md", changes=[["indexable", "true", "false"]]),
    ])
    def test_a_changed_path_class_kind_added_field_or_change_is_returned(
        self, entry: Dict[str, Any]
    ) -> None:
        assert tool.unapproved_entries([planned("a.md")], approved_report([entry])) == ["a.md"]

    def test_an_integer_does_not_stand_in_for_a_boolean(self) -> None:
        entry = approved_entry("a.md", added={"doc_role": "spec", "indexable": 1})
        assert tool.unapproved_entries([planned("a.md")], approved_report([entry])) == ["a.md"]

    def test_approved_entries_that_were_not_planned_are_ignored(self) -> None:
        report = approved_report([approved_entry("a.md"), approved_entry("b.md"), approved_entry("c.md")])
        assert tool.unapproved_entries([planned("b.md")], report) == []

    def test_only_planned_writes_are_compared(self) -> None:
        outcomes = [
            tool.Outcome("s.md", "skipped", reason="GITIGNORED"),
            tool.Outcome("c.md", "already_complete"),
            tool.Outcome("n.md", "not_target"),
        ]
        assert tool.unapproved_entries(outcomes, approved_report([])) == []

    @pytest.mark.parametrize("writes", [None, "text", 7, {"a.md": 1}, [None], ["a.md"], [{"path": 1}]])
    def test_a_malformed_report_approves_nothing_and_never_raises(self, writes: Any) -> None:
        report = {"mode": "preview", "run": 1, "writes": writes}
        assert tool.unapproved_entries([planned("a.md")], report) == ["a.md"]
        assert tool.unapproved_entries([planned("a.md")], {}) == ["a.md"]


class TestApprovedReportLoad:
    def test_a_preview_report_for_the_run_loads(self, tmp_path: Path) -> None:
        report = approved_report([approved_entry("a.md")])
        assert tool.load_approved_report(write_json(tmp_path / "r.json", report), 1) == report

    def load_code(self, path: Path, run: int = RUN_ADD_FLIP) -> str:
        """Return the closed code load_approved_report raises."""
        with pytest.raises(tool.PreconditionError) as info:
            tool.load_approved_report(path, run)
        return str(info.value)

    def test_a_missing_file_or_folder_is_invalid(self, tmp_path: Path) -> None:
        assert self.load_code(tmp_path / "absent.json") == "APPROVED_REPORT_INVALID"
        assert self.load_code(tmp_path) == "APPROVED_REPORT_INVALID"

    @pytest.mark.parametrize("raw", [
        b"", b"not json", b"[1, 2]", b"null", b"\xff\xfe\x00", b"[" * 100000,
        b'{"mode": "preview", "run": 1}',
        b'{"mode": "preview", "run": 1, "writes": {}}',
        b'{"mode": "preview", "run": 1, "writes": [{"class": "add"}]}',
        b'{"mode": "preview", "run": 1, "writes": [{"path": "a.md"}, {"path": "a.md"}]}',
    ])
    def test_a_file_that_is_not_a_report_is_invalid(self, tmp_path: Path, raw: bytes) -> None:
        path = tmp_path / "r.json"
        path.write_bytes(raw)
        assert self.load_code(path) == "APPROVED_REPORT_INVALID"

    @pytest.mark.parametrize("mode,run,asked", [
        ("apply", 1, 1), ("preview", 2, 1), ("preview", "1", 1), ("preview", True, 1),
        ("preview", 1.0, 1), ("preview", None, 1), (None, 1, 1), ("Preview", 1, 1),
    ])
    def test_a_report_that_is_not_a_preview_for_this_run_is_a_mismatch(
        self, tmp_path: Path, mode: Any, run: Any, asked: int
    ) -> None:
        path = write_json(tmp_path / "r.json", {"mode": mode, "run": run, "writes": []})
        assert self.load_code(path, asked) == "APPROVED_REPORT_MISMATCH"

    def test_the_code_carries_no_file_text(self, tmp_path: Path) -> None:
        path = tmp_path / "r.json"
        path.write_text("CANARY_7Q2X_DO_NOT_LEAK {", encoding="utf-8")
        assert self.load_code(path) == "APPROVED_REPORT_INVALID"


def build_ten_adds(vault: RunVault) -> List[str]:
    """Commit ten Run 1 add candidates that all take the review row K7, and return their paths."""
    rels = [ticket_path("qa-findings-{}.md".format(n)) for n in range(10)]
    for rel in rels:
        vault.write(rel, KITCHEN_INCOMPLETE)
    vault.commit_all()
    return rels


def refused(
    capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture, vault: RunVault,
    args: List[str], code: str,
) -> None:
    """Assert main exits 2 with one closed code, prints nothing, and leaves every file untouched."""
    before = snapshot(vault.root)
    with caplog.at_level(logging.INFO):
        exit_code, out, _err = run_main(capsys, args)
    assert exit_code == 2 and out == ""
    assert fatal_messages(caplog)[-1] == FATAL_PREFIX + code
    assert snapshot(vault.root) == before


class TestApprovedReport:
    def test_an_extra_planned_entry_is_refused_and_nothing_is_written(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_ten_adds(rv)
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        rv.write(ticket_path("qa-findings-new.md"), KITCHEN_INCOMPLETE)
        rv.commit_all()
        args = cli_args(rv.root, RUN_ADD_FLIP, True, approved)
        refused(capsys, caplog, rv, args, "NOT_APPROVED")
        assert any(msg.endswith(": 1") for msg in fatal_messages(caplog))

    @pytest.mark.parametrize("change", ["added", "class", "kind", "path", "changes"])
    def test_a_changed_entry_in_the_approved_report_is_refused(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture, change: str,
    ) -> None:
        rels = build_ten_adds(rv)
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        data = json.loads(approved.read_text(encoding="utf-8"))
        entry = next(item for item in data["writes"] if item["path"] == rels[3])
        if change == "added":
            entry["added"]["doc_role"] = "design"
        elif change == "class":
            entry["class"] = "create"
        elif change == "kind":
            entry["kind"] = "K6"
        elif change == "path":
            entry["path"] = rels[3] + ".moved"
        else:
            entry["changes"] = [["indexable", "true", "false"]]
        write_json(approved, data)
        refused(capsys, caplog, rv, cli_args(rv.root, RUN_ADD_FLIP, True, approved), "NOT_APPROVED")

    def test_a_planned_file_edited_after_the_preview_is_refused(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        rels = build_ten_adds(rv)
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        rv.write(rels[4], doc(["title: Fixture", "status: active", "catalog_type: ticket"]))
        rv.commit_all()
        refused(capsys, caplog, rv, cli_args(rv.root, RUN_ADD_FLIP, True, approved), "NOT_APPROVED")

    def test_a_report_for_another_run_is_refused(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_ten_adds(rv)
        other = save_preview(rv, capsys, RUN_CREATE, "run2.json")
        refused(capsys, caplog, rv, cli_args(rv.root, RUN_ADD_FLIP, True, other),
                "APPROVED_REPORT_MISMATCH")

    def test_a_missing_report_file_is_refused(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_ten_adds(rv)
        args = cli_args(rv.root, RUN_ADD_FLIP, True, rv.out / "absent.json")
        refused(capsys, caplog, rv, args, "APPROVED_REPORT_INVALID")

    def test_an_apply_mode_report_is_refused(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_ten_adds(rv)
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        applied = rv.out / "applied.json"
        code, _out, _err = run_main(
            capsys, cli_args(rv.root, RUN_ADD_FLIP, True, approved, applied)
        )
        assert code == 0 and json.loads(applied.read_text(encoding="utf-8"))["mode"] == "apply"
        rv.git("checkout", "--", ".")
        refused(capsys, caplog, rv, cli_args(rv.root, RUN_ADD_FLIP, True, applied),
                "APPROVED_REPORT_MISMATCH")

    def test_a_subset_of_the_approved_entries_passes_and_writes_only_those(
        self, rv: RunVault, capsys: pytest.CaptureFixture
    ) -> None:
        rels = build_ten_adds(rv)
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        done = expected_add(("ticket", "qa", True))
        for rel in rels[:4]:
            rv.write(rel, done)
        rv.commit_all()
        again = rv.out / "rerun.json"
        code, _out, _err = run_main(
            capsys, cli_args(rv.root, RUN_ADD_FLIP, True, approved, again)
        )
        report = json.loads(again.read_text(encoding="utf-8"))
        assert code == 0
        assert report["counts"]["written"] == 6
        assert [entry["path"] for entry in report["writes"]] == sorted(rels[4:])
        assert all(rv.read(rel) == done for rel in rels)

    def test_a_full_approved_report_writes_every_entry(
        self, rv: RunVault, capsys: pytest.CaptureFixture
    ) -> None:
        rels = build_ten_adds(rv)
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        code, _out, _err = run_main(capsys, cli_args(rv.root, RUN_ADD_FLIP, True, approved))
        assert code == 0
        assert all(rv.read(rel) == expected_add(("ticket", "qa", True)) for rel in rels)

    def test_apply_without_a_report_dict_is_refused_at_the_run_function(self, rv: RunVault) -> None:
        build_ten_adds(rv)
        before = snapshot(rv.root)
        with pytest.raises(tool.PreconditionError) as info:
            tool.run_policy(rv.root, RUN_ADD_FLIP, True, None)
        assert str(info.value) == "APPROVED_REPORT_REQUIRED"
        assert snapshot(rv.root) == before

    def test_apply_checks_the_run_of_the_report_dict_at_the_run_function(self, rv: RunVault) -> None:
        build_ten_adds(rv)
        before = snapshot(rv.root)
        other = as_approved(preview(rv, RUN_CREATE))
        with pytest.raises(tool.PreconditionError) as info:
            tool.run_policy(rv.root, RUN_ADD_FLIP, True, other)
        assert str(info.value) == "APPROVED_REPORT_MISMATCH"
        assert snapshot(rv.root) == before

    def test_the_approved_check_comes_before_the_first_write(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_ten_adds(rv)
        stale = as_approved(preview(rv, RUN_ADD_FLIP))
        rv.write(ticket_path("qa-findings-new.md"), KITCHEN_INCOMPLETE)
        rv.commit_all()
        monkeypatch.setattr(tool, "apply_edit", lambda *a, **k: pytest.fail("a write began"))
        with pytest.raises(tool.PreconditionError):
            tool.run_policy(rv.root, RUN_ADD_FLIP, True, stale)


class TestTreeClean:
    def test_a_clean_tree_reports_true_and_zero(self, rv: RunVault) -> None:
        assert tool.check_tree_clean(rv.root) == (True, 0)

    def test_an_untracked_file_counts_one(self, rv: RunVault) -> None:
        rv.write("00-landing/new.md", KITCHEN_BARE)
        assert tool.check_tree_clean(rv.root) == (False, 1)

    def test_untracked_files_in_a_new_folder_count_one_each(self, rv: RunVault) -> None:
        for name in ("a.md", "b.md", "c.md"):
            rv.write("00-landing/fresh/" + name, KITCHEN_BARE)
        assert tool.check_tree_clean(rv.root) == (False, 3)

    def test_a_modified_tracked_file_counts_one(self, rv: RunVault) -> None:
        rv.write("00-landing/a.md", KITCHEN_BARE)
        rv.commit_all()
        rv.write("00-landing/a.md", KITCHEN_BARE + b"more\n")
        assert tool.check_tree_clean(rv.root) == (False, 1)

    def test_a_staged_new_file_counts_one(self, rv: RunVault) -> None:
        rv.write("00-landing/a.md", KITCHEN_BARE)
        rv.git("add", "--", "00-landing/a.md")
        assert tool.check_tree_clean(rv.root) == (False, 1)

    def test_a_deleted_tracked_file_counts_one(self, rv: RunVault) -> None:
        rv.write("00-landing/a.md", KITCHEN_BARE)
        rv.commit_all()
        (rv.root / "00-landing/a.md").unlink()
        assert tool.check_tree_clean(rv.root) == (False, 1)

    def test_an_ignored_file_does_not_count(self, rv: RunVault) -> None:
        rv.write("ignored/skip.md", KITCHEN_BARE)
        assert tool.check_tree_clean(rv.root) == (True, 0)

    def test_a_folder_that_is_not_a_repository_raises_a_closed_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isolate_git(monkeypatch, tmp_path)
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(tool.GitStateError) as info:
            tool.check_tree_clean(plain)
        assert str(info.value) == "GIT_NONZERO_EXIT"

    def test_a_preview_on_a_dirty_tree_reports_it_and_still_plans(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), KITCHEN_INCOMPLETE)
        rv.commit_all()
        rv.write("00-landing/stray-1.md", KITCHEN_BARE)
        rv.write("00-landing/stray-2.md", KITCHEN_BARE)
        report = preview(rv, RUN_ADD_FLIP)
        assert report["tree"] == {"clean": False, "dirty_count": 2}
        assert report["counts"]["written"] == 1

    def test_a_clean_tree_is_reported_clean(self, rv: RunVault) -> None:
        assert preview(rv, RUN_CREATE)["tree"] == {"clean": True, "dirty_count": 0}

    def test_apply_refuses_a_dirty_tree_before_reading_any_file(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        build_ten_adds(rv)
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        rv.write("00-landing/stray.md", KITCHEN_BARE)
        monkeypatch.setattr(tool, "load_git_state", lambda root: pytest.fail("the run started"))
        monkeypatch.setattr(tool, "plan_run_file", lambda *a, **k: pytest.fail("a file was read"))
        args = cli_args(rv.root, RUN_ADD_FLIP, True, approved)
        refused(capsys, caplog, rv, args, "DIRTY_TREE")
        assert any(msg == "dirty tree, nothing written: 1 entries" for msg in fatal_messages(caplog))

    def test_apply_with_an_untracked_file_in_the_tree_writes_nothing(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_ten_adds(rv)
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        rv.write(ticket_path("untracked-note.md"), KITCHEN_INCOMPLETE)
        refused(capsys, caplog, rv, cli_args(rv.root, RUN_ADD_FLIP, True, approved), "DIRTY_TREE")

    def test_apply_refuses_after_a_partial_apply_until_the_tree_is_clean_again(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        rels = build_ten_adds(rv)
        approved = as_approved(preview(rv, RUN_ADD_FLIP))
        rv.write(rels[0], expected_add(("ticket", "qa", True)))
        path = write_json(rv.out / "approved.json", approved)
        refused(capsys, caplog, rv, cli_args(rv.root, RUN_ADD_FLIP, True, path), "DIRTY_TREE")


def temp_files(root: Path) -> List[str]:
    """Paths of any stray temp file the atomic apply may have left under root."""
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [name for name in dirnames if name != GIT_DIR_NAME]
        found.extend(name for name in filenames if name.startswith(TEMP_NAME_PREFIX))
    return found


def git_subcommands(calls: List[List[str]]) -> List[str]:
    """The git subcommand of each recorded call, skipping global options such as --no-optional-locks."""
    found: List[str] = []
    for command in calls:
        assert command[0] == "git", command
        found.append(next(word for word in command[1:] if not word.startswith("-")))
    return found


class TestRunWiring:
    @pytest.mark.parametrize("run", ALL_RUNS)
    def test_a_preview_never_reaches_apply_edit(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch, run: int
    ) -> None:
        build_kitchen(rv, KITCHEN_CONTENT[run])
        monkeypatch.setattr(tool, "apply_edit", lambda *a, **k: pytest.fail("a write began"))
        before = snapshot(rv.root)
        report = preview(rv, run)
        assert report["counts"]["written"] + report["counts"]["changed"] == 13
        assert snapshot(rv.root) == before

    def test_apply_writes_each_planned_file_once_through_apply_outcome(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        calls: List[str] = []
        real = tool._apply_outcome

        def spy(root: Path, item: Any) -> Any:
            calls.append(item.rel)
            return real(root, item)

        monkeypatch.setattr(tool, "_apply_outcome", spy)
        preview(rv, RUN_ADD_FLIP)
        assert calls == []
        report = apply_run(rv, RUN_ADD_FLIP)
        assert sorted(calls) == [entry["path"] for entry in report["writes"]]
        assert len(calls) == len(set(calls)) == 13

    def test_the_apply_report_records_the_tree_as_it_was_before_the_writes(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        report = apply_run(rv, RUN_CREATE)
        assert report["mode"] == "apply" and report["run"] == RUN_CREATE
        assert report["tree"] == {"clean": True, "dirty_count": 0}

    def test_an_unexpected_planning_error_skips_the_file_and_logs_only_the_class_name(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        rv.write(ticket_path("spec.md"), KITCHEN_INCOMPLETE)
        rv.commit_all()

        def broken(rel: str) -> Any:
            raise RuntimeError(CANARY)

        monkeypatch.setattr(tool, "kind_row_for", broken)
        with caplog.at_level(logging.DEBUG):
            out = plan_one(rv, ticket_path("spec.md"), RUN_ADD_FLIP)
        assert (out.kind, out.reason) == ("skipped", "VERIFY_FAILED")
        assert "RuntimeError" in caplog.text and CANARY not in caplog.text

    def test_an_interrupt_while_planning_writes_nothing_and_logs_the_count(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        approved = as_approved(preview(rv, RUN_ADD_FLIP))
        real = tool.plan_run_file
        seen: List[str] = []

        def interrupting(root: Path, rel: str, git: Any, run: int) -> Any:
            seen.append(rel)
            if len(seen) == 3:
                raise KeyboardInterrupt
            return real(root, rel, git, run)

        monkeypatch.setattr(tool, "plan_run_file", interrupting)
        before = snapshot(rv.root)
        with caplog.at_level(logging.WARNING), pytest.raises(KeyboardInterrupt):
            tool.run_policy(rv.root, RUN_ADD_FLIP, True, approved)
        assert snapshot(rv.root) == before
        assert "interrupted while planning after 2 files; nothing was written" in caplog.text

    def test_an_interrupt_while_writing_leaves_whole_files_and_a_rerun_finishes(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        approved = as_approved(preview(rv, RUN_ADD_FLIP))
        real = tool.apply_edit
        count: List[int] = []

        def interrupting(path: Path, original: bytes, new_raw: bytes) -> Optional[str]:
            count.append(1)
            if len(count) == 3:
                raise KeyboardInterrupt
            return real(path, original, new_raw)

        monkeypatch.setattr(tool, "apply_edit", interrupting)
        with caplog.at_level(logging.WARNING), pytest.raises(KeyboardInterrupt):
            tool.run_policy(rv.root, RUN_ADD_FLIP, True, approved)
        assert "interrupted after 2 files" in caplog.text
        assert temp_files(rv.root) == []
        monkeypatch.setattr(tool, "apply_edit", real)
        whole = [file_state(rv, name, KITCHEN_INCOMPLETE, triple) for _k, name, triple in KIND_FIXTURES]
        assert whole.count("done") == 2 and whole.count("original") == 11
        rv.commit_all()
        report = tool.run_policy(rv.root, RUN_ADD_FLIP, True, approved)
        assert report["counts"]["written"] == 11
        assert all(rv.read(ticket_path(n)) == expected_add(t) for _k, n, t in KIND_FIXTURES)

    def test_a_file_changed_after_planning_keeps_its_newer_bytes(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        approved = as_approved(preview(rv, RUN_ADD_FLIP))
        real = tool._write_planned
        newer = KITCHEN_INCOMPLETE + b"A newer line typed meanwhile.\n"

        def late_edit(root: Path, outcomes: List[Any]) -> List[Any]:
            (root / ticket_path("design.md")).write_bytes(newer)
            return real(root, outcomes)

        monkeypatch.setattr(tool, "_write_planned", late_edit)
        report = tool.run_policy(rv.root, RUN_ADD_FLIP, True, approved)
        assert skip_codes(report) == {
            ticket_path("design.md"): "CHANGED_DURING_RUN",
            ticket_path(UNMATCHED_FIXTURE): "NO_KIND_ROW",
        }
        assert rv.read(ticket_path("design.md")) == newer
        assert report["counts"]["written"] == 12

    def test_git_runs_only_read_only_subcommands(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        calls: List[List[str]] = []
        real = subprocess.run

        def recording(command: List[str], *args: Any, **kwargs: Any) -> Any:
            calls.append(list(command))
            return real(command, *args, **kwargs)

        monkeypatch.setattr(tool.subprocess, "run", recording)
        apply_run(rv, RUN_ADD_FLIP)
        assert calls and set(git_subcommands(calls)) <= ALLOWED_GIT_COMMANDS
        assert {"status", "ls-files", "diff"} == set(git_subcommands(calls))
        status_calls = [c for c in calls if "status" in c]
        assert status_calls and all(c[1] == "--no-optional-locks" for c in status_calls)


def file_state(vault: RunVault, name: str, original: bytes, triple: Tuple[str, str, bool]) -> str:
    """Classify a file as original, done (the expected add bytes), or broken (anything else)."""
    raw = vault.read(ticket_path(name))
    if raw == original:
        return "original"
    return "done" if raw == expected_add(triple) else "broken"


FLAG_CASES: List[Tuple[str, List[str], str]] = [
    ("approved report without run", ["--approved-report", "{report}"], "FLAG_COMBINATION"),
    ("approved report and apply without run", ["--apply", "--approved-report", "{report}"],
     "FLAG_COMBINATION"),
    ("approved report and run without apply", ["--run", "1", "--approved-report", "{report}"],
     "FLAG_COMBINATION"),
    ("run and apply without a report", ["--run", "1", "--apply"], "APPROVED_REPORT_REQUIRED"),
    ("run three and apply without a report", ["--run", "3", "--apply"], "APPROVED_REPORT_REQUIRED"),
]


class TestRunCli:
    @pytest.mark.parametrize("case,flags,code", FLAG_CASES, ids=[case[0] for case in FLAG_CASES])
    def test_a_refused_flag_combination_exits_two_and_reads_nothing(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch, case: str, flags: List[str], code: str,
    ) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        report = write_json(rv.out / "r.json", approved_report([]))
        monkeypatch.setattr(tool, "load_git_state", lambda root: pytest.fail("the run started"))
        monkeypatch.setattr(tool, "check_tree_clean", lambda root: pytest.fail("the tree was read"))
        args = ["--vault-root", str(rv.root)] + [flag.format(report=report) for flag in flags]
        refused(capsys, caplog, rv, args, code)

    @pytest.mark.parametrize("argv", [
        ["--run", "0"], ["--run", "5"], ["--run", "-1"], ["--run", "x"], ["--run", "1.5"],
        ["--run"], ["--ru", "1"], ["--approved", "x"], ["--approved-report"],
    ])
    def test_a_bad_run_flag_exits_two(self, argv: List[str], capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as info:
            tool.parse_args(argv)
        assert info.value.code == 2

    def test_the_new_flags_default_to_off_and_parse_to_their_types(self, tmp_path: Path) -> None:
        defaults = tool.parse_args([])
        assert defaults.run is None and defaults.approved_report is None
        args = tool.parse_args(["--run", "2", "--apply", "--approved-report", str(tmp_path / "r.json")])
        assert args.run == 2 and isinstance(args.run, int)
        assert args.approved_report == tmp_path / "r.json" and isinstance(args.approved_report, Path)

    def test_a_preview_prints_the_report_and_saves_the_same_text(
        self, rv: RunVault, capsys: pytest.CaptureFixture
    ) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        saved = rv.out / "preview.json"
        code, out, _err = run_main(capsys, cli_args(rv.root, RUN_CREATE, report_path=saved))
        assert code == 0
        assert saved.read_text(encoding="utf-8") == out
        assert out == json.dumps(json.loads(out), sort_keys=True, indent=2) + "\n"
        assert json.loads(out)["counts"]["written"] == 13

    def test_an_apply_through_main_writes_the_files_and_exits_zero(
        self, rv: RunVault, capsys: pytest.CaptureFixture
    ) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        approved = save_preview(rv, capsys, RUN_CREATE)
        code, out, _err = run_main(capsys, cli_args(rv.root, RUN_CREATE, True, approved))
        assert code == 0 and json.loads(out)["mode"] == "apply"
        assert all(rv.read(ticket_path(n)) == expected_create(t) for _k, n, t in KIND_FIXTURES)

    def test_the_log_summary_carries_counts_and_no_path(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        with caplog.at_level(logging.INFO):
            run_main(capsys, cli_args(rv.root, RUN_CREATE))
        message = next(r.getMessage() for r in caplog.records if r.levelno == logging.INFO)
        assert message.startswith("preview run 2: scanned=")
        assert "written=13" in message and "tree_clean=True" in message
        assert "02-tickets" not in message

    def test_a_report_path_that_cannot_be_used_exits_two_in_run_mode(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        args = cli_args(rv.root, RUN_CREATE, report_path=rv.out / "missing" / "r.json")
        refused(capsys, caplog, rv, args, "REPORT_PATH_INVALID")

    def test_a_vault_that_is_not_a_repository_exits_two_in_run_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        isolate_git(monkeypatch, tmp_path)
        plain = tmp_path / "plain"
        (plain / "02-tickets" / "T-900").mkdir(parents=True)
        (plain / "02-tickets" / "T-900" / "spec.md").write_bytes(KITCHEN_BARE)
        with caplog.at_level(logging.INFO):
            code, out, _err = run_main(capsys, cli_args(plain, RUN_CREATE))
        assert code == 2 and out == ""
        assert fatal_messages(caplog)[-1] == FATAL_PREFIX + "GIT_NONZERO_EXIT"
        assert (plain / "02-tickets" / "T-900" / "spec.md").read_bytes() == KITCHEN_BARE

    def test_a_read_only_target_among_ten_writes_exits_three_and_a_rerun_finishes(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        rels = build_ten_adds(rv)
        locked = rels[6]
        approved = save_preview(rv, capsys, RUN_ADD_FLIP)
        (rv.root / locked).chmod(READ_ONLY_FILE_MODE)
        saved = rv.out / "applied.json"
        code, _out, _err = run_main(capsys, cli_args(rv.root, RUN_ADD_FLIP, True, approved, saved))
        report = json.loads(saved.read_text(encoding="utf-8"))
        assert code == 3
        assert skip_codes(report) == {locked: "WRITE_FAILED"}
        assert report["counts"]["written"] == 9 and report["counts"]["skipped"] == 1
        assert temp_files(rv.root) == [] and rv.read(locked) == KITCHEN_INCOMPLETE
        assert [rel for rel in rels if rv.read(rel) == expected_add(("ticket", "qa", True))] == [
            rel for rel in rels if rel != locked
        ]
        refused(capsys, caplog, rv, cli_args(rv.root, RUN_ADD_FLIP, True, approved), "DIRTY_TREE")
        rv.commit_all()
        (rv.root / locked).chmod(0o644)
        code, _out, _err = run_main(capsys, cli_args(rv.root, RUN_ADD_FLIP, True, approved, saved))
        assert code == 0 and json.loads(saved.read_text(encoding="utf-8"))["counts"]["written"] == 1
        assert rv.read(locked) == expected_add(("ticket", "qa", True))


def build_mixed_run1(vault: RunVault) -> None:
    """A vault that gives Run 1 every kind of outcome: adds, flips, skips, complete, and not target."""
    build_kitchen(vault, KITCHEN_INCOMPLETE)
    flip = doc(["status: dropped", "catalog_type: ticket", "doc_role: spec", "indexable: true", "indexed: null"])
    vault.write("02-tickets/T-1/spec.md", flip)
    vault.write("02-tickets/T-2/design.md", flip.replace(b"dropped", b"Cancelled"))
    vault.write("00-landing/note.md", doc(["status: archived", "indexable: true"]))
    vault.write("02-tickets/T-3/spec.md", b"---\ntitle: [unclosed\n---\nbody\n")
    vault.write("02-tickets/T-4/spec.md", doc(["status: cancelled", "indexable: true", "doc_role: spec"]))
    vault.write("02-tickets/T-5/spec.md", flip.replace(b"indexable: true", b"indexable: True"))
    vault.write("02-tickets/T-6/spec.md", doc(["doc_role: custom"]))
    vault.write("02-tickets/T-7/spec.md", doc(["catalog_type: ticket", "doc_role: spec", "indexable: true", "indexed: null"]))
    vault.write("02-tickets/T-8/spec.md", doc(["catalog_type: ticket", "doc_role: reference", "indexable: false", "indexed: null"]))
    vault.write("02-tickets/T-9/spec.md", KITCHEN_BARE)
    vault.write("00-landing/plain.md", KITCHEN_BARE)
    vault.commit_all()
    vault.write("02-tickets/T-10/ignored/spec.md", KITCHEN_INCOMPLETE)


class TestReportContract:
    def test_the_report_has_exactly_the_contract_keys(self, rv: RunVault) -> None:
        build_mixed_run1(rv)
        report = preview(rv, RUN_ADD_FLIP)
        assert set(report) == REPORT_KEYS
        assert set(report["counts"]) == COUNT_KEYS
        assert set(report["by_class"]) == set(CLASS_NAMES)
        assert set(report["tree"]) == {"clean", "dirty_count"}
        assert (report["mode"], report["run"]) == ("preview", RUN_ADD_FLIP)

    def test_the_counts_match_the_fixture(self, rv: RunVault) -> None:
        build_mixed_run1(rv)
        report = preview(rv, RUN_ADD_FLIP)
        counts = report["counts"]
        assert (counts["written"], counts["changed"], counts["skipped"]) == (13, 3, 6)
        assert counts["already_complete"] == 2
        assert (counts["result_true"], counts["result_false"]) == (10, 6)
        assert report["by_class"] == {"add": 13, "create": 0, "flip": 3, "rewrite": 0}
        assert report["flips_by_status"] == {"archived": 1, "cancelled": 1, "dropped": 1}
        assert report["by_kind"]["K5"] == {"add": 1, "create": 0, "flip": 1, "rewrite": 0}
        assert report["by_kind"]["none"] == {"add": 0, "create": 0, "flip": 1, "rewrite": 0}
        assert report["skipped_by_reason"] == {
            "PARSE_ERROR": 1, "MIXED_EDIT": 1, "UNEXPECTED_LINE_FORM": 1,
            "CONFLICT_DOC_ROLE": 1, "GITIGNORED": 1, "NO_KIND_ROW": 1,
        }
        assert report["complete_differs"] == ["02-tickets/T-8/spec.md"]

    def test_the_counts_reconcile(self, rv: RunVault) -> None:
        build_mixed_run1(rv)
        counts = preview(rv, RUN_ADD_FLIP)["counts"]
        assert counts["written"] + counts["changed"] + counts["skipped"] + counts["already_complete"] == (
            counts["classified"]
        )
        assert counts["scanned"] == counts["not_target"] + counts["classified"]
        files = [name for _d, _n, names in os.walk(str(rv.root)) for name in names if name.endswith(".md")]
        assert counts["scanned"] == len(files)
        assert counts["result_true"] + counts["result_false"] == counts["written"] + counts["changed"]

    def test_writes_and_skips_are_sorted_with_the_contract_entry_shapes(self, rv: RunVault) -> None:
        build_mixed_run1(rv)
        report = preview(rv, RUN_ADD_FLIP)
        paths = [entry["path"] for entry in report["writes"]]
        assert paths == sorted(paths) and len(paths) == 16
        assert all(set(entry) == WRITE_ENTRY_KEYS for entry in report["writes"])
        skipped = [entry["path"] for entry in report["skipped"]]
        assert skipped == sorted(skipped)
        assert all(set(entry) == {"path", "reason"} for entry in report["skipped"])

    def test_changes_are_field_old_new_lists_for_a_flip_and_empty_for_an_add(self, rv: RunVault) -> None:
        build_mixed_run1(rv)
        entries = write_entries(preview(rv, RUN_ADD_FLIP))
        flip = entries["02-tickets/T-1/spec.md"]
        assert (flip["class"], flip["kind"], flip["added"]) == ("flip", "K5", {})
        assert flip["changes"] == [["indexable", "true", "false"]]
        add = entries[ticket_path("spec.md")]
        assert (add["class"], add["kind"], add["changes"]) == ("add", "K5", [])
        assert add["added"] == {"catalog_type": "ticket", "doc_role": "spec", "indexable": True, "indexed": None}

    def test_a_rewrite_entry_lists_two_or_three_changes(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path(REVIEW_FIXTURE), KITCHEN_PLACEHOLDER)
        rv.commit_all()
        entries = write_entries(preview(rv, RUN_REWRITE))
        assert len(entries[ticket_path("spec.md")]["changes"]) == 3
        assert len(entries[ticket_path(REVIEW_FIXTURE)]["changes"]) == 2
        assert entries[ticket_path("spec.md")]["added"] == {}

    def test_not_labeled_and_exclusions_are_reported_in_every_run(self, rv: RunVault) -> None:
        for run in ALL_RUNS:
            report = preview(rv, run)
            assert report["not_labeled"] == NOT_LABELED and report["exclusions"] == S257_EXCLUSIONS

    def test_an_empty_vault_gives_every_key_and_zero_counts(self, rv: RunVault) -> None:
        report = preview(rv, RUN_REWRITE)
        assert set(report) == REPORT_KEYS
        assert all(value == 0 for value in report["counts"].values())
        assert report["writes"] == [] and report["skipped"] == [] and report["by_kind"] == {}
        assert report["complete_differs"] == [] and report["dispositions"] == {}
        assert report["flips_by_status"] == {} and report["skipped_by_reason"] == {}

    def test_the_report_is_plain_json(self, rv: RunVault) -> None:
        build_mixed_run1(rv)
        report = preview(rv, RUN_ADD_FLIP)
        assert json.loads(json.dumps(report)) == report


def manifest(root: Path, rels: Sequence[str]) -> Dict[str, str]:
    """Hash each path, and name the target of a symlink instead of reading through it."""
    result: Dict[str, str] = {}
    for rel in rels:
        path = root / rel
        result[rel] = "link:" + os.readlink(str(path)) if path.is_symlink() else sha_of(path.read_bytes())
    return result


BROKEN_FRONT = b"---\ntitle: [unclosed\n---\nbody\n"
FLIP_FRONT = doc(["status: cancelled", "catalog_type: ticket", "doc_role: spec",
                  "indexable: true", "indexed: null"])
LEFT_ALONE_FILES: Dict[str, bytes] = {
    "02-tickets/T-901/spec.md": BROKEN_FRONT,
    "02-tickets/T-900/scratch-a.md": KITCHEN_INCOMPLETE,
    "02-tickets/T-900/scratch-b.md": KITCHEN_BARE,
    "02-tickets/T-900/scratch-c.md": KITCHEN_PLACEHOLDER,
    "02-tickets/loose-incomplete.md": KITCHEN_INCOMPLETE,
    "02-tickets/loose-bare.md": KITCHEN_BARE,
    "02-tickets/loose-placeholder.md": KITCHEN_PLACEHOLDER,
    "02-tickets/T-902/spec.md": doc(["catalog_type: ticket", "doc_role: reference",
                                     "indexable: false", "indexed: null"]),
    "05-conversations/log.md": FLIP_FRONT,
    "06-chat-threads/day.md": KITCHEN_INCOMPLETE,
    "00-landing/plain.md": KITCHEN_BARE,
    "00-landing/real.md": KITCHEN_BARE,
}
IGNORED_FILES: Dict[str, bytes] = {
    "02-tickets/T-900/ignored/spec.md": KITCHEN_INCOMPLETE,
    "02-tickets/T-900/ignored/design.md": KITCHEN_BARE,
    "02-tickets/T-900/ignored/qa-findings.md": KITCHEN_PLACEHOLDER,
    "02-tickets/T-900/ignored/arch.md": FLIP_FRONT,
}
SYMLINK_REL = "02-tickets/T-900/cursor.md"
CONTROL_FILES: Dict[str, bytes] = {
    "02-tickets/T-903/spec.md": KITCHEN_INCOMPLETE,
    "02-tickets/T-903/design.md": KITCHEN_BARE,
    "02-tickets/T-903/qa-findings.md": KITCHEN_PLACEHOLDER,
    "02-tickets/T-903/arch.md": FLIP_FRONT,
}


def build_left_alone_vault(vault: RunVault) -> List[str]:
    """Build files no run may touch beside control files each run does change; return the left alone paths."""
    for rel, content in {**LEFT_ALONE_FILES, **CONTROL_FILES}.items():
        vault.write(rel, content)
    vault.symlink(SYMLINK_REL, "../../00-landing/real.md")
    vault.commit_all()
    for rel, content in IGNORED_FILES.items():
        vault.write(rel, content)
    return sorted(list(LEFT_ALONE_FILES) + list(IGNORED_FILES) + [SYMLINK_REL])


class TestAC04LeftAlone:
    def test_gitignored_and_unparseable_files_stay_byte_identical(self, rv: RunVault) -> None:
        left = build_left_alone_vault(rv)
        before = manifest(rv.root, left)
        changed_per_run = {RUN_ADD_FLIP: 2, RUN_CREATE: 1, RUN_REWRITE: 1}
        for run in ALL_RUNS:
            report = apply_run(rv, run)
            assert report["counts"]["written"] + report["counts"]["changed"] == changed_per_run[run]
            rv.commit_all()
            assert manifest(rv.root, left) == before, run
        for rel, content in CONTROL_FILES.items():
            assert rv.read(rel) != content, rel

    def test_each_left_alone_file_reports_its_own_closed_code(self, rv: RunVault) -> None:
        build_left_alone_vault(rv)
        first = skip_codes(preview(rv, RUN_ADD_FLIP))
        assert first["02-tickets/T-900/ignored/spec.md"] == "GITIGNORED"
        assert first["02-tickets/T-900/ignored/arch.md"] == "GITIGNORED"
        assert first[SYMLINK_REL] == "SYMLINK"
        assert first["02-tickets/T-901/spec.md"] == "PARSE_ERROR"
        assert first["02-tickets/T-900/scratch-a.md"] == "NO_KIND_ROW"
        assert first["02-tickets/loose-incomplete.md"] == "NO_KIND_ROW"
        second = skip_codes(preview(rv, RUN_CREATE))
        assert second["02-tickets/T-900/ignored/design.md"] == "GITIGNORED"
        assert second["02-tickets/T-900/scratch-b.md"] == "NO_KIND_ROW"
        third = skip_codes(preview(rv, RUN_REWRITE))
        assert third["02-tickets/T-900/ignored/qa-findings.md"] == "GITIGNORED"
        assert third["02-tickets/loose-placeholder.md"] == "NO_KIND_ROW"

    def test_the_unlabeled_folders_and_hand_set_files_are_never_listed_as_writes(self, rv: RunVault) -> None:
        build_left_alone_vault(rv)
        for run in ALL_RUNS:
            paths = [entry["path"] for entry in preview(rv, run)["writes"]]
            assert not any(p.startswith(("05-conversations", "06-chat-threads", "00-landing")) for p in paths)
            assert "02-tickets/T-902/spec.md" not in paths
        assert preview(rv, RUN_ADD_FLIP)["complete_differs"] == ["02-tickets/T-902/spec.md"]

    @pytest.mark.parametrize("run", ALL_RUNS)
    def test_untracked_and_uncommitted_candidates_are_skipped_with_their_codes(
        self, rv: RunVault, run: int
    ) -> None:
        content = KITCHEN_CONTENT[run]
        rv.write(ticket_path("spec.md"), content)
        rv.commit_all()
        edited = content + b"A line typed after the last commit.\n"
        rv.write(ticket_path("spec.md"), edited)
        rv.write(ticket_path("design.md"), content)
        staged = rv.write(ticket_path("qa-findings.md"), content)
        rv.git("add", "--", ticket_path("qa-findings.md"))
        report = preview(rv, run)
        assert skip_codes(report) == {
            ticket_path("spec.md"): "UNCOMMITTED",
            ticket_path("design.md"): "UNTRACKED",
            ticket_path("qa-findings.md"): "UNCOMMITTED",
        }
        assert report["writes"] == []
        assert rv.read(ticket_path("spec.md")) == edited and staged.read_bytes() == content


TERMINAL_SPELLINGS: List[Tuple[str, str]] = [
    ("cancelled", "cancelled"), ("Cancelled", "cancelled"), ('"  dropped  "', "dropped"),
    ("superseded", "superseded"), ("SUPERSEDED", "superseded"), ("archived", "archived"),
    ("  Archived", "archived"), ("absorbed", "absorbed"), ("dropped", "dropped"),
]
NOT_TERMINAL_VALUES = [
    "active | archived", "parked", "closed", "shipped", "active", "''", "cancelled soon",
    "not cancelled", "1", "true", "~", "[cancelled]", "{state: cancelled}",
]


def status_file(status: str, indexable: str = "true") -> bytes:
    """A complete spec file with the given raw status text and indexable value."""
    return doc(["title: Fixture", "status: " + status, "catalog_type: ticket", "doc_role: spec",
                "indexable: " + indexable, "indexed: null"])


class TestAC05TerminalRule:
    def test_each_terminal_value_flips(self, rv: RunVault) -> None:
        rels = ["02-tickets/T-{}/spec.md".format(n) for n in range(len(TERMINAL_SPELLINGS))]
        for rel, (spelling, _word) in zip(rels, TERMINAL_SPELLINGS):
            rv.write(rel, status_file(spelling))
        rv.commit_all()
        report = apply_run(rv, RUN_ADD_FLIP)
        for rel, (spelling, _word) in zip(rels, TERMINAL_SPELLINGS):
            assert rv.read(rel) == status_file(spelling, "false"), spelling
        assert report["counts"]["changed"] == len(TERMINAL_SPELLINGS)
        assert report["flips_by_status"] == {
            "cancelled": 2, "dropped": 2, "superseded": 2, "archived": 2, "absorbed": 1,
        }

    @pytest.mark.parametrize("word", ["cancelled", "superseded", "dropped", "archived", "absorbed"])
    def test_every_one_of_the_five_words_flips_on_its_own(self, rv: RunVault, word: str) -> None:
        rv.write(ticket_path("spec.md"), status_file(word))
        rv.commit_all()
        report = apply_run(rv, RUN_ADD_FLIP)
        assert report["flips_by_status"] == {word: 1}
        assert rv.read(ticket_path("spec.md")) == status_file(word, "false")

    def test_values_that_are_not_terminal_never_flip(self, rv: RunVault) -> None:
        rels = ["02-tickets/T-{}/spec.md".format(n) for n in range(len(NOT_TERMINAL_VALUES))]
        for rel, value in zip(rels, NOT_TERMINAL_VALUES):
            rv.write(rel, status_file(value))
        rv.commit_all()
        before = hashes(rv.root, rels)
        report = apply_run(rv, RUN_ADD_FLIP)
        assert report["counts"]["changed"] == 0 and report["flips_by_status"] == {}
        assert hashes(rv.root, rels) == before

    def test_a_status_missing_from_the_file_never_flips(self, rv: RunVault) -> None:
        raw = doc(["title: Fixture", "catalog_type: ticket", "doc_role: spec",
                   "indexable: true", "indexed: null"])
        rv.write(ticket_path("spec.md"), raw)
        rv.commit_all()
        assert apply_run(rv, RUN_ADD_FLIP)["counts"]["changed"] == 0
        assert rv.read(ticket_path("spec.md")) == raw

    def test_no_terminal_file_keeps_indexable_true_after_run_one(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), status_file("cancelled"))
        rv.write("02-tickets/T-1/design.md", doc(["status: dropped"]))
        rv.write("00-landing/2026/09/weekly-1-1.md", doc(["status: archived", "indexable: true"]))
        rv.write("00-landing/open.md", doc(["status: active", "indexable: true"]))
        rv.commit_all()
        apply_run(rv, RUN_ADD_FLIP)
        words = {"cancelled", "superseded", "dropped", "archived", "absorbed"}
        stale = []
        for dirpath, _dirs, names in os.walk(str(rv.root / "00-landing")):
            for name in names:
                front = parse_front((Path(dirpath) / name).read_bytes())
                if str(front.get("status")).strip().lower() in words and front.get("indexable") is True:
                    stale.append(name)
        assert stale == []
        assert parse_front(rv.read("02-tickets/T-1/design.md"))["indexable"] is False
        assert parse_front(rv.read("00-landing/open.md"))["indexable"] is True


PLACEHOLDER_VARIANT_FILES = [
    ("T-{}".format(n), doc(PLACEHOLDER_HEAD + lines + ["indexed: null"]))
    for n, (_case, lines) in enumerate(HAND_VARIANTS + LINE_FORM_VARIANTS)
]


class TestAC06Rewrite:
    def test_only_the_exact_placeholder_triple_is_rewritten(self, rv: RunVault) -> None:
        rels = ["02-tickets/{}/spec.md".format(folder) for folder, _raw in PLACEHOLDER_VARIANT_FILES]
        for rel, (_folder, raw) in zip(rels, PLACEHOLDER_VARIANT_FILES):
            rv.write(rel, raw)
        rv.write(ticket_path("spec.md"), KITCHEN_PLACEHOLDER)
        rv.write("00-landing/outside.md", KITCHEN_PLACEHOLDER)
        rv.commit_all()
        before = hashes(rv.root, rels + ["00-landing/outside.md"])
        report = apply_run(rv, RUN_REWRITE)
        assert rv.read(ticket_path("spec.md")) == expected_rewrite(SPEC_TRIPLE)
        assert hashes(rv.root, rels + ["00-landing/outside.md"]) == before
        assert report["counts"]["changed"] == 1
        assert report["skipped_by_reason"] == {"UNEXPECTED_LINE_FORM": len(LINE_FORM_VARIANTS)}

    def test_a_placeholder_without_a_row_is_counted_as_left(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path(UNMATCHED_FIXTURE), KITCHEN_PLACEHOLDER)
        rv.commit_all()
        report = apply_run(rv, RUN_REWRITE)
        assert report["dispositions"] == {"legacy-note": {"resolved": 1, "left": 1}}
        assert rv.read(ticket_path(UNMATCHED_FIXTURE)) == KITCHEN_PLACEHOLDER

    def test_after_run_three_no_placeholder_with_a_row_remains(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_PLACEHOLDER)
        apply_run(rv, RUN_REWRITE)
        rv.commit_all()
        assert preview(rv, RUN_REWRITE)["counts"]["changed"] == 0
        left = [e for e in preview(rv, RUN_REWRITE)["skipped"] if e["reason"] == "NO_KIND_ROW"]
        assert [e["path"] for e in left] == [ticket_path(UNMATCHED_FIXTURE)]


def hand_edit(vault: RunVault) -> Dict[str, bytes]:
    """Type two values by hand into labeled files, commit, and return the edited bytes by path."""
    edited: Dict[str, bytes] = {}
    review = ticket_path(REVIEW_FIXTURE)
    edited[review] = vault.read(review).replace(b"indexable: false", b"indexable: true")
    spec = ticket_path(SPEC_FIXTURE)
    edited[spec] = vault.read(spec).replace(b"doc_role: spec", b"doc_role: custom")
    for rel, raw in edited.items():
        vault.write(rel, raw)
    vault.commit_all()
    return edited


class TestAC07PreviewApplyRerun:
    @pytest.mark.parametrize("run", ALL_RUNS)
    def test_preview_matches_apply_and_second_run_is_empty(
        self, rv: RunVault, monkeypatch: pytest.MonkeyPatch, run: int
    ) -> None:
        build_kitchen(rv, KITCHEN_CONTENT[run])
        before = snapshot(rv.root)
        with monkeypatch.context() as patch:
            patch.setattr(tool, "apply_edit", lambda *a, **k: pytest.fail("a write began"))
            first = preview(rv, run)
            second = preview(rv, run)
        assert first == second and snapshot(rv.root) == before
        applied = apply_run(rv, run, as_approved(first))
        assert json.dumps(first["writes"], sort_keys=True) == json.dumps(applied["writes"], sort_keys=True)
        rv.commit_all()
        after_apply = snapshot(rv.root)
        again = preview(rv, run)
        assert again["writes"] == [] and (again["counts"]["written"], again["counts"]["changed"]) == (0, 0)
        assert snapshot(rv.root) == after_apply
        replay = apply_run(rv, run, as_approved(first))
        assert replay["writes"] == [] and snapshot(rv.root) == after_apply

    @pytest.mark.parametrize("run", ALL_RUNS)
    def test_hand_edits_survive_a_second_run(self, rv: RunVault, run: int) -> None:
        build_kitchen(rv, KITCHEN_CONTENT[run])
        apply_run(rv, run)
        rv.commit_all()
        edited = hand_edit(rv)
        report = apply_run(rv, run)
        assert report["writes"] == []
        assert all(rv.read(rel) == raw for rel, raw in edited.items())

    def test_the_second_run_one_preview_after_apply_plans_no_flip_either(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), status_file("cancelled"))
        rv.write(ticket_path("design.md"), doc(["status: dropped"]))
        rv.commit_all()
        apply_run(rv, RUN_ADD_FLIP)
        rv.commit_all()
        again = preview(rv, RUN_ADD_FLIP)
        assert again["by_class"] == {"add": 0, "create": 0, "flip": 0, "rewrite": 0}
        assert again["counts"]["already_complete"] == 2

    def test_the_three_runs_touch_disjoint_files(self, rv: RunVault) -> None:
        rv.write(ticket_path("spec.md"), KITCHEN_INCOMPLETE)
        rv.write(ticket_path("design.md"), KITCHEN_BARE)
        rv.write(ticket_path("qa-findings.md"), KITCHEN_PLACEHOLDER)
        rv.write(ticket_path("arch.md"), FLIP_FRONT)
        rv.commit_all()
        touched = [{e["path"] for e in preview(rv, run)["writes"]} for run in ALL_RUNS]
        assert touched[0] == {ticket_path("spec.md"), ticket_path("arch.md")}
        assert touched[1] == {ticket_path("design.md")}
        assert touched[2] == {ticket_path("qa-findings.md")}


def canary_files(run: int) -> Dict[str, bytes]:
    """Files whose every nonclassifying value and body carries the canary, for one run."""
    body = "Body mentions {}.\n".format(CANARY).encode("utf-8")
    titled = ["title: {}".format(CANARY), "tags: [{}]".format(CANARY)]
    shapes = {
        RUN_ADD_FLIP: doc(titled + ["status: {}".format(CANARY)], body=body),
        RUN_CREATE: "# {}\n".format(CANARY).encode("utf-8") + body,
        RUN_REWRITE: doc(titled + ["doc_type: legacy-note", "catalog_type: unknown",
                                   "doc_role: unknown", "indexable: false",
                                   "indexed: {}".format(CANARY)], body=body),
    }
    extras = {
        "02-tickets/T-901/spec.md": "---\ntitle: [{}\n---\nbody\n".format(CANARY).encode("utf-8"),
        "02-tickets/T-902/spec.md": "---\nkey: !!int {}\n---\nbody\n".format(CANARY).encode("utf-8"),
        "02-tickets/T-903/spec.md": "---\nkey: !!bool {}\n---\nbody\n".format(CANARY).encode("utf-8"),
        "02-tickets/T-904/spec.md": "---\na: &x {0}\nb: *x\n*bad {0}\n---\n".format(CANARY).encode("utf-8"),
        "02-tickets/T-905/spec.md": b"---\ntitle: \xff " + CANARY.encode("utf-8") + b"\n---\nbody\n",
        "02-tickets/T-906/spec.md": doc(["title: {}".format(CANARY), "doc_role: {}".format(CANARY)], body=body),
        "02-tickets/T-907/spec.md": doc(["title: {}".format(CANARY), "status: cancelled",
                                          "catalog_type: ticket", "doc_role: spec",
                                          "indexable: true", "indexed: null"], body=body),
        "00-landing/note.md": doc(["title: {}".format(CANARY), "status: archived", "indexable: true"], body=body),
    }
    extras.update({ticket_path(name): shapes[run] for _k, name, _t in KIND_FIXTURES})
    extras[ticket_path(UNMATCHED_FIXTURE)] = shapes[run]
    return extras


def leak_text(capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture, saved: Path) -> str:
    """Everything a run could show: stdout, stderr, the saved report, and every log record."""
    captured = capsys.readouterr()
    return captured.out + captured.err + saved.read_text(encoding="utf-8") + caplog.text


def reconciles(report: Dict[str, Any]) -> bool:
    """True when the report's counts satisfy the identity and add up to the lists."""
    counts = report["counts"]
    parts = counts["written"] + counts["changed"] + counts["skipped"] + counts["already_complete"]
    return (
        parts == counts["classified"]
        and counts["scanned"] == counts["not_target"] + counts["classified"]
        and len(report["writes"]) == counts["written"] + counts["changed"]
        and len(report["skipped"]) == counts["skipped"]
        and sum(report["skipped_by_reason"].values()) == counts["skipped"]
        and sum(report["by_class"].values()) == len(report["writes"])
    )


class TestAC08ReportContent:
    @pytest.mark.parametrize("run", ALL_RUNS)
    def test_canary_absent_and_counts_reconcile(
        self, rv: RunVault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture, run: int
    ) -> None:
        for rel, raw in canary_files(run).items():
            rv.write(rel, raw)
        rv.commit_all()
        saved = rv.out / "preview.json"
        with caplog.at_level(logging.DEBUG):
            code, _out, _err = run_main(capsys, cli_args(rv.root, run, report_path=saved))
            assert code == 0
            report = json.loads(saved.read_text(encoding="utf-8"))
            assert reconciles(report) and report["counts"]["skipped"] >= 6
            applied = rv.out / "applied.json"
            code, _out, _err = run_main(capsys, cli_args(rv.root, run, True, saved, applied))
            assert code == 0 and reconciles(json.loads(applied.read_text(encoding="utf-8")))
            text = leak_text(capsys, caplog, applied) + saved.read_text(encoding="utf-8")
        assert CANARY not in text
        assert CANARY.encode("utf-8") in rv.read("02-tickets/T-901/spec.md")

    @pytest.mark.parametrize("run", ALL_RUNS)
    def test_the_report_values_come_from_a_closed_vocabulary(self, rv: RunVault, run: int) -> None:
        for rel, raw in canary_files(run).items():
            rv.write(rel, raw)
        rv.commit_all()
        report = preview(rv, run)
        reasons = set(report["skipped_by_reason"])
        assert reasons <= {
            "PARSE_ERROR", "NO_KIND_ROW", "MIXED_EDIT", "UNEXPECTED_LINE_FORM", "UNSAFE_TOP",
            "CONFLICT_DOC_ROLE", "CONFLICT_CATALOG_TYPE", "CONFLICT_INDEXABLE", "GITIGNORED",
            "UNTRACKED", "UNCOMMITTED", "SYMLINK", "UNREADABLE", "VERIFY_FAILED",
        }
        assert all(entry["reason"] in reasons for entry in report["skipped"])
        assert set(report["flips_by_status"]) <= {"cancelled", "superseded", "dropped", "archived", "absorbed"}

    def test_every_kind_row_gets_one_correct_triple_in_the_apply_report(self, rv: RunVault) -> None:
        build_kitchen(rv, KITCHEN_BARE)
        report = apply_run(rv, RUN_CREATE)
        entries = write_entries(report)
        for kind_id, name, triple in KIND_FIXTURES:
            entry = entries[ticket_path(name)]
            assert entry["kind"] == kind_id
            assert (entry["added"]["catalog_type"], entry["added"]["doc_role"],
                    entry["added"]["indexable"]) == triple
            assert entry["added"]["indexed"] is None


S257_GOLDEN_FILES: Dict[str, bytes] = {
    "02-tickets/T-900/T-900-state.md": doc(["title: State"]),
    "02-tickets/T-900/spec.md": b"# Spec\nBody.\n",
    "02-tickets/T-900/design.md": doc(["title: Design"]),
    "00-landing/decision.md": doc(["doc_type: decision"]),
    "00-landing/typed.md": doc(["type: conversation"]),
    "00-landing/odd.md": doc(["doc_type: made_up_type"]),
    "00-landing/broken.md": b"---\ndoc_type: [unclosed\n---\nBody\n",
    "00-landing/plain.md": b"No frontmatter.\n",
    "00-landing/done.md": doc(["doc_type: decision", "catalog_type: knowledge", "doc_role: decision",
                               "indexable: true", "indexed: null"]),
}
S257_GOLDEN_WRITES = [
    {"added": {"catalog_type": "knowledge", "doc_role": "decision", "indexable": True, "indexed": None},
     "path": "00-landing/decision.md"},
    {"added": {"catalog_type": "unknown", "doc_role": "unknown", "indexable": False, "indexed": None},
     "path": "00-landing/odd.md"},
    {"added": {"catalog_type": "session", "doc_role": "log", "indexable": False, "indexed": None},
     "path": "00-landing/typed.md"},
    {"added": {"catalog_type": "ticket", "doc_role": "state", "indexable": True, "indexed": None},
     "path": "02-tickets/T-900/T-900-state.md"},
]
# Source: the earlier tool at commit 02e2b19 run over the S257_GOLDEN_FILES fixture, 2026-10-05.
S257_GOLDEN_REPORT = {
    "counts": {
        "already_complete": 1, "classified": 7, "needing_fields": 5, "not_target": 3, "scanned": 10,
        "skipped": 2, "writes_indexable": 2, "written": 4,
    },
    "exclusions": S257_EXCLUSIONS,
    "rows": {"1": 1, "2": 3, "3": 1, "4": 1},
    "skipped": [
        {"path": "00-landing/broken.md", "reason": "PARSE_ERROR"},
        {"path": "ignored/skip.md", "reason": "GITIGNORED"},
    ],
    "skipped_by_reason": {"GITIGNORED": 1, "PARSE_ERROR": 1},
    "unmapped_doc_types": {"made_up_type": 1},
    "writes": S257_GOLDEN_WRITES,
}
S257_GOLDEN_RESULT_BYTES = {
    "00-landing/decision.md": b"---\ndoc_type: decision\ncatalog_type: knowledge\ndoc_role: decision\n"
                              b"indexable: true\nindexed: null\n---\nbody\n",
    "00-landing/odd.md": b"---\ndoc_type: made_up_type\ncatalog_type: unknown\ndoc_role: unknown\n"
                         b"indexable: false\nindexed: null\n---\nbody\n",
    "00-landing/typed.md": b"---\ntype: conversation\ncatalog_type: session\ndoc_role: log\n"
                           b"indexable: false\nindexed: null\n---\nbody\n",
    "02-tickets/T-900/T-900-state.md": b"---\ntitle: State\ncatalog_type: ticket\ndoc_role: state\n"
                                       b"indexable: true\nindexed: null\n---\nbody\n",
}


def build_s257_vault(vault: RunVault) -> None:
    """The fixture the earlier golden report came from: committed files plus one ignored candidate."""
    for rel, raw in S257_GOLDEN_FILES.items():
        vault.write(rel, raw)
    vault.commit_all()
    vault.write("ignored/skip.md", doc(["doc_type: decision"]))


class TestS257ModeUnchanged:
    def test_a_preview_without_run_gives_the_s257_report_exactly(
        self, rv: RunVault, capsys: pytest.CaptureFixture
    ) -> None:
        build_s257_vault(rv)
        code, out, _err = run_main(capsys, ["--vault-root", str(rv.root)])
        assert code == 0
        assert json.loads(out) == {**S257_GOLDEN_REPORT, "mode": "preview"}
        assert tool.run(rv.root, False) == {**S257_GOLDEN_REPORT, "mode": "preview"}

    def test_an_apply_without_run_writes_the_s257_bytes_and_needs_no_clean_tree(
        self, rv: RunVault, capsys: pytest.CaptureFixture
    ) -> None:
        build_s257_vault(rv)
        rv.write("00-landing/stray.txt", b"stray\n")
        code, out, _err = run_main(capsys, ["--vault-root", str(rv.root), "--apply"])
        assert code == 0
        assert json.loads(out) == {**S257_GOLDEN_REPORT, "mode": "apply"}
        for rel, raw in S257_GOLDEN_RESULT_BYTES.items():
            assert rv.read(rel) == raw
        assert rv.read("02-tickets/T-900/spec.md") == S257_GOLDEN_FILES["02-tickets/T-900/spec.md"]

    def test_the_report_has_none_of_the_run_keys(self, rv: RunVault) -> None:
        build_s257_vault(rv)
        report = tool.run(rv.root, False)
        assert not {"run", "tree", "by_class", "by_kind", "dispositions", "not_labeled"} & set(report)

    def test_without_run_none_of_the_s266_machinery_runs(
        self, rv: RunVault, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_s257_vault(rv)
        for name in ("run_policy", "plan_run_file", "check_tree_clean", "load_approved_report"):
            monkeypatch.setattr(tool, name, lambda *a, **k: pytest.fail("run mode code ran"))
        assert run_main(capsys, ["--vault-root", str(rv.root)])[0] == 0
        assert run_main(capsys, ["--vault-root", str(rv.root), "--apply"])[0] == 0

    def test_ticket_files_s257_never_touches_stay_unlabeled_in_s257_mode(
        self, rv: RunVault, capsys: pytest.CaptureFixture
    ) -> None:
        build_kitchen(rv, KITCHEN_INCOMPLETE)
        before = snapshot(rv.root)
        code, out, _err = run_main(capsys, ["--vault-root", str(rv.root), "--apply"])
        assert code == 0
        written = [entry["path"] for entry in json.loads(out)["writes"]]
        assert written == [ticket_path("T-900-state.md")]
        assert snapshot(rv.root) != before

    def test_check_preconditions_still_takes_two_arguments(self, tmp_path: Path) -> None:
        tool._check_preconditions(tmp_path, None)
        with pytest.raises(tool.PreconditionError):
            tool._check_preconditions(tmp_path / "absent", None)
        with pytest.raises(tool.PreconditionError):
            tool._check_preconditions(tmp_path, tmp_path / "no-folder" / "r.json")

    def test_the_s257_exit_codes_are_unchanged(self) -> None:
        assert (tool.EXIT_OK, tool.EXIT_PRECONDITION, tool.EXIT_WRITE_FAILED) == (0, 2, 3)
