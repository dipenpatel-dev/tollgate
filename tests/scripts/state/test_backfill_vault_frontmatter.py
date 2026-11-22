# Module:      test_backfill_vault_frontmatter.py
# Description: Tests for backfill_vault_frontmatter.py: the pure core (frontmatter
#              span, classification, line insertion) and the vault safety layer
#              (scan, git snapshot, planner, atomic apply), the report, the command
#              line, and the eight acceptance criteria, all over fixture vaults built
#              in pytest temp folders. The 37 expected mapping rows are literals
#              here. This file imports neither the tool's mapping table nor its
#              sentinel, state, or exclusion constants. An autouse fixture makes the
#              tool's default vault lookup raise, so no test can reach the real vault.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Test classes: TestCoreSpan, TestClassification, TestInsertion (B-01);
#              TestIterVaultFiles, TestGitState, TestPlanFile, TestAtomicApply (B-02);
#              TestBuildReport, TestParseArgs, TestDefaultVaultRoot, TestRun,
#              TestAC01MappingRows through TestAC08ReportContent, TestExitCodes,
#              TestCommandLine (B-03); TestF01YamlCrashContainment (QA F-01 fix)
# Version:     1.3
# ChangeLog:
#   Initial implementation
#   Fixture vault builder and safety layer tests
#   Report, CLI, AC level tests, vault fallback guard
#   QA F-01: YAML crash containment tests

import dataclasses
import hashlib
import json
import logging
import os
import re
import shutil
import signal
import site
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Tuple

import minipytest as pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "state"))
import backfill_vault_frontmatter as tool  # noqa: E402

REAL_DEFAULT_VAULT_ROOT = tool.default_vault_root


def refuse_default_vault_root() -> Any:
    """Stand in for default_vault_root in every test: a fallback to the real vault is a bug."""
    raise AssertionError("default_vault_root was called: a test would fall back to the real vault")


@pytest.fixture(autouse=True)
def forbid_real_vault_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the tool's default vault lookup raise for every test in this module."""
    monkeypatch.setattr(tool, "default_vault_root", refuse_default_vault_root)


EXPECTED_ROW_COUNT = 37
ROW_STATE = 1
ROW_DOC_TYPE_MAPPED = 2
ROW_DOC_TYPE_UNMAPPED = 3
ROW_TYPE_MAPPED = 4
ROW_NOT_TARGET = 5
LABEL_LIMIT = 64
ANY_NOTE_PATH = "00-landing/note.md"
STATE_PATH = "02-tickets/T-900/T-900-state.md"
CANARY = "CANARY_7Q2X_DO_NOT_LEAK"
LF = b"\n"
CRLF = b"\r\n"
EXPECTED_FIELD_ORDER = ["catalog_type", "doc_role", "indexable", "indexed"]
EXPECTED_STATE = ("ticket", "state", True)
EXPECTED_SENTINEL = ("unknown", "unknown", False)
UNMAPPED_DOC_TYPE = "made_up_type"
LABEL_NON_STRING = "<non-string>"
LABEL_UNPRINTABLE = "<unprintable>"

# Source: the spec doc_type Mapping, re-typed here as literals.
# Columns: doc_type, catalog_type, doc_role, indexable.
EXPECTED_ROWS: List[Tuple[str, str, str, bool]] = [
    ("session-start", "session", "session_log", True),
    ("coordinator-session", "session", "index", True),
    ("client-reference", "reference", "reference", True),
    ("repo-index", "reference", "index", True),
    ("architecture-reference", "reference", "reference", True),
    ("product-reference", "reference", "reference", True),
    ("databricks-reference", "reference", "reference", True),
    ("ticket_state", "ticket", "state", True),
    ("ticket_spec", "ticket", "spec", True),
    ("ticket_design", "ticket", "design", True),
    ("ticket_arch", "ticket", "design", True),
    ("ticket_qa", "ticket", "qa", True),
    ("ticket_session", "ticket", "session_log", True),
    ("ticket_whiteboard", "ticket", "whiteboard", True),
    ("ticket_diagram", "ticket", "reference", True),
    ("ticket_context", "ticket", "reference", True),
    ("ticket_other", "ticket", "reference", True),
    ("decision", "knowledge", "decision", True),
    ("learning", "knowledge", "learning", True),
    ("pattern", "knowledge", "pattern", True),
    ("whiteboard", "knowledge", "whiteboard", True),
    ("review", "knowledge", "review", True),
    ("standard", "knowledge", "standard", True),
    ("education", "knowledge", "education", True),
    ("conversation", "session", "log", False),
    ("trajectory", "session", "trajectory", False),
    ("module", "code_doc", "module", True),
    ("config", "code_doc", "config", True),
    ("test", "code_doc", "test", True),
    ("notebook", "code_doc", "notebook", True),
    ("sql", "code_doc", "sql", True),
    ("pipeline", "code_doc", "pipeline", True),
    ("script", "code_doc", "script", True),
    ("terraform", "code_doc", "terraform", True),
    ("shell", "code_doc", "shell", True),
    ("dockerfile", "code_doc", "dockerfile", True),
    ("repo_index", "code_doc", "index", True),
]
ROW_IDS = [row[0] for row in EXPECTED_ROWS]

# Frontmatter endings that could swallow or distort an inserted line (edge cases 9 to 14).
FRONTMATTER_VARIANTS: Dict[str, bytes] = {
    "list_end": b"doc_type: ticket_spec\ntags:\n  - a\n  - b\n",
    "comment_end": b"doc_type: ticket_spec\ntitle: x\n# trailing comment\n",
    "block_scalar_end": b"doc_type: ticket_spec\nnote: |\n  line one\n  line two\n",
    "block_scalar_keep": b"doc_type: ticket_spec\nnote: |+\n  text\n\n",
    "folded_scalar_end": b"doc_type: ticket_spec\nnote: >\n  folded\n  text\n",
    "quotes_and_links": (
        b'doc_type: ticket_spec\ntitle: "Quoted: value"\n'
        b"links:\n  - \"[[T-257-state]]\"\n  - '[[T-255-spec]]'\n"
    ),
    "inline_dashes": b'doc_type: ticket_spec\ntitle: "a --- b"\nnote: x---y\n',
    "flow_end": b"doc_type: ticket_spec\ntags: [a, b]\n",
    "nested_map_end": b"doc_type: ticket_spec\nmeta:\n  a: 1\n  b:\n    c: 2\n",
    "empty_value_end": b"doc_type: ticket_spec\nowner:\n",
    "plain_multiline_end": b"doc_type: ticket_spec\ntitle: first\n  second\n",
    "blank_line_before_close": b"doc_type: ticket_spec\ntitle: x\n\n",
    "date_value": b"doc_type: ticket_spec\ndate: 2026-10-01\n",
    "old_type_key": b"type: ticket_spec\ntitle: x\n",
}


class Edit(NamedTuple):
    """Everything the pure core produces for one file."""

    raw: bytes
    new_raw: bytes
    span: Any
    added: bytes
    fm: Dict[str, Any]
    additions: Dict[str, Any]


def as_tuple(values: Any) -> Optional[Tuple[str, str, bool]]:
    """Flatten a Values object to a plain tuple, or None."""
    if values is None:
        return None
    return (values.catalog_type, values.doc_role, values.indexable)


def make_file(block: bytes, eol: bytes = LF, tail: bytes = b"Body text.\n") -> bytes:
    """Build raw file bytes: opening delimiter, block lines, closing delimiter, tail."""
    delimiter = b"---" + eol
    text = block.replace(LF, eol) if eol != LF else block
    body = tail.replace(LF, eol) if eol != LF else tail
    return delimiter + text + delimiter + body


def build_edit(rel: str, raw: bytes) -> Optional[Edit]:
    """Run the pure core end to end the way the planner will."""
    span = tool.split_frontmatter(raw)
    if span is None:
        return None
    fm = tool.parse_block(span.block)
    if fm is None:
        return None
    values = tool.classify(rel, fm).values
    if values is None:
        return None
    additions = tool.missing_additions(fm, values)
    added = tool.render_additions(additions, span.eol)
    new_raw = tool.insert_lines(raw, span, added)
    return Edit(raw, new_raw, span, added, fm, additions)


def reparse(raw: bytes) -> Tuple[Any, Dict[str, Any]]:
    """Return the span and parsed mapping of raw, failing loudly if either is absent."""
    span = tool.split_frontmatter(raw)
    assert span is not None
    parsed = tool.parse_block(span.block)
    assert parsed is not None
    return span, parsed


def top_level_key_counts(block: bytes) -> Dict[str, int]:
    """Count top level 'key:' lines by text, since PyYAML hides duplicate keys."""
    counts: Dict[str, int] = {}
    for line in block.decode("utf-8").splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", line)
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def verify(edit: Edit, new_raw: Optional[bytes] = None, added: Optional[bytes] = None,
           additions: Optional[Dict[str, Any]] = None) -> bool:
    """Call verify_edit on an Edit, with optional tampered inputs."""
    return tool.verify_edit(
        edit.raw,
        edit.span,
        edit.added if added is None else added,
        edit.new_raw if new_raw is None else new_raw,
        edit.fm,
        edit.additions if additions is None else additions,
    )


