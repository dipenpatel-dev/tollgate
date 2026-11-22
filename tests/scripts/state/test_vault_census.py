# Module:      test_vault_census.py
# Description: Tests for vault_census.py, the Scan C census of the earlier change. Every test runs over
#              fixture vaults built in pytest temp folders, with git init inside the
#              fixture where git is needed, so no test reaches the real vault. The 13
#              kind rows of the earlier spec policy table are typed here as literals. This
#              file never reads the census table, and an AST test proves it. Further
#              tests prove the census never imports the backfill tool, imports only the
#              allowlist, never writes (hash and mtime snapshot plus an AST scan), keeps
#              a canary out of stdout and logs, and follows the coding standards.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Test classes: TestKindRowTriples, TestTerminalOverride, TestFrontmatterFacts,
#              TestScanCounts, TestInScope, TestUnreadable, TestCheckWrites, TestMain,
#              TestCommandLine, TestCanary, TestReadOnly, TestIndependence, TestLocalOnly,
#              TestStandards
# Version:     1.1
# ChangeLog:
#   Initial implementation
#   Spec Q2 change: session-notes.md is K10, not K9

import ast
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import minipytest as pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "state"))
import vault_census as census  # noqa: E402

CENSUS_PATH = Path(census.__file__).resolve()
THIS_PATH = Path(__file__).resolve()

Triple = Tuple[str, str, bool]

CANARY = "CANARY_7Q2X_DO_NOT_LEAK"
BODY = "# Heading\nbody text\n"
SCALAR_KEYS = (
    "files", "with_all_four", "with_some", "with_none", "no_frontmatter", "unparseable",
    "symlinks", "unreadable", "terminal_indexable_true", "catalog_type_unknown_tickets",
    "in_scope_missing_fields",
)
MAP_KEYS = ("catalog_type", "doc_role", "triple")
FOUR_FIELDS = ("catalog_type", "doc_role", "indexable", "indexed")
TERMINAL_VALUES = ("cancelled", "superseded", "dropped", "archived", "absorbed")
NOT_TERMINAL_VALUES = ("active | archived", "parked", "closed", "shipped", "", "   ")
FIXTURE_FILE_LIMIT_ERROR = "fixture vault build failed"

# Source: the spec, Policy Table, typed here as literals and kept apart from the
# census. Columns: row id, a vault relative path that row must claim, and the triple.
T = "02-tickets/T-9/"
ROW_CASES: List[Tuple[str, str, Triple]] = [
    ("K1", T + "archive/T-9-misc.md", ("ticket", "reference", False)),
    ("K1", T + "history/T-9-spec.md", ("ticket", "spec", False)),
    ("K1", T + "archive/T-9-state.md", ("ticket", "state", False)),
    ("K1", T + "archive/T-9-cursor-1.md", ("ticket", "review", False)),
    ("K1", T + "archive/T-9-design.md", ("ticket", "design", False)),
    ("K1", T + "archive/sub/T-9-session-1.md", ("ticket", "session_log", False)),
    ("K1", T + "Archive/T-9-misc.md", ("ticket", "reference", False)),
    ("K2", T + "T-9-state.md", ("ticket", "state", True)),
    ("K2", T + "T-9-STATE.md", ("ticket", "state", True)),
    ("K3", T + "T-9-cursor-r1.md", ("ticket", "review", False)),
    ("K3", T + "T-9-qa-cursor-r1.md", ("ticket", "review", False)),
    ("K3", T + "T-9-arch-review-1.md", ("ticket", "review", False)),
    ("K3", T + "cursor-notes.md", ("ticket", "review", False)),
    ("K4", T + "Block_B-01-DIFF.md", ("ticket", "reference", False)),
    ("K4", T + "T-9-prompt-b1.md", ("ticket", "reference", False)),
    ("K4", T + "starter-prompt.md", ("ticket", "reference", False)),
    ("K4", T + "T-9-starter-prompt-b2.md", ("ticket", "reference", False)),
    ("K5", T + "T-9-spec.md", ("ticket", "spec", True)),
    ("K5", T + "T-9-pre-spec.md", ("ticket", "spec", True)),
    ("K5", T + "PRE-SPEC.md", ("ticket", "spec", True)),
    ("K5", "02-tickets/archive/archive-spec.md", ("ticket", "spec", True)),
    ("K9", "02-tickets/history/history-session-1.md", ("ticket", "session_log", True)),
    ("K6", T + "T-9-design.md", ("ticket", "design", True)),
    ("K6", T + "T-9-arch.md", ("ticket", "design", True)),
    ("K7", T + "T-9-qa-findings.md", ("ticket", "qa", True)),
    ("K7", T + "T-9-qa-findings-r2.md", ("ticket", "qa", True)),
    ("K8", T + "T-9-edge-case-validation.md", ("ticket", "qa", True)),
    ("K9", T + "T-9-session-2026-10-05.md", ("ticket", "session_log", True)),
    ("K9", T + "T-9-session.md", ("ticket", "session_log", True)),
    ("K9", T + "T-9-session-notes-2026-10-05.md", ("ticket", "session_log", True)),
    ("K10", "02-tickets/T-1/T-1-session-notes.md", ("ticket", "reference", True)),
    ("K10", T + "T-9-SESSION-NOTES.md", ("ticket", "reference", True)),
    ("K1", T + "archive/T-9-session-notes.md", ("ticket", "reference", False)),
    ("K10", "02-tickets/T-9/T-9.md", ("ticket", "reference", True)),
    ("K11", T + "T-9-context.md", ("ticket", "reference", True)),
    ("K11", T + "diagrams.md", ("ticket", "reference", True)),
    ("K12", T + "T-9-shipped.md", ("ticket", "reference", True)),
    ("K13", T + "HANDOFF.md", ("ticket", "reference", True)),
    ("K13", T + "T-9-support-handoff.md", ("ticket", "reference", True)),
    ("K13", T + "T-9-notes.md", ("ticket", "reference", True)),
    ("K13", T + "T-9-plan.md", ("ticket", "reference", True)),
    ("K13", T + "T-9-jira-draft.md", ("ticket", "reference", True)),
    ("K13", T + "T-9-coord.md", ("ticket", "reference", True)),
]
NO_ROW_PATHS: List[str] = [
    T + "T-9-random.md",
    "02-tickets/T-1/T-1-qa-prompts.md",
    T + "sub/T-9-state.md",
    T + "T-9-statement.md",
    "02-tickets/T-9.md",
    "02-tickets/loose.md",
    "00-landing/T-9-state.md",
    "03-knowledge-base/x/T-9-spec.md",
    "T-9-spec.md",
    T + "other-state.md",
    T + "T-8-state.md",
    T + "T-9-qa-finding.md",
    "03-knowledge-base/x/spec.md",
    "00-landing/2026/HANDOFF.md",
    "02-tickets/spec.md",
    "02-tickets/design.md",
]
ROW_IDS = ["K{}".format(number) for number in range(1, 14)]
ONE_PER_ROW: List[Tuple[str, str, Triple]] = [
    next(case for case in ROW_CASES if case[0] == row_id) for row_id in ROW_IDS
]

STATE_FIELDS = ["catalog_type: ticket", "doc_role: state", "indexable: true", "indexed: null"]
REF_FIELDS = ["catalog_type: ticket", "doc_role: reference", "indexable: true", "indexed: null"]
UNKNOWN_FIELDS = [
    "catalog_type: unknown", "doc_role: unknown", "indexable: false", "indexed: null",
]
BAD_YAML = ["title: [unclosed"]


def doc(lines: Sequence[str], body: str = BODY, eol: str = "\n") -> bytes:
    """Return a markdown file with a frontmatter block of the given lines."""
    inner = eol.join(lines) + eol if lines else ""
    return ("---" + eol + inner + "---" + eol + body).encode("utf-8")


FIXTURE_FILES: Dict[str, bytes] = {
    "README.md": b"# Readme\n",
    "00-landing/full.md": doc(
        ["catalog_type: reference", "doc_role: reference", "indexable: true",
         "indexed: null", "status: archived"]
    ),
    "00-landing/none.md": b"# Plain\n",
    "00-landing/bare.md": doc(["title: bare"]),
    "00-landing/some.md": doc(["catalog_type: session", "indexable: false"]),
    "00-landing/bad.md": doc(BAD_YAML),
    "00-landing/data.txt": b"not markdown\n",
    "01-system-map/ref.md": doc(
        ["catalog_type: reference", "doc_role: index", "indexable: false",
         "indexed: null", "status: active"]
    ),
    "02-tickets/loose.md": b"# Loose\n",
    "02-tickets/T-100/T-100-state.md": doc(STATE_FIELDS),
    "02-tickets/T-100/T-100-spec.md": doc(["catalog_type: ticket"]),
    "02-tickets/T-100/T-100-design.md": b"# Design\n",
    "02-tickets/T-100/T-100-cursor-1.md": doc(["title: cursor"]),
    "02-tickets/T-100/T-100-random.md": b"# No row\n",
    "02-tickets/T-100/archive/T-100-old.md": b"# Old\n",
    "02-tickets/T-100/T-100-session-1.md": doc(BAD_YAML),
    "02-tickets/T-100/T-100-qa-findings.md": doc(UNKNOWN_FIELDS),
    "02-tickets/T-100/T-100-plan.md": b"# Plan\n",
    "02-tickets/T-200/T-200-state.md": doc(["status: cancelled"] + STATE_FIELDS),
    "02-tickets/T-200/T-200.md": doc(
        ["catalog_type: ticket", "doc_role: reference", "indexable: true"]
    ),
    "02-tickets/T-200/T-200-handoff.md": doc(REF_FIELDS),
    "02-tickets/T-200/T-200-target.md": b"# Link target\n",
    "03-knowledge-base/decisions/d.md": doc(
        ["catalog_type: knowledge", "doc_role: decision", "indexable: true", "indexed: null"]
    ),
    "03-knowledge-base/.hidden/h.md": b"# Hidden below the root\n",
    ".obsidian/o.md": doc(STATE_FIELDS),
    "memory/m.md": doc(STATE_FIELDS),
}
FIXTURE_LINKS: Dict[str, str] = {"02-tickets/T-200/T-200-notes.md": "T-200-target.md"}
FIXTURE_DIRTY: Dict[str, bytes] = {"02-tickets/T-100/T-100-plan.md": b"# Plan\nedited\n"}
FIXTURE_UNTRACKED: Dict[str, bytes] = {"02-tickets/T-100/T-100-shipped.md": b"# Shipped\n"}


def zero_block(**values: Any) -> Dict[str, Any]:
    """Return the expected count block: zero scalars, empty maps, then the given values."""
    block: Dict[str, Any] = {key: 0 for key in SCALAR_KEYS}
    block.update({key: {} for key in MAP_KEYS})
    block.update(values)
    return block


EXPECTED_TOTAL = zero_block(
    files=25, with_all_four=7, with_some=3, with_none=2, no_frontmatter=10, unparseable=2,
    symlinks=1, terminal_indexable_true=2, catalog_type_unknown_tickets=1,
    in_scope_missing_fields=5,
    catalog_type={"ticket": 5, "unknown": 1, "reference": 2, "session": 1, "knowledge": 1},
    doc_role={"state": 2, "unknown": 1, "reference": 3, "index": 1, "decision": 1},
    triple={
        "ticket|state|true": 2, "unknown|unknown|false": 1, "ticket|reference|true": 2,
        "reference|reference|true": 1, "reference|index|false": 1,
        "knowledge|decision|true": 1,
    },
)
EXPECTED_FOLDERS: Dict[str, Dict[str, Any]] = {
    "<root>": zero_block(files=1, no_frontmatter=1),
    "00-landing": zero_block(
        files=5, with_all_four=1, with_some=1, with_none=1, no_frontmatter=1,
        unparseable=1, terminal_indexable_true=1,
        catalog_type={"reference": 1, "session": 1}, doc_role={"reference": 1},
        triple={"reference|reference|true": 1},
    ),
    "01-system-map": zero_block(
        files=1, with_all_four=1, catalog_type={"reference": 1}, doc_role={"index": 1},
        triple={"reference|index|false": 1},
    ),
    "02-tickets": zero_block(
        files=16, with_all_four=4, with_some=2, with_none=1, no_frontmatter=7,
        unparseable=1, symlinks=1, terminal_indexable_true=1,
        catalog_type_unknown_tickets=1, in_scope_missing_fields=5,
        catalog_type={"ticket": 5, "unknown": 1}, doc_role={"state": 2, "unknown": 1, "reference": 2},
        triple={
            "ticket|state|true": 2, "unknown|unknown|false": 1, "ticket|reference|true": 2,
        },
    ),
    "03-knowledge-base": zero_block(
        files=2, with_all_four=1, no_frontmatter=1, catalog_type={"knowledge": 1},
        doc_role={"decision": 1}, triple={"knowledge|decision|true": 1},
    ),
}

GIT_FIXTURE_ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
GIT_IDENTITY = ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid")
GIT_NO_HOOKS = ("-c", "core.hooksPath=" + os.devnull, "-c", "commit.gpgsign=false")


def git_run(root: Path, *args: str) -> None:
    """Run one git command inside a fixture vault. A failure stops the test."""
    command = ["git", *GIT_IDENTITY, *GIT_NO_HOOKS, "-C", str(root), *args]
    result = subprocess.run(command, capture_output=True, env=GIT_FIXTURE_ENV, check=False)
    assert result.returncode == 0, FIXTURE_FILE_LIMIT_ERROR


def write_files(root: Path, files: Dict[str, bytes]) -> None:
    """Write fixture files under root, creating folders."""
    for rel, data in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def make_vault(
    root: Path,
    files: Dict[str, bytes],
    links: Optional[Dict[str, str]] = None,
    dirty: Optional[Dict[str, bytes]] = None,
    untracked: Optional[Dict[str, bytes]] = None,
) -> Path:
    """Build a fixture vault, commit it, then dirty some files and add untracked ones."""
    root.mkdir(parents=True, exist_ok=True)
    write_files(root, files)
    for rel, target in (links or {}).items():
        os.symlink(target, root / rel)
    git_run(root, "init", "-q")
    git_run(root, "add", "-A")
    git_run(root, "commit", "-q", "-m", "fixture")
    write_files(root, dirty or {})
    write_files(root, untracked or {})
    return root