class TestCoreSpan:
    """split_frontmatter and parse_block."""

    def test_lf_span_fields(self) -> None:
        raw = b"---\ndoc_type: decision\n---\nbody\n"
        span = tool.split_frontmatter(raw)
        assert span is not None
        assert span.block == b"doc_type: decision\n"
        assert span.eol == LF
        assert raw[span.close_start:] == b"---\nbody\n"

    def test_crlf_span_fields(self) -> None:
        raw = b"---\r\ndoc_type: decision\r\n---\r\nbody\r\n"
        span = tool.split_frontmatter(raw)
        assert span is not None
        assert span.block == b"doc_type: decision\r\n"
        assert span.eol == CRLF
        assert raw[span.close_start:] == b"---\r\nbody\r\n"

    def test_empty_block(self) -> None:
        raw = b"---\n---\nbody\n"
        span = tool.split_frontmatter(raw)
        assert span is not None
        assert span.block == b""
        assert raw[span.close_start:] == b"---\nbody\n"

    def test_close_at_end_of_file_without_newline(self) -> None:
        raw = b"---\ndoc_type: decision\n---"
        span = tool.split_frontmatter(raw)
        assert span is not None
        assert raw[span.close_start:] == b"---"

    def test_first_close_line_wins(self) -> None:
        raw = b"---\na: 1\n---\nbody\n---\nmore\n"
        span = tool.split_frontmatter(raw)
        assert span is not None
        assert span.block == b"a: 1\n"
        assert raw[span.close_start:] == b"---\nbody\n---\nmore\n"

    @pytest.mark.parametrize(
        "line",
        [b"--- \n", b"----\n", b"---x\n", b" ---\n", b"\t---\n", b"--\n", b"a --- b\n"],
        ids=["trailing_space", "four_dashes", "suffix", "indent", "tab", "two", "inline"],
    )
    def test_only_an_exact_line_closes(self, line: bytes) -> None:
        raw = b"---\na: 1\n" + line + b"b: 2\n"
        assert tool.split_frontmatter(raw) is None

    @pytest.mark.parametrize(
        "raw",
        [
            b"",
            b"---",
            b"---\n",
            b"---\na: 1\n",
            b"\n---\na: 1\n---\n",
            b"\xef\xbb\xbf---\na: 1\n---\n",
            b"--- \na: 1\n---\n",
            b"----\na: 1\n---\n",
            b"# Title\n---\na: 1\n---\n",
            b"---\ra: 1\r---\r",
        ],
        ids=[
            "empty", "bare_delimiter", "open_only", "no_close", "leading_blank",
            "bom", "open_trailing_space", "open_four_dashes", "starts_below_line_one",
            "lone_cr",
        ],
    )
    def test_not_frontmatter_returns_none(self, raw: bytes) -> None:
        assert tool.split_frontmatter(raw) is None

    def test_body_bytes_are_never_decoded(self) -> None:
        tail = b"\xff\xfe binary \x00 \x80 tail"
        raw = b"---\ndoc_type: decision\n---\n" + tail
        span = tool.split_frontmatter(raw)
        assert span is not None
        assert raw[span.close_start:] == b"---\n" + tail

    def test_parse_block_returns_mapping(self) -> None:
        parsed = tool.parse_block(b'title: "Quoted: value"\ncount: 3\ntags: [a, b]\n')
        assert parsed == {"title": "Quoted: value", "count": 3, "tags": ["a", "b"]}

    @pytest.mark.parametrize("block", [b"", b"\n", b"# only a comment\n"],
                             ids=["empty", "blank", "comment"])
    def test_parse_block_empty_gives_empty_mapping(self, block: bytes) -> None:
        assert tool.parse_block(block) == {}

    @pytest.mark.parametrize(
        "block",
        [
            b"- a\n- b\n",
            b"just a string\n",
            b"42\n",
            b"a: [unclosed\n",
            b"a: b: c\n",
            b"a: \xff\n",
            b"d: 2026-13-45\n",
            b"d: 0000-01-01\n",
            b"a: \x00\n",
            b"? [a, b]\n: c\n",
            b"a: !!python/object:os.system x\n",
            b"a: " + b"[" * 5000 + b"]" * 5000 + b"\n",
        ],
        ids=[
            "list", "string", "int", "unclosed_flow", "nested_colon", "bad_utf8",
            "month_13", "year_zero", "nul", "unhashable_key", "python_tag", "deep_nesting",
        ],
    )
    def test_parse_block_failures_return_none(self, block: bytes) -> None:
        assert tool.parse_block(block) is None

    def test_parse_failure_logs_no_frontmatter_text(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        block = "title: visible_key_value\nbroken: [" + CANARY + "\n"
        with caplog.at_level(logging.DEBUG):
            assert tool.parse_block(block.encode("utf-8")) is None
        assert caplog.records, "a failed parse should leave a class name record"
        assert CANARY not in caplog.text
        assert "visible_key_value" not in caplog.text


class TestClassification:
    """Mapping lookup, the five row contract, additions, and conflicts."""

    def test_literals_hold_37_distinct_rows(self) -> None:
        assert len(EXPECTED_ROWS) == EXPECTED_ROW_COUNT
        assert len({row[0] for row in EXPECTED_ROWS}) == EXPECTED_ROW_COUNT

    @pytest.mark.parametrize("row", EXPECTED_ROWS, ids=ROW_IDS)
    def test_lookup_returns_each_table_row(self, row: Tuple[str, str, str, bool]) -> None:
        assert as_tuple(tool.lookup_values(row[0])) == row[1:]

    @pytest.mark.parametrize("row", EXPECTED_ROWS, ids=ROW_IDS)
    def test_doc_type_classifies_as_row_two(self, row: Tuple[str, str, str, bool]) -> None:
        result = tool.classify(ANY_NOTE_PATH, {"doc_type": row[0]})
        assert result.row == ROW_DOC_TYPE_MAPPED
        assert as_tuple(result.values) == row[1:]
        assert result.label is None

    @pytest.mark.parametrize("row", EXPECTED_ROWS, ids=ROW_IDS)
    def test_old_type_key_classifies_as_row_four(self, row: Tuple[str, str, str, bool]) -> None:
        result = tool.classify(ANY_NOTE_PATH, {"type": row[0]})
        assert result.row == ROW_TYPE_MAPPED
        assert as_tuple(result.values) == row[1:]
        assert result.label is None

    @pytest.mark.parametrize(
        "value",
        ["ticket-spec", "Ticket_Spec", "ticket_spec ", " ticket_spec", "session_start",
         "repo-index2", "", "ticket_spec\n", "REPO-INDEX"],
    )
    def test_lookup_does_not_normalize(self, value: str) -> None:
        assert tool.lookup_values(value) is None

    @pytest.mark.parametrize(
        "value",
        ["context", "session_log", "spec", "design", "state", "index", "reference", "build",
         "feature", "ticket", "code_doc", "knowledge"],
    )
    def test_known_drift_values_stay_unmapped(self, value: str) -> None:
        """Source: the spec Scope Out 1 names context, session_log, spec, design."""
        assert tool.lookup_values(value) is None

    @pytest.mark.parametrize(
        "value",
        [None, 5, 1.5, True, ["ticket_spec"], {"a": 1}, b"ticket_spec"],
        ids=["none", "int", "float", "bool", "list", "dict", "bytes"],
    )
    def test_lookup_non_string_is_none_without_raising(self, value: Any) -> None:
        assert tool.lookup_values(value) is None

    @pytest.mark.parametrize(
        "rel",
        ["02-tickets/T-900/T-900-state.md", "02-tickets/ex-07/ex-07-state.md"],
    )
    def test_state_path_true(self, rel: str) -> None:
        assert tool.is_ticket_state_path(rel) is True

    @pytest.mark.parametrize(
        "rel",
        [
            "02-tickets/T-900/T-901-state.md",
            "02-tickets/T-900/sub/T-900-state.md",
            "02-tickets/T-900-state.md",
            "01-tickets/T-900/T-900-state.md",
            "T-900/T-900-state.md",
            "x/02-tickets/T-900/T-900-state.md",
            "/02-tickets/T-900/T-900-state.md",
            "02-tickets/T-900/T-900-state.txt",
            "02-tickets/T-900/T-900-spec.md",
            "02-tickets/T-900/T-900-STATE.md",
            "02-tickets//-state.md",
            "",
        ],
    )
    def test_state_path_false(self, rel: str) -> None:
        assert tool.is_ticket_state_path(rel) is False

    @pytest.mark.parametrize(
        "fm",
        [{"type": "ticket_state"}, {"type": "build"}, {"type": "feature"}, {},
         {"doc_type": UNMAPPED_DOC_TYPE}, {"doc_type": "ticket_spec"}],
        ids=["ticket_state", "build", "feature", "no_type", "unmapped_doc_type", "other_doc_type"],
    )
    def test_state_path_is_row_one_whatever_the_keys(self, fm: Dict[str, Any]) -> None:
        result = tool.classify(STATE_PATH, fm)
        assert result.row == ROW_STATE
        assert as_tuple(result.values) == EXPECTED_STATE
        assert result.label is None

    def test_state_path_without_frontmatter_is_row_one(self) -> None:
        assert tool.classify(STATE_PATH, None).row == ROW_STATE

    def test_state_named_file_in_wrong_place_falls_to_other_rows(self) -> None:
        wrong = "02-tickets/T-900/T-901-state.md"
        assert tool.classify(wrong, {"type": "build"}).row == ROW_NOT_TARGET
        spec = tool.classify(wrong, {"doc_type": "ticket_spec"})
        assert spec.row == ROW_DOC_TYPE_MAPPED
        assert as_tuple(spec.values) == ("ticket", "spec", True)

    def test_unmapped_doc_type_gets_sentinel_and_label(self) -> None:
        result = tool.classify(ANY_NOTE_PATH, {"doc_type": UNMAPPED_DOC_TYPE})
        assert result.row == ROW_DOC_TYPE_UNMAPPED
        assert as_tuple(result.values) == EXPECTED_SENTINEL
        assert result.label == UNMAPPED_DOC_TYPE

    @pytest.mark.parametrize("value", [None, ["a"], {"a": 1}, 7, True])
    def test_non_string_doc_type_is_row_three_without_raising(self, value: Any) -> None:
        result = tool.classify(ANY_NOTE_PATH, {"doc_type": value})
        assert result.row == ROW_DOC_TYPE_UNMAPPED
        assert as_tuple(result.values) == EXPECTED_SENTINEL
        assert result.label == LABEL_NON_STRING

    @pytest.mark.parametrize(
        "value,label",
        [
            (UNMAPPED_DOC_TYPE, UNMAPPED_DOC_TYPE),
            ("a.b-c_9", "a.b-c_9"),
            ("x" * LABEL_LIMIT, "x" * LABEL_LIMIT),
            ("x" * (LABEL_LIMIT + 1), LABEL_UNPRINTABLE),
            ("two words", LABEL_UNPRINTABLE),
            ("", LABEL_UNPRINTABLE),
            ("tab\there", LABEL_UNPRINTABLE),
            ("line\n", LABEL_UNPRINTABLE),
            ("caf\u00e9", LABEL_UNPRINTABLE),
            ("path/like", LABEL_UNPRINTABLE),
            (None, LABEL_NON_STRING),
            (5, LABEL_NON_STRING),
            (["a"], LABEL_NON_STRING),
            ({"a": 1}, LABEL_NON_STRING),
            (b"bytes", LABEL_NON_STRING),
        ],
    )
    def test_unmapped_label(self, value: Any, label: str) -> None:
        assert tool.unmapped_label(value) == label

    def test_doc_type_decides_when_both_keys_are_present(self) -> None:
        unmapped = tool.classify(ANY_NOTE_PATH, {"doc_type": UNMAPPED_DOC_TYPE, "type": "ticket_spec"})
        assert unmapped.row == ROW_DOC_TYPE_UNMAPPED
        assert as_tuple(unmapped.values) == EXPECTED_SENTINEL
        mapped = tool.classify(ANY_NOTE_PATH, {"doc_type": "decision", "type": "ticket_spec"})
        assert as_tuple(mapped.values) == ("knowledge", "decision", True)

    @pytest.mark.parametrize(
        "fm",
        [None, {}, {"type": "build"}, {"type": "feature"}, {"type": None},
         {"type": ["ticket_spec"]}, {"title": "x"}],
        ids=["no_frontmatter", "empty", "build", "feature", "null_type", "list_type", "other_keys"],
    )
    def test_everything_else_is_not_a_target(self, fm: Optional[Dict[str, Any]]) -> None:
        result = tool.classify(ANY_NOTE_PATH, fm)
        assert result.row == ROW_NOT_TARGET
        assert result.values is None
        assert result.label is None

    def test_missing_additions_all_four_in_field_order(self) -> None:
        values = tool.lookup_values("ticket_spec")
        additions = tool.missing_additions({"doc_type": "ticket_spec"}, values)
        assert list(additions) == EXPECTED_FIELD_ORDER
        assert additions == {
            "catalog_type": "ticket", "doc_role": "spec", "indexable": True, "indexed": None,
        }

    def test_missing_additions_partial_file(self) -> None:
        values = tool.lookup_values("ticket_spec")
        fm = {"catalog_type": "knowledge", "doc_role": "other"}
        additions = tool.missing_additions(fm, values)
        assert list(additions) == ["indexable", "indexed"]

    def test_missing_additions_complete_file_adds_nothing(self) -> None:
        values = tool.lookup_values("ticket_spec")
        fm = {"catalog_type": "x", "doc_role": "y", "indexable": "z", "indexed": "2026-10-01"}
        assert tool.missing_additions(fm, values) == {}

    @pytest.mark.parametrize("name", EXPECTED_FIELD_ORDER)
    def test_missing_additions_single_gap(self, name: str) -> None:
        values = tool.lookup_values("decision")
        fm = {key: "present" for key in EXPECTED_FIELD_ORDER if key != name}
        assert list(tool.missing_additions(fm, values)) == [name]

    def test_missing_additions_derive_sentinel_and_state_values(self) -> None:
        sentinel = tool.classify(ANY_NOTE_PATH, {"doc_type": UNMAPPED_DOC_TYPE}).values
        assert tool.missing_additions({}, sentinel) == {
            "catalog_type": "unknown", "doc_role": "unknown", "indexable": False, "indexed": None,
        }
        state = tool.classify(STATE_PATH, {}).values
        assert tool.missing_additions({}, state) == {
            "catalog_type": "ticket", "doc_role": "state", "indexable": True, "indexed": None,
        }

    def test_missing_additions_indexed_is_none_even_for_non_indexable_rows(self) -> None:
        values = tool.lookup_values("conversation")
        additions = tool.missing_additions({}, values)
        assert additions["indexable"] is False
        assert additions["indexed"] is None

    def test_no_conflict_when_values_match_or_keys_absent(self) -> None:
        values = tool.lookup_values("ticket_spec")
        assert tool.find_conflict({}, values) is None
        assert tool.find_conflict({"catalog_type": "ticket", "doc_role": "spec",
                                   "indexable": True}, values) is None
        off = tool.lookup_values("conversation")
        assert tool.find_conflict({"indexable": False}, off) is None

    @pytest.mark.parametrize(
        "fm,expected",
        [
            ({"catalog_type": "knowledge"}, "CONFLICT_CATALOG_TYPE"),
            ({"catalog_type": "Ticket"}, "CONFLICT_CATALOG_TYPE"),
            ({"catalog_type": ["ticket"]}, "CONFLICT_CATALOG_TYPE"),
            ({"doc_role": "design"}, "CONFLICT_DOC_ROLE"),
            ({"doc_role": None}, "CONFLICT_DOC_ROLE"),
            ({"indexable": False}, "CONFLICT_INDEXABLE"),
            ({"indexable": "true"}, "CONFLICT_INDEXABLE"),
            ({"indexable": 1}, "CONFLICT_INDEXABLE"),
            ({"indexable": None}, "CONFLICT_INDEXABLE"),
        ],
    )
    def test_conflicts_compare_type_and_value(self, fm: Dict[str, Any], expected: str) -> None:
        assert tool.find_conflict(fm, tool.lookup_values("ticket_spec")) == expected

    @pytest.mark.parametrize("indexed", [None, "2026-10-01", 5, "x", True, ["a"]])
    def test_indexed_never_conflicts(self, indexed: Any) -> None:
        assert tool.find_conflict({"indexed": indexed}, tool.lookup_values("ticket_spec")) is None

    def test_first_conflict_follows_field_order(self) -> None:
        fm = {"indexable": False, "doc_role": "x", "catalog_type": "y"}
        assert tool.find_conflict(fm, tool.lookup_values("ticket_spec")) == "CONFLICT_CATALOG_TYPE"
        del fm["catalog_type"]
        assert tool.find_conflict(fm, tool.lookup_values("ticket_spec")) == "CONFLICT_DOC_ROLE"


class TestInsertion:
    """render_additions, insert_lines, and verify_edit."""

    def test_render_lf(self) -> None:
        additions = {"catalog_type": "ticket", "doc_role": "spec", "indexable": True, "indexed": None}
        expected = b"catalog_type: ticket\ndoc_role: spec\nindexable: true\nindexed: null\n"
        assert tool.render_additions(additions, LF) == expected

    def test_render_crlf_and_false(self) -> None:
        additions = {"indexable": False, "indexed": None}
        assert tool.render_additions(additions, CRLF) == b"indexable: false\r\nindexed: null\r\n"

    def test_render_empty_is_empty_bytes(self) -> None:
        assert tool.render_additions({}, LF) == b""

    @pytest.mark.parametrize("row", EXPECTED_ROWS, ids=ROW_IDS)
    def test_rendered_lines_parse_back_to_the_same_typed_values(
        self, row: Tuple[str, str, str, bool]
    ) -> None:
        additions = tool.missing_additions({}, tool.lookup_values(row[0]))
        parsed = tool.parse_block(tool.render_additions(additions, LF))
        assert parsed == additions
        assert type(parsed["indexable"]) is bool
        assert parsed["indexed"] is None

    def test_insert_places_lines_above_the_closing_delimiter(self) -> None:
        raw = b"---\ndoc_type: decision\n---\nbody\n"
        span = tool.split_frontmatter(raw)
        assert span is not None
        result = tool.insert_lines(raw, span, b"x: 1\n")
        assert result == b"---\ndoc_type: decision\nx: 1\n---\nbody\n"

    def test_insert_into_crlf_file(self) -> None:
        raw = b"---\r\na: 1\r\n---\r\nbody\r\n"
        span = tool.split_frontmatter(raw)
        assert span is not None
        result = tool.insert_lines(raw, span, b"x: 1\r\n")
        assert result == b"---\r\na: 1\r\nx: 1\r\n---\r\nbody\r\n"

    def test_insert_into_empty_block(self) -> None:
        span = tool.split_frontmatter(b"---\n---\nbody\n")
        assert span is not None
        assert tool.insert_lines(b"---\n---\nbody\n", span, b"x: 1\n") == b"---\nx: 1\n---\nbody\n"

    def test_insert_when_file_ends_at_the_closing_delimiter(self) -> None:
        raw = b"---\na: 1\n---"
        span = tool.split_frontmatter(raw)
        assert span is not None
        assert tool.insert_lines(raw, span, b"x: 1\n") == b"---\na: 1\nx: 1\n---"

    def test_insert_nothing_returns_identical_bytes(self) -> None:
        raw = b"---\na: 1\n---\nbody\n"
        span = tool.split_frontmatter(raw)
        assert span is not None
        assert tool.insert_lines(raw, span, b"") == raw

    @pytest.mark.parametrize("eol", [LF, CRLF], ids=["lf", "crlf"])
    @pytest.mark.parametrize("name", sorted(FRONTMATTER_VARIANTS))
    def test_old_bytes_and_values_survive(self, name: str, eol: bytes) -> None:
        raw = make_file(FRONTMATTER_VARIANTS[name], eol)
        edit = build_edit(ANY_NOTE_PATH, raw)
        assert edit is not None
        cut = edit.span.close_start
        assert edit.new_raw[:cut] == raw[:cut]
        assert edit.new_raw[cut + len(edit.added):] == raw[cut:]
        new_span, new_fm = reparse(edit.new_raw)
        for key, value in edit.fm.items():
            assert new_fm[key] == value
        assert set(new_fm) == set(edit.fm) | set(EXPECTED_FIELD_ORDER)
        counts = top_level_key_counts(new_span.block)
        assert all(counts[field] == 1 for field in EXPECTED_FIELD_ORDER)
        assert verify(edit) is True

    def test_lf_file_gains_no_carriage_return(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n", LF))
        assert edit is not None
        assert b"\r" not in edit.new_raw

    def test_crlf_file_stays_pure_crlf(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n", CRLF))
        assert edit is not None
        assert edit.new_raw.count(LF) == edit.new_raw.count(CRLF) > 0

    def test_partial_file_gets_only_the_missing_lines(self) -> None:
        block = b"doc_type: ticket_spec\ncatalog_type: ticket\ndoc_role: spec\ntitle: x\n"
        edit = build_edit(ANY_NOTE_PATH, make_file(block))
        assert edit is not None
        assert edit.added == b"indexable: true\nindexed: null\n"
        new_span, _ = reparse(edit.new_raw)
        counts = top_level_key_counts(new_span.block)
        assert counts["catalog_type"] == 1 and counts["doc_role"] == 1

    def test_empty_block_state_file_gets_all_four_lines(self) -> None:
        edit = build_edit(STATE_PATH, b"---\n---\nbody\n")
        assert edit is not None
        expected = (b"---\ncatalog_type: ticket\ndoc_role: state\nindexable: true\n"
                    b"indexed: null\n---\nbody\n")
        assert edit.new_raw == expected

    @pytest.mark.parametrize(
        "block",
        [b"type: ticket_state\n", b"type: build\n", b"type: feature\n", b"title: no type key\n"],
        ids=["ticket_state", "build", "feature", "no_type"],
    )
    def test_state_file_gets_state_values_whatever_its_type(self, block: bytes) -> None:
        edit = build_edit(STATE_PATH, make_file(block))
        assert edit is not None
        _, new_fm = reparse(edit.new_raw)
        assert (new_fm["catalog_type"], new_fm["doc_role"], new_fm["indexable"]) == EXPECTED_STATE
        assert new_fm["indexed"] is None
        assert new_fm.get("type") == edit.fm.get("type")

    def test_file_without_trailing_newline_keeps_its_ending(self) -> None:
        raw = b"---\ndoc_type: decision\n---"
        edit = build_edit(ANY_NOTE_PATH, raw)
        assert edit is not None
        assert edit.new_raw.endswith(b"indexed: null\n---")
        assert verify(edit) is True

    def test_non_utf8_body_is_carried_through_untouched(self) -> None:
        tail = b"\xff\xfe\x00 raw body bytes \x80\n---\nstill body\n"
        raw = make_file(b"doc_type: decision\n", tail=tail)
        edit = build_edit(ANY_NOTE_PATH, raw)
        assert edit is not None
        assert edit.new_raw.endswith(b"---\n" + tail)
        assert verify(edit) is True

    @pytest.mark.parametrize("row", EXPECTED_ROWS, ids=ROW_IDS)
    def test_each_row_writes_its_values_and_a_second_pass_plans_nothing(
        self, row: Tuple[str, str, str, bool]
    ) -> None:
        raw = make_file(("doc_type: " + row[0] + "\n").encode("utf-8"))
        edit = build_edit(ANY_NOTE_PATH, raw)
        assert edit is not None
        _, new_fm = reparse(edit.new_raw)
        assert (new_fm["catalog_type"], new_fm["doc_role"], new_fm["indexable"]) == row[1:]
        assert new_fm["indexed"] is None
        assert tool.missing_additions(new_fm, tool.lookup_values(row[0])) == {}

    def test_verify_accepts_a_correct_edit(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        assert verify(edit) is True

    def test_verify_rejects_a_changed_prefix(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        assert verify(edit, new_raw=edit.new_raw.replace(b"decision", b"decisioX", 1)) is False

    def test_verify_rejects_a_changed_suffix(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        assert verify(edit, new_raw=edit.new_raw[:-1] + b"X") is False

    def test_verify_rejects_different_inserted_bytes(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        assert verify(edit, new_raw=edit.new_raw.replace(b"true", b"fals", 1)) is False

    def test_verify_rejects_a_prefix_change_that_parses_the_same(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n# keep this comment\n"))
        assert edit is not None
        tampered = edit.new_raw.replace(b"keep this", b"drop this", 1)
        assert reparse(tampered)[1] == {**edit.fm, **edit.additions}
        assert verify(edit, new_raw=tampered) is False

    def test_verify_rejects_inserted_bytes_that_parse_the_same(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        tampered = edit.new_raw.replace(b"indexable: true", b"indexable: True", 1)
        assert reparse(tampered)[1] == {**edit.fm, **edit.additions}
        assert verify(edit, new_raw=tampered) is False

    def test_verify_rejects_an_unedited_file(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        assert verify(edit, new_raw=edit.raw) is False

    def test_verify_rejects_a_dropped_suffix(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        assert verify(edit, new_raw=edit.new_raw[: edit.span.close_start + len(edit.added)]) is False

    def test_verify_rejects_parsed_values_that_differ_from_the_claim(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        claimed = dict(edit.additions, indexable=False)
        assert verify(edit, additions=claimed) is False

    def test_verify_rejects_added_lines_that_close_the_block_early(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        added = b"x: 1\n---\ny: 2\n"
        new_raw = tool.insert_lines(edit.raw, edit.span, added)
        assert verify(edit, new_raw=new_raw, added=added, additions={"x": 1, "y": 2}) is False

    def test_verify_rejects_added_lines_that_break_the_yaml(self) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(b"doc_type: decision\n"))
        assert edit is not None
        added = b"x: [\n"
        new_raw = tool.insert_lines(edit.raw, edit.span, added)
        assert verify(edit, new_raw=new_raw, added=added, additions={"x": 1}) is False

    def test_verify_returns_false_on_degenerate_input_without_raising(self) -> None:
        span = tool.Span(block=b"", close_start=0, eol=LF)
        assert tool.verify_edit(b"", span, b"", b"", {}, {}) is False


# ---------------------------------------------------------------------------
# Block B-02: fixture vault builder and shared helpers
# ---------------------------------------------------------------------------

GIT_LEAK_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX",
    "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE",
)
FIXTURE_USER = "Fixture User"
FIXTURE_EMAIL = "fixture@example.invalid"
FIXTURE_IGNORE_RULES = b"ignored/\n*.ignored.md\n"
FIXTURE_COMMIT_MESSAGE = "fixture commit"
MODE_MASK = 0o777
READ_ONLY_FOLDER_MODE = 0o555
READ_ONLY_FILE_MODE = 0o444
OPEN_FOLDER_MODE = 0o755
UNLOCKED_FILE_MODE = 0o644
GIT_DIR_NAME = ".git"
WORKING_EDIT = b"Extra working copy line.\n"
DECISION_DOC = b"---\ndoc_type: decision\n---\nBody line.\n"
DECISION_ADDED_LINES = (
    b"catalog_type: knowledge\ndoc_role: decision\nindexable: true\nindexed: null\n"
)
DECISION_NEW = b"---\ndoc_type: decision\n" + DECISION_ADDED_LINES + b"---\nBody line.\n"
DECISION_ADDITIONS = {
    "catalog_type": "knowledge", "doc_role": "decision", "indexable": True, "indexed": None,
}
SENTINEL_ADDITIONS = {
    "catalog_type": "unknown", "doc_role": "unknown", "indexable": False, "indexed": None,
}
STATE_ADDITIONS = {
    "catalog_type": "ticket", "doc_role": "state", "indexable": True, "indexed": None,
}
KIND_WRITE = "write"
KIND_SKIPPED = "skipped"
KIND_NOT_TARGET = "not_target"
KIND_ALREADY_COMPLETE = "already_complete"


def isolate_git(mp: pytest.MonkeyPatch, base: Path) -> None:
    """Make git read no user or system config and never search above base for a repository.

    The tool's own git calls inherit this process environment, so patching it here
    isolates both the fixture commands and the code under test. HOME and the XDG
    folder are redirected because git reads a user level ignore file from there
    even when GIT_CONFIG_GLOBAL points at the null device.
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


class VaultBuilder:
    """A throwaway vault folder under a pytest temp folder, backed by an isolated git repo."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def git(self, *args: str) -> str:
        """Run one git command in the vault with fixed identity and no signing or CRLF rewrite."""
        command = [
            "git", "-c", "user.name=" + FIXTURE_USER, "-c", "user.email=" + FIXTURE_EMAIL,
            "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args,
        ]
        done = subprocess.run(command, cwd=str(self.root), check=True, capture_output=True)
        return done.stdout.decode("utf-8", "replace")

    def init(self) -> None:
        """Create the folder, the repository, and an initial commit holding the ignore rules."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q")
        self.write(".gitignore", FIXTURE_IGNORE_RULES)
        self.add(".gitignore")
        self.commit()

    def write(self, rel: str, content: bytes, mode: Optional[int] = None) -> Path:
        """Write bytes at a vault relative path, creating folders, optionally setting the mode."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if mode is not None:
            path.chmod(mode)
        return path

    def symlink(self, rel: str, target: str) -> Path:
        """Create a symlink at rel pointing at target (any string)."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        return path

    def add(self, *rels: str, force: bool = False) -> None:
        """Stage paths. force stages a file that matches an ignore rule."""
        if not rels:
            return
        flags = ["-f"] if force else []
        self.git("add", *flags, "--", *rels)

    def commit(self) -> None:
        """Commit whatever is staged. An empty commit is allowed so HEAD always exists."""
        self.git("commit", "-q", "--allow-empty", "-m", FIXTURE_COMMIT_MESSAGE)

    def commit_file(self, rel: str, content: bytes, mode: Optional[int] = None) -> Path:
        """Write one file, stage it, and commit it alone."""
        path = self.write(rel, content, mode)
        self.add(rel)
        self.commit()
        return path


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VaultBuilder:
    """A fresh isolated git vault at tmp_path/vault holding only .gitignore."""
    isolate_git(monkeypatch, tmp_path)
    builder = VaultBuilder(tmp_path / "vault")
    builder.init()
    return builder


def snapshot(root: Path) -> Dict[str, Tuple[str, int]]:
    """Content hash and st_mtime_ns of every regular file under root, skipping .git."""
    result: Dict[str, Tuple[str, int]] = {}
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [name for name in dirnames if name != GIT_DIR_NAME]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[str(path.relative_to(root))] = (digest, path.stat().st_mtime_ns)
    return result


def make_git(tracked: Tuple[str, ...] = (), differing: Tuple[str, ...] = (),
             ignored: Tuple[str, ...] = ()) -> Any:
    """Build a GitState by hand, for tests that must not depend on a real repository."""
    return tool.GitState(frozenset(tracked), frozenset(differing), frozenset(ignored))


def touch_files(root: Path, rels: List[str]) -> None:
    """Create each relative path as a small eligible markdown file."""
    for rel in rels:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(DECISION_DOC)


def temp_names(folder: Path, keep: str) -> List[str]:
    """Names in folder other than keep, which is where a stray temp file would show."""
    return sorted(name for name in os.listdir(str(folder)) if name != keep)


class TestIterVaultFiles:
    """iter_vault_files: scan order, root level dot folders, excluded prefixes, symlinks."""

    def test_yields_markdown_only_in_sorted_per_directory_order(self, tmp_path: Path) -> None:
        touch_files(tmp_path, [
            "b.md", "a.md", "c.txt", "d.markdown", "e.MD", "x/z.md", "x/y.md",
            "x/notes.txt", "a-dir/k.md",
        ])
        found = list(tool.iter_vault_files(tmp_path))
        assert found == ["a.md", "b.md", "a-dir/k.md", "x/y.md", "x/z.md"]

    def test_paths_are_root_relative_posix_strings(self, tmp_path: Path) -> None:
        touch_files(tmp_path, ["one/two/three.md"])
        found = list(tool.iter_vault_files(tmp_path))
        assert found == ["one/two/three.md"]
        assert all(isinstance(item, str) and not item.startswith("/") for item in found)

    def test_empty_root_yields_nothing(self, tmp_path: Path) -> None:
        assert list(tool.iter_vault_files(tmp_path)) == []

    def test_a_folder_named_like_a_markdown_file_is_walked_not_yielded(self, tmp_path: Path) -> None:
        touch_files(tmp_path, ["folder.md/inner.md"])
        assert list(tool.iter_vault_files(tmp_path)) == ["folder.md/inner.md"]

    @pytest.mark.parametrize(
        "rel",
        [
            ".claude/worktrees/copy/doc.md",
            ".obsidian/plugins/note.md",
            ".git/info/note.md",
            ".trash/old.md",
            ".hidden/deep/er/doc.md",
        ],
    )
    def test_root_level_dot_folders_are_pruned(self, tmp_path: Path, rel: str) -> None:
        touch_files(tmp_path, [rel, "kept.md"])
        assert list(tool.iter_vault_files(tmp_path)) == ["kept.md"]

    @pytest.mark.parametrize("rel", ["08-reference/.hidden/doc.md", "a/b/.github/doc.md"])
    def test_dot_folders_below_the_root_are_walked(self, tmp_path: Path, rel: str) -> None:
        touch_files(tmp_path, [rel])
        assert list(tool.iter_vault_files(tmp_path)) == [rel]

    @pytest.mark.parametrize("prefix", ["memory/"])
    def test_excluded_prefix_folders_are_pruned_at_any_depth(
        self, tmp_path: Path, prefix: str
    ) -> None:
        touch_files(tmp_path, [
            prefix + "eligible.md", prefix + "deep/er/eligible.md", "03-knowledge-base/kept.md",
        ])
        assert list(tool.iter_vault_files(tmp_path)) == ["03-knowledge-base/kept.md"]

    @pytest.mark.parametrize(
        "rel",
        [
            "memory2/n.md",
            "03-knowledge-base/memory/n.md",
            "03-knowledge-base/decisions/memory/n.md",
            "08-reference/memory/n.md",
            "03-knowledge-base/System-notes/n.md",
            "03-knowledge-base/sql/n.md",
        ],
    )
    def test_near_misses_of_the_excluded_prefixes_are_walked(
        self, tmp_path: Path, rel: str
    ) -> None:
        touch_files(tmp_path, [rel])
        assert list(tool.iter_vault_files(tmp_path)) == [rel]

    def test_directory_symlinks_are_not_followed(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        vault_root = tmp_path / "vault"
        touch_files(outside, ["secret.md"])
        touch_files(vault_root, ["real/a.md"])
        (vault_root / "link_out").symlink_to(outside, target_is_directory=True)
        (vault_root / "link_in").symlink_to(vault_root / "real", target_is_directory=True)
        (vault_root / "loop").symlink_to(vault_root, target_is_directory=True)
        assert list(tool.iter_vault_files(vault_root)) == ["real/a.md"]

    def test_file_symlinks_are_yielded_so_the_planner_can_report_them(self, tmp_path: Path) -> None:
        touch_files(tmp_path, ["target.md"])
        (tmp_path / "link.md").symlink_to(tmp_path / "target.md")
        (tmp_path / "dangling.md").symlink_to(tmp_path / "missing.md")
        assert list(tool.iter_vault_files(tmp_path)) == ["dangling.md", "link.md", "target.md"]

    def test_scanning_changes_nothing(self, tmp_path: Path) -> None:
        touch_files(tmp_path, ["a.md", "x/b.md", ".claude/c.md"])
        before = snapshot(tmp_path)
        list(tool.iter_vault_files(tmp_path))
        assert snapshot(tmp_path) == before


GIT_STATE_NAMES = (
    "with space.md", 'quote"mark.md', "line\nbreak.md", "café.md",
    "sub dir/über file.md", "-dash-first.md",
)
EXPECTED_STATE_REASONS: Dict[str, Optional[str]] = {
    "clean.md": None,
    "forced.ignored.md": None,
    "modified.md": "UNCOMMITTED",
    "staged_mod.md": "UNCOMMITTED",
    "staged_new.md": "UNCOMMITTED",
    "deleted.md": "UNCOMMITTED",
    "untracked.md": "UNTRACKED",
    "ignored/x.md": "GITIGNORED",
    "note.ignored.md": "GITIGNORED",
}


def build_state_files(vb: VaultBuilder) -> None:
    """Create one file per git state: clean, force added, edited, staged, deleted, untracked, ignored."""
    for rel in ("clean.md", "modified.md", "staged_mod.md", "deleted.md"):
        vb.write(rel, DECISION_DOC)
        vb.add(rel)
    vb.write("forced.ignored.md", DECISION_DOC)
    vb.add("forced.ignored.md", force=True)
    vb.commit()
    vb.write("modified.md", DECISION_DOC + WORKING_EDIT)
    vb.write("staged_mod.md", DECISION_DOC + WORKING_EDIT)
    vb.add("staged_mod.md")
    (vb.root / "deleted.md").unlink()
    vb.write("staged_new.md", DECISION_DOC)
    vb.add("staged_new.md")
    for rel in ("untracked.md", "ignored/x.md", "note.ignored.md"):
        vb.write(rel, DECISION_DOC)


class TestGitState:
    """load_git_state and unrestorable_reason."""

    def test_snapshot_sorts_each_file_into_the_right_sets(self, vault: VaultBuilder) -> None:
        build_state_files(vault)
        git = tool.load_git_state(vault.root)
        assert git.tracked == frozenset({
            ".gitignore", "clean.md", "modified.md", "staged_mod.md", "deleted.md",
            "staged_new.md", "forced.ignored.md",
        })
        assert git.differing == frozenset({"modified.md", "staged_mod.md", "deleted.md", "staged_new.md"})
        assert git.ignored == frozenset({"ignored/x.md", "note.ignored.md"})

    def test_force_added_file_matching_an_ignore_rule_is_tracked_and_not_ignored(
        self, vault: VaultBuilder
    ) -> None:
        build_state_files(vault)
        git = tool.load_git_state(vault.root)
        assert "forced.ignored.md" in git.tracked
        assert "forced.ignored.md" not in git.ignored
        assert "forced.ignored.md" not in git.differing

    def test_unusual_file_names_come_back_exactly(self, vault: VaultBuilder) -> None:
        for name in GIT_STATE_NAMES:
            vault.write(name, DECISION_DOC)
        vault.add(*GIT_STATE_NAMES)
        vault.commit()
        git = tool.load_git_state(vault.root)
        assert set(GIT_STATE_NAMES) <= git.tracked
        assert not (set(GIT_STATE_NAMES) & git.differing)

    def test_state_is_immutable(self, vault: VaultBuilder) -> None:
        git = tool.load_git_state(vault.root)
        assert isinstance(git.tracked, frozenset)
        assert isinstance(git.differing, frozenset)
        assert isinstance(git.ignored, frozenset)
        with pytest.raises(dataclasses.FrozenInstanceError):
            git.tracked = frozenset()  # type: ignore[misc]

    def test_three_read_only_git_commands_run_in_the_vault(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: List[Tuple[List[str], Dict[str, Any]]] = []
        real_run = subprocess.run

        def spy(args: Any, **kwargs: Any) -> Any:
            calls.append((list(args), kwargs))
            return real_run(args, **kwargs)

        monkeypatch.setattr(subprocess, "run", spy)
        tool.load_git_state(vault.root)
        assert [call[0] for call in calls] == [
            ["git", "ls-files", "-z"],
            ["git", "diff", "--no-renames", "--relative", "--name-only", "-z", "HEAD"],
            ["git", "ls-files", "-o", "-i", "--exclude-standard", "-z"],
        ]
        for _, kwargs in calls:
            assert kwargs["cwd"] == str(vault.root)
            assert kwargs["timeout"] > 0

    def test_snapshot_changes_no_vault_file(self, vault: VaultBuilder) -> None:
        build_state_files(vault)
        os.utime(str(vault.root / "clean.md"), ns=(1, 1))
        before = snapshot(vault.root)
        tool.load_git_state(vault.root)
        assert snapshot(vault.root) == before

    def test_not_a_repository_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        isolate_git(monkeypatch, tmp_path)
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(tool.GitStateError):
            tool.load_git_state(plain)

    def test_repository_without_a_commit_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isolate_git(monkeypatch, tmp_path)
        builder = VaultBuilder(tmp_path / "unborn")
        builder.root.mkdir()
        builder.git("init", "-q")
        with pytest.raises(tool.GitStateError):
            tool.load_git_state(builder.root)

    def test_missing_vault_folder_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        isolate_git(monkeypatch, tmp_path)
        with pytest.raises(tool.GitStateError):
            tool.load_git_state(tmp_path / "does-not-exist")

    def test_git_not_installed_raises(
        self, vault: VaultBuilder, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_bin = tmp_path / "empty-bin"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        with pytest.raises(tool.GitStateError):
            tool.load_git_state(vault.root)

    @pytest.mark.parametrize("failure", ["timeout", "oserror", "nonzero"])
    def test_failures_raise_a_closed_code_that_carries_no_text(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch, failure: str
    ) -> None:
        def fake(args: Any, **kwargs: Any) -> Any:
            if failure == "timeout":
                raise subprocess.TimeoutExpired(cmd=CANARY, timeout=1)
            if failure == "oserror":
                raise OSError(CANARY)
            return subprocess.CompletedProcess(args, 128, CANARY.encode(), ("fatal: " + CANARY).encode())

        monkeypatch.setattr(subprocess, "run", fake)
        with pytest.raises(tool.GitStateError) as info:
            tool.load_git_state(vault.root)
        text = str(info.value)
        assert re.fullmatch(r"[A-Z_]+", text), text
        assert info.value.__cause__ is None
        assert info.value.__context__ is None or info.value.__suppress_context__ is True

    @pytest.mark.parametrize(
        "git,rel,expected",
        [
            (make_git(tracked=("a.md",)), "a.md", None),
            (make_git(tracked=("a.md",), differing=("a.md",)), "a.md", "UNCOMMITTED"),
            (make_git(differing=("a.md",)), "a.md", "UNCOMMITTED"),
            (make_git(), "a.md", "UNTRACKED"),
            (make_git(ignored=("a.md",)), "a.md", "GITIGNORED"),
            (make_git(tracked=("a.md",), ignored=("a.md",)), "a.md", None),
            (make_git(tracked=("b.md",)), "a.md", "UNTRACKED"),
            (make_git(tracked=("A.md",)), "a.md", "UNTRACKED"),
        ],
        ids=["clean", "staged", "differing_only", "untracked", "ignored", "tracked_wins",
             "other_file", "case_sensitive"],
    )
    def test_unrestorable_reason_table(self, git: Any, rel: str, expected: Optional[str]) -> None:
        assert tool.unrestorable_reason(git, rel) == expected

    def test_unrestorable_reason_over_real_file_states(self, vault: VaultBuilder) -> None:
        build_state_files(vault)
        git = tool.load_git_state(vault.root)
        actual = {rel: tool.unrestorable_reason(git, rel) for rel in EXPECTED_STATE_REASONS}
        assert actual == EXPECTED_STATE_REASONS

    def test_committing_an_edited_file_makes_it_restorable_on_the_next_snapshot(
        self, vault: VaultBuilder
    ) -> None:
        vault.commit_file("a.md", DECISION_DOC)
        vault.write("a.md", DECISION_DOC + WORKING_EDIT)
        before = tool.load_git_state(vault.root)
        assert tool.unrestorable_reason(before, "a.md") == "UNCOMMITTED"
        vault.add("a.md")
        vault.commit()
        after = tool.load_git_state(vault.root)
        assert tool.unrestorable_reason(after, "a.md") is None


class Scenario(NamedTuple):
    """One fixture file, the git state it is built in, and the literal outcome expected."""

    rel: str
    content: bytes
    state: str
    kind: str
    reason: Optional[str] = None
    row: Optional[int] = None
    label: Optional[str] = None
    additions: Optional[Dict[str, Any]] = None
    new_raw: Optional[bytes] = None


def write_case(rel: str, content: bytes, new_raw: bytes, additions: Dict[str, Any], row: int,
               label: Optional[str] = None, state: str = "clean") -> Scenario:
    """A fixture file the planner must plan as a write, with the exact bytes expected."""
    return Scenario(rel, content, state, KIND_WRITE, None, row, label, additions, new_raw)


def skip_case(rel: str, content: bytes, reason: str, row: Optional[int],
              state: str = "clean", label: Optional[str] = None) -> Scenario:
    """A fixture file the planner must skip with the given reason code."""
    return Scenario(rel, content, state, KIND_SKIPPED, reason, row, label)


def plain_case(rel: str, content: bytes, kind: str, row: int, label: Optional[str] = None,
               state: str = "clean") -> Scenario:
    """A fixture file the planner must report as not_target or already_complete."""
    return Scenario(rel, content, state, kind, None, row, label)


CONVERSATION_DOC = b"---\ndoc_type: conversation\n---\nBody line.\n"
COMPLETE_DECISION = (
    b"---\ndoc_type: decision\ncatalog_type: knowledge\ndoc_role: decision\n"
    b"indexable: true\nindexed: null\n---\nBody line.\n"
)
CONFLICT_DOC_ROLE_DOC = b"---\ndoc_type: ticket_spec\ndoc_role: design\n---\nBody line.\n"
NO_FRONTMATTER_DOC = b"# Just a heading\nBody line.\n"
SENTINEL_LINES = b"catalog_type: unknown\ndoc_role: unknown\nindexable: false\nindexed: null\n"
STATE_LINES = b"catalog_type: ticket\ndoc_role: state\nindexable: true\nindexed: null\n"

SCENARIOS: List[Scenario] = [
    write_case("00-landing/clean.md", DECISION_DOC, DECISION_NEW, DECISION_ADDITIONS, 2),
    write_case(
        "08-reference/old-key.md",
        b"---\ntype: ticket_spec\ntitle: x\n---\nBody line.\n",
        b"---\ntype: ticket_spec\ntitle: x\ncatalog_type: ticket\ndoc_role: spec\n"
        b"indexable: true\nindexed: null\n---\nBody line.\n",
        {"catalog_type": "ticket", "doc_role": "spec", "indexable": True, "indexed": None}, 4,
    ),
    write_case(
        "08-reference/odd.md",
        b"---\ndoc_type: made_up_type\n---\nBody line.\n",
        b"---\ndoc_type: made_up_type\n" + SENTINEL_LINES + b"---\nBody line.\n",
        SENTINEL_ADDITIONS, 3, "made_up_type",
    ),
    write_case(
        "08-reference/odd-list.md",
        b"---\ndoc_type: [a, b]\n---\nBody line.\n",
        b"---\ndoc_type: [a, b]\n" + SENTINEL_LINES + b"---\nBody line.\n",
        SENTINEL_ADDITIONS, 3, "<non-string>",
    ),
    write_case(
        "02-tickets/T-900/T-900-state.md",
        b"---\ntype: build\ntitle: x\n---\nBody line.\n",
        b"---\ntype: build\ntitle: x\n" + STATE_LINES + b"---\nBody line.\n",
        STATE_ADDITIONS, 1,
    ),
    write_case(
        "02-tickets/T-901/T-901-state.md",
        b"---\n---\nBody line.\n",
        b"---\n" + STATE_LINES + b"---\nBody line.\n",
        STATE_ADDITIONS, 1,
    ),
    write_case(
        "00-landing/crlf.md",
        b"---\r\ndoc_type: decision\r\n---\r\nBody line.\r\n",
        b"---\r\ndoc_type: decision\r\ncatalog_type: knowledge\r\ndoc_role: decision\r\n"
        b"indexable: true\r\nindexed: null\r\n---\r\nBody line.\r\n",
        DECISION_ADDITIONS, 2,
    ),
    write_case(
        "00-landing/partial.md",
        b"---\ndoc_type: decision\ncatalog_type: knowledge\ndoc_role: decision\n---\nBody line.\n",
        b"---\ndoc_type: decision\ncatalog_type: knowledge\ndoc_role: decision\n"
        b"indexable: true\nindexed: null\n---\nBody line.\n",
        {"indexable": True, "indexed": None}, 2,
    ),
    write_case(
        "00-landing/non-utf8-body.md",
        b"---\ndoc_type: decision\n---\n\xff\xfe binary \x80\n",
        b"---\ndoc_type: decision\n" + DECISION_ADDED_LINES + b"---\n\xff\xfe binary \x80\n",
        DECISION_ADDITIONS, 2,
    ),
    write_case(
        "00-landing/no-final-newline.md",
        b"---\ndoc_type: decision\n---",
        b"---\ndoc_type: decision\n" + DECISION_ADDED_LINES + b"---",
        DECISION_ADDITIONS, 2,
    ),
    write_case(
        "05-conversations/talk.md",
        CONVERSATION_DOC,
        b"---\ndoc_type: conversation\ncatalog_type: session\ndoc_role: log\n"
        b"indexable: false\nindexed: null\n---\nBody line.\n",
        {"catalog_type": "session", "doc_role": "log", "indexable": False, "indexed": None}, 2,
    ),
    write_case("08-reference/forced.ignored.md", DECISION_DOC, DECISION_NEW,
               DECISION_ADDITIONS, 2, state="force_added"),
    skip_case("00-landing/untracked.md", DECISION_DOC, "UNTRACKED", 2, "untracked"),
    skip_case("ignored/hidden.md", DECISION_DOC, "GITIGNORED", 2, "untracked"),
    skip_case("00-landing/note.ignored.md", DECISION_DOC, "GITIGNORED", 2, "untracked"),
    skip_case("00-landing/modified.md", DECISION_DOC, "UNCOMMITTED", 2, "modified"),
    skip_case("00-landing/staged-modified.md", DECISION_DOC, "UNCOMMITTED", 2, "staged_modified"),
    skip_case("00-landing/staged-new.md", DECISION_DOC, "UNCOMMITTED", 2, "staged_new"),
    skip_case("00-landing/conflict-role.md", CONFLICT_DOC_ROLE_DOC, "CONFLICT_DOC_ROLE", 2),
    skip_case("00-landing/conflict-role-untracked.md", CONFLICT_DOC_ROLE_DOC,
              "CONFLICT_DOC_ROLE", 2, "untracked"),
    skip_case("00-landing/conflict-catalog.md",
              b"---\ndoc_type: decision\ncatalog_type: ticket\n---\nBody line.\n",
              "CONFLICT_CATALOG_TYPE", 2),
    skip_case("00-landing/conflict-indexable.md",
              b'---\ndoc_type: decision\nindexable: "true"\n---\nBody line.\n',
              "CONFLICT_INDEXABLE", 2),
    skip_case("08-reference/odd-untracked.md", b"---\ndoc_type: made_up_type\n---\nBody line.\n",
              "UNTRACKED", 3, "untracked", "made_up_type"),
    skip_case("08-reference/odd-modified.md", b"---\ndoc_type: 42\n---\nBody line.\n",
              "UNCOMMITTED", 3, "modified", "<non-string>"),
    skip_case("08-reference/odd-conflict.md",
              b"---\ndoc_type: made_up_type\ncatalog_type: ticket\n---\nBody line.\n",
              "CONFLICT_CATALOG_TYPE", 3, label="made_up_type"),
    skip_case("00-landing/broken.md",
              b"---\ndoc_type: [" + CANARY.encode("utf-8") + b"\n---\nBody line.\n",
              "PARSE_ERROR", None),
    skip_case("02-tickets/T-902/T-902-state.md", NO_FRONTMATTER_DOC, "NO_FRONTMATTER", 1),
    skip_case("02-tickets/T-903/T-903-state.md", NO_FRONTMATTER_DOC, "NO_FRONTMATTER", 1, "untracked"),
    plain_case("00-landing/complete-untracked.md", COMPLETE_DECISION, KIND_ALREADY_COMPLETE, 2,
               state="untracked"),
    plain_case(
        "00-landing/complete-other-values.md",
        b"---\ndoc_type: decision\ncatalog_type: other\ndoc_role: other\n"
        b"indexable: false\nindexed: 2026-10-01\n---\nBody line.\n",
        KIND_ALREADY_COMPLETE, 2,
    ),
    plain_case(
        "08-reference/complete-unmapped.md",
        b"---\ndoc_type: design\ncatalog_type: ticket\ndoc_role: design\n"
        b"indexable: true\nindexed: null\n---\nBody line.\n",
        KIND_ALREADY_COMPLETE, 3, "design",
    ),
    plain_case("00-landing/plain.md", b"# Heading only\n", KIND_NOT_TARGET, 5),
    plain_case("00-landing/type-build.md", b"---\ntype: build\n---\nBody line.\n",
               KIND_NOT_TARGET, 5),
    plain_case("00-landing/type-build-untracked.md", b"---\ntype: build\n---\nBody line.\n",
               KIND_NOT_TARGET, 5, state="untracked"),
    plain_case("00-landing/title-only.md", b"---\ntitle: x\n---\nBody line.\n",
               KIND_NOT_TARGET, 5),
    plain_case("00-landing/empty-block.md", b"---\n---\nBody line.\n", KIND_NOT_TARGET, 5),
    plain_case("00-landing/bom.md", b"\xef\xbb\xbf---\ndoc_type: decision\n---\nBody line.\n",
               KIND_NOT_TARGET, 5),
    plain_case("00-landing/below-line-one.md",
               b"# Title\n---\ndoc_type: decision\n---\nBody line.\n", KIND_NOT_TARGET, 5),
]
WRITE_SCENARIOS = [case for case in SCENARIOS if case.kind == KIND_WRITE]
COMMITTED_STATES = ("clean", "force_added", "modified", "staged_modified")
EDITED_STATES = ("modified", "staged_modified")


def working_bytes(case: Scenario) -> bytes:
    """The bytes a scenario file holds on disk when the planner reads it."""
    return case.content + WORKING_EDIT if case.state in EDITED_STATES else case.content


def build_scenarios(vb: VaultBuilder) -> None:
    """Build every scenario file in its git state: commit first, then edit, stage, or leave loose."""
    for case in SCENARIOS:
        if case.state in COMMITTED_STATES:
            vb.write(case.rel, case.content)
            vb.add(case.rel, force=case.state == "force_added")
    vb.commit()
    for case in SCENARIOS:
        if case.state in EDITED_STATES:
            vb.write(case.rel, working_bytes(case))
        if case.state == "staged_modified":
            vb.add(case.rel)
        if case.state in ("staged_new", "untracked"):
            vb.write(case.rel, case.content)
        if case.state == "staged_new":
            vb.add(case.rel)


class Planned(NamedTuple):
    """A built scenario vault, its git snapshot, one outcome per scenario, and a pre plan snapshot."""

    root: Path
    git: Any
    outcomes: Dict[str, Any]
    before: Dict[str, Tuple[str, int]]


@pytest.fixture(scope="class")
def planned(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Planned]:
    """Build the scenario vault once for a class and plan every file in it."""
    base = tmp_path_factory.mktemp("planned")
    mp = pytest.MonkeyPatch()
    try:
        isolate_git(mp, base)
        builder = VaultBuilder(base / "vault")
        builder.init()
        build_scenarios(builder)
        git = tool.load_git_state(builder.root)
        before = snapshot(builder.root)
        outcomes = {case.rel: tool.plan_file(builder.root, case.rel, git) for case in SCENARIOS}
        yield Planned(builder.root, git, outcomes, before)
    finally:
        mp.undo()


class TestPlanFile:
    """plan_file: one outcome per file, in the order the design fixes."""

    def test_scenario_rels_are_unique(self) -> None:
        rels = [case.rel for case in SCENARIOS]
        assert len(set(rels)) == len(rels)

    @pytest.mark.parametrize("case", SCENARIOS, ids=[case.rel for case in SCENARIOS])
    def test_kind_reason_row_and_label(self, planned: Planned, case: Scenario) -> None:
        got = planned.outcomes[case.rel]
        assert got.rel == case.rel
        assert (got.kind, got.reason, got.row, got.label) == (
            case.kind, case.reason, case.row, case.label,
        )

    @pytest.mark.parametrize("case", WRITE_SCENARIOS, ids=[case.rel for case in WRITE_SCENARIOS])
    def test_write_outcome_carries_exact_bytes_and_additions(
        self, planned: Planned, case: Scenario
    ) -> None:
        got = planned.outcomes[case.rel]
        assert got.original == working_bytes(case)
        assert got.new_raw == case.new_raw
        assert got.additions == case.additions
        assert list(got.additions) == list(case.additions or {})

    def test_null_rule_holds_for_every_outcome(self, planned: Planned) -> None:
        for case in SCENARIOS:
            got = planned.outcomes[case.rel]
            is_write = got.kind == KIND_WRITE
            assert (got.original is not None) == is_write, case.rel
            assert (got.new_raw is not None) == is_write, case.rel
            assert (got.reason is not None) == (got.kind == KIND_SKIPPED), case.rel
            assert bool(got.additions) == is_write, case.rel
            if got.kind == KIND_NOT_TARGET:
                assert got.row == ROW_NOT_TARGET, case.rel

    def test_every_file_ends_in_exactly_one_known_kind(self, planned: Planned) -> None:
        kinds = {planned.outcomes[case.rel].kind for case in SCENARIOS}
        assert kinds == {KIND_WRITE, KIND_SKIPPED, KIND_NOT_TARGET, KIND_ALREADY_COMPLETE}

    def test_planning_wrote_nothing(self, planned: Planned) -> None:
        assert snapshot(planned.root) == planned.before

    def test_outcome_is_frozen(self, planned: Planned) -> None:
        got = planned.outcomes["00-landing/clean.md"]
        with pytest.raises(dataclasses.FrozenInstanceError):
            got.kind = "skipped"  # type: ignore[misc]

    def test_planning_twice_gives_equal_outcomes(self, planned: Planned) -> None:
        for case in SCENARIOS:
            again = tool.plan_file(planned.root, case.rel, planned.git)
            assert again == planned.outcomes[case.rel], case.rel

    def test_symlink_is_skipped_and_its_target_is_untouched(self, vault: VaultBuilder) -> None:
        vault.commit_file("target.md", DECISION_DOC)
        vault.symlink("link.md", "target.md")
        vault.add("link.md")
        vault.commit()
        got = tool.plan_file(vault.root, "link.md", tool.load_git_state(vault.root))
        assert (got.kind, got.reason, got.row) == (KIND_SKIPPED, "SYMLINK", None)
        assert (vault.root / "target.md").read_bytes() == DECISION_DOC

    def test_dangling_symlink_is_a_symlink_skip_not_unreadable(self, vault: VaultBuilder) -> None:
        vault.symlink("dangling.md", "nowhere.md")
        got = tool.plan_file(vault.root, "dangling.md", tool.load_git_state(vault.root))
        assert (got.kind, got.reason) == (KIND_SKIPPED, "SYMLINK")

    def test_missing_file_is_unreadable(self, tmp_path: Path) -> None:
        got = tool.plan_file(tmp_path, "gone.md", make_git())
        assert (got.kind, got.reason, got.row) == (KIND_SKIPPED, "UNREADABLE", None)

    def test_folder_named_like_a_note_is_unreadable(self, tmp_path: Path) -> None:
        (tmp_path / "folder.md").mkdir()
        got = tool.plan_file(tmp_path, "folder.md", make_git())
        assert (got.kind, got.reason) == (KIND_SKIPPED, "UNREADABLE")

    def test_permission_denied_is_unreadable(self, tmp_path: Path) -> None:
        if os.geteuid() == 0:
            pytest.skip("root reads files whatever their mode")
        path = tmp_path / "locked.md"
        path.write_bytes(DECISION_DOC)
        path.chmod(0)
        try:
            got = tool.plan_file(tmp_path, "locked.md", make_git(tracked=("locked.md",)))
        finally:
            path.chmod(UNLOCKED_FILE_MODE)
        assert (got.kind, got.reason) == (KIND_SKIPPED, "UNREADABLE")

    @pytest.mark.parametrize(
        "git,kind,reason",
        [
            (make_git(tracked=("a.md",)), KIND_WRITE, None),
            (make_git(tracked=("a.md",), differing=("a.md",)), KIND_SKIPPED, "UNCOMMITTED"),
            (make_git(), KIND_SKIPPED, "UNTRACKED"),
            (make_git(ignored=("a.md",)), KIND_SKIPPED, "GITIGNORED"),
        ],
        ids=["tracked_clean", "differing", "untracked", "ignored"],
    )
    def test_the_git_snapshot_alone_decides_the_git_check(
        self, tmp_path: Path, git: Any, kind: str, reason: Optional[str]
    ) -> None:
        (tmp_path / "a.md").write_bytes(DECISION_DOC)
        got = tool.plan_file(tmp_path, "a.md", git)
        assert (got.kind, got.reason) == (kind, reason)

    def test_failed_self_check_skips_and_logs_an_error_without_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        body = b"---\ndoc_type: made_up_type\n---\n" + CANARY.encode("utf-8") + b"\n"
        (tmp_path / "a.md").write_bytes(body)
        monkeypatch.setattr(tool, "verify_edit", lambda *args, **kwargs: False)
        with caplog.at_level(logging.DEBUG):
            got = tool.plan_file(tmp_path, "a.md", make_git(tracked=("a.md",)))
        assert (got.kind, got.reason, got.row, got.label) == (
            KIND_SKIPPED, "VERIFY_FAILED", 3, "made_up_type",
        )
        assert got.original is None and got.new_raw is None
        assert any(record.levelno == logging.ERROR for record in caplog.records)
        assert CANARY not in caplog.text
        assert (tmp_path / "a.md").read_bytes() == body

    def test_unparseable_frontmatter_leaks_no_text_to_the_outcome_or_the_log(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        canary = CANARY.encode("utf-8")
        raw = b"---\ntitle: " + canary + b"\nbroken: [" + canary + b"\n---\n" + canary + b"\n"
        (tmp_path / "a.md").write_bytes(raw)
        with caplog.at_level(logging.DEBUG):
            got = tool.plan_file(tmp_path, "a.md", make_git(tracked=("a.md",)))
        assert got.reason == "PARSE_ERROR"
        assert CANARY not in repr(got)
        assert CANARY not in caplog.text

    def test_skipped_then_committed_then_rerun_is_written(self, vault: VaultBuilder) -> None:
        vault.commit_file("a.md", DECISION_DOC)
        vault.write("a.md", DECISION_DOC + WORKING_EDIT)
        first = tool.plan_file(vault.root, "a.md", tool.load_git_state(vault.root))
        assert (first.kind, first.reason) == (KIND_SKIPPED, "UNCOMMITTED")
        vault.add("a.md")
        vault.commit()
        second = tool.plan_file(vault.root, "a.md", tool.load_git_state(vault.root))
        assert second.kind == KIND_WRITE
        assert second.original == DECISION_DOC + WORKING_EDIT

    def test_a_file_after_its_edit_plans_as_already_complete(self, vault: VaultBuilder) -> None:
        vault.commit_file("a.md", DECISION_DOC)
        first = tool.plan_file(vault.root, "a.md", tool.load_git_state(vault.root))
        assert first.new_raw is not None
        (vault.root / "a.md").write_bytes(first.new_raw)
        dirty = tool.plan_file(vault.root, "a.md", tool.load_git_state(vault.root))
        assert dirty.kind == KIND_ALREADY_COMPLETE
        vault.add("a.md")
        vault.commit()
        clean = tool.plan_file(vault.root, "a.md", tool.load_git_state(vault.root))
        assert clean.kind == KIND_ALREADY_COMPLETE


APPLY_TARGET = "note.md"
DEFAULT_FILE_MODE = 0o640
DISTINCT_FILE_MODE = 0o664
FILE_MODES = (0o600, 0o640, 0o664, 0o755)
STALE_VERSIONS = {
    "appended": DECISION_DOC + b"x",
    "same_length": b"---\ndoc_type: decisioX\n---\nBody line.\n",
    "truncated": DECISION_DOC[:-1],
    "emptied": b"",
}


def make_target(folder: Path, content: bytes = DECISION_DOC, mode: int = DEFAULT_FILE_MODE) -> Path:
    """Create the file that apply_edit will replace, with a known mode."""
    path = folder / APPLY_TARGET
    path.write_bytes(content)
    path.chmod(mode)
    return path


def mode_of(path: Path) -> int:
    """Permission bits of a path."""
    return path.stat().st_mode & MODE_MASK


def raise_disk_error(*args: Any, **kwargs: Any) -> Any:
    """Stand in for a failing system call. The text is a canary that must never surface."""
    raise OSError(CANARY)


class TestAtomicApply:
    """apply_edit: stale guard, atomic replace, mode copy, failure handling."""

    def test_success_replaces_the_bytes_and_leaves_no_temp_file(self, tmp_path: Path) -> None:
        path = make_target(tmp_path)
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) is None
        assert path.read_bytes() == DECISION_NEW
        assert temp_names(tmp_path, APPLY_TARGET) == []

    @pytest.mark.parametrize("mode", FILE_MODES)
    def test_file_mode_is_preserved(self, tmp_path: Path, mode: int) -> None:
        path = make_target(tmp_path, mode=mode)
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) is None
        assert mode_of(path) == mode

    def test_crlf_and_non_utf8_bytes_are_written_exactly(self, tmp_path: Path) -> None:
        original = b"---\r\ndoc_type: decision\r\n---\r\n\xff\xfe body \x80\r\n"
        new_raw = (b"---\r\ndoc_type: decision\r\n" + DECISION_ADDED_LINES.replace(b"\n", b"\r\n")
                   + b"---\r\n\xff\xfe body \x80\r\n")
        path = make_target(tmp_path, original)
        assert tool.apply_edit(path, original, new_raw) is None
        assert path.read_bytes() == new_raw

    def test_other_files_in_the_folder_are_untouched(self, tmp_path: Path) -> None:
        make_target(tmp_path)
        (tmp_path / "neighbour.md").write_bytes(DECISION_DOC)
        (tmp_path / "other.txt").write_bytes(b"plain\n")
        before = {name: value for name, value in snapshot(tmp_path).items() if name != APPLY_TARGET}
        assert tool.apply_edit(tmp_path / APPLY_TARGET, DECISION_DOC, DECISION_NEW) is None
        after = {name: value for name, value in snapshot(tmp_path).items() if name != APPLY_TARGET}
        assert after == before

    @pytest.mark.parametrize("newer", list(STALE_VERSIONS.values()), ids=list(STALE_VERSIONS))
    def test_stale_original_is_refused_and_the_newer_file_survives(
        self, tmp_path: Path, newer: bytes
    ) -> None:
        path = make_target(tmp_path, newer, DISTINCT_FILE_MODE)
        before = path.stat().st_mtime_ns
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) == "CHANGED_DURING_RUN"
        assert path.read_bytes() == newer
        assert path.stat().st_mtime_ns == before
        assert mode_of(path) == DISTINCT_FILE_MODE
        assert temp_names(tmp_path, APPLY_TARGET) == []

    def test_applying_the_same_edit_twice_never_inserts_twice(self, tmp_path: Path) -> None:
        path = make_target(tmp_path)
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) is None
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) == "CHANGED_DURING_RUN"
        assert path.read_bytes() == DECISION_NEW

    def test_a_vanished_file_is_reported_not_raised_and_not_recreated(self, tmp_path: Path) -> None:
        result = tool.apply_edit(tmp_path / APPLY_TARGET, DECISION_DOC, DECISION_NEW)
        assert result == "UNREADABLE"
        assert os.listdir(str(tmp_path)) == []

    @pytest.mark.parametrize(
        "module,name",
        [(os, "fsync"), (shutil, "copymode"), (os, "replace")],
        ids=["fsync", "copymode", "replace"],
    )
    def test_failure_after_the_temp_file_exists_leaves_the_original_and_no_temp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: Any, name: str
    ) -> None:
        path = make_target(tmp_path, mode=DISTINCT_FILE_MODE)
        monkeypatch.setattr(module, name, raise_disk_error)
        result = tool.apply_edit(path, DECISION_DOC, DECISION_NEW)
        monkeypatch.undo()
        assert result == "WRITE_FAILED"
        assert path.read_bytes() == DECISION_DOC
        assert mode_of(path) == DISTINCT_FILE_MODE
        assert temp_names(tmp_path, APPLY_TARGET) == []

    def test_a_failed_cleanup_still_returns_write_failed_and_logs_no_error_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = make_target(tmp_path)
        monkeypatch.setattr(os, "replace", raise_disk_error)
        monkeypatch.setattr(os, "unlink", raise_disk_error)
        with caplog.at_level(logging.DEBUG):
            result = tool.apply_edit(path, DECISION_DOC, DECISION_NEW)
        monkeypatch.undo()
        assert result == "WRITE_FAILED"
        assert path.read_bytes() == DECISION_DOC
        assert CANARY not in caplog.text
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_a_read_only_folder_gives_write_failed_and_changes_nothing(self, tmp_path: Path) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores folder permissions")
        folder = tmp_path / "locked"
        folder.mkdir()
        path = make_target(folder)
        folder.chmod(READ_ONLY_FOLDER_MODE)
        try:
            result = tool.apply_edit(path, DECISION_DOC, DECISION_NEW)
        finally:
            folder.chmod(OPEN_FOLDER_MODE)
        assert result == "WRITE_FAILED"
        assert path.read_bytes() == DECISION_DOC
        assert temp_names(folder, APPLY_TARGET) == []

    def test_temp_file_is_a_sibling_with_the_new_bytes_and_the_old_mode_at_swap_time(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = make_target(tmp_path, mode=DISTINCT_FILE_MODE)
        seen: List[Dict[str, Any]] = []
        real_replace = os.replace

        def spy(src: Any, dst: Any) -> None:
            temp = Path(str(src))
            seen.append({"parent": temp.parent, "name": temp.name, "dst": str(dst),
                         "bytes": temp.read_bytes(), "mode": mode_of(temp)})
            real_replace(src, dst)

        monkeypatch.setattr(os, "replace", spy)
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) is None
        monkeypatch.undo()
        assert len(seen) == 1
        assert seen[0]["parent"] == tmp_path
        assert seen[0]["dst"] == str(path)
        assert seen[0]["name"] != APPLY_TARGET and not seen[0]["name"].endswith(".md")
        assert seen[0]["bytes"] == DECISION_NEW
        assert seen[0]["mode"] == DISTINCT_FILE_MODE

    def test_data_is_synced_before_the_swap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = make_target(tmp_path)
        order: List[str] = []
        real_fsync, real_replace = os.fsync, os.replace

        def spy_fsync(fd: int) -> None:
            order.append("fsync")
            real_fsync(fd)

        def spy_replace(src: Any, dst: Any) -> None:
            order.append("replace")
            real_replace(src, dst)

        monkeypatch.setattr(os, "fsync", spy_fsync)
        monkeypatch.setattr(os, "replace", spy_replace)
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) is None
        monkeypatch.undo()
        assert order == ["fsync", "replace"]

    def test_plan_then_apply_changes_git_only_by_the_added_lines(self, vault: VaultBuilder) -> None:
        vault.commit_file(APPLY_TARGET, DECISION_DOC)
        planned_edit = tool.plan_file(vault.root, APPLY_TARGET, tool.load_git_state(vault.root))
        assert planned_edit.original is not None and planned_edit.new_raw is not None
        result = tool.apply_edit(vault.root / APPLY_TARGET, planned_edit.original, planned_edit.new_raw)
        assert result is None
        assert vault.git("diff", "--numstat") == "4\t0\t" + APPLY_TARGET + "\n"
        assert vault.git("status", "--porcelain") == " M " + APPLY_TARGET + "\n"
        added = [line for line in vault.git("diff", "-U0").splitlines()
                 if line.startswith("+") and not line.startswith("+++")]
        assert added == ["+" + line for line in DECISION_ADDED_LINES.decode("utf-8").splitlines()]

    def test_a_read_only_file_in_a_writable_folder_gives_write_failed_and_changes_nothing(
        self, tmp_path: Path
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores file permissions")
        path = make_target(tmp_path, mode=READ_ONLY_FILE_MODE)
        before = path.stat().st_mtime_ns
        result = tool.apply_edit(path, DECISION_DOC, DECISION_NEW)
        assert result == "WRITE_FAILED"
        assert path.read_bytes() == DECISION_DOC
        assert mode_of(path) == READ_ONLY_FILE_MODE
        assert path.stat().st_mtime_ns == before
        assert temp_names(tmp_path, APPLY_TARGET) == []

    def test_a_read_only_file_is_refused_before_any_temp_file_is_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores file permissions")
        path = make_target(tmp_path, mode=READ_ONLY_FILE_MODE)
        created: List[str] = []

        def forbid_temp(*args: Any, **kwargs: Any) -> Any:
            created.append("mkstemp")
            raise AssertionError("a temp file was created for a read only target")

        monkeypatch.setattr(tool.tempfile, "mkstemp", forbid_temp)
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) == "WRITE_FAILED"
        assert created == []

    def test_a_stale_read_only_file_still_reports_the_stale_original_first(
        self, tmp_path: Path
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores file permissions")
        path = make_target(tmp_path, STALE_VERSIONS["appended"], READ_ONLY_FILE_MODE)
        assert tool.apply_edit(path, DECISION_DOC, DECISION_NEW) == "CHANGED_DURING_RUN"


# ---------------------------------------------------------------------------
# Block B-03: report, command line, run wiring
# ---------------------------------------------------------------------------

REPORT_KEYS = {
    "mode", "counts", "skipped_by_reason", "rows", "skipped", "writes",
    "unmapped_doc_types", "exclusions",
}
COUNT_KEYS = {
    "scanned", "not_target", "classified", "already_complete", "written", "skipped",
    "writes_indexable", "needing_fields",
}
EXPECTED_EXCLUSIONS = ["memory/"]
EMPTY_ROWS = {"1": 0, "2": 0, "3": 0, "4": 0}
SUBPROCESS_TIMEOUT_SECONDS = 60
INTERRUPT_EXIT_CODE = 130
SCRIPT_PATH = Path(tool.__file__).resolve()
REAL_USER_BASE = site.getuserbase()
CONVERSATION_ADDITIONS = {
    "catalog_type": "session", "doc_role": "log", "indexable": False, "indexed": None,
}
PARTIAL_ADDITIONS = {"indexed": None}


def commit_files(vb: VaultBuilder, files: Dict[str, bytes]) -> None:
    """Write, stage, and commit every file in one commit."""
    for rel, content in files.items():
        vb.write(rel, content)
        vb.add(rel)
    vb.commit()


def cli_args(root: Path, apply: bool = False, report_path: Optional[Path] = None) -> List[str]:
    """Build the argument list for main. The vault root is always explicit."""
    args = ["--vault-root", str(root)]
    if apply:
        args.append("--apply")
    if report_path is not None:
        args.extend(["--report-path", str(report_path)])
    return args


def run_cli_text(capsys: pytest.CaptureFixture, root: Path, apply: bool = False,
                 report_path: Optional[Path] = None) -> Tuple[int, str, str]:
    """Run main and return the exit code with the raw stdout and stderr text."""
    code = tool.main(cli_args(root, apply, report_path))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def run_cli(capsys: pytest.CaptureFixture, root: Path, apply: bool = False,
            report_path: Optional[Path] = None) -> Tuple[int, Dict[str, Any]]:
    """Run main and return the exit code and the report parsed from stdout."""
    code, out, _ = run_cli_text(capsys, root, apply, report_path)
    assert out.strip(), "main printed no report"
    return code, json.loads(out)


def fm_of(raw: bytes) -> Dict[str, Any]:
    """Parse the frontmatter of file bytes without using the tool, LF or CRLF."""
    lines = raw.decode("utf-8", "replace").splitlines(keepends=True)
    assert lines[0].rstrip("\r\n") == "---", "no opening delimiter"
    end = next(i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---")
    loaded = yaml.safe_load("".join(lines[1:end]))
    return loaded if loaded is not None else {}


def field_values(raw: bytes) -> Tuple[Any, Any, Any]:
    """The catalog_type, doc_role, and indexable of a backfilled file, with indexed checked null."""
    fm = fm_of(raw)
    assert all(name in fm for name in EXPECTED_FIELD_ORDER), "a field is missing"
    assert fm["indexed"] is None
    return fm["catalog_type"], fm["doc_role"], fm["indexable"]


def outcome(rel: str, kind: str, reason: Optional[str] = None, row: Optional[int] = None,
            label: Optional[str] = None, additions: Optional[Dict[str, Any]] = None) -> Any:
    """Build an Outcome by hand for report tests."""
    is_write = kind == KIND_WRITE
    return tool.Outcome(
        rel, kind, reason=reason, row=row, label=label, additions=additions or {},
        original=b"old" if is_write else None, new_raw=b"new" if is_write else None,
    )


HAND_OUTCOMES = [
    outcome("w1.md", "write", row=2, additions=DECISION_ADDITIONS),
    outcome("w2.md", "write", row=2, additions=CONVERSATION_ADDITIONS),
    outcome("w3.md", "write", row=3, label="odd", additions=SENTINEL_ADDITIONS),
    outcome("w4.md", "write", row=2, additions=PARTIAL_ADDITIONS),
    outcome("w5.md", "write", row=1, additions=STATE_ADDITIONS),
    outcome("ac.md", "already_complete", row=3, label="design"),
    outcome("nt.md", "not_target", row=5),
    outcome("s1.md", "skipped", "PARSE_ERROR"),
    outcome("s2.md", "skipped", "NO_FRONTMATTER", row=1),
    outcome("s3.md", "skipped", "UNCOMMITTED", row=2),
    outcome("s4.md", "skipped", "UNCOMMITTED", row=3, label="odd"),
    outcome("s5.md", "skipped", "SYMLINK"),
    outcome("s6.md", "skipped", "CONFLICT_DOC_ROLE", row=4),
]


class TestBuildReport:
    """build_report: counts, reason tallies, rows, lists, and unmapped labels."""

    def test_empty_run_has_every_key_and_zero_counts(self) -> None:
        report = tool.build_report("preview", [])
        assert set(report) == REPORT_KEYS
        assert set(report["counts"]) == COUNT_KEYS
        assert all(value == 0 for value in report["counts"].values())
        assert report["skipped_by_reason"] == {}
        assert report["rows"] == EMPTY_ROWS
        assert report["skipped"] == [] and report["writes"] == []
        assert report["unmapped_doc_types"] == {}
        assert report["exclusions"] == EXPECTED_EXCLUSIONS

    def test_mode_is_passed_through(self) -> None:
        assert tool.build_report("preview", [])["mode"] == "preview"
        assert tool.build_report("apply", [])["mode"] == "apply"

    def test_counts_for_a_hand_built_mix(self) -> None:
        counts = tool.build_report("preview", HAND_OUTCOMES)["counts"]
        assert counts == {
            "scanned": 13, "not_target": 1, "classified": 12, "already_complete": 1,
            "written": 5, "skipped": 6, "writes_indexable": 2, "needing_fields": 9,
        }

    def test_scanned_is_not_target_plus_classified(self) -> None:
        counts = tool.build_report("preview", HAND_OUTCOMES)["counts"]
        assert counts["scanned"] == counts["not_target"] + counts["classified"]
        assert counts["classified"] == (
            counts["written"] + counts["skipped"] + counts["already_complete"]
        )

    def test_writes_indexable_counts_only_writes_that_add_indexable_true(self) -> None:
        only = [
            outcome("a.md", "write", row=2, additions=DECISION_ADDITIONS),
            outcome("b.md", "write", row=2, additions=CONVERSATION_ADDITIONS),
            outcome("c.md", "write", row=3, label="x", additions=SENTINEL_ADDITIONS),
            outcome("d.md", "write", row=2, additions=PARTIAL_ADDITIONS),
            outcome("e.md", "skipped", "UNTRACKED", row=2),
            outcome("f.md", "already_complete", row=2),
        ]
        assert tool.build_report("preview", only)["counts"]["writes_indexable"] == 1

    def test_needing_fields_excludes_only_the_two_stop_rule_codes(self) -> None:
        skips = [
            outcome("a.md", "skipped", "PARSE_ERROR"),
            outcome("b.md", "skipped", "NO_FRONTMATTER", row=1),
            outcome("c.md", "skipped", "SYMLINK"),
            outcome("d.md", "skipped", "UNREADABLE"),
            outcome("e.md", "skipped", "UNTRACKED", row=2),
            outcome("f.md", "write", row=2, additions=DECISION_ADDITIONS),
        ]
        counts = tool.build_report("preview", skips)["counts"]
        assert counts["needing_fields"] == 4
        assert counts["written"] + counts["skipped"] == 6

    def test_needing_fields_with_no_excluded_code_present_counts_zero_for_them(self) -> None:
        only = [outcome("a.md", "skipped", "UNTRACKED", row=2),
                outcome("b.md", "write", row=2, additions=DECISION_ADDITIONS)]
        assert tool.build_report("preview", only)["counts"]["needing_fields"] == 2

    def test_skipped_by_reason_tallies_each_code_and_sums_to_skipped(self) -> None:
        report = tool.build_report("preview", HAND_OUTCOMES)
        assert report["skipped_by_reason"] == {
            "PARSE_ERROR": 1, "NO_FRONTMATTER": 1, "UNCOMMITTED": 2, "SYMLINK": 1,
            "CONFLICT_DOC_ROLE": 1,
        }
        assert sum(report["skipped_by_reason"].values()) == report["counts"]["skipped"]

    def test_rows_count_outcomes_with_row_one_through_four_only(self) -> None:
        rows = tool.build_report("preview", HAND_OUTCOMES)["rows"]
        assert rows == {"1": 2, "2": 4, "3": 3, "4": 1}

    def test_a_state_file_without_frontmatter_counts_in_row_one(self) -> None:
        only = [outcome("s.md", "skipped", "NO_FRONTMATTER", row=1)]
        assert tool.build_report("preview", only)["rows"] == {"1": 1, "2": 0, "3": 0, "4": 0}

    def test_files_that_were_never_classified_have_no_row(self) -> None:
        only = [outcome("a.md", "skipped", "PARSE_ERROR"), outcome("b.md", "skipped", "SYMLINK"),
                outcome("c.md", "skipped", "UNREADABLE"), outcome("d.md", "not_target", row=5)]
        report = tool.build_report("preview", only)
        assert report["rows"] == EMPTY_ROWS
        assert report["counts"]["classified"] == 3

    def test_unmapped_labels_count_every_row_three_outcome_whatever_its_kind(self) -> None:
        unmapped = tool.build_report("preview", HAND_OUTCOMES)["unmapped_doc_types"]
        assert unmapped == {"odd": 2, "design": 1}

    def test_lists_are_sorted_by_path(self) -> None:
        shuffled = [
            outcome("z.md", "skipped", "UNTRACKED", row=2),
            outcome("b.md", "write", row=2, additions=DECISION_ADDITIONS),
            outcome("a.md", "skipped", "SYMLINK"),
            outcome("a-write.md", "write", row=2, additions=DECISION_ADDITIONS),
        ]
        report = tool.build_report("preview", shuffled)
        assert [entry["path"] for entry in report["skipped"]] == ["a.md", "z.md"]
        assert [entry["path"] for entry in report["writes"]] == ["a-write.md", "b.md"]

    def test_entries_hold_path_and_reason_or_path_and_added_fields_only(self) -> None:
        report = tool.build_report("preview", HAND_OUTCOMES)
        assert report["skipped"][0] == {"path": "s1.md", "reason": "PARSE_ERROR"}
        assert report["writes"][0] == {"path": "w1.md", "added": DECISION_ADDITIONS}
        for entry in report["skipped"]:
            assert set(entry) == {"path", "reason"}
        for entry in report["writes"]:
            assert set(entry) == {"path", "added"}

    def test_report_is_json_serializable_and_the_input_is_not_changed(self) -> None:
        before = list(HAND_OUTCOMES)
        report = tool.build_report("apply", HAND_OUTCOMES)
        assert HAND_OUTCOMES == before
        decoded = json.loads(json.dumps(report, sort_keys=True))
        assert decoded["writes"][0]["added"]["indexed"] is None
        assert decoded["writes"][0]["added"]["indexable"] is True

    def test_exclusions_list_the_three_excluded_prefixes(self) -> None:
        assert tool.build_report("preview", HAND_OUTCOMES)["exclusions"] == EXPECTED_EXCLUSIONS


class TestParseArgs:
    """parse_args: preview is the default and abbreviations are refused."""

    def test_defaults_are_preview_with_no_paths(self) -> None:
        args = tool.parse_args([])
        assert args.apply is False
        assert args.vault_root is None
        assert args.report_path is None

    def test_all_flags(self, tmp_path: Path) -> None:
        args = tool.parse_args(
            ["--vault-root", str(tmp_path), "--apply", "--report-path", str(tmp_path / "r.json")]
        )
        assert args.apply is True
        assert args.vault_root == tmp_path
        assert args.report_path == tmp_path / "r.json"
        assert isinstance(args.vault_root, Path)

    @pytest.mark.parametrize("flag", ["--app", "--ap", "--appl", "--vault", "--report"])
    def test_abbreviated_flags_are_refused(self, flag: str, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as info:
            tool.parse_args([flag])
        assert info.value.code == 2

    @pytest.mark.parametrize("argv", [["--unknown"], ["--apply=yes"], ["stray"], ["--vault-root"]])
    def test_bad_arguments_exit_two(self, argv: List[str], capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as info:
            tool.parse_args(argv)
        assert info.value.code == 2

    def test_none_reads_the_process_arguments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["prog", "--apply"])
        assert tool.parse_args(None).apply is True


def install_fake_paths(mp: pytest.MonkeyPatch, load: Any) -> None:
    """Put a stand in `core.paths` module in sys.modules so the real loader is never read."""
    fake = types.ModuleType("core.paths")
    fake.get_path = lambda name: load()[name]  # type: ignore[attr-defined]
    mp.setitem(sys.modules, "core.paths", fake)


class TestDefaultVaultRoot:
    """default_vault_root: reads the path loader, with exit 2 on any failure."""

    def test_returns_the_vault_path_from_the_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_fake_paths(monkeypatch, lambda: {"vault": tmp_path / "v", "other": tmp_path})
        assert REAL_DEFAULT_VAULT_ROOT() == tmp_path / "v"

    def test_a_string_value_becomes_a_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_fake_paths(monkeypatch, lambda: {"vault": str(tmp_path)})
        result = REAL_DEFAULT_VAULT_ROOT()
        assert isinstance(result, Path)
        assert result == tmp_path

    def test_the_script_folder_is_put_on_the_import_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        script_dir = str(SCRIPT_PATH.parents[1])
        monkeypatch.setattr(sys, "path", [item for item in sys.path if item != script_dir])
        install_fake_paths(monkeypatch, lambda: {"vault": tmp_path})
        REAL_DEFAULT_VAULT_ROOT()
        assert sys.path[0] == script_dir

    def raising(self, exc: BaseException) -> Any:
        def load() -> Dict[str, Any]:
            raise exc
        return load

    @pytest.mark.parametrize(
        "load",
        [
            lambda: {},
            lambda: {"other": Path("/tmp")},
            lambda: (_ for _ in ()).throw(FileNotFoundError("missing")),
            lambda: (_ for _ in ()).throw(PermissionError("denied")),
            lambda: (_ for _ in ()).throw(yaml.YAMLError("bad yaml")),
            lambda: (_ for _ in ()).throw(AttributeError("no get")),
            lambda: None,
        ],
        ids=["empty", "no_vault_key", "no_file", "denied", "bad_yaml", "bad_shape", "none"],
    )
    def test_a_missing_file_or_key_raises_the_precondition_error(
        self, monkeypatch: pytest.MonkeyPatch, load: Any
    ) -> None:
        install_fake_paths(monkeypatch, load)
        with pytest.raises(tool.PreconditionError) as info:
            REAL_DEFAULT_VAULT_ROOT()
        assert str(info.value) == "PATHS_MANIFEST_UNREADABLE"

    def test_a_missing_paths_module_raises_the_precondition_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "core.paths", None)
        with pytest.raises(tool.PreconditionError):
            REAL_DEFAULT_VAULT_ROOT()

    def test_error_text_from_the_manifest_never_surfaces(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        install_fake_paths(monkeypatch, self.raising(OSError(CANARY)))
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(tool.PreconditionError) as info:
                REAL_DEFAULT_VAULT_ROOT()
        assert CANARY not in str(info.value)
        assert info.value.__cause__ is None
        assert info.value.__suppress_context__ is True
        assert CANARY not in caplog.text


RUN_FILES = {
    "a.md": DECISION_DOC,
    "b.md": DECISION_DOC,
    "c.md": b"# plain note\n",
}


def small_vault(vb: VaultBuilder) -> VaultBuilder:
    """Commit two eligible files and one plain note."""
    commit_files(vb, RUN_FILES)
    return vb


class TestRun:
    """run: one git snapshot, plan every file, write only in apply mode."""

    def test_preview_never_calls_apply_edit_and_writes_nothing(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        small_vault(vault)
        calls: List[Any] = []
        monkeypatch.setattr(tool, "apply_edit", lambda *args: calls.append(args))
        before = snapshot(vault.root)
        report = tool.run(vault.root, False)
        assert calls == []
        assert snapshot(vault.root) == before
        assert report["mode"] == "preview"
        assert report["counts"]["written"] == 2

    def test_apply_calls_apply_edit_once_per_planned_write(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        small_vault(vault)
        calls: List[Tuple[Path, bytes, bytes]] = []
        real = tool.apply_edit

        def spy(path: Path, original: bytes, new_raw: bytes) -> Optional[str]:
            calls.append((path, original, new_raw))
            return real(path, original, new_raw)

        monkeypatch.setattr(tool, "apply_edit", spy)
        report = tool.run(vault.root, True)
        assert report["mode"] == "apply"
        assert [call[0] for call in calls] == [vault.root / "a.md", vault.root / "b.md"]
        assert all(call[1] == DECISION_DOC and call[2] == DECISION_NEW for call in calls)
        assert (vault.root / "a.md").read_bytes() == DECISION_NEW
        assert (vault.root / "c.md").read_bytes() == RUN_FILES["c.md"]

    def test_a_failed_write_is_skipped_with_its_row_and_the_run_continues(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        small_vault(vault)
        real = tool.apply_edit

        def flaky(path: Path, original: bytes, new_raw: bytes) -> Optional[str]:
            if path.name == "a.md":
                return "WRITE_FAILED"
            return real(path, original, new_raw)

        monkeypatch.setattr(tool, "apply_edit", flaky)
        report = tool.run(vault.root, True)
        assert report["skipped"] == [{"path": "a.md", "reason": "WRITE_FAILED"}]
        assert [entry["path"] for entry in report["writes"]] == ["b.md"]
        assert report["counts"]["written"] == 1 and report["counts"]["skipped"] == 1
        assert report["rows"]["2"] == 2
        assert (vault.root / "a.md").read_bytes() == DECISION_DOC
        assert (vault.root / "b.md").read_bytes() == DECISION_NEW

    def test_a_file_changed_after_planning_is_skipped_and_the_newer_bytes_survive(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        small_vault(vault)
        real = tool.plan_file
        newer = DECISION_DOC + b"Another session wrote this.\n"

        def racing(root: Path, rel: str, git: Any) -> Any:
            planned_outcome = real(root, rel, git)
            if rel == "a.md":
                (root / rel).write_bytes(newer)
            return planned_outcome

        monkeypatch.setattr(tool, "plan_file", racing)
        report = tool.run(vault.root, True)
        assert report["skipped"] == [{"path": "a.md", "reason": "CHANGED_DURING_RUN"}]
        assert (vault.root / "a.md").read_bytes() == newer
        assert (vault.root / "b.md").read_bytes() == DECISION_NEW

    def test_a_write_outcome_without_bytes_is_skipped_and_logged_not_written(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        small_vault(vault)
        broken = tool.Outcome("a.md", "write", row=2, additions=dict(DECISION_ADDITIONS))
        monkeypatch.setattr(tool, "plan_file", lambda root, rel, git: broken)
        calls: List[Any] = []
        monkeypatch.setattr(tool, "apply_edit", lambda *args: calls.append(args))
        with caplog.at_level(logging.ERROR):
            report = tool.run(vault.root, True)
        assert calls == []
        assert {entry["reason"] for entry in report["skipped"]} == {"VERIFY_FAILED"}
        assert report["counts"]["written"] == 0
        assert any(record.levelno == logging.ERROR for record in caplog.records)

    def test_the_git_snapshot_is_taken_once_and_before_any_file_is_planned(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        small_vault(vault)
        order: List[str] = []
        real_state, real_plan = tool.load_git_state, tool.plan_file

        def spy_state(root: Path) -> Any:
            order.append("git")
            return real_state(root)

        def spy_plan(root: Path, rel: str, git: Any) -> Any:
            order.append("plan:" + rel)
            return real_plan(root, rel, git)

        monkeypatch.setattr(tool, "load_git_state", spy_state)
        monkeypatch.setattr(tool, "plan_file", spy_plan)
        tool.run(vault.root, True)
        assert order == ["git", "plan:a.md", "plan:b.md", "plan:c.md"]

    def test_a_vault_that_is_not_a_repository_is_fatal_before_any_file_is_planned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isolate_git(monkeypatch, tmp_path)
        plain = tmp_path / "plain"
        touch_files(plain, ["a.md"])
        monkeypatch.setattr(tool, "plan_file", lambda *args: pytest.fail("planned a file"))
        with pytest.raises(tool.GitStateError):
            tool.run(plain, True)
        assert (plain / "a.md").read_bytes() == DECISION_DOC

    def test_an_interrupt_logs_the_count_and_is_raised_again(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        small_vault(vault)
        real = tool.plan_file
        seen: List[str] = []

        def interrupted(root: Path, rel: str, git: Any) -> Any:
            seen.append(rel)
            if len(seen) == 2:
                raise KeyboardInterrupt
            return real(root, rel, git)

        monkeypatch.setattr(tool, "plan_file", interrupted)
        with caplog.at_level(logging.WARNING):
            with pytest.raises(KeyboardInterrupt):
                tool.run(vault.root, True)
        assert any("interrupted after 1 files" in record.getMessage() for record in caplog.records)
        assert (vault.root / "a.md").read_bytes() == DECISION_NEW
        assert (vault.root / "b.md").read_bytes() == DECISION_DOC

    def test_the_report_holds_every_scanned_file_exactly_once(self, vault: VaultBuilder) -> None:
        small_vault(vault)
        report = tool.run(vault.root, False)
        assert report["counts"]["scanned"] == 3
        assert report["counts"]["not_target"] == 1
        listed = [entry["path"] for entry in report["writes"]]
        assert listed == ["a.md", "b.md"]


# ---------------------------------------------------------------------------
# Acceptance criteria AC-01 through AC-08, driven through main
# ---------------------------------------------------------------------------

FIELD_LINE = re.compile(r"^\+(catalog_type|doc_role|indexable|indexed): ")
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
ROW_PATH_PREFIX = "08-reference/row-"
UNMAPPED_PATH = "08-reference/unmapped.md"
OLD_KEY_PATH = "08-reference/old-key.md"
BOTH_KEYS_PATH = "08-reference/both-keys.md"
FIELD_NAMES = ("catalog_type", "doc_role", "indexable", "indexed")
INDEXED_TRUE_ROWS = sum(1 for row in EXPECTED_ROWS if row[3])


def frontmatter_lines(raw: bytes) -> Tuple[List[bytes], int]:
    """Split file bytes into lines and return them with the index of the closing delimiter."""
    lines = raw.splitlines(keepends=True)
    close = next(i for i in range(1, len(lines)) if lines[i].rstrip(b"\r\n") == b"---")
    return lines, close


def block_of(raw: bytes) -> bytes:
    """The bytes between the two delimiter lines."""
    lines, close = frontmatter_lines(raw)
    return b"".join(lines[1:close])


def added_line_numbers(diff_text: str) -> List[int]:
    """New file line numbers of every added line in a zero context diff."""
    numbers: List[int] = []
    for line in diff_text.splitlines():
        match = HUNK_HEADER.match(line)
        if match:
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) is not None else 1
            numbers.extend(range(start, start + count))
    return numbers


def parse_numstat(text: str) -> Dict[str, Tuple[str, str]]:
    """Map path to (added, deleted) from `git diff --numstat`."""
    result: Dict[str, Tuple[str, str]] = {}
    for line in text.splitlines():
        added, deleted, path = line.split("\t", 2)
        result[path] = (added, deleted)
    return result


def row_file(doc_type: str) -> bytes:
    """A fixture file whose frontmatter holds one doc_type and a title."""
    return "---\ndoc_type: {0}\ntitle: Row {0}\n---\nBody.\n".format(doc_type).encode("utf-8")


class TestAC01MappingRows:
    """AC-01: one file per table row, an unmapped value, and the older type key."""

    def build(self, vault: VaultBuilder) -> None:
        files = {ROW_PATH_PREFIX + row[0] + ".md": row_file(row[0]) for row in EXPECTED_ROWS}
        files[UNMAPPED_PATH] = row_file(UNMAPPED_DOC_TYPE)
        files[OLD_KEY_PATH] = b"---\ntype: ticket_spec\ntitle: Old key\n---\nBody.\n"
        commit_files(vault, files)

    def test_each_row_unmapped_and_old_key(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        self.build(vault)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        for doc_type, catalog, role, indexable in EXPECTED_ROWS:
            raw = (vault.root / (ROW_PATH_PREFIX + doc_type + ".md")).read_bytes()
            assert field_values(raw) == (catalog, role, indexable), doc_type
            assert fm_of(raw)["doc_type"] == doc_type
        assert field_values((vault.root / UNMAPPED_PATH).read_bytes()) == EXPECTED_SENTINEL
        assert field_values((vault.root / OLD_KEY_PATH).read_bytes()) == ("ticket", "spec", True)
        assert report["counts"]["written"] == EXPECTED_ROW_COUNT + 2

    def test_added_lines_are_exact_text_in_field_order(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        self.build(vault)
        run_cli(capsys, vault.root, apply=True)
        for doc_type, catalog, role, indexable in EXPECTED_ROWS:
            flag = "true" if indexable else "false"
            expected = (
                "---\ndoc_type: {0}\ntitle: Row {0}\ncatalog_type: {1}\ndoc_role: {2}\n"
                "indexable: {3}\nindexed: null\n---\nBody.\n"
            ).format(doc_type, catalog, role, flag).encode("utf-8")
            assert (vault.root / (ROW_PATH_PREFIX + doc_type + ".md")).read_bytes() == expected

    def test_the_report_counts_the_fixture(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        self.build(vault)
        _, report = run_cli(capsys, vault.root, apply=True)
        assert report["counts"]["scanned"] == EXPECTED_ROW_COUNT + 2
        assert report["counts"]["classified"] == EXPECTED_ROW_COUNT + 2
        assert report["counts"]["skipped"] == 0
        assert report["rows"] == {"1": 0, "2": EXPECTED_ROW_COUNT, "3": 1, "4": 1}
        assert report["unmapped_doc_types"] == {UNMAPPED_DOC_TYPE: 1}
        assert report["counts"]["writes_indexable"] == INDEXED_TRUE_ROWS + 1 == 36
        assert report["counts"]["needing_fields"] == EXPECTED_ROW_COUNT + 2

    @pytest.mark.parametrize(
        "line,label",
        [
            ("doc_type: [a, b]", "<non-string>"),
            ("doc_type: 42", "<non-string>"),
            ("doc_type: ~", "<non-string>"),
            ('doc_type: "two words"', "<unprintable>"),
            ('doc_type: "Ticket_Spec"', "Ticket_Spec"),
            ("doc_type: session_log", "session_log"),
        ],
        ids=["list", "int", "null", "spaces", "case_variant", "drift_value"],
    )
    def test_unmapped_variants_get_sentinel_values_and_a_safe_label(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, line: str, label: str
    ) -> None:
        commit_files(vault, {"08-reference/odd.md": "---\n{}\n---\nBody.\n".format(line).encode()})
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        assert field_values((vault.root / "08-reference/odd.md").read_bytes()) == EXPECTED_SENTINEL
        assert report["unmapped_doc_types"] == {label: 1}

    def test_doc_type_decides_when_both_keys_are_present(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        commit_files(vault, {
            BOTH_KEYS_PATH: b"---\ndoc_type: made_up_type\ntype: ticket_spec\n---\nBody.\n",
        })
        run_cli(capsys, vault.root, apply=True)
        assert field_values((vault.root / BOTH_KEYS_PATH).read_bytes()) == EXPECTED_SENTINEL

    def test_a_mapped_type_value_under_the_old_key_only_counts_in_row_four(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        commit_files(vault, {OLD_KEY_PATH: b"---\ntype: ticket_spec\n---\nBody.\n"})
        _, report = run_cli(capsys, vault.root, apply=False)
        assert report["rows"] == {"1": 0, "2": 0, "3": 0, "4": 1}
        assert report["unmapped_doc_types"] == {}


AC02_STATE_FILES = {
    "02-tickets/T-931/T-931-state.md": b"---\ntype: ticket_state\nticket: T-931\n---\nBody.\n",
    "02-tickets/T-932/T-932-state.md": b"---\ntype: build\nticket: T-932\n---\nBody.\n",
    "02-tickets/T-933/T-933-state.md": b"---\ntype: feature\nticket: T-933\n---\nBody.\n",
    "02-tickets/T-934/T-934-state.md": b"---\ntitle: No type key\n---\nBody.\n",
    "02-tickets/T-935/T-935-state.md": b"---\n---\nBody.\n",
}
AC02_LOOKALIKES = {
    "02-tickets/T-936/T-937-state.md": b"---\ntype: build\n---\nBody.\n",
    "02-tickets/T-936/sub/T-936-state.md": b"---\ntype: build\n---\nBody.\n",
    "00-landing/T-936-state.md": b"---\ntype: build\n---\nBody.\n",
    "03-knowledge-base/T-936/T-936-state.md": b"---\ntype: feature\n---\nBody.\n",
}
AC02_LOOKALIKE_WITH_DOC_TYPE = "02-tickets/T-938/T-939-state.md"


class TestAC02StateFiles:
    """AC-02: the filename decides ticket state files, whatever the type key says."""

    def build(self, vault: VaultBuilder) -> None:
        files = dict(AC02_STATE_FILES)
        files.update(AC02_LOOKALIKES)
        files[AC02_LOOKALIKE_WITH_DOC_TYPE] = b"---\ndoc_type: decision\n---\nBody.\n"
        commit_files(vault, files)

    def test_state_file_variants(self, vault: VaultBuilder, capsys: pytest.CaptureFixture) -> None:
        self.build(vault)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        for rel, original in AC02_STATE_FILES.items():
            raw = (vault.root / rel).read_bytes()
            assert field_values(raw) == EXPECTED_STATE, rel
            for key, value in fm_of(original).items():
                assert fm_of(raw)[key] == value, (rel, key)
        for rel, original in AC02_LOOKALIKES.items():
            assert (vault.root / rel).read_bytes() == original, rel
        lookalike = (vault.root / AC02_LOOKALIKE_WITH_DOC_TYPE).read_bytes()
        assert field_values(lookalike) == ("knowledge", "decision", True)
        assert report["rows"] == {"1": 5, "2": 1, "3": 0, "4": 0}
        assert report["counts"]["not_target"] == len(AC02_LOOKALIKES)

    def test_a_state_file_keeps_its_task_category_key(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        commit_files(vault, AC02_STATE_FILES)
        run_cli(capsys, vault.root, apply=True)
        raw = (vault.root / "02-tickets/T-932/T-932-state.md").read_bytes()
        assert fm_of(raw)["type"] == "build"
        assert raw.startswith(b"---\ntype: build\nticket: T-932\n")

    def test_row_one_wins_over_an_unmapped_doc_type_on_a_state_path(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        rel = "02-tickets/T-940/T-940-state.md"
        commit_files(vault, {rel: b"---\ndoc_type: made_up_type\n---\nBody.\n"})
        _, report = run_cli(capsys, vault.root, apply=True)
        assert field_values((vault.root / rel).read_bytes()) == EXPECTED_STATE
        assert report["unmapped_doc_types"] == {}
        assert report["rows"]["1"] == 1

    def test_an_empty_block_gets_all_four_fields(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        rel = "02-tickets/T-941/T-941-state.md"
        commit_files(vault, {rel: b"---\n---\nBody.\n"})
        run_cli(capsys, vault.root, apply=True)
        assert (vault.root / rel).read_bytes() == (
            b"---\ncatalog_type: ticket\ndoc_role: state\nindexable: true\nindexed: null\n---\nBody.\n"
        )


def ac03_files() -> Dict[str, bytes]:
    """Files whose frontmatter ends in awkward ways, plus partial, CRLF, and odd body bytes."""
    files = {
        "00-landing/variant-" + name + ".md": make_file(block)
        for name, block in FRONTMATTER_VARIANTS.items()
    }
    files["00-landing/partial.md"] = (
        b"---\ndoc_type: decision\ncatalog_type: knowledge\ndoc_role: decision\n---\nBody.\n"
    )
    files["00-landing/crlf-links.md"] = make_file(FRONTMATTER_VARIANTS["quotes_and_links"], CRLF)
    files["00-landing/crlf-list.md"] = make_file(FRONTMATTER_VARIANTS["list_end"], CRLF)
    files["00-landing/odd-body.md"] = make_file(
        b"doc_type: ticket_spec\n", tail=b"\xff\xfe binary \x80"
    )
    return files


class TestAC03ByteIdentity:
    """AC-03: git sees only added field lines, placed above the closing delimiter."""

    def test_git_diff_adds_only_field_lines(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        files = ac03_files()
        commit_files(vault, files)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        assert report["counts"]["written"] == len(files)
        status = vault.git("status", "--porcelain").splitlines()
        assert sorted(line for line in status) == sorted(" M " + rel for rel in files)
        numstat = parse_numstat(vault.git("diff", "--numstat"))
        assert set(numstat) == set(files)
        for rel, original in files.items():
            added_count, deleted_count = numstat[rel]
            assert deleted_count == "0", rel
            assert added_count == ("2" if rel.endswith("partial.md") else "4"), rel
            self.check_one_file(vault, rel, original)

    def check_one_file(self, vault: VaultBuilder, rel: str, original: bytes) -> None:
        diff = vault.git("diff", "-U0", "--no-color", "--", rel)
        added = [line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
        assert added and all(FIELD_LINE.match(line) for line in added), rel
        new_raw = (vault.root / rel).read_bytes()
        _, close = frontmatter_lines(new_raw)
        assert added_line_numbers(diff) == list(range(close + 1 - len(added), close + 1)), rel
        key_counts = top_level_key_counts(block_of(new_raw))
        assert all(count == 1 for count in key_counts.values()), (rel, key_counts)
        before, after = fm_of(original), fm_of(new_raw)
        for key, value in before.items():
            assert key in after and after[key] == value, (rel, key)
            assert type(after[key]) is type(value), (rel, key)

    def test_every_byte_outside_the_added_lines_is_unchanged(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        files = ac03_files()
        commit_files(vault, files)
        run_cli(capsys, vault.root, apply=True)
        for rel, original in files.items():
            new_raw = (vault.root / rel).read_bytes()
            lines, close = frontmatter_lines(new_raw)
            added_count = 2 if rel.endswith("partial.md") else 4
            rebuilt = b"".join(lines[: close - added_count] + lines[close:])
            assert rebuilt == original, rel

    def test_added_lines_use_the_files_own_line_ending(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        files = ac03_files()
        commit_files(vault, files)
        run_cli(capsys, vault.root, apply=True)
        for rel in files:
            new_raw = (vault.root / rel).read_bytes()
            if "crlf" in rel:
                assert new_raw.count(b"\n") == new_raw.count(b"\r\n"), rel
            else:
                assert b"\r" not in new_raw, rel

    def test_a_partially_populated_file_gains_only_the_missing_fields(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        rel = "00-landing/partial.md"
        commit_files(vault, {rel: ac03_files()[rel]})
        run_cli(capsys, vault.root, apply=True)
        assert (vault.root / rel).read_bytes() == (
            b"---\ndoc_type: decision\ncatalog_type: knowledge\ndoc_role: decision\n"
            b"indexable: true\nindexed: null\n---\nBody.\n"
        )

    def test_a_file_with_no_final_newline_and_a_non_utf8_body_keeps_its_tail(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        rel = "00-landing/odd-body.md"
        commit_files(vault, {rel: ac03_files()[rel]})
        run_cli(capsys, vault.root, apply=True)
        raw = (vault.root / rel).read_bytes()
        assert raw.endswith(b"---\n\xff\xfe binary \x80")


CANARY_BYTES = CANARY.encode("utf-8")
AC04_UNPARSEABLE = "00-landing/unparseable.md"
AC04_CONFLICT = "00-landing/conflict.md"
AC04_STATE_WITHOUT_FRONTMATTER = "02-tickets/T-950/T-950-state.md"
AC04_FILES = {
    AC04_UNPARSEABLE: b"---\ndoc_type: decision\nbroken: [" + CANARY_BYTES + b"\n---\nBody.\n",
    AC04_CONFLICT: b"---\ndoc_type: ticket_spec\ndoc_role: design\n---\nBody.\n",
    AC04_STATE_WITHOUT_FRONTMATTER: b"# State without frontmatter\nBody.\n",
}
AC04_CONTROL = "00-landing/ok.md"
CONFLICT_LINES = [
    ("catalog_type: ticket", "CONFLICT_CATALOG_TYPE"),
    ("doc_role: design", "CONFLICT_DOC_ROLE"),
    ('indexable: "true"', "CONFLICT_INDEXABLE"),
    ("indexable: 1", "CONFLICT_INDEXABLE"),
    ("indexable: false", "CONFLICT_INDEXABLE"),
]
PARSE_FAILURES = {
    "unclosed_flow": b"---\ndoc_type: decision\nx: [a\n---\nBody.\n",
    "tab_indent": b"---\ndoc_type: decision\n\tx: 1\n---\nBody.\n",
    "list_not_mapping": b"---\n- a\n- b\n---\nBody.\n",
    "scalar_not_mapping": b"---\njust text\n---\nBody.\n",
    "month_13": b"---\ndoc_type: decision\ndate: 2026-13-01\n---\nBody.\n",
    "invalid_utf8": b"---\ndoc_type: decision\ntitle: \xff\xfe\n---\nBody.\n",
}


class TestAC04SkipAndReport:
    """AC-04: unparseable, conflicting, and frontmatter free state files stay byte identical."""

    def test_parse_conflict_and_missing_frontmatter(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        files = dict(AC04_FILES)
        files[AC04_CONTROL] = DECISION_DOC
        commit_files(vault, files)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        for rel, original in AC04_FILES.items():
            assert (vault.root / rel).read_bytes() == original, rel
        assert report["skipped"] == [
            {"path": AC04_CONFLICT, "reason": "CONFLICT_DOC_ROLE"},
            {"path": AC04_UNPARSEABLE, "reason": "PARSE_ERROR"},
            {"path": AC04_STATE_WITHOUT_FRONTMATTER, "reason": "NO_FRONTMATTER"},
        ]
        assert report["skipped_by_reason"] == {
            "CONFLICT_DOC_ROLE": 1, "PARSE_ERROR": 1, "NO_FRONTMATTER": 1,
        }
        assert (vault.root / AC04_CONTROL).read_bytes() == DECISION_NEW
        assert vault.git("status", "--porcelain") == " M " + AC04_CONTROL + "\n"

    @pytest.mark.parametrize("line,reason", CONFLICT_LINES)
    def test_each_conflict_field_is_skipped_with_its_own_code(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, line: str, reason: str
    ) -> None:
        original = "---\ndoc_type: decision\n{}\n---\nBody.\n".format(line).encode("utf-8")
        commit_files(vault, {"00-landing/c.md": original})
        _, report = run_cli(capsys, vault.root, apply=True)
        assert (vault.root / "00-landing/c.md").read_bytes() == original
        assert report["skipped"] == [{"path": "00-landing/c.md", "reason": reason}]

    def test_values_that_match_are_not_a_conflict(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        original = b"---\ndoc_type: decision\ncatalog_type: knowledge\nindexable: true\n---\nBody.\n"
        commit_files(vault, {"00-landing/m.md": original})
        _, report = run_cli(capsys, vault.root, apply=True)
        assert report["skipped"] == []
        assert (vault.root / "00-landing/m.md").read_bytes() == (
            b"---\ndoc_type: decision\ncatalog_type: knowledge\nindexable: true\n"
            b"doc_role: decision\nindexed: null\n---\nBody.\n"
        )

    def test_the_machine_stamped_indexed_field_is_never_compared(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        original = b"---\ndoc_type: decision\nindexed: 2026-10-01\n---\nBody.\n"
        commit_files(vault, {"00-landing/s.md": original})
        _, report = run_cli(capsys, vault.root, apply=True)
        assert report["skipped"] == []
        fm = fm_of((vault.root / "00-landing/s.md").read_bytes())
        assert str(fm["indexed"]) == "2026-10-01"
        assert (fm["catalog_type"], fm["doc_role"], fm["indexable"]) == ("knowledge", "decision", True)

    @pytest.mark.parametrize("name", sorted(PARSE_FAILURES))
    def test_every_kind_of_parse_failure_is_skipped_untouched_and_listed(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, name: str
    ) -> None:
        original = PARSE_FAILURES[name]
        commit_files(vault, {"00-landing/p.md": original})
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        assert (vault.root / "00-landing/p.md").read_bytes() == original
        assert report["skipped"] == [{"path": "00-landing/p.md", "reason": "PARSE_ERROR"}]

    def test_unparseable_frontmatter_is_skipped_even_when_it_may_not_be_a_target(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        original = b"---\ntitle: x\nbroken: [a\n---\nBody.\n"
        commit_files(vault, {"00-landing/n.md": original})
        _, report = run_cli(capsys, vault.root, apply=True)
        assert report["skipped"] == [{"path": "00-landing/n.md", "reason": "PARSE_ERROR"}]
        assert report["counts"]["not_target"] == 0


AC05_PROTECTED = {
    ".claude/worktrees/wt1/doc.md": DECISION_DOC,
    ".obsidian/note.md": DECISION_DOC,
    ".hidden/deep/doc.md": DECISION_DOC,
    "memory/m.md": DECISION_DOC,
    "memory/deep/er/m.md": DECISION_DOC,
}
AC05_NOT_TARGETS = {
    "00-landing/below-line-one.md": b"# Title\n---\ndoc_type: decision\n---\nBody.\n",
    "00-landing/bom.md": b"\xef\xbb\xbf---\ndoc_type: decision\n---\nBody.\n",
    "00-landing/blank-first.md": b"\n---\ndoc_type: decision\n---\nBody.\n",
    "00-landing/type-build.md": b"---\ntype: build\n---\nBody.\n",
}
AC05_WALKED = {
    "00-landing/control.md": DECISION_DOC,
    "08-reference/.hidden/doc.md": DECISION_DOC,
    "memory2/n.md": DECISION_DOC,
    "03-knowledge-base/memory/n.md": DECISION_DOC,
    "03-knowledge-base/decisions/memory/n.md": DECISION_DOC,
}


class TestAC05Exclusions:
    """AC-05: hidden root folders, excluded prefixes, odd frontmatter starts, and row 5 files."""

    def build(self, vault: VaultBuilder) -> None:
        files = dict(AC05_PROTECTED)
        files.update(AC05_NOT_TARGETS)
        files.update(AC05_WALKED)
        commit_files(vault, files)

    def test_excluded_files_byte_identical(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        self.build(vault)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        for rel, original in {**AC05_PROTECTED, **AC05_NOT_TARGETS}.items():
            assert (vault.root / rel).read_bytes() == original, rel
        for rel in AC05_WALKED:
            assert (vault.root / rel).read_bytes() == DECISION_NEW, rel
        assert sorted(line[3:] for line in vault.git("status", "--porcelain").splitlines()) == (
            sorted(AC05_WALKED)
        )
        assert report["counts"]["scanned"] == len(AC05_WALKED) + len(AC05_NOT_TARGETS)
        assert report["counts"]["not_target"] == len(AC05_NOT_TARGETS)
        assert report["counts"]["written"] == len(AC05_WALKED)
        assert report["exclusions"] == EXPECTED_EXCLUSIONS

    def test_excluded_paths_are_absent_from_every_report_list(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        self.build(vault)
        _, report = run_cli(capsys, vault.root, apply=False)
        listed = [entry["path"] for entry in report["writes"] + report["skipped"]]
        assert not [path for path in listed if path in AC05_PROTECTED]

    def test_a_dot_folder_below_the_root_is_walked(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        commit_files(vault, {"08-reference/.hidden/doc.md": DECISION_DOC})
        _, report = run_cli(capsys, vault.root, apply=False)
        assert [entry["path"] for entry in report["writes"]] == ["08-reference/.hidden/doc.md"]

    def test_non_markdown_files_are_never_read_or_counted(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        commit_files(vault, {
            "00-landing/note.txt": DECISION_DOC, "00-landing/note.markdown": DECISION_DOC,
            "00-landing/note.MD": DECISION_DOC,
        })
        _, report = run_cli(capsys, vault.root, apply=True)
        assert report["counts"]["scanned"] == 0
        assert (vault.root / "00-landing/note.txt").read_bytes() == DECISION_DOC


def without_mode(report: Dict[str, Any]) -> Dict[str, Any]:
    """The report minus its mode key, for preview versus apply comparisons."""
    return {key: value for key, value in report.items() if key != "mode"}


def canary_doc(front: bytes, body: bytes = b"") -> bytes:
    """A fixture file with the canary in its body and the given frontmatter lines."""
    return b"---\n" + front + b"---\nBody " + CANARY_BYTES + b"\n" + body


COMPLETE_FRONT = (
    b"catalog_type: knowledge\ndoc_role: decision\nindexable: true\nindexed: null\n"
)


class MixedCase(NamedTuple):
    """One file of the mixed vault, with the literal outcome expected for it."""

    rel: str
    content: bytes
    state: str
    kind: str
    reason: Optional[str]
    row: Optional[int]
    label: Optional[str]
    adds_indexable_true: bool


def mixed_write(rel: str, front: bytes, row: int, label: Optional[str] = None,
                adds_true: bool = False) -> MixedCase:
    """A clean tracked file the run must plan as a write."""
    return MixedCase(rel, canary_doc(front), "clean", KIND_WRITE, None, row, label, adds_true)


def mixed_skip(rel: str, content: bytes, reason: str, row: Optional[int],
               state: str = "clean") -> MixedCase:
    """A file the run must skip with the given reason."""
    return MixedCase(rel, content, state, KIND_SKIPPED, reason, row, None, False)


MIXED: List[MixedCase] = [
    mixed_write("00-landing/a-write.md",
                b"doc_type: decision\ntitle: " + CANARY_BYTES + b"\n", 2, adds_true=True),
    mixed_write("00-landing/b-conversation.md",
                b"doc_type: conversation\nnote: " + CANARY_BYTES + b"\n", 2),
    mixed_write("08-reference/c-sentinel.md",
                b"doc_type: made_up_type\nnote: " + CANARY_BYTES + b"\n", 3, "made_up_type"),
    mixed_write("08-reference/d-sentinel.md",
                b"doc_type: made_up_type\nnote: " + CANARY_BYTES + b"\n", 3, "made_up_type"),
    mixed_write("08-reference/e-nonstring.md",
                b"doc_type: [" + CANARY_BYTES + b"]\n", 3, "<non-string>"),
    mixed_write("08-reference/f-unprintable.md",
                b'doc_type: "two words ' + CANARY_BYTES + b'"\n', 3, "<unprintable>"),
    mixed_write("00-landing/g-oldkey.md",
                b"type: ticket_spec\nnote: " + CANARY_BYTES + b"\n", 4, adds_true=True),
    mixed_write("02-tickets/T-920/T-920-state.md",
                b"type: build\nnote: " + CANARY_BYTES + b"\n", 1, adds_true=True),
    MixedCase("00-landing/h-complete.md",
              canary_doc(b"doc_type: decision\ntitle: " + CANARY_BYTES + b"\n" + COMPLETE_FRONT),
              "clean", KIND_ALREADY_COMPLETE, None, 2, None, False),
    MixedCase("08-reference/i-complete-unmapped.md",
              canary_doc(b"doc_type: design\ncatalog_type: ticket\ndoc_role: design\n"
                         b"indexable: true\nindexed: null\n"),
              "clean", KIND_ALREADY_COMPLETE, None, 3, "design", False),
    mixed_skip("00-landing/j-parse-error.md",
               b"---\ndoc_type: decision\ntitle: [" + CANARY_BYTES + b"\n---\nBody "
               + CANARY_BYTES + b"\n", "PARSE_ERROR", None),
    mixed_skip("00-landing/k-conflict.md",
               canary_doc(b"doc_type: ticket_spec\ndoc_role: design\ntitle: " + CANARY_BYTES + b"\n"),
               "CONFLICT_DOC_ROLE", 2),
    mixed_skip("02-tickets/T-921/T-921-state.md",
               b"# State\nBody " + CANARY_BYTES + b"\n", "NO_FRONTMATTER", 1),
    mixed_skip("00-landing/l-untracked.md", canary_doc(b"doc_type: decision\n"),
               "UNTRACKED", 2, "untracked"),
    mixed_skip("00-landing/m-modified.md", canary_doc(b"doc_type: decision\n"),
               "UNCOMMITTED", 2, "modified"),
    MixedCase("00-landing/n-plain.md", b"# Plain\nBody " + CANARY_BYTES + b"\n",
              "clean", KIND_NOT_TARGET, None, 5, None, False),
    MixedCase("00-landing/o-type-build.md", canary_doc(b"type: build\n"),
              "clean", KIND_NOT_TARGET, None, 5, None, False),
    mixed_skip("00-landing/p-symlink.md", b"", "SYMLINK", None, "symlink"),
    mixed_write("00-landing/q-partial.md",
                b"doc_type: decision\ncatalog_type: knowledge\ndoc_role: decision\n", 2,
                adds_true=True),
    mixed_write("00-landing/r-partial-indexable.md",
                b"doc_type: decision\ncatalog_type: knowledge\ndoc_role: decision\n"
                b"indexable: true\n", 2),
]
MIXED_COUNTS = {
    "scanned": 20, "not_target": 2, "classified": 18, "already_complete": 2, "written": 10,
    "skipped": 6, "writes_indexable": 4, "needing_fields": 14,
}
MIXED_SKIPPED_BY_REASON = {
    "PARSE_ERROR": 1, "CONFLICT_DOC_ROLE": 1, "NO_FRONTMATTER": 1, "UNTRACKED": 1,
    "UNCOMMITTED": 1, "SYMLINK": 1,
}
MIXED_ROWS = {"1": 2, "2": 8, "3": 5, "4": 1}
MIXED_UNMAPPED = {"made_up_type": 2, "<non-string>": 1, "<unprintable>": 1, "design": 1}
SYMLINK_TARGET = "a-write.md"


def build_mixed_vault(vb: VaultBuilder) -> None:
    """Build MIXED: commit clean and modified files, link the symlink, edit, then add untracked."""
    for case in MIXED:
        if case.state in ("clean", "modified"):
            vb.write(case.rel, case.content)
            vb.add(case.rel)
        if case.state == "symlink":
            vb.symlink(case.rel, SYMLINK_TARGET)
            vb.add(case.rel)
    vb.commit()
    for case in MIXED:
        if case.state == "modified":
            vb.write(case.rel, case.content + WORKING_EDIT)
        if case.state == "untracked":
            vb.write(case.rel, case.content)


def mixed_counts_from_the_table() -> Dict[str, int]:
    """Counts worked out from the fixture table alone, never from a report."""
    kinds = [case.kind for case in MIXED]
    classified = len(MIXED) - kinds.count(KIND_NOT_TARGET)
    reasons = [case.reason for case in MIXED if case.kind == KIND_SKIPPED]
    return {
        "scanned": len(MIXED),
        "not_target": kinds.count(KIND_NOT_TARGET),
        "classified": classified,
        "already_complete": kinds.count(KIND_ALREADY_COMPLETE),
        "written": kinds.count(KIND_WRITE),
        "skipped": kinds.count(KIND_SKIPPED),
        "writes_indexable": sum(1 for case in MIXED if case.kind == KIND_WRITE and case.adds_indexable_true),
        "needing_fields": kinds.count(KIND_WRITE) + kinds.count(KIND_SKIPPED)
        - reasons.count("PARSE_ERROR") - reasons.count("NO_FRONTMATTER"),
    }


class TestMixedFixture:
    """The mixed vault's literal expectations agree with the table they come from."""

    def test_literal_counts_match_the_counts_worked_out_from_the_table(self) -> None:
        assert mixed_counts_from_the_table() == MIXED_COUNTS

    def test_rel_paths_are_unique(self) -> None:
        rels = [case.rel for case in MIXED]
        assert len(set(rels)) == len(rels)


class TestAC06PreviewApplyRerun:
    """AC-06: preview writes nothing, apply matches it, a second apply changes nothing."""

    def test_preview_matches_apply_and_second_run_is_empty(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        build_mixed_vault(vault)
        before = snapshot(vault.root)
        status_before = vault.git("status", "--porcelain")
        code, preview = run_cli(capsys, vault.root, apply=False)
        assert code == 0 and preview["mode"] == "preview"
        assert snapshot(vault.root) == before
        assert vault.git("status", "--porcelain") == status_before
        code, applied = run_cli(capsys, vault.root, apply=True)
        assert code == 0 and applied["mode"] == "apply"
        assert without_mode(applied) == without_mode(preview)
        after = snapshot(vault.root)
        changed = sorted(rel for rel in after if after[rel][0] != before[rel][0])
        assert changed == sorted(entry["path"] for entry in preview["writes"])
        code, again = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        assert snapshot(vault.root) == after
        assert again["counts"]["written"] == 0 and again["writes"] == []
        assert again["counts"]["already_complete"] == (
            applied["counts"]["already_complete"] + applied["counts"]["written"]
        )
        assert again["skipped"] == applied["skipped"]

    def test_the_second_run_never_calls_apply_edit(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_mixed_vault(vault)
        run_cli(capsys, vault.root, apply=True)
        calls: List[Any] = []
        monkeypatch.setattr(tool, "apply_edit", lambda *args: calls.append(args))
        run_cli(capsys, vault.root, apply=True)
        assert calls == []

    def test_preview_never_calls_apply_edit_through_main(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_mixed_vault(vault)
        calls: List[Any] = []
        monkeypatch.setattr(tool, "apply_edit", lambda *args: calls.append(args))
        run_cli(capsys, vault.root, apply=False)
        assert calls == []

    def test_without_the_apply_flag_the_default_is_preview(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        small_vault(vault)
        code = tool.main(["--vault-root", str(vault.root)])
        report = json.loads(capsys.readouterr().out)
        assert code == 0 and report["mode"] == "preview"
        assert (vault.root / "a.md").read_bytes() == DECISION_DOC


class TestAC07Unrestorable:
    """AC-07: files git cannot restore keep their exact bytes and are listed with a reason."""

    PROTECTED = {
        "00-landing/modified.md": "UNCOMMITTED",
        "00-landing/staged-modified.md": "UNCOMMITTED",
        "00-landing/staged-new.md": "UNCOMMITTED",
        "00-landing/untracked.md": "UNTRACKED",
        "ignored/hidden.md": "GITIGNORED",
        "00-landing/note.ignored.md": "GITIGNORED",
    }
    WRITTEN = ("00-landing/clean.md", "08-reference/forced.ignored.md")

    def build(self, vault: VaultBuilder) -> Dict[str, bytes]:
        for rel in ("00-landing/clean.md", "00-landing/modified.md", "00-landing/staged-modified.md"):
            vault.write(rel, DECISION_DOC)
            vault.add(rel)
        vault.write("08-reference/forced.ignored.md", DECISION_DOC)
        vault.add("08-reference/forced.ignored.md", force=True)
        vault.commit()
        vault.write("00-landing/modified.md", DECISION_DOC + WORKING_EDIT)
        vault.write("00-landing/staged-modified.md", DECISION_DOC + WORKING_EDIT)
        vault.add("00-landing/staged-modified.md")
        vault.write("00-landing/staged-new.md", DECISION_DOC)
        vault.add("00-landing/staged-new.md")
        for rel in ("00-landing/untracked.md", "ignored/hidden.md", "00-landing/note.ignored.md"):
            vault.write(rel, DECISION_DOC)
        return {rel: (vault.root / rel).read_bytes() for rel in self.PROTECTED}

    def test_untracked_ignored_dirty_unchanged(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        before = self.build(vault)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        for rel, original in before.items():
            assert (vault.root / rel).read_bytes() == original, rel
        assert report["skipped"] == [
            {"path": rel, "reason": self.PROTECTED[rel]} for rel in sorted(self.PROTECTED)
        ]
        assert report["skipped_by_reason"] == {"UNCOMMITTED": 3, "UNTRACKED": 1, "GITIGNORED": 2}
        for rel in self.WRITTEN:
            assert (vault.root / rel).read_bytes() == DECISION_NEW, rel
        assert sorted(entry["path"] for entry in report["writes"]) == sorted(self.WRITTEN)

    def test_preview_lists_the_same_skips_as_apply(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        self.build(vault)
        _, preview = run_cli(capsys, vault.root, apply=False)
        _, applied = run_cli(capsys, vault.root, apply=True)
        assert preview["skipped"] == applied["skipped"]

    def test_a_force_added_file_that_matches_an_ignore_rule_is_written(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        self.build(vault)
        run_cli(capsys, vault.root, apply=True)
        assert (vault.root / "08-reference/forced.ignored.md").read_bytes() == DECISION_NEW

    def test_a_skipped_file_is_written_after_it_is_committed(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        self.build(vault)
        run_cli(capsys, vault.root, apply=True)
        vault.add("00-landing/modified.md", "00-landing/staged-modified.md", "00-landing/staged-new.md",
                  "00-landing/untracked.md")
        vault.commit()
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        assert report["skipped_by_reason"] == {"GITIGNORED": 2}
        assert sorted(entry["path"] for entry in report["writes"]) == [
            "00-landing/modified.md", "00-landing/staged-modified.md", "00-landing/staged-new.md",
            "00-landing/untracked.md",
        ]
        assert (vault.root / "00-landing/untracked.md").read_bytes() == DECISION_NEW

    def test_nothing_unrestorable_is_ever_passed_to_apply_edit(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self.build(vault)
        seen: List[str] = []
        real = tool.apply_edit

        def spy(path: Path, original: bytes, new_raw: bytes) -> Optional[str]:
            seen.append(path.relative_to(vault.root).as_posix())
            return real(path, original, new_raw)

        monkeypatch.setattr(tool, "apply_edit", spy)
        run_cli(capsys, vault.root, apply=True)
        assert sorted(seen) == sorted(self.WRITTEN)


class TestAC08ReportContent:
    """AC-08: no canary in any output, and the counts reconcile with the fixture table."""

    def test_canary_absent_and_counts_reconcile(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
    ) -> None:
        build_mixed_vault(vault)
        report_file = tmp_path / "report.json"
        texts: List[str] = []
        reports: List[Dict[str, Any]] = []
        with caplog.at_level(logging.DEBUG):
            for apply in (False, True):
                code, out, err = run_cli_text(capsys, vault.root, apply, report_file)
                assert code == 0
                texts.extend([out, err, report_file.read_text(encoding="utf-8")])
                reports.append(json.loads(out))
            texts.append(caplog.text)
        for text in texts:
            assert CANARY not in text
        for report in reports:
            self.check_counts(report)
        assert without_mode(reports[0]) == without_mode(reports[1])

    def check_counts(self, report: Dict[str, Any]) -> None:
        counts = report["counts"]
        classified = len([case for case in MIXED if case.kind != KIND_NOT_TARGET])
        assert counts == MIXED_COUNTS
        assert counts["classified"] == classified
        assert counts["written"] + counts["skipped"] + counts["already_complete"] == classified
        assert counts["scanned"] == counts["not_target"] + classified
        assert report["skipped_by_reason"] == MIXED_SKIPPED_BY_REASON
        assert sum(report["skipped_by_reason"].values()) == counts["skipped"]
        assert report["rows"] == MIXED_ROWS
        assert report["unmapped_doc_types"] == MIXED_UNMAPPED
        assert report["skipped"] == [
            {"path": case.rel, "reason": case.reason}
            for case in sorted(MIXED, key=lambda item: item.rel) if case.kind == KIND_SKIPPED
        ]
        assert [entry["path"] for entry in report["writes"]] == sorted(
            case.rel for case in MIXED if case.kind == KIND_WRITE
        )

    def test_the_report_holds_only_paths_codes_field_values_and_counts(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        build_mixed_vault(vault)
        _, report = run_cli(capsys, vault.root, apply=False)
        assert set(report) == REPORT_KEYS
        assert set(report["counts"]) == COUNT_KEYS
        for entry in report["writes"]:
            assert set(entry["added"]) <= set(FIELD_NAMES)
        known_paths = {case.rel for case in MIXED}
        assert {entry["path"] for entry in report["skipped"] + report["writes"]} <= known_paths

    def test_a_failed_self_check_logs_no_canary(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        build_mixed_vault(vault)
        monkeypatch.setattr(tool, "verify_edit", lambda *args, **kwargs: False)
        with caplog.at_level(logging.DEBUG):
            code, out, err = run_cli_text(capsys, vault.root, True)
        assert code == 0
        assert any(record.levelno == logging.ERROR for record in caplog.records)
        for text in (out, err, caplog.text):
            assert CANARY not in text
        assert json.loads(out)["skipped_by_reason"]["VERIFY_FAILED"] == MIXED_COUNTS["written"]

    def test_fixture_values_never_reach_the_report_even_when_they_look_like_codes(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        commit_files(vault, {
            "00-landing/t.md": b"---\ndoc_type: made_up_type\ntitle: PARSE_ERROR " + CANARY_BYTES
            + b"\nnote: ok\n---\nBody " + CANARY_BYTES + b"\n",
        })
        _, out, _ = run_cli_text(capsys, vault.root, False)
        assert CANARY not in out
        assert "title" not in out


READ_ONLY_FOLDER_FILE = "locked/x.md"
OPEN_FOLDER_FILE = "open/y.md"
FATAL_PRECONDITION = "fatal precondition, nothing written"


def fatal_records(caplog: pytest.LogCaptureFixture) -> List[logging.LogRecord]:
    """The ERROR records logged by the tool."""
    return [record for record in caplog.records if record.levelno >= logging.ERROR]


def forbid_git_state(mp: pytest.MonkeyPatch) -> None:
    """Fail the test if the run reaches the git snapshot, which comes before any file read."""
    mp.setattr(tool, "load_git_state", lambda root: pytest.fail("the run started"))


class TestExitCodes:
    """main: 0 finished, 2 fatal precondition, 3 at least one WRITE_FAILED."""

    def test_a_preview_with_skips_exits_zero(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        build_mixed_vault(vault)
        code, report = run_cli(capsys, vault.root, apply=False)
        assert code == 0
        assert report["counts"]["skipped"] == MIXED_COUNTS["skipped"]

    def test_an_apply_with_skips_and_no_write_failure_exits_zero(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        build_mixed_vault(vault)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        assert "WRITE_FAILED" not in report["skipped_by_reason"]

    def test_a_missing_vault_root_exits_two_and_reads_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        forbid_git_state(monkeypatch)
        with caplog.at_level(logging.INFO):
            code = tool.main(cli_args(tmp_path / "does-not-exist", apply=True))
        assert code == 2
        assert capsys.readouterr().out == ""
        records = fatal_records(caplog)
        assert len(records) == 1
        assert records[0].getMessage() == FATAL_PRECONDITION + ": VAULT_ROOT_NOT_A_FOLDER"

    def test_a_vault_root_that_is_a_file_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        forbid_git_state(monkeypatch)
        (tmp_path / "file.md").write_bytes(DECISION_DOC)
        assert tool.main(cli_args(tmp_path / "file.md")) == 2
        assert capsys.readouterr().out == ""

    def test_a_vault_that_is_not_a_git_repository_exits_two_and_writes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        isolate_git(monkeypatch, tmp_path)
        plain = tmp_path / "plain"
        touch_files(plain, ["a.md", "sub/b.md"])
        before = snapshot(plain)
        with caplog.at_level(logging.INFO):
            code = tool.main(cli_args(plain, apply=True))
        assert code == 2
        assert capsys.readouterr().out == ""
        assert snapshot(plain) == before
        assert [record.getMessage() for record in fatal_records(caplog)] == [
            FATAL_PRECONDITION + ": GIT_NONZERO_EXIT",
        ]

    def test_a_repository_without_a_commit_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isolate_git(monkeypatch, tmp_path)
        builder = VaultBuilder(tmp_path / "unborn")
        builder.root.mkdir()
        builder.git("init", "-q")
        touch_files(builder.root, ["a.md"])
        before = snapshot(builder.root)
        assert tool.main(cli_args(builder.root, apply=True)) == 2
        assert capsys.readouterr().out == ""
        assert snapshot(builder.root) == before

    def test_git_that_is_not_installed_exits_two(
        self, vault: VaultBuilder, tmp_path: Path, capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        small_vault(vault)
        empty_bin = tmp_path / "empty-bin"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        assert tool.main(cli_args(vault.root, apply=True)) == 2
        assert capsys.readouterr().out == ""
        assert (vault.root / "a.md").read_bytes() == DECISION_DOC

    def test_a_git_error_message_is_a_closed_code_with_no_exception_text(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def broken(args: Any, **kwargs: Any) -> Any:
            raise OSError(CANARY)

        monkeypatch.setattr(subprocess, "run", broken)
        with caplog.at_level(logging.DEBUG):
            code = tool.main(cli_args(vault.root))
        assert code == 2
        assert CANARY not in caplog.text
        assert CANARY not in capsys.readouterr().err

    def test_a_report_path_with_a_missing_parent_exits_two_before_any_write(
        self, vault: VaultBuilder, tmp_path: Path, capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        small_vault(vault)
        forbid_git_state(monkeypatch)
        before = snapshot(vault.root)
        with caplog.at_level(logging.INFO):
            code = tool.main(cli_args(vault.root, True, tmp_path / "missing" / "report.json"))
        assert code == 2
        assert capsys.readouterr().out == ""
        assert snapshot(vault.root) == before
        assert [record.getMessage() for record in fatal_records(caplog)] == [
            FATAL_PRECONDITION + ": REPORT_PATH_INVALID",
        ]

    def test_a_report_path_that_is_a_folder_exits_two(
        self, vault: VaultBuilder, tmp_path: Path, capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        small_vault(vault)
        forbid_git_state(monkeypatch)
        assert tool.main(cli_args(vault.root, True, tmp_path)) == 2
        assert capsys.readouterr().out == ""

    def test_an_unknown_flag_exits_two(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as info:
            tool.main(["--no-such-flag"])
        assert info.value.code == 2
        assert capsys.readouterr().out == ""

    def test_a_manifest_failure_exits_two_and_writes_nothing(
        self, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def unreadable() -> Path:
            raise tool.PreconditionError("PATHS_MANIFEST_UNREADABLE")

        monkeypatch.setattr(tool, "default_vault_root", unreadable)
        forbid_git_state(monkeypatch)
        with caplog.at_level(logging.INFO):
            assert tool.main([]) == 2
        assert capsys.readouterr().out == ""
        assert [record.getMessage() for record in fatal_records(caplog)] == [
            FATAL_PRECONDITION + ": PATHS_MANIFEST_UNREADABLE",
        ]

    def test_the_manifest_default_is_used_only_without_a_vault_root_flag(
        self, vault: VaultBuilder, tmp_path: Path, capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        small_vault(vault)
        asked: List[str] = []

        def manifest_default() -> Path:
            asked.append("asked")
            return vault.root

        monkeypatch.setattr(tool, "default_vault_root", manifest_default)
        assert tool.main([]) == 0
        assert json.loads(capsys.readouterr().out)["counts"]["written"] == 2
        assert asked == ["asked"]
        assert tool.main(cli_args(vault.root)) == 0
        capsys.readouterr()
        assert asked == ["asked"]

    def test_a_read_only_file_in_a_writable_folder_exits_three_and_stays_intact(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores file permissions")
        commit_files(vault, {"00-landing/a.md": DECISION_DOC, "00-landing/b.md": DECISION_DOC})
        target = vault.root / "00-landing/a.md"
        target.chmod(READ_ONLY_FILE_MODE)
        try:
            code, report = run_cli(capsys, vault.root, apply=True)
        finally:
            target.chmod(UNLOCKED_FILE_MODE)
        assert code == 3
        assert target.read_bytes() == DECISION_DOC
        assert report["skipped"] == [{"path": "00-landing/a.md", "reason": "WRITE_FAILED"}]
        assert report["skipped_by_reason"] == {"WRITE_FAILED": 1}
        assert (vault.root / "00-landing/b.md").read_bytes() == DECISION_NEW
        assert sorted(os.listdir(str(vault.root / "00-landing"))) == ["a.md", "b.md"]

    def test_a_read_only_folder_exits_three_and_stays_intact(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores folder permissions")
        commit_files(vault, {READ_ONLY_FOLDER_FILE: DECISION_DOC, OPEN_FOLDER_FILE: DECISION_DOC})
        folder = vault.root / "locked"
        folder.chmod(READ_ONLY_FOLDER_MODE)
        try:
            code, report = run_cli(capsys, vault.root, apply=True)
        finally:
            folder.chmod(OPEN_FOLDER_MODE)
        assert code == 3
        assert (vault.root / READ_ONLY_FOLDER_FILE).read_bytes() == DECISION_DOC
        assert report["skipped"] == [{"path": READ_ONLY_FOLDER_FILE, "reason": "WRITE_FAILED"}]
        assert (vault.root / OPEN_FOLDER_FILE).read_bytes() == DECISION_NEW
        assert os.listdir(str(folder)) == ["x.md"]

    def test_a_preview_of_a_read_only_target_still_exits_zero(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("root ignores file permissions")
        commit_files(vault, {"00-landing/a.md": DECISION_DOC})
        target = vault.root / "00-landing/a.md"
        target.chmod(READ_ONLY_FILE_MODE)
        try:
            code, report = run_cli(capsys, vault.root, apply=False)
        finally:
            target.chmod(UNLOCKED_FILE_MODE)
        assert code == 0
        assert report["counts"]["written"] == 1

    def test_any_write_failed_in_the_report_exits_three_and_other_files_are_written(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        small_vault(vault)
        real = tool.apply_edit

        def fail_a(path: Path, original: bytes, new_raw: bytes) -> Optional[str]:
            return "WRITE_FAILED" if path.name == "a.md" else real(path, original, new_raw)

        monkeypatch.setattr(tool, "apply_edit", fail_a)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 3
        assert report["skipped_by_reason"] == {"WRITE_FAILED": 1}
        assert (vault.root / "b.md").read_bytes() == DECISION_NEW

    @pytest.mark.parametrize("reason", ["CHANGED_DURING_RUN", "UNREADABLE"])
    def test_other_apply_skip_codes_do_not_change_the_exit_code(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch,
        reason: str,
    ) -> None:
        small_vault(vault)
        monkeypatch.setattr(tool, "apply_edit", lambda path, original, new_raw: reason)
        code, report = run_cli(capsys, vault.root, apply=True)
        assert code == 0
        assert report["skipped_by_reason"] == {reason: 2}

    def test_a_failed_report_file_exits_two_but_the_report_is_on_stdout(
        self, vault: VaultBuilder, tmp_path: Path, capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        small_vault(vault)

        def refuse(self: Path, *args: Any, **kwargs: Any) -> int:
            raise OSError(CANARY)

        monkeypatch.setattr(Path, "write_text", refuse)
        with caplog.at_level(logging.INFO):
            code, report = run_cli(capsys, vault.root, apply=False, report_path=tmp_path / "r.json")
        assert code == 2
        assert report["counts"]["written"] == 2
        assert CANARY not in caplog.text
        assert any("REPORT_WRITE_FAILED" in record.getMessage() for record in caplog.records)

    def test_a_write_failure_wins_over_a_failed_report_file(
        self, vault: VaultBuilder, tmp_path: Path, capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        small_vault(vault)
        monkeypatch.setattr(tool, "apply_edit", lambda path, original, new_raw: "WRITE_FAILED")
        monkeypatch.setattr(Path, "write_text", lambda self, *a, **k: (_ for _ in ()).throw(OSError()))
        code, _ = run_cli(capsys, vault.root, apply=True, report_path=tmp_path / "r.json")
        assert code == 3

    def test_an_interrupt_propagates_without_a_report_and_leaves_whole_files(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture, tmp_path: Path,
    ) -> None:
        small_vault(vault)
        real = tool.plan_file
        seen: List[str] = []

        def interrupted(root: Path, rel: str, git: Any) -> Any:
            seen.append(rel)
            if len(seen) == 2:
                raise KeyboardInterrupt
            return real(root, rel, git)

        monkeypatch.setattr(tool, "plan_file", interrupted)
        report_file = tmp_path / "report.json"
        with caplog.at_level(logging.WARNING):
            with pytest.raises(KeyboardInterrupt):
                tool.main(cli_args(vault.root, True, report_file))
        assert capsys.readouterr().out == ""
        assert not report_file.exists()
        assert (vault.root / "a.md").read_bytes() == DECISION_NEW
        assert (vault.root / "b.md").read_bytes() == DECISION_DOC
        assert any("interrupted after 1 files" in record.getMessage() for record in caplog.records)


class TestReportOutput:
    """What main prints and saves."""

    def test_stdout_holds_the_report_alone_with_sorted_keys(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        small_vault(vault)
        code, out, _ = run_cli_text(capsys, vault.root)
        assert code == 0
        decoded = json.loads(out)
        assert out == json.dumps(decoded, sort_keys=True, indent=2) + "\n"
        assert set(decoded) == REPORT_KEYS

    def test_the_report_file_equals_stdout_and_replaces_older_content(
        self, vault: VaultBuilder, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        small_vault(vault)
        report_file = tmp_path / "report.json"
        report_file.write_text("old report " * 1000, encoding="utf-8")
        _, out, _ = run_cli_text(capsys, vault.root, False, report_file)
        assert report_file.read_text(encoding="utf-8") == out

    def test_no_report_path_means_no_file_anywhere_in_the_vault(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        small_vault(vault)
        before = snapshot(vault.root)
        run_cli(capsys, vault.root)
        assert snapshot(vault.root) == before
        assert vault.git("status", "--porcelain") == ""

    def test_one_summary_line_of_counts_is_logged(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        small_vault(vault)
        with caplog.at_level(logging.INFO):
            run_cli(capsys, vault.root)
        summaries = [record.getMessage() for record in caplog.records
                     if record.levelno == logging.INFO and record.name == tool.__name__]
        assert summaries == [
            "preview: scanned=3 not_target=1 classified=2 already_complete=0 written=2 "
            "skipped=0 needing_fields=2"
        ]

    def test_the_summary_line_names_no_path_or_value(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_mixed_vault(vault)
        with caplog.at_level(logging.INFO):
            run_cli(capsys, vault.root)
        line = [record.getMessage() for record in caplog.records
                if record.levelno == logging.INFO][-1]
        assert re.fullmatch(r"[a-z]+: ([a-z_]+=\d+ ?)+", line), line

    def test_json_nulls_and_booleans_are_json_not_text(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture
    ) -> None:
        small_vault(vault)
        _, out, _ = run_cli_text(capsys, vault.root)
        assert '"indexed": null' in out
        assert '"indexable": true' in out


def run_script(*args: str) -> "subprocess.CompletedProcess[str]":
    """Run the tool as a command with the current environment and no bytecode files.

    The git isolation fixture points HOME at an empty folder, which would hide a user
    level PyYAML install from the child process, so the real user base is passed on.
    """
    env = dict(os.environ)
    env["PYTHONUSERBASE"] = REAL_USER_BASE
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT_PATH), *args],
        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS, env=env,
    )


class TestCommandLine:
    """The tool run as a real command: exit codes, stdout, and stderr."""

    def test_help_exits_zero_and_names_the_apply_flag(self) -> None:
        done = run_script("--help")
        assert done.returncode == 0
        assert "--apply" in done.stdout and "--vault-root" in done.stdout

    def test_a_missing_vault_root_exits_two_with_one_stderr_line_and_no_stdout(
        self, tmp_path: Path
    ) -> None:
        done = run_script("--vault-root", str(tmp_path / "nope"))
        assert done.returncode == 2
        assert done.stdout == ""
        assert done.stderr.splitlines() == [
            "ERROR " + FATAL_PRECONDITION + ": VAULT_ROOT_NOT_A_FOLDER",
        ]

    def test_an_unknown_flag_exits_two(self) -> None:
        done = run_script("--no-such-flag")
        assert done.returncode == 2
        assert "usage" in done.stderr.lower()
        assert done.stdout == ""

    def test_preview_prints_the_report_and_one_summary_line_and_writes_nothing(
        self, vault: VaultBuilder
    ) -> None:
        small_vault(vault)
        before = snapshot(vault.root)
        done = run_script("--vault-root", str(vault.root))
        assert done.returncode == 0
        assert json.loads(done.stdout)["mode"] == "preview"
        assert done.stderr.splitlines() == [
            "INFO preview: scanned=3 not_target=1 classified=2 already_complete=0 written=2 "
            "skipped=0 needing_fields=2"
        ]
        assert snapshot(vault.root) == before

    def test_apply_writes_the_files_and_the_report_file(
        self, vault: VaultBuilder, tmp_path: Path
    ) -> None:
        small_vault(vault)
        report_file = tmp_path / "report.json"
        done = run_script("--vault-root", str(vault.root), "--apply", "--report-path", str(report_file))
        assert done.returncode == 0
        assert (vault.root / "a.md").read_bytes() == DECISION_NEW
        assert report_file.read_text(encoding="utf-8") == done.stdout
        assert json.loads(done.stdout)["mode"] == "apply"

    def test_a_vault_that_is_not_a_repository_exits_two(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        touch_files(plain, ["a.md"])
        done = run_script("--vault-root", str(plain), "--apply")
        assert done.returncode == 2
        assert (plain / "a.md").read_bytes() == DECISION_DOC

    def test_an_interrupt_ends_the_command_with_the_interrupt_status_and_no_report(
        self, vault: VaultBuilder
    ) -> None:
        small_vault(vault)
        program = (
            "import sys; sys.path.insert(0, {folder!r}); import backfill_vault_frontmatter as t; "
            "t.plan_file = lambda root, rel, git: (_ for _ in ()).throw(KeyboardInterrupt()); "
            "sys.exit(t.main(sys.argv[1:]))"
        ).format(folder=str(SCRIPT_PATH.parent))
        env = dict(os.environ)
        env["PYTHONUSERBASE"] = REAL_USER_BASE
        done = subprocess.run(
            [sys.executable, "-B", "-c", program, "--vault-root", str(vault.root), "--apply"],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS, env=env,
        )
        assert done.returncode in (INTERRUPT_EXIT_CODE, -signal.SIGINT)
        assert done.stdout == ""
        assert "interrupted after 0 files" in done.stderr
        assert (vault.root / "a.md").read_bytes() == DECISION_DOC

    def test_no_canary_reaches_stdout_or_stderr(self, vault: VaultBuilder) -> None:
        build_mixed_vault(vault)
        for flags in ((), ("--apply",)):
            done = run_script("--vault-root", str(vault.root), *flags)
            assert done.returncode == 0
            assert CANARY not in done.stdout and CANARY not in done.stderr


F01_FIRST_PATH = "00-landing/a-first.md"
F01_BAD_PATH = "00-landing/b-bad.md"
F01_LAST_PATH = "00-landing/c-last.md"
F01_PARSE_FRONTS: Dict[str, bytes] = {
    "bool_with_a_word": b"doc_type: decision\nflag: !!bool " + CANARY_BYTES + b"\n",
    "timestamp_with_a_word": b"doc_type: decision\nwhen: !!timestamp " + CANARY_BYTES + b"\n",
    "bare_int": b"doc_type: decision\ntitle: " + CANARY_BYTES + b"\nn: !!int\n",
    "bare_float": b"doc_type: decision\ntitle: " + CANARY_BYTES + b"\nn: !!float\n",
}
F01_RECURSIVE_FRONT = b"doc_type: decision\ntitle: " + CANARY_BYTES + b"\nx: &a [*a]\n"
F01_CASES: Dict[str, Tuple[bytes, str]] = {
    **{name: (front, "PARSE_ERROR") for name, front in F01_PARSE_FRONTS.items()},
    "recursive_anchor": (F01_RECURSIVE_FRONT, "VERIFY_FAILED"),
}
F01_MIDDLE_CASES = ("bool_with_a_word", "recursive_anchor")
F01_WRITTEN_STATUS = " M {}\n M {}\n".format(F01_FIRST_PATH, F01_LAST_PATH)


def f01_leaks(texts: List[str], caplog: pytest.LogCaptureFixture) -> bool:
    """True when the canary is in any text or any log record carries a traceback."""
    return any(CANARY in text for text in texts) or any(
        record.exc_info is not None for record in caplog.records
    )


class TestF01YamlCrashContainment:
    """F-01: any YAML crash becomes one skipped entry, leaks no value, and never stops the run."""

    @pytest.mark.parametrize("name", sorted(F01_CASES))
    def test_a_yaml_crash_is_one_skipped_entry_and_leaks_nothing(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture,
        caplog: pytest.LogCaptureFixture, tmp_path: Path, name: str,
    ) -> None:
        front, reason = F01_CASES[name]
        original = canary_doc(front)
        commit_files(vault, {F01_BAD_PATH: original})
        report_file = tmp_path / "report.json"
        texts: List[str] = []
        with caplog.at_level(logging.DEBUG):
            for apply in (False, True):
                code, out, err = run_cli_text(capsys, vault.root, apply, report_file)
                assert code == 0
                assert json.loads(out)["skipped"] == [{"path": F01_BAD_PATH, "reason": reason}]
                assert (vault.root / F01_BAD_PATH).read_bytes() == original
                texts.extend([out, err, report_file.read_text(encoding="utf-8")])
            texts.append(caplog.text)
        assert not f01_leaks(texts, caplog)
        has_error = any(record.levelno == logging.ERROR for record in caplog.records)
        assert has_error == (reason == "VERIFY_FAILED")

    @pytest.mark.parametrize("name", F01_MIDDLE_CASES)
    def test_a_bad_file_in_the_middle_does_not_stop_the_run_or_a_rerun(
        self, vault: VaultBuilder, capsys: pytest.CaptureFixture,
        caplog: pytest.LogCaptureFixture, name: str,
    ) -> None:
        front, reason = F01_CASES[name]
        bad = canary_doc(front)
        commit_files(vault, {
            F01_FIRST_PATH: DECISION_DOC, F01_BAD_PATH: bad, F01_LAST_PATH: DECISION_DOC,
        })
        texts: List[str] = []
        with caplog.at_level(logging.DEBUG):
            code, out, err = run_cli_text(capsys, vault.root, True)
            texts.extend([out, err])
            assert code == 0
            report = json.loads(out)
            assert [entry["path"] for entry in report["writes"]] == [F01_FIRST_PATH, F01_LAST_PATH]
            assert report["skipped"] == [{"path": F01_BAD_PATH, "reason": reason}]
            assert (vault.root / F01_FIRST_PATH).read_bytes() == DECISION_NEW
            assert (vault.root / F01_LAST_PATH).read_bytes() == DECISION_NEW
            assert (vault.root / F01_BAD_PATH).read_bytes() == bad
            assert vault.git("status", "--porcelain") == F01_WRITTEN_STATUS
            code, out, err = run_cli_text(capsys, vault.root, True)
            texts.extend([out, err, caplog.text])
        assert code == 0
        rerun = json.loads(out)
        assert rerun["writes"] == []
        assert rerun["skipped"] == [{"path": F01_BAD_PATH, "reason": reason}]
        assert (vault.root / F01_BAD_PATH).read_bytes() == bad
        assert vault.git("status", "--porcelain") == F01_WRITTEN_STATUS
        assert not f01_leaks(texts, caplog)

    @pytest.mark.parametrize("name", sorted(F01_PARSE_FRONTS))
    def test_parse_block_returns_none_instead_of_raising(
        self, caplog: pytest.LogCaptureFixture, name: str
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            assert tool.parse_block(F01_PARSE_FRONTS[name]) is None
        assert caplog.records
        assert not f01_leaks([caplog.text], caplog)

    def test_verify_edit_returns_false_when_the_comparison_raises(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        edit = build_edit(ANY_NOTE_PATH, make_file(F01_RECURSIVE_FRONT))
        assert edit is not None
        with caplog.at_level(logging.DEBUG):
            assert verify(edit) is False
        assert "RecursionError" in caplog.text
        assert not f01_leaks([caplog.text], caplog)

    def test_an_unexpected_planner_error_is_skipped_with_a_closed_code(
        self, vault: VaultBuilder, caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        commit_files(vault, {F01_FIRST_PATH: DECISION_DOC, F01_LAST_PATH: DECISION_DOC})

        def explode(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError(CANARY)

        monkeypatch.setattr(tool, "classify", explode)
        with caplog.at_level(logging.DEBUG):
            report = tool.run(vault.root, apply=True)
        assert report["skipped"] == [
            {"path": F01_FIRST_PATH, "reason": "VERIFY_FAILED"},
            {"path": F01_LAST_PATH, "reason": "VERIFY_FAILED"},
        ]
        assert report["writes"] == []
        assert (vault.root / F01_FIRST_PATH).read_bytes() == DECISION_DOC
        assert (vault.root / F01_LAST_PATH).read_bytes() == DECISION_DOC
        assert any(record.levelno == logging.ERROR for record in caplog.records)
        assert "RuntimeError" in caplog.text
        assert not f01_leaks([caplog.text], caplog)

    def test_an_interrupt_inside_planning_still_propagates(
        self, vault: VaultBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commit_files(vault, {F01_FIRST_PATH: DECISION_DOC})

        def interrupt(*args: Any, **kwargs: Any) -> Any:
            raise KeyboardInterrupt()

        monkeypatch.setattr(tool, "classify", interrupt)
        with pytest.raises(KeyboardInterrupt):
            tool.run(vault.root, apply=True)
        assert (vault.root / F01_FIRST_PATH).read_bytes() == DECISION_DOC