@pytest.fixture(scope="module")
def shared_vault(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The known counts fixture vault. Tests using it must not change it."""
    return make_vault(
        tmp_path_factory.mktemp("census") / "vault",
        FIXTURE_FILES, FIXTURE_LINKS, FIXTURE_DIRTY, FIXTURE_UNTRACKED,
    )


def one_file_vault(tmp_path: Path, rel: str, data: bytes) -> Path:
    """Build a vault with one committed file."""
    return make_vault(tmp_path / "vault", {rel: data})


def run_main(argv: Sequence[str], capsys: pytest.CaptureFixture) -> Tuple[int, str, str]:
    """Call census.main and return its exit code, stdout, and stderr text."""
    code = census.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def entry(rel: str, change_class: str = "create", kind: str = "K5") -> Dict[str, Any]:
    """Build one run report writes entry in the shape the design's report contract names."""
    return {"path": rel, "class": change_class, "kind": kind, "added": {}, "changes": []}


def write_report(folder: Path, name: str, entries: Sequence[Any]) -> Path:
    """Write a run report with the given writes list and return its path."""
    path = folder / name
    path.write_text(json.dumps({"mode": "apply", "run": 1, "writes": list(entries)}), "utf-8")
    return path


def triple_lines(triple: Triple) -> List[str]:
    """Render a triple as the four frontmatter lines with indexed null."""
    catalog, role, indexable = triple
    flag = "true" if indexable else "false"
    return [
        "catalog_type: " + catalog, "doc_role: " + role, "indexable: " + flag, "indexed: null",
    ]


def row_files(cases: Sequence[Tuple[str, str, Triple]]) -> Dict[str, bytes]:
    """Return one fixture file per case, each carrying that case's literal triple."""
    return {rel: doc(triple_lines(want)) for _, rel, want in cases}


class TestKindRowTriples:
    @pytest.mark.parametrize("row_id,rel,want", ROW_CASES, ids=[c[0] + ":" + c[1] for c in ROW_CASES])
    def test_each_path_receives_its_rows_triple(self, row_id: str, rel: str, want: Triple) -> None:
        assert census.expected_triple(rel, None) == want
        assert census.expected_triple(rel, {}) == want

    def test_every_row_from_one_to_thirteen_is_covered_by_the_literals(self) -> None:
        assert sorted({case[0] for case in ROW_CASES}, key=lambda r: int(r[1:])) == ROW_IDS

    @pytest.mark.parametrize("rel", NO_ROW_PATHS)
    def test_a_path_with_no_row_gets_none(self, rel: str) -> None:
        assert census.expected_triple(rel, None) is None

    def test_matching_ignores_case_and_strips_only_the_leading_folder_prefix(self) -> None:
        assert census.expected_triple("02-tickets/T-1/t-1-SPEC.md", None) == ("ticket", "spec", True)
        assert census.expected_triple("02-tickets/T-1/T-1-T-1-spec.md", None) is None

    def test_the_first_matching_row_wins_on_overlap(self) -> None:
        assert census.expected_triple(T + "archive/T-9-spec.md", None) == ("ticket", "spec", False)
        assert census.expected_triple(T + "T-9-cursor-spec.md", None) == ("ticket", "review", False)

    def test_a_triple_is_a_tuple_of_two_strings_and_a_real_bool(self) -> None:
        for _, rel, _ in ROW_CASES:
            result = census.expected_triple(rel, None)
            assert result is not None
            assert [type(item) for item in result] == [str, str, bool]


class TestTerminalOverride:
    @pytest.mark.parametrize("status", TERMINAL_VALUES)
    def test_each_terminal_value_forces_indexable_false(self, status: str) -> None:
        for padded in (status, status.upper(), "  " + status.title() + " "):
            got = census.expected_triple(T + "T-9-spec.md", {"status": padded})
            assert got == ("ticket", "spec", False)

    @pytest.mark.parametrize("status", NOT_TERMINAL_VALUES)
    def test_a_value_outside_the_rule_leaves_the_row_alone(self, status: str) -> None:
        got = census.expected_triple(T + "T-9-spec.md", {"status": status})
        assert got == ("ticket", "spec", True)

    @pytest.mark.parametrize("status", [5, None, ["cancelled"], {"a": 1}, True])
    def test_a_non_string_status_is_not_terminal(self, status: Any) -> None:
        got = census.expected_triple(T + "T-9-spec.md", {"status": status})
        assert got == ("ticket", "spec", True)

    def test_a_missing_status_and_a_missing_mapping_are_not_terminal(self) -> None:
        assert census.expected_triple(T + "T-9-spec.md", {"title": "x"}) == ("ticket", "spec", True)
        assert census.expected_triple(T + "T-9-spec.md", None) == ("ticket", "spec", True)

    def test_the_override_never_creates_a_row(self) -> None:
        assert census.expected_triple(T + "T-9-random.md", {"status": "cancelled"}) is None


def facts_kind(raw: bytes) -> str:
    """Return the count kind the census gives raw file bytes."""
    return census.facts_from_bytes(raw).kind


class TestFrontmatterFacts:
    def test_a_block_with_all_four_fields_is_complete_even_when_indexed_is_null(self) -> None:
        assert facts_kind(doc(REF_FIELDS)) == "with_all_four"

    def test_some_and_none_are_split_by_how_many_of_the_four_are_present(self) -> None:
        assert facts_kind(doc(["indexed: null"])) == "with_some"
        assert facts_kind(doc(["catalog_type: ticket", "doc_role: spec", "indexable: true"])) == "with_some"
        assert facts_kind(doc(["title: x"])) == "with_none"
        assert facts_kind(doc([])) == "with_none"

    def test_crlf_files_and_a_closing_delimiter_at_the_end_of_the_file_parse(self) -> None:
        assert facts_kind(doc(REF_FIELDS, eol="\r\n")) == "with_all_four"
        assert facts_kind(b"---\ntitle: x\n---") == "with_none"
        assert facts_kind(b"---\r\ntitle: x\r\n---") == "with_none"

    @pytest.mark.parametrize(
        "raw",
        [b"", b"# Plain\n", b"\n---\ntitle: x\n---\n", b"\xef\xbb\xbf---\ntitle: x\n---\n",
         b"---\ntitle: x\n", b"--- \ntitle: x\n---\n", b"---\ntitle: x\n--- \n"],
        ids=["empty", "plain", "leading_blank", "bom", "unclosed", "padded_open", "padded_close"],
    )
    def test_a_file_without_a_line_one_block_counts_as_no_frontmatter(self, raw: bytes) -> None:
        assert census.facts_from_bytes(raw) == census.FileFacts("no_frontmatter")

    @pytest.mark.parametrize(
        "block",
        [b"title: [unclosed", b"a: b\n\tc: d", b"- a\n- b", b"just text", b"a: !!bool maybe",
         b"a: !!int x", b"a: !!timestamp zzz", b"title: \xff\xfe"],
        ids=["parser", "scanner", "list", "scalar", "keyerror", "valueerror", "attributeerror", "bytes"],
    )
    def test_unparseable_frontmatter_is_counted_and_never_raised(self, block: bytes) -> None:
        raw = b"---\n" + block + b"\n---\n" + BODY.encode("utf-8")
        assert census.facts_from_bytes(raw) == census.FileFacts("unparseable")

    def test_a_file_that_is_all_frontmatter_with_a_non_utf8_body_still_parses(self) -> None:
        raw = doc(REF_FIELDS, body="") + b"\xff\xfe body bytes\n"
        assert facts_kind(raw) == "with_all_four"

    def test_a_mapping_is_returned_with_its_values_and_a_null_value_stays_present(self) -> None:
        facts = census.facts_from_bytes(doc(["indexed: null", "title: x"]))
        assert facts.fm == {"indexed": None, "title": "x"}


class TestScanCounts:
    def test_the_total_matches_the_known_counts(self, shared_vault: Path) -> None:
        result = census.scan_vault(shared_vault)
        total = {key: result[key] for key in SCALAR_KEYS + MAP_KEYS}
        assert total == EXPECTED_TOTAL

    def test_each_top_level_folder_matches_its_known_counts(self, shared_vault: Path) -> None:
        result = census.scan_vault(shared_vault)
        assert sorted(result["by_folder"]) == sorted(EXPECTED_FOLDERS)
        for folder, want in EXPECTED_FOLDERS.items():
            assert result["by_folder"][folder] == want, folder

    def test_the_result_holds_exactly_the_documented_keys(self, shared_vault: Path) -> None:
        result = census.scan_vault(shared_vault)
        assert sorted(result) == sorted(SCALAR_KEYS + MAP_KEYS + ("by_folder", "exclusions"))
        assert result["exclusions"] == ["memory/"]

    def test_every_file_lands_in_exactly_one_class_so_the_parts_sum_to_the_files(
        self, shared_vault: Path
    ) -> None:
        result = census.scan_vault(shared_vault)
        parts = ("with_all_four", "with_some", "with_none", "no_frontmatter",
                 "unparseable", "symlinks", "unreadable")
        assert sum(result[key] for key in parts) == result["files"]
        for block in result["by_folder"].values():
            assert sum(block[key] for key in parts) == block["files"]

    def test_the_folders_sum_to_the_total_for_every_scalar(self, shared_vault: Path) -> None:
        result = census.scan_vault(shared_vault)
        for key in SCALAR_KEYS:
            assert sum(block[key] for block in result["by_folder"].values()) == result[key], key

    def test_a_file_without_a_key_adds_nothing_to_that_keys_counts(self, shared_vault: Path) -> None:
        result = census.scan_vault(shared_vault)
        assert sum(result["catalog_type"].values()) == 10
        assert sum(result["doc_role"].values()) == 8
        assert sum(result["triple"].values()) == 8
        for key in MAP_KEYS:
            assert "null" not in result[key] and "None" not in result[key]

    def test_hidden_folders_are_pruned_at_the_root_only_and_the_excluded_folders_always(
        self, shared_vault: Path
    ) -> None:
        result = census.scan_vault(shared_vault)
        assert result["by_folder"]["03-knowledge-base"]["files"] == 2
        assert ".obsidian" not in result["by_folder"]

    def test_a_folder_symlink_is_not_followed(self, tmp_path: Path) -> None:
        files = {"00-landing/a.md": b"# a\n", "01-system-map/b.md": b"# b\n"}
        root = make_vault(tmp_path / "v", files, {"00-landing/linkdir": "../01-system-map"})
        result = census.scan_vault(root)
        assert result["files"] == 2 and result["by_folder"]["00-landing"]["files"] == 1

    def test_a_non_markdown_file_is_ignored(self, shared_vault: Path) -> None:
        assert census.scan_vault(shared_vault)["by_folder"]["00-landing"]["files"] == 5

    def test_odd_classifying_values_become_closed_labels(self, tmp_path: Path) -> None:
        files = {
            "00-landing/a.md": doc(["catalog_type: two words", "doc_role: [x]", "indexable: 'true'"]),
            "00-landing/b.md": doc(["catalog_type: null", "doc_role: " + "x" * 65, "indexable: null"]),
        }
        result = census.scan_vault(make_vault(tmp_path / "v", files))
        assert result["catalog_type"] == {"<unsafe>": 1, "<non-string>": 1}
        assert result["doc_role"] == {"<non-string>": 1, "<unsafe>": 1}
        assert sorted(result["triple"]) == [
            "<non-string>|<unsafe>|<non-bool>", "<unsafe>|<non-string>|<non-bool>",
        ]


def terminal_vault(tmp_path: Path, status_line: str, indexable_line: str) -> Dict[str, Any]:
    """Scan a one file vault holding the given status and indexable lines."""
    lines = [status_line, "catalog_type: ticket", "doc_role: spec", indexable_line, "indexed: null"]
    root = one_file_vault(tmp_path, "00-landing/n.md", doc(lines))
    return census.scan_vault(root)


class TestTerminalCount:
    @pytest.mark.parametrize("status", TERMINAL_VALUES)
    def test_each_terminal_value_with_indexable_true_is_counted(
        self, tmp_path: Path, status: str
    ) -> None:
        assert terminal_vault(tmp_path, "status: " + status.title(), "indexable: true")[
            "terminal_indexable_true"
        ] == 1

    @pytest.mark.parametrize("status", ["'active | archived'", "parked", "closed", "shipped", "5"])
    def test_a_value_outside_the_rule_is_not_counted(self, tmp_path: Path, status: str) -> None:
        assert terminal_vault(tmp_path, "status: " + status, "indexable: true")[
            "terminal_indexable_true"
        ] == 0

    @pytest.mark.parametrize("flag", ["indexable: false", "indexable: 'true'", "indexable: 1"])
    def test_a_terminal_file_whose_indexable_is_not_the_boolean_true_is_not_counted(
        self, tmp_path: Path, flag: str
    ) -> None:
        assert terminal_vault(tmp_path, "status: cancelled", flag)["terminal_indexable_true"] == 0

    def test_a_file_that_misses_the_indexable_line_is_not_counted(self, tmp_path: Path) -> None:
        root = one_file_vault(tmp_path, "00-landing/n.md", doc(["status: dropped"]))
        assert census.scan_vault(root)["terminal_indexable_true"] == 0

    def test_catalog_type_unknown_counts_ticket_files_only(self, tmp_path: Path) -> None:
        files = {
            "02-tickets/T-1/T-1-spec.md": doc(UNKNOWN_FIELDS),
            "02-tickets/T-1/T-1-other.md": doc(["catalog_type: Unknown"]),
            "00-landing/x.md": doc(UNKNOWN_FIELDS),
        }
        result = census.scan_vault(make_vault(tmp_path / "v", files))
        assert result["catalog_type_unknown_tickets"] == 1
        assert result["by_folder"]["00-landing"]["catalog_type_unknown_tickets"] == 0


IN_SCOPE_CASES: List[Tuple[str, str, bytes, bool, bool, int]] = [
    ("missing_all", "02-tickets/T-1/T-1-spec.md", b"# Plain\n", False, False, 1),
    ("missing_one", "02-tickets/T-1/T-1-spec.md", doc(REF_FIELDS[:3]), False, False, 1),
    ("complete", "02-tickets/T-1/T-1-spec.md", doc(REF_FIELDS), False, False, 0),
    ("untracked", "02-tickets/T-1/T-1-spec.md", b"# Plain\n", True, False, 0),
    ("dirty", "02-tickets/T-1/T-1-spec.md", b"# Plain\n", False, True, 0),
    ("unparseable", "02-tickets/T-1/T-1-spec.md", doc(BAD_YAML), False, False, 0),
    ("no_row", "02-tickets/T-1/T-1-random.md", b"# Plain\n", False, False, 0),
    ("loose_root", "02-tickets/loose.md", b"# Plain\n", False, False, 0),
    ("outside_tickets", "00-landing/T-1-spec.md", b"# Plain\n", False, False, 0),
    ("archive", "02-tickets/T-1/archive/anything.md", b"# Plain\n", False, False, 1),
    ("history", "02-tickets/T-1/history/anything.md", b"# Plain\n", False, False, 1),
    ("deep_state", "02-tickets/T-1/sub/T-1-state.md", b"# Plain\n", False, False, 0),
]


class TestInScope:
    @pytest.mark.parametrize(
        "name,rel,data,untracked,dirty,want", IN_SCOPE_CASES, ids=[c[0] for c in IN_SCOPE_CASES]
    )
    def test_only_a_tracked_clean_parseable_file_with_a_row_counts_when_it_misses_a_field(
        self, tmp_path: Path, name: str, rel: str, data: bytes, untracked: bool, dirty: bool, want: int
    ) -> None:
        files = {} if untracked else {rel: data}
        root = make_vault(
            tmp_path / "v", {"README.md": b"# r\n", **files},
            dirty={rel: data + b"edit\n"} if dirty else None,
            untracked={rel: data} if untracked else None,
        )
        assert census.scan_vault(root)["in_scope_missing_fields"] == want

    def test_a_staged_but_uncommitted_change_is_not_clean(self, tmp_path: Path) -> None:
        rel = "02-tickets/T-1/T-1-spec.md"
        root = make_vault(tmp_path / "v", {rel: b"# Plain\n"})
        (root / rel).write_bytes(b"# Plain\nstaged\n")
        git_run(root, "add", rel)
        assert census.scan_vault(root)["in_scope_missing_fields"] == 0

    def test_a_terminal_status_does_not_take_a_file_out_of_scope(self, tmp_path: Path) -> None:
        root = one_file_vault(tmp_path, "02-tickets/T-1/T-1-spec.md", doc(["status: cancelled"]))
        assert census.scan_vault(root)["in_scope_missing_fields"] == 1


class TestUnreadable:
    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads every file")
    def test_an_unreadable_file_is_counted_and_never_raised(self, tmp_path: Path) -> None:
        rel = "02-tickets/T-1/T-1-spec.md"
        root = make_vault(tmp_path / "v", {"README.md": b"# r\n"}, untracked={rel: doc(REF_FIELDS)})
        os.chmod(root / rel, 0)
        try:
            result = census.scan_vault(root)
        finally:
            os.chmod(root / rel, 0o600)
        assert result["unreadable"] == 1 and result["with_all_four"] == 0

    @pytest.mark.parametrize("kind", ["unreadable", "symlinks", "unparseable"])
    def test_a_file_with_no_readable_frontmatter_is_never_in_scope(self, kind: str) -> None:
        rel = "02-tickets/T-1/T-1-spec.md"
        git = census.GitSnapshot(tracked=frozenset({rel}), differing=frozenset())
        assert census.is_in_scope(rel, census.FileFacts(kind), git) is False
        assert census.is_in_scope(rel, census.FileFacts("no_frontmatter"), git) is True


def row_vault(tmp_path: Path) -> Path:
    """Build a plain folder (no git needed) holding one file per kind row, with its triple."""
    root = tmp_path / "rows"
    write_files(root, row_files(ONE_PER_ROW))
    return root


def row_entries(change_class: str = "create") -> List[Dict[str, Any]]:
    """One report entry per kind row, cycling add, create, and rewrite."""
    classes = ["add", "create", "rewrite"]
    return [
        entry(rel, classes[index % len(classes)] if change_class == "cycle" else change_class, row)
        for index, (row, rel, _) in enumerate(ONE_PER_ROW)
    ]


class TestCheckWrites:
    def test_one_file_per_kind_row_with_its_literal_triple_checks_clean(self, tmp_path: Path) -> None:
        report = write_report(tmp_path, "r.json", row_entries("cycle"))
        result = census.check_writes(row_vault(tmp_path), [report])
        assert result["checked"] == 13 and result["mismatches"] == 0
        assert result["mismatch_codes"] == {} and result["mismatch_paths"] == []

    @pytest.mark.parametrize("row_id,rel,want", ONE_PER_ROW, ids=ROW_IDS)
    def test_a_wrong_indexable_value_on_any_row_is_exactly_one_mismatch(
        self, tmp_path: Path, row_id: str, rel: str, want: Triple
    ) -> None:
        root = row_vault(tmp_path)
        flipped = (want[0], want[1], not want[2])
        (root / rel).write_bytes(doc(triple_lines(flipped)))
        result = census.check_writes(root, [write_report(tmp_path, "r.json", row_entries())])
        assert result["mismatches"] == 1
        assert result["mismatch_codes"] == {"TRIPLE_DIFFERS": 1}
        assert result["mismatch_paths"] == [rel]

    @pytest.mark.parametrize("field_index", [0, 1])
    def test_a_wrong_catalog_type_or_doc_role_is_a_mismatch(self, tmp_path: Path, field_index: int) -> None:
        root = row_vault(tmp_path)
        rel = ONE_PER_ROW[4][1]
        lines = triple_lines(ONE_PER_ROW[4][2])
        lines[field_index] = lines[field_index] + "_x"
        (root / rel).write_bytes(doc(lines))
        result = census.check_writes(root, [write_report(tmp_path, "r.json", row_entries())])
        assert result["mismatch_codes"] == {"TRIPLE_DIFFERS": 1}

    def test_a_string_true_or_an_integer_is_not_the_boolean(self, tmp_path: Path) -> None:
        root = row_vault(tmp_path)
        rel, lines = ONE_PER_ROW[4][1], triple_lines(ONE_PER_ROW[4][2])
        for bad in ("indexable: 'true'", "indexable: 1"):
            lines[2] = bad
            (root / rel).write_bytes(doc(lines))
            result = census.check_writes(root, [write_report(tmp_path, "r.json", row_entries())])
            assert result["mismatch_codes"] == {"TRIPLE_DIFFERS": 1}

    def test_a_terminal_status_file_must_carry_indexable_false(self, tmp_path: Path) -> None:
        rel = T + "T-9-spec.md"
        lines = ["status: Cancelled"] + triple_lines(("ticket", "spec", False))
        root = tmp_path / "v"
        write_files(root, {rel: doc(lines)})
        report = write_report(tmp_path, "r.json", [entry(rel, "add")])
        assert census.check_writes(root, [report])["mismatches"] == 0
        write_files(root, {rel: doc(["status: Cancelled"] + triple_lines(("ticket", "spec", True)))})
        assert census.check_writes(root, [report])["mismatch_codes"] == {"TRIPLE_DIFFERS": 1}

    def test_a_flip_entry_is_skipped_even_when_its_file_would_mismatch(self, tmp_path: Path) -> None:
        rel = T + "T-9-spec.md"
        root = tmp_path / "v"
        write_files(root, {rel: doc(triple_lines(("ticket", "spec", False)))})
        report = write_report(tmp_path, "r.json", [entry(rel, "flip")])
        result = census.check_writes(root, [report])
        assert (result["checked"], result["mismatches"], result["flips_skipped"]) == (0, 0, 1)

    def test_entries_from_several_reports_are_summed(self, tmp_path: Path) -> None:
        root = row_vault(tmp_path)
        first = write_report(tmp_path, "a.json", row_entries()[:6])
        second = write_report(tmp_path, "b.json", row_entries()[6:] + [entry(ONE_PER_ROW[0][1], "flip")])
        result = census.check_writes(root, [first, second])
        assert (result["reports"], result["checked"], result["flips_skipped"]) == (2, 13, 1)

    @pytest.mark.parametrize(
        "name,data,code",
        [
            ("absent", None, "FILE_UNREADABLE"),
            ("plain", b"# Plain\n", "NO_FRONTMATTER"),
            ("broken", doc(BAD_YAML), "FRONTMATTER_UNPARSEABLE"),
            ("fields_missing", doc(["catalog_type: ticket", "doc_role: spec", "indexable: true"]),
             "FIELD_MISSING"),
            ("indexed_set", doc(triple_lines(("ticket", "spec", True))[:3] + ["indexed: 2026-10-06"]),
             "INDEXED_NOT_NULL"),
        ],
    )
    def test_each_failure_of_a_written_file_has_its_closed_code(
        self, tmp_path: Path, name: str, data: Optional[bytes], code: str
    ) -> None:
        rel = T + "T-9-spec.md"
        root = tmp_path / "v"
        root.mkdir()
        if data is not None:
            write_files(root, {rel: data})
        result = census.check_writes(root, [write_report(tmp_path, "r.json", [entry(rel)])])
        assert result["mismatch_codes"] == {code: 1} and result["mismatch_paths"] == [rel]

    def test_mismatch_paths_are_sorted_whatever_the_report_order(self, tmp_path: Path) -> None:
        rels = [T + "T-9-spec.md", T + "T-9-design.md", T + "T-9-arch.md"]
        write_files(tmp_path / "v", {rel: b"# Plain\n" for rel in rels})
        report = write_report(tmp_path, "r.json", [entry(rel) for rel in rels])
        result = census.check_writes(tmp_path / "v", [report])
        assert result["mismatch_paths"] == sorted(rels) != rels

    def test_a_write_to_a_path_with_no_kind_row_is_a_mismatch(self, tmp_path: Path) -> None:
        rel = T + "T-9-random.md"
        write_files(tmp_path / "v", {rel: doc(triple_lines(("ticket", "reference", True)))})
        result = census.check_writes(tmp_path / "v", [write_report(tmp_path, "r.json", [entry(rel)])])
        assert result["mismatch_codes"] == {"NO_KIND_ROW": 1}

    def test_a_symlinked_target_is_not_followed(self, tmp_path: Path) -> None:
        rel = T + "T-9-spec.md"
        root = tmp_path / "v"
        write_files(root, {T + "real.md": doc(triple_lines(("ticket", "spec", True)))})
        os.symlink("real.md", root / rel)
        result = census.check_writes(root, [write_report(tmp_path, "r.json", [entry(rel)])])
        assert result["mismatch_codes"] == {"FILE_UNREADABLE": 1}

    @pytest.mark.parametrize(
        "bad",
        ["/etc/passwd", "../outside.md", "a/../../b.md", "", None, 5, "a\\b.md"],
    )
    def test_an_unsafe_or_missing_path_is_a_mismatch_and_is_never_read_or_echoed(
        self, tmp_path: Path, bad: Any
    ) -> None:
        bad_entry = {"path": bad, "class": "create", "kind": "K5"}
        result = census.check_writes(tmp_path, [write_report(tmp_path, "r.json", [bad_entry])])
        assert result["mismatch_codes"] == {"PATH_UNSAFE": 1}
        assert result["mismatch_paths"] == []

    def test_an_entry_with_no_path_key_is_a_path_mismatch(self, tmp_path: Path) -> None:
        report = write_report(tmp_path, "r.json", [{"class": "create", "kind": "K5"}])
        result = census.check_writes(tmp_path, [report])
        assert result["mismatch_codes"] == {"PATH_UNSAFE": 1} and result["mismatch_paths"] == []

    @pytest.mark.parametrize("bad", ["text", 5, None, [], {"path": "x"},
                                     {"path": "x.md", "class": "delete"}, {"path": "x.md", "class": 7}])
    def test_a_malformed_entry_or_an_unknown_class_is_a_mismatch(self, tmp_path: Path, bad: Any) -> None:
        result = census.check_writes(tmp_path, [write_report(tmp_path, "r.json", [bad])])
        assert result["mismatch_codes"] == {"MALFORMED_ENTRY": 1}

    @pytest.mark.parametrize(
        "text,code",
        [("{not json", "REPORT_UNPARSEABLE"), ("", "REPORT_UNPARSEABLE"), ("[]", "REPORT_SHAPE_INVALID"),
         ('{"mode": "apply"}', "REPORT_SHAPE_INVALID"), ('{"writes": {}}', "REPORT_SHAPE_INVALID")],
    )
    def test_a_bad_report_raises_its_closed_code(self, tmp_path: Path, text: str, code: str) -> None:
        path = tmp_path / "r.json"
        path.write_text(text, "utf-8")
        with pytest.raises(census.PreconditionError, match="^" + code + "$"):
            census.check_writes(tmp_path, [path])

    def test_a_missing_report_and_a_folder_raise_report_not_found(self, tmp_path: Path) -> None:
        for path in (tmp_path / "absent.json", tmp_path):
            with pytest.raises(census.PreconditionError, match="^REPORT_NOT_FOUND$"):
                census.check_writes(tmp_path, [path])

    def test_a_non_utf8_report_raises_report_unreadable(self, tmp_path: Path) -> None:
        path = tmp_path / "r.json"
        path.write_bytes(b'{"writes": [] \xff}')
        with pytest.raises(census.PreconditionError, match="^REPORT_UNREADABLE$"):
            census.check_writes(tmp_path, [path])

    def test_one_bad_report_among_good_ones_stops_the_check(self, tmp_path: Path) -> None:
        good = write_report(tmp_path, "a.json", row_entries())
        with pytest.raises(census.PreconditionError):
            census.check_writes(row_vault(tmp_path), [good, tmp_path / "absent.json"])


class TestMain:
    def test_a_scan_prints_one_json_document_that_equals_scan_vault(
        self, shared_vault: Path, capsys: pytest.CaptureFixture
    ) -> None:
        code, out, _ = run_main(["--vault-root", str(shared_vault)], capsys)
        assert code == 0
        assert json.loads(out) == census.scan_vault(shared_vault)
        assert out.endswith("}\n") and out.count("\n\n") == 0

    def test_check_writes_prints_the_check_result_and_not_the_scan(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        report = write_report(tmp_path, "r.json", row_entries())
        code, out, _ = run_main(["--vault-root", str(row_vault(tmp_path)), "--check-writes", str(report)], capsys)
        parsed = json.loads(out)
        assert code == 0 and parsed["checked"] == 13 and parsed["mismatches"] == 0
        assert "by_folder" not in parsed

    def test_mismatches_do_not_change_the_exit_code(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        report = write_report(tmp_path, "r.json", [entry(T + "T-9-spec.md")])
        argv = ["--vault-root", str(tmp_path), "--check-writes", str(report)]
        code, out, _ = run_main(argv, capsys)
        assert code == 0 and json.loads(out)["mismatches"] == 1

    @pytest.mark.parametrize(
        "text,code",
        [(None, "REPORT_NOT_FOUND"), ("{bad", "REPORT_UNPARSEABLE"), ("[]", "REPORT_SHAPE_INVALID")],
    )
    def test_a_bad_report_exits_two_with_its_closed_code_and_prints_no_result(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture,
        text: Optional[str], code: str,
    ) -> None:
        path = tmp_path / "r.json"
        if text is not None:
            path.write_text(text, "utf-8")
        exit_code, out, _ = run_main(["--vault-root", str(tmp_path), "--check-writes", str(path)], capsys)
        assert (exit_code, out) == (2, "")
        assert [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR] == [
            "fatal precondition: " + code
        ]

    @pytest.mark.parametrize("flag", ["--vault", "--check"])
    def test_an_abbreviated_flag_is_an_argument_error(self, tmp_path: Path, flag: str) -> None:
        with pytest.raises(SystemExit) as raised:
            census.main([flag, str(tmp_path), "--vault-root", str(tmp_path)])
        assert raised.value.code == 2

    def test_a_vault_root_that_is_not_a_folder_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        code, out, _ = run_main(["--vault-root", str(tmp_path / "absent")], capsys)
        assert (code, out) == (2, "")
        assert "fatal precondition: VAULT_ROOT_NOT_A_FOLDER" in caplog.text

    def test_a_missing_vault_root_flag_is_an_argument_error_and_never_a_default_vault(self) -> None:
        with pytest.raises(SystemExit) as raised:
            census.main([])
        assert raised.value.code == 2

    def test_a_folder_that_is_not_a_git_repository_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        write_files(tmp_path / "v", {"00-landing/a.md": b"# a\n"})
        code, out, _ = run_main(["--vault-root", str(tmp_path / "v")], capsys)
        assert (code, out) == (2, "")
        assert "fatal precondition: GIT_NONZERO_EXIT" in caplog.text

    def test_a_repository_with_no_commit_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        write_files(tmp_path / "v", {"00-landing/a.md": b"# a\n"})
        git_run(tmp_path / "v", "init", "-q")
        code, out, _ = run_main(["--vault-root", str(tmp_path / "v")], capsys)
        assert (code, out) == (2, "")

    @pytest.mark.parametrize(
        "raised,code",
        [(FileNotFoundError(), "GIT_UNAVAILABLE"),
         (subprocess.TimeoutExpired(cmd="git", timeout=1), "GIT_TIMEOUT")],
    )
    def test_a_git_failure_becomes_its_closed_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
        caplog: pytest.LogCaptureFixture, raised: Exception, code: str,
    ) -> None:
        def fail(*args: Any, **kwargs: Any) -> Any:
            raise raised

        monkeypatch.setattr(census.subprocess, "run", fail)
        exit_code, out, _ = run_main(["--vault-root", str(tmp_path)], capsys)
        assert (exit_code, out) == (2, "")
        assert "fatal precondition: " + code in caplog.text

    def test_only_the_read_only_git_subcommands_ls_files_and_diff_are_used(
        self, shared_vault: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: List[List[str]] = []
        real_run = subprocess.run

        def spy(command: List[str], *args: Any, **kwargs: Any) -> Any:
            seen.append(list(command))
            return real_run(command, *args, **kwargs)

        monkeypatch.setattr(census.subprocess, "run", spy)
        census.scan_vault(shared_vault)
        assert seen and {command[0] for command in seen} == {"git"}
        assert {command[1] for command in seen} == {"ls-files", "diff"}

    def test_git_runs_with_optional_locks_off(
        self, shared_vault: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        envs: List[Dict[str, str]] = []
        real_run = subprocess.run

        def spy(command: List[str], *args: Any, **kwargs: Any) -> Any:
            envs.append(kwargs["env"])
            return real_run(command, *args, **kwargs)

        monkeypatch.setattr(census.subprocess, "run", spy)
        census.scan_vault(shared_vault)
        assert envs and all(env["GIT_OPTIONAL_LOCKS"] == "0" for env in envs)


def run_cli(args: Sequence[str]) -> "subprocess.CompletedProcess[bytes]":
    """Run vault_census.py as a script under the interpreter that runs the tests."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, "-B", str(CENSUS_PATH), *args]
    return subprocess.run(command, capture_output=True, env=env, timeout=120, check=False)


class TestCommandLine:
    def test_the_script_prints_the_scan_to_stdout_and_logs_counts_to_stderr(
        self, shared_vault: Path
    ) -> None:
        result = run_cli(["--vault-root", str(shared_vault)])
        assert result.returncode == 0
        assert json.loads(result.stdout) == census.scan_vault(shared_vault)
        assert result.stderr.decode("utf-8").startswith("INFO scanned=25 ")

    def test_a_missing_report_exits_two_with_the_code_on_stderr_and_nothing_on_stdout(
        self, shared_vault: Path, tmp_path: Path
    ) -> None:
        result = run_cli(["--vault-root", str(shared_vault), "--check-writes", str(tmp_path / "no.json")])
        assert result.returncode == 2 and result.stdout == b""
        assert result.stderr.decode("utf-8").strip() == "ERROR fatal precondition: REPORT_NOT_FOUND"

    def test_check_writes_runs_from_the_command_line_over_two_reports(self, tmp_path: Path) -> None:
        root = row_vault(tmp_path)
        first = write_report(tmp_path, "a.json", row_entries()[:7])
        second = write_report(tmp_path, "b.json", row_entries()[7:])
        result = run_cli(["--vault-root", str(root), "--check-writes", str(first), str(second)])
        parsed = json.loads(result.stdout)
        assert (result.returncode, parsed["checked"], parsed["mismatches"]) == (0, 13, 0)


def canary_vault(tmp_path: Path) -> Path:
    """Build a vault where the canary sits in bodies, nonclassifying values, and bad YAML."""
    cases = {
        "02-tickets/T-1/T-1-spec.md": doc(
            ["catalog_type: ticket", "title: " + CANARY, "owner: [" + CANARY + "]"], CANARY + "\n"
        ),
        "02-tickets/T-1/T-1-design.md": CANARY.encode("utf-8") + b"\n",
        "02-tickets/T-1/T-1-notes.md": doc(["status: " + CANARY, "indexable: true"]),
        "02-tickets/T-1/T-1-plan.md": doc(["title: [" + CANARY]),
        "02-tickets/T-1/T-1-qa-findings.md": doc(["a: !!int " + CANARY]),
        "02-tickets/T-1/T-1-shipped.md": doc(["catalog_type: " + CANARY + " with spaces"]),
        "02-tickets/T-1/T-1-context.md": doc(["doc_role: [" + CANARY + "]"]),
    }
    return make_vault(tmp_path / "v", cases)


def canary_report(tmp_path: Path) -> Path:
    """A report whose entries carry the canary in every key and in an unsafe path."""
    rel = "02-tickets/T-1/T-1-spec.md"
    entries: List[Any] = [
        {"path": "../" + CANARY, "class": "create", "kind": CANARY, "added": {"x": CANARY}},
        {"path": rel, "class": CANARY, "kind": CANARY},
        {"path": rel, "class": "add", "kind": CANARY, "changes": [["a", CANARY, CANARY]]},
        CANARY,
    ]
    return write_report(tmp_path, "r.json", entries)


class TestCanary:
    def test_a_scan_never_prints_or_logs_the_canary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        code, out, err = run_main(["--vault-root", str(canary_vault(tmp_path))], capsys)
        assert code == 0
        assert CANARY not in out + err + caplog.text
        assert all(CANARY not in str(record.__dict__) for record in caplog.records)

    def test_a_check_writes_run_never_prints_or_logs_the_canary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        root, report = canary_vault(tmp_path), canary_report(tmp_path)
        code, out, err = run_main(["--vault-root", str(root), "--check-writes", str(report)], capsys)
        assert code == 0 and json.loads(out)["mismatches"] == 4
        assert CANARY not in out + err + caplog.text
        assert all(CANARY not in str(record.__dict__) for record in caplog.records)

    def test_the_script_never_prints_the_canary_on_either_stream(self, tmp_path: Path) -> None:
        root, report = canary_vault(tmp_path), canary_report(tmp_path)
        for extra in ([], ["--check-writes", str(report)]):
            result = run_cli(["--vault-root", str(root), *extra])
            assert result.returncode == 0
            assert CANARY.encode("utf-8") not in result.stdout + result.stderr

    def test_a_bad_report_error_carries_no_report_content(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "r.json"
        path.write_text('{"writes": ' + CANARY + "}", "utf-8")
        code, out, err = run_main(["--vault-root", str(tmp_path), "--check-writes", str(path)], capsys)
        assert code == 2 and CANARY not in out + err + caplog.text and str(tmp_path) not in caplog.text

    def test_the_canary_vault_really_holds_the_canary_in_every_kind_of_place(self, tmp_path: Path) -> None:
        root = canary_vault(tmp_path)
        texts = [path.read_text("utf-8") for path in root.rglob("*.md")]
        assert sum(CANARY in text for text in texts) == 7


def snapshot(root: Path) -> Dict[str, Tuple[str, int]]:
    """Map every path under root, .git included, to (content hash, mtime in nanoseconds)."""
    result: Dict[str, Tuple[str, int]] = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            result[rel] = (os.readlink(path), path.lstat().st_mtime_ns)
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[rel] = (digest, path.stat().st_mtime_ns)
    return result


WRITE_ATTRIBUTES = frozenset({
    "write_text", "write_bytes", "write", "writelines", "replace", "rename", "remove",
    "unlink", "rmdir", "mkdir", "makedirs", "touch", "chmod", "utime", "truncate",
    "symlink", "link", "copy", "copyfile", "copytree", "move", "rmtree",
})
WRITE_MODE_CHARS = "wax+"


def is_stdout_write(node: ast.Call) -> bool:
    """True for the one allowed write: sys.stdout.write."""
    func = node.func
    return (
        isinstance(func, ast.Attribute) and func.attr == "write"
        and isinstance(func.value, ast.Attribute) and func.value.attr == "stdout"
        and isinstance(func.value.value, ast.Name) and func.value.value.id == "sys"
    )


def open_call_writes(node: ast.Call) -> bool:
    """True when a call to open has a mode string that writes, appends, or creates."""
    modes = [arg.value for arg in node.args[1:2] if isinstance(arg, ast.Constant)]
    modes += [kw.value.value for kw in node.keywords
              if kw.arg == "mode" and isinstance(kw.value, ast.Constant)]
    return any(isinstance(mode, str) and any(c in mode for c in WRITE_MODE_CHARS) for mode in modes)


def write_violations(source: str) -> List[str]:
    """Return a note for every call in source that could write: an attribute or an open mode."""
    found: List[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in WRITE_ATTRIBUTES and not is_stdout_write(node):
            found.append("line {}: {}".format(node.lineno, func.attr))
        if isinstance(func, ast.Name) and func.id == "open" and open_call_writes(node):
            found.append("line {}: open for writing".format(node.lineno))
    return found


class TestReadOnly:
    def test_a_scan_and_a_check_leave_every_file_and_the_git_index_untouched(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        root = make_vault(tmp_path / "v", FIXTURE_FILES, FIXTURE_LINKS, FIXTURE_DIRTY, FIXTURE_UNTRACKED)
        report = write_report(tmp_path, "r.json", row_entries())
        before = snapshot(root)
        for argv in (["--vault-root", str(root)],
                     ["--vault-root", str(root), "--check-writes", str(report)]):
            assert run_main(argv, capsys)[0] == 0
        after = snapshot(root)
        assert after == before and ".git/index" in before

    def test_the_snapshot_sees_a_changed_byte_and_a_touched_mtime(self, tmp_path: Path) -> None:
        root = tmp_path / "v"
        write_files(root, {"a.md": b"abc\n"})
        before = snapshot(root)
        stat = (root / "a.md").stat()
        (root / "a.md").write_bytes(b"abd\n")
        os.utime(root / "a.md", ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert snapshot(root) != before
        (root / "a.md").write_bytes(b"abc\n")
        os.utime(root / "a.md", ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert snapshot(root) == before
        os.utime(root / "a.md", ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
        assert snapshot(root) != before

    def test_the_census_source_has_no_call_that_could_write(self) -> None:
        assert write_violations(CENSUS_PATH.read_text("utf-8")) == []

    def test_the_write_scan_flags_each_kind_of_write(self) -> None:
        sources = [
            "def f(p):\n    p.write_text('x')\n",
            "def f(p):\n    p.write_bytes(b'x')\n",
            "import os\ndef f():\n    os.replace('a', 'b')\n",
            "import os\ndef f():\n    os.remove('a')\n",
            "def f():\n    open('a', 'w')\n",
            "def f():\n    open('a', mode='ab')\n",
            "def f(h):\n    h.write('x')\n",
            "import sys\ndef f():\n    sys.stderr.write('x')\n",
        ]
        for source in sources:
            assert write_violations(source) != [], source

    def test_the_write_scan_allows_stdout_and_read_modes(self) -> None:
        source = "import sys\ndef f(p):\n    sys.stdout.write('x')\n    open(p)\n    open(p, 'rb')\n"
        assert write_violations(source) == []


IMPORT_ALLOWLIST = frozenset({
    "argparse", "dataclasses", "json", "logging", "os", "pathlib", "re", "subprocess",
    "sys", "typing", "yaml", "core",
})
TOOL_MODULE = "backfill_vault_frontmatter"
FORBIDDEN_ROOTS = (
    "socket", "ssl", "http", "requests", "httpx", "anthropic", "openai", "torch",
    "transformers", "chromadb", "sentence_transformers", "ollama",
)
FORBIDDEN_DOTTED = ("urllib.request",)
MAX_FUNCTION_LINES = 40
HEADER_LABELS = (
    "# Module:", "# Description:", "# Author:", "# Date:", "# Scope:", "# ChangeLog:",
)
HEADER_SCAN_LINES = 40
UNFINISHED_MARKER = "TO" + "DO"


def imported_names(source: str) -> List[str]:
    """Return every imported module name in source, at any depth, and flag dynamic imports."""
    found: List[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__":
            found.append("__import__")
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "import_module":
            found.append("import_module")
    return found


def import_violations(source: str) -> List[str]:
    """Return every imported name outside the allowlist."""
    return [name for name in imported_names(source) if name.split(".")[0] not in IMPORT_ALLOWLIST]


def missing_annotations(node: Any) -> List[str]:
    """Return the arguments and return value of a function that lack a type hint."""
    args = node.args
    every = args.posonlyargs + args.args + args.kwonlyargs
    every += [arg for arg in (args.vararg, args.kwarg) if arg is not None]
    gaps = [arg.arg for arg in every if arg.annotation is None and arg.arg not in ("self", "cls")]
    return gaps + (["return"] if node.returns is None else [])


def standards_violations(source: str) -> List[str]:
    """Return one note per function that is untyped or too long, and per print call."""
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
    """Return the header labels missing from the top of source and any unfinished marker."""
    head = "\n".join(source.splitlines()[:HEADER_SCAN_LINES])
    found = ["missing {}".format(label) for label in HEADER_LABELS if label not in head]
    for number, line in enumerate(source.splitlines(), start=1):
        if UNFINISHED_MARKER in line:
            found.append("unfinished marker on line {}".format(number))
    return found


def python39_violations(source: str) -> List[str]:
    """Return a note for each match statement and each bar union inside an annotation."""
    found: List[str] = []
    annotations: List[Any] = []
    for node in ast.walk(ast.parse(source)):
        if type(node).__name__ == "Match":
            found.append("match statement on line {}".format(node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            every = args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]
            annotations += [arg.annotation for arg in every if arg is not None] + [node.returns]
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
    for annotation in [item for item in annotations if item is not None]:
        for inner in ast.walk(annotation):
            if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.BitOr):
                found.append("union with a vertical bar on line {}".format(inner.lineno))
    return found


def table_names(source: str) -> List[str]:
    """Return the module level names in source that are assigned a tuple holding KindRow calls."""
    names: List[str] = []
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        value = getattr(node, "value", None)
        calls = [n for n in ast.walk(value)] if value is not None else []
        if any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "KindRow" for n in calls):
            names += [t.id for t in targets if isinstance(t, ast.Name)]
    return names


def census_attributes_used(source: str, alias: str) -> List[str]:
    """Return every attribute this source reads from the module bound to alias."""
    return [
        node.attr for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == alias
    ]


class TestIndependence:
    def test_the_census_does_not_import_the_backfill_tool(self) -> None:
        names = imported_names(CENSUS_PATH.read_text("utf-8"))
        assert not any(name.split(".")[0] == TOOL_MODULE for name in names)

    def test_this_test_file_does_not_import_the_backfill_tool(self) -> None:
        names = imported_names(THIS_PATH.read_text("utf-8"))
        assert not any(name.split(".")[0] == TOOL_MODULE for name in names)

    def test_the_tool_name_check_flags_each_form_of_import(self) -> None:
        for source in ("import backfill_vault_frontmatter\n", "from backfill_vault_frontmatter import x\n",
                       "import backfill_vault_frontmatter as t\n"):
            assert any(n.split(".")[0] == TOOL_MODULE for n in imported_names(source)), source

    def test_the_census_holds_one_table_of_kind_rows(self) -> None:
        names = table_names(CENSUS_PATH.read_text("utf-8"))
        assert names == ["KIND_ROWS"]

    def test_this_test_file_never_reads_the_census_table(self) -> None:
        used = census_attributes_used(THIS_PATH.read_text("utf-8"), "census")
        table = set(table_names(CENSUS_PATH.read_text("utf-8"))) | {"ROLE_ROWS", "KindRow"}
        assert table.isdisjoint(used)

    def test_the_table_check_sees_a_read_of_the_table_and_a_table_definition(self) -> None:
        assert "KIND_ROWS" in census_attributes_used("x = census.KIND_ROWS\n", "census")
        assert table_names("ROWS = (KindRow('K1'),)\n") == ["ROWS"]
        assert table_names("ROWS = (1, 2)\n") == []

    def test_the_test_literals_do_not_come_from_the_census(self) -> None:
        tree = ast.parse(THIS_PATH.read_text("utf-8"))
        literal_rows = [n for n in tree.body if isinstance(n, ast.AnnAssign)
                        and getattr(n.target, "id", "") == "ROW_CASES"]
        assert len(literal_rows) == 1
        assert isinstance(literal_rows[0].value, ast.List)
        assert all(isinstance(item, ast.Tuple) for item in literal_rows[0].value.elts)


RUNTIME_PROBE = """
import json, sys
sys.path.insert(0, {root!r})
import vault_census
roots = {roots!r}
dotted = {dotted!r}
hits = sorted(
    name for name in sys.modules
    if name.split('.')[0] in roots or any(name == d or name.startswith(d + '.') for d in dotted)
)
sys.stdout.write(json.dumps(hits))
"""


def loaded_forbidden_modules() -> List[str]:
    """Import the census in a fresh interpreter and list the forbidden modules it loaded."""
    roots = FORBIDDEN_ROOTS + (TOOL_MODULE,)
    code = RUNTIME_PROBE.format(root=str(CENSUS_PATH.parent), roots=roots, dotted=FORBIDDEN_DOTTED)
    result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, timeout=120, check=False)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")[-300:]
    loaded: List[str] = json.loads(result.stdout.decode("utf-8"))
    return loaded


class TestLocalOnly:
    def test_the_census_imports_only_the_allowlist(self) -> None:
        assert import_violations(CENSUS_PATH.read_text("utf-8")) == []

    def test_the_check_flags_a_network_model_or_tool_import_even_inside_a_function(self) -> None:
        sources = [
            "import socket\n", "from urllib import request\n", "import urllib.request\n",
            "def f() -> None:\n    import requests\n", "def f() -> None:\n    from anthropic import X\n",
            "import backfill_vault_frontmatter\n", "from . import sibling\n",
            "x = __import__('socket')\n", "import importlib\nx = importlib.import_module('socket')\n",
            "import shutil\n", "import tempfile\n",
        ]
        for source in sources:
            assert import_violations(source) != [], source

    def test_the_check_accepts_an_allowed_import_anywhere(self) -> None:
        source = "import os\nfrom typing import Any\ndef f() -> None:\n    import yaml\n"
        assert import_violations(source) == []

    def test_a_fresh_interpreter_loads_no_network_model_tool_or_paths_module(self) -> None:
        assert loaded_forbidden_modules() == []

    def test_the_probe_does_see_a_forbidden_module_when_one_is_loaded(self) -> None:
        probe = RUNTIME_PROBE.replace("import vault_census", "import vault_census, socket")
        code = probe.format(root=str(CENSUS_PATH.parent), roots=("socket",), dotted=())
        result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, check=False)
        assert "socket" in json.loads(result.stdout.decode("utf-8"))


def function_source(total_lines: int) -> str:
    """Return a function named f whose definition spans exactly total_lines lines."""
    return "def f() -> None:\n" + "    x = 0\n" * (total_lines - 1)


class TestStandards:
    @pytest.mark.parametrize("path", [CENSUS_PATH, THIS_PATH], ids=["census", "tests"])
    def test_functions_are_typed_short_and_never_print(self, path: Path) -> None:
        assert standards_violations(path.read_text("utf-8")) == []

    @pytest.mark.parametrize("path", [CENSUS_PATH, THIS_PATH], ids=["census", "tests"])
    def test_the_file_carries_the_header_block_and_no_unfinished_marker(self, path: Path) -> None:
        assert header_violations(path.read_text("utf-8")) == []

    @pytest.mark.parametrize("path", [CENSUS_PATH, THIS_PATH], ids=["census", "tests"])
    def test_no_match_statement_and_no_bar_union_in_an_annotation(self, path: Path) -> None:
        assert python39_violations(path.read_text("utf-8")) == []

    def test_the_length_check_flags_a_function_one_line_over_the_limit(self) -> None:
        over = MAX_FUNCTION_LINES + 1
        assert standards_violations(function_source(over)) == ["f is {} lines".format(over)]
        assert standards_violations(function_source(MAX_FUNCTION_LINES)) == []

    def test_the_hint_check_flags_each_missing_hint(self) -> None:
        assert standards_violations("def f(a, b: int):\n    return 1\n") == ["f lacks hints for ['a', 'return']"]
        assert standards_violations("class C:\n    def m(self, *r, **k) -> None:\n        pass\n") != []
        assert standards_violations("class C:\n    def m(self) -> None:\n        pass\n") == []

    def test_the_print_check_flags_a_print_call(self) -> None:
        assert standards_violations("def f() -> None:\n    print('x')\n") == ["print call on line 2"]

    def test_the_header_check_flags_a_missing_label_and_an_unfinished_marker(self) -> None:
        assert header_violations("# Module: x\n") != []
        full = "".join("{} x\n".format(label) for label in HEADER_LABELS)
        assert header_violations(full) == []
        assert header_violations(full + "# " + UNFINISHED_MARKER + " later\n") != []

    def test_the_bar_union_check_flags_each_annotation_position(self) -> None:
        for source in ("def f(x: int | None) -> None:\n    pass\n", "def f(x: int) -> str | None:\n    pass\n",
                       "x: int | None = None\n", "def f(*a: int | str) -> None:\n    pass\n"):
            assert python39_violations(source) != [], source
        assert python39_violations("def f(a: int, b: int) -> int:\n    return a | b\n") == []

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="match needs Python 3.10 to parse")
    def test_the_match_check_flags_a_match_statement(self) -> None:
        source = "def f(x: int) -> int:\n    match x:\n        case 1:\n            return 1\n    return 0\n"
        assert python39_violations(source) != []
