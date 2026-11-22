# Module:      test_backfill_nonticket_policy.py
# Description: Tests for Run 4 of backfill_vault_frontmatter.py: the folder
#              rows N1 to N6 and N10, the scope A planner, the walk that skips
#              memory folder, the report contract, the apply gates, and the census check
#              of a Run 4 report in vault_census.py. Every input is a synthetic byte
#              string or a fixture vault built in a pytest temp folder, so no test reaches
#              the real vault. The expected N rows are literals here. This file never
#              reads the tool's folder table, so a typo in the table cannot hide behind a
#              copy of itself. An autouse fixture makes the tool's default vault lookup raise.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Test classes: TestFolderRows, TestRun4Classes, TestRun4Scope, TestRun4Policy,
#              TestRun4Gates, TestRun4Report, TestRun4Census, TestRun4Regression,
#              TestRun4Standards
# Version:     1.0
# ChangeLog:
#   Initial implementation

import ast
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import minipytest as pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "state"))
import backfill_vault_frontmatter as tool  # noqa: E402
import vault_census as census  # noqa: E402

TOOL_PATH = Path(__file__).resolve().parents[3] / "scripts" / "state" / "backfill_vault_frontmatter.py"
CENSUS_PATH = Path(__file__).resolve().parents[3] / "scripts" / "state" / "vault_census.py"

RUN = 4
LF = b"\n"
CRLF = b"\r\n"
CANARY = "CANARY_7Q2X_DO_NOT_LEAK"
FIXTURE_USER = "Fixture User"
FIXTURE_EMAIL = "fixture@example.invalid"
FIXTURE_COMMIT_MESSAGE = "fixture"
GIT_DIR_NAME = ".git"
GIT_LEAK_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE",
)
MAX_FUNCTION_LINES = 40
EXIT_PRECONDITION = 2

# Source: the spec, Policy table, re-typed here as literals.
# Columns: row id, a path that must take the row, catalog_type, doc_role, indexable.
EXPECTED_ROWS: List[Tuple[str, str, str, str, bool]] = [
    ("N1", "01-system-map/clients/acme.md", "reference", "reference", True),
    ("N2", "01-system-map/pipelines/p.md", "reference", "reference", True),
    ("N2", "01-system-map/architecture/a.md", "reference", "reference", True),
    ("N2", "01-system-map/data-model/d.md", "reference", "reference", True),
    ("N3", "01-system-map/platform-learning/l.md", "knowledge", "learning", True),
    ("N4", "03-knowledge-base/decisions/d.md", "knowledge", "decision", True),
    ("N5", "03-knowledge-base/learnings/l.md", "knowledge", "learning", True),
    ("N6", "03-knowledge-base/patterns/p.md", "knowledge", "pattern", True),
    ("N10", "04-education/e.md", "knowledge", "education", True),
]
ROW_IDS = [row[0] for row in EXPECTED_ROWS]
ROW_CASES = [pytest.param(*row, id=row[1]) for row in EXPECTED_ROWS]

OUT_OF_SCOPE_NOTES: Dict[str, bytes] = {
    "00-landing/idea.md": b"plain note, no block\n",
    "02-tickets/T-900/T-900-state.md": b"---\nstatus: ACTIVE\n---\nbody\n",
    "02-tickets/T-900/spec.md": b"no block here\n",
    "memory/m.md": b"---\ntags: [m]\n---\nmemory\n",
    "03-knowledge-base/sql/q.md": b"query notes\n",
    "05-conversations/c.md": b"---\ndoc_type: conversation\n---\nchat\n",
    "07-workflows/w.md": b"workflow\n",
    "08-trajectories/t.md": b"---\ndoc_type: trajectory\n---\n",
    "claude-skills-reference.md": b"top level note\n",
}


def refuse_default_vault_root() -> Any:
    """Stand in for default_vault_root: a fallback to the real vault is a bug."""
    raise AssertionError("default_vault_root was called: a test would fall back to the real vault")


@pytest.fixture(autouse=True)
def forbid_real_vault_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the tool's default vault lookup raise for every test in this module."""
    monkeypatch.setattr(tool, "default_vault_root", refuse_default_vault_root)


class Vault:
    """A throwaway vault folder inside a pytest temp folder, backed by an isolated git repo."""

    def __init__(self, root: Path, out: Path) -> None:
        self.root = root
        self.out = out

    def git(self, *args: str) -> str:
        """Run one git command in the vault with a fixed identity and no signing."""
        command = [
            "git", "-c", "user.name=" + FIXTURE_USER, "-c", "user.email=" + FIXTURE_EMAIL,
            "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args,
        ]
        done = subprocess.run(command, cwd=str(self.root), check=True, capture_output=True)
        return done.stdout.decode("utf-8", "replace")

    def init(self) -> None:
        """Create the folders and the repository, with an initial empty commit."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.out.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q")
        self.commit_all()

    def write(self, rel: str, content: bytes) -> Path:
        """Write bytes at a vault relative path, creating folders."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def read(self, rel: str) -> bytes:
        """Return the bytes of a vault relative path."""
        return (self.root / rel).read_bytes()

    def commit_all(self) -> None:
        """Stage everything and commit. An empty commit is allowed so HEAD always exists."""
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", FIXTURE_COMMIT_MESSAGE)

    def seed(self, notes: Dict[str, bytes]) -> None:
        """Write every note and commit, so the tree is clean and every note is tracked."""
        for rel, content in notes.items():
            self.write(rel, content)
        self.commit_all()


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Vault:
    """A fresh isolated git vault at tmp_path/vault, with an output folder beside it."""
    home = tmp_path / "home"
    home.mkdir()
    for name in GIT_LEAK_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    fixture = Vault(tmp_path / "vault", tmp_path / "out")
    fixture.init()
    return fixture


def tags_only(extra: str = "") -> bytes:
    """A note with a tags line, an optional extra frontmatter text, and a canary body."""
    return ("---\ntags: [a]\n" + extra + "---\nbody " + CANARY + "\n").encode("utf-8")


def parsed(raw: bytes) -> Dict[str, Any]:
    """Return the frontmatter mapping of raw, split on the first two delimiter lines."""
    text = raw.decode("utf-8").replace("\r\n", "\n")
    return yaml.safe_load(text.split("---\n", 2)[1]) or {}


def preview(vault: Vault) -> Dict[str, Any]:
    """Run 4 preview over the fixture vault."""
    return tool.run_policy(vault.root, RUN, False, None)


def apply_run4(vault: Vault) -> Dict[str, Any]:
    """Run 4 preview, then apply bound to that preview. Returns the apply report."""
    approved = preview(vault)
    return tool.run_policy(vault.root, RUN, True, approved)


def sha(raw: bytes) -> str:
    """Return the sha256 hex digest of raw."""
    return hashlib.sha256(raw).hexdigest()


def entry_for(report: Dict[str, Any], rel: str) -> Dict[str, Any]:
    """Return the report entry of one written path."""
    return [entry for entry in report["writes"] if entry["path"] == rel][0]


class TestFolderRows:
    @pytest.mark.parametrize("row_id,rel,catalog,role,indexable", ROW_CASES)
    def test_a_note_in_each_row_gets_its_triple(
        self, vault: Vault, row_id: str, rel: str, catalog: str, role: str, indexable: bool
    ) -> None:
        vault.seed({rel: tags_only()})
        report = apply_run4(vault)
        entry = entry_for(report, rel)
        assert entry["kind"] == row_id
        assert entry["class"] == "add"
        fm = parsed(vault.read(rel))
        assert (fm["catalog_type"], fm["doc_role"], fm["indexable"]) == (catalog, role, indexable)
        assert fm["indexed"] is None
        assert type(fm["indexable"]) is bool

    def test_the_row_ids_are_unique_and_start_with_n(self) -> None:
        distinct = set(ROW_IDS)
        assert len(distinct) == 7
        assert all(row_id.startswith("N") for row_id in ROW_IDS)
        assert not distinct & {"K" + str(number) for number in range(1, 15)}

    def test_a_duplicate_row_id_is_refused_at_load(self) -> None:
        one = tool.FolderRow("N1", ("a/",), "reference", "reference", True)
        with pytest.raises(ValueError):
            tool.check_folder_rows((one, one))

    def test_a_row_id_without_the_n_prefix_is_refused(self) -> None:
        with pytest.raises(ValueError):
            tool.check_folder_rows((tool.FolderRow("K1", ("a/",), "x", "y", True),))

    @pytest.mark.parametrize("rel", ["01-system-map/misc/x.md", "01-system-map/top.md"])
    def test_a_scope_a_path_under_no_row_is_listed_as_no_kind_row(
        self, vault: Vault, rel: str
    ) -> None:
        vault.seed({rel: tags_only()})
        report = preview(vault)
        assert {entry["path"]: entry["reason"] for entry in report["skipped"]} == {
            rel: "NO_KIND_ROW"
        }
        assert report["writes"] == []

    @pytest.mark.parametrize("doc_type", [
        "decision-note", "Decision", "ticket-spec", "client_reference", "ticket-state",
        "conversation", "trajectory", "nonsense", "",
    ])
    def test_the_folder_decides_and_doc_type_is_ignored(self, vault: Vault, doc_type: str) -> None:
        rel = "03-knowledge-base/learnings/x.md"
        vault.seed({rel: ("---\ndoc_type: " + doc_type + "\n---\nbody\n").encode("utf-8")})
        apply_run4(vault)
        fm = parsed(vault.read(rel))
        assert (fm["catalog_type"], fm["doc_role"], fm["indexable"]) == ("knowledge", "learning", True)


class TestRun4Classes:
    def test_a_note_with_no_frontmatter_gets_a_four_line_block(self, vault: Vault) -> None:
        rel = "03-knowledge-base/decisions/plain.md"
        original = b"# Title\n\nbody " + CANARY.encode() + b"\n"
        vault.seed({rel: original})
        report = apply_run4(vault)
        block = (
            b"---\ncatalog_type: knowledge\ndoc_role: decision\nindexable: true\n"
            b"indexed: null\n---\n"
        )
        assert vault.read(rel) == block + original
        assert entry_for(report, rel)["class"] == "create"

    def test_a_note_with_tags_only_gets_lines_above_the_closing_delimiter(
        self, vault: Vault
    ) -> None:
        rel = "04-education/e.md"
        original = tags_only()
        vault.seed({rel: original})
        apply_run4(vault)
        added = b"catalog_type: knowledge\ndoc_role: education\nindexable: true\nindexed: null\n"
        cut = original.index(b"---\nbody")
        assert vault.read(rel) == original[:cut] + added + original[cut:]

    def test_a_placeholder_note_is_rewritten_line_for_line(self, vault: Vault) -> None:
        rel = "03-knowledge-base/patterns/p.md"
        original = (
            b"---\ncatalog_type: unknown\ndoc_role: unknown\nindexable: false\n"
            b"indexed: null\n---\nbody\n"
        )
        vault.seed({rel: original})
        report = apply_run4(vault)
        expected = (
            b"---\ncatalog_type: knowledge\ndoc_role: pattern\nindexable: true\n"
            b"indexed: null\n---\nbody\n"
        )
        assert vault.read(rel) == expected
        assert entry_for(report, rel)["class"] == "rewrite"
        assert report["counts"]["changed"] == 1 and report["counts"]["written"] == 0

    def test_a_crlf_note_keeps_crlf_for_add_and_for_create(self, vault: Vault) -> None:
        added_rel, create_rel = "04-education/a.md", "04-education/c.md"
        vault.seed({
            added_rel: b"---\r\ntags: [a]\r\n---\r\nbody\r\n",
            create_rel: b"# Title\r\nbody\r\n",
        })
        apply_run4(vault)
        for rel in (added_rel, create_rel):
            raw = vault.read(rel)
            assert raw.count(LF) == raw.count(CRLF)
            assert parsed(raw)["doc_role"] == "education"

    def test_a_complete_note_is_left_alone_and_listed_when_it_differs(
        self, vault: Vault
    ) -> None:
        same = "03-knowledge-base/learnings/same.md"
        differs = "03-knowledge-base/learnings/differs.md"
        block = b"---\ncatalog_type: %s\ndoc_role: %s\nindexable: true\nindexed: null\n---\nb\n"
        vault.seed({
            same: block % (b"knowledge", b"learning"),
            differs: block % (b"knowledge", b"review"),
        })
        before = {rel: vault.read(rel) for rel in (same, differs)}
        report = apply_run4(vault)
        assert {rel: vault.read(rel) for rel in (same, differs)} == before
        assert report["counts"]["already_complete"] == 2
        assert report["complete_differs"] == [differs]

    @pytest.mark.parametrize("status", ["cancelled", " Superseded ", "DROPPED", "archived", "absorbed"])
    def test_a_terminal_status_gets_indexable_false(self, vault: Vault, status: str) -> None:
        rel = "03-knowledge-base/decisions/old.md"
        vault.seed({rel: tags_only("status: " + status + "\n")})
        apply_run4(vault)
        fm = parsed(vault.read(rel))
        assert (fm["catalog_type"], fm["doc_role"], fm["indexable"]) == ("knowledge", "decision", False)

    def test_a_status_that_only_contains_a_terminal_word_stays_indexable(
        self, vault: Vault
    ) -> None:
        rel = "03-knowledge-base/decisions/open.md"
        vault.seed({rel: tags_only("status: active | archived\n")})
        apply_run4(vault)
        assert parsed(vault.read(rel))["indexable"] is True

    def test_an_unparseable_block_is_skipped_and_untouched(self, vault: Vault) -> None:
        rel = "04-education/bad.md"
        original = b"---\nkey: [unclosed\n---\nbody\n"
        vault.seed({rel: original})
        report = apply_run4(vault)
        assert vault.read(rel) == original
        assert report["skipped_by_reason"] == {"PARSE_ERROR": 1}

    def test_an_unsafe_top_is_skipped_and_untouched(self, vault: Vault) -> None:
        rel = "04-education/rule.md"
        original = b"---\nnot closed\nbody\n"
        vault.seed({rel: original})
        report = apply_run4(vault)
        assert vault.read(rel) == original
        assert report["skipped_by_reason"] == {"UNSAFE_TOP": 1}


class TestRun4Scope:
    def test_notes_outside_scope_a_are_not_targets_and_stay_identical(self, vault: Vault) -> None:
        vault.seed(OUT_OF_SCOPE_NOTES)
        report = apply_run4(vault)
        for rel, original in OUT_OF_SCOPE_NOTES.items():
            assert vault.read(rel) == original
        assert report["writes"] == []
        assert report["counts"]["written"] == 0 and report["counts"]["changed"] == 0

    def test_the_walk_skips_only_the_memory_folder_for_run_4(self, vault: Vault) -> None:
        paths = [
            "memory/m.md", "03-knowledge-base/decisions/d.md",
            "03-knowledge-base/sql/q.md", ".hidden/h.md", "04-education/e.md",
        ]
        vault.seed({rel: tags_only() for rel in paths})
        found = list(tool.iter_vault_files(vault.root, tool.excluded_for_run(RUN)))
        assert found == [
            "03-knowledge-base/decisions/d.md", "03-knowledge-base/sql/q.md", "04-education/e.md",
        ]

    def test_the_default_walk_skips_the_memory_folder_and_is_the_same_for_every_run(
        self, vault: Vault
    ) -> None:
        paths = ["memory/m.md", "04-education/e.md"]
        vault.seed({rel: tags_only() for rel in paths})
        assert list(tool.iter_vault_files(vault.root)) == ["04-education/e.md"]
        for run in (1, 2, 3):
            assert tool.excluded_for_run(run) == tool.EXCLUDED_PATH_PREFIXES
        assert tool.excluded_for_run(None) == tool.EXCLUDED_PATH_PREFIXES

    def test_a_decision_note_is_labeled_but_the_memory_folder_is_not(self, vault: Vault) -> None:
        vault.seed({
            "03-knowledge-base/decisions/s.md": tags_only(),
            "memory/m.md": tags_only(),
        })
        memory = vault.read("memory/m.md")
        report = apply_run4(vault)
        assert [entry["path"] for entry in report["writes"]] == ["03-knowledge-base/decisions/s.md"]
        assert vault.read("memory/m.md") == memory
        assert report["exclusions"] == ["memory/"]

    def test_a_ticket_note_is_not_a_target_even_with_no_label(self, vault: Vault) -> None:
        rel = "02-tickets/T-900/T-900-state.md"
        vault.seed({rel: tags_only()})
        report = apply_run4(vault)
        assert report["writes"] == [] and report["skipped"] == []


class TestRun4Policy:
    def seed_mixed(self, vault: Vault) -> None:
        vault.seed({
            "03-knowledge-base/decisions/a.md": tags_only(),
            "03-knowledge-base/decisions/b.md": b"no block\n",
            "04-education/c.md": (
                b"---\ncatalog_type: unknown\ndoc_role: unknown\nindexable: false\n"
                b"indexed: null\n---\nbody\n"
            ),
            "04-education/d.md": (
                b"---\ncatalog_type: knowledge\ndoc_role: education\nindexable: true\n"
                b"indexed: null\n---\nbody\n"
            ),
            "04-education/e.md": b"---\nkey: [unclosed\n---\n",
            "01-system-map/misc/f.md": tags_only(),
            "00-landing/g.md": b"outside\n",
        })

    def test_preview_writes_nothing(self, vault: Vault) -> None:
        self.seed_mixed(vault)
        status = vault.git("status", "--porcelain")
        stamps = {
            str(path): (sha(path.read_bytes()), path.stat().st_mtime_ns)
            for path in vault.root.rglob("*.md")
        }
        report = preview(vault)
        assert report["mode"] == "preview" and report["counts"]["written"] == 2
        assert vault.git("status", "--porcelain") == status
        assert stamps == {
            str(path): (sha(path.read_bytes()), path.stat().st_mtime_ns)
            for path in vault.root.rglob("*.md")
        }

    def test_preview_equals_apply(self, vault: Vault) -> None:
        self.seed_mixed(vault)
        previewed = preview(vault)
        applied = tool.run_policy(vault.root, RUN, True, previewed)
        for key in ("counts", "by_class", "by_kind", "skipped_by_reason", "writes", "skipped"):
            assert applied[key] == previewed[key], key

    def test_a_second_preview_plans_nothing(self, vault: Vault) -> None:
        self.seed_mixed(vault)
        apply_run4(vault)
        again = preview(vault)
        assert again["counts"]["written"] == 0 and again["counts"]["changed"] == 0
        assert again["writes"] == []
        vault.commit_all()
        committed = preview(vault)
        assert committed["writes"] == [] and committed["tree"]["clean"] is True

    def test_counts_reconcile(self, vault: Vault) -> None:
        self.seed_mixed(vault)
        counts = apply_run4(vault)["counts"]
        total = counts["written"] + counts["changed"] + counts["skipped"] + counts["already_complete"]
        assert counts["classified"] == total
        assert (counts["written"], counts["changed"]) == (2, 1)
        assert (counts["skipped"], counts["already_complete"]) == (2, 1)
        assert counts["scanned"] == counts["classified"] + counts["not_target"]

    def test_the_report_names_the_n_row_in_the_kind_column(self, vault: Vault) -> None:
        self.seed_mixed(vault)
        report = apply_run4(vault)
        assert report["by_kind"]["N4"] == {"add": 1, "create": 1, "flip": 0, "rewrite": 0}
        assert report["by_kind"]["N10"] == {"add": 0, "create": 0, "flip": 0, "rewrite": 1}
        assert report["skipped_by_reason"] == {"NO_KIND_ROW": 1, "PARSE_ERROR": 1}


class TestRun4Gates:
    def test_apply_refuses_a_dirty_tree(self, vault: Vault) -> None:
        vault.seed({"04-education/e.md": tags_only()})
        approved = preview(vault)
        vault.write("00-landing/new.md", b"untracked\n")
        before = vault.read("04-education/e.md")
        with pytest.raises(tool.PreconditionError) as info:
            tool.run_policy(vault.root, RUN, True, approved)
        assert str(info.value) == tool.ERROR_DIRTY_TREE
        assert vault.read("04-education/e.md") == before

    def test_apply_refuses_without_an_approved_report(self, vault: Vault) -> None:
        vault.seed({"04-education/e.md": tags_only()})
        before = vault.read("04-education/e.md")
        with pytest.raises(tool.PreconditionError) as info:
            tool.run_policy(vault.root, RUN, True, None)
        assert str(info.value) == tool.ERROR_APPROVED_REPORT_REQUIRED
        assert vault.read("04-education/e.md") == before

    def test_apply_refuses_a_report_from_another_run(self, vault: Vault) -> None:
        vault.seed({"04-education/e.md": tags_only()})
        other = tool.run_policy(vault.root, 2, False, None)
        with pytest.raises(tool.PreconditionError) as info:
            tool.run_policy(vault.root, RUN, True, other)
        assert str(info.value) == tool.ERROR_APPROVED_REPORT_MISMATCH

    def test_apply_refuses_a_write_that_the_preview_did_not_show(self, vault: Vault) -> None:
        vault.seed({"04-education/e.md": tags_only()})
        approved = preview(vault)
        vault.write("04-education/late.md", tags_only())
        vault.commit_all()
        with pytest.raises(tool.PreconditionError) as info:
            tool.run_policy(vault.root, RUN, True, approved)
        assert str(info.value) == tool.ERROR_NOT_APPROVED

    def test_an_uncommitted_note_is_skipped_not_written(self, vault: Vault) -> None:
        vault.seed({"04-education/a.md": tags_only()})
        vault.write("04-education/b.md", tags_only())
        report = preview(vault)
        assert report["skipped_by_reason"] == {"UNTRACKED": 1}

    def test_the_cli_accepts_run_4_and_applies_only_with_an_approved_report(
        self, vault: Vault, capsys: pytest.CaptureFixture
    ) -> None:
        vault.seed({"04-education/e.md": tags_only()})
        base = ["--vault-root", str(vault.root), "--run", "4"]
        report_path = vault.out / "preview.json"
        assert tool.main(base + ["--report-path", str(report_path)]) == 0
        capsys.readouterr()
        assert tool.main(base + ["--apply"]) == EXIT_PRECONDITION
        assert "catalog_type" not in vault.read("04-education/e.md").decode()
        assert tool.main(base + ["--apply", "--approved-report", str(report_path)]) == 0
        assert parsed(vault.read("04-education/e.md"))["doc_role"] == "education"

    def test_the_cli_refuses_an_approved_report_without_apply(
        self, vault: Vault
    ) -> None:
        vault.seed({"04-education/e.md": tags_only()})
        args = ["--vault-root", str(vault.root), "--run", "4", "--approved-report", "x.json"]
        assert tool.main(args) == EXIT_PRECONDITION


class TestRun4Report:
    def test_the_canary_never_reaches_the_report_stdout_or_logs(
        self, vault: Vault, capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        extra = "title: " + CANARY + "\nauthor: " + CANARY + "\n"
        vault.seed({
            "04-education/a.md": tags_only(extra + "doc_type: " + CANARY + "\n"),
            "04-education/b.md": ("# " + CANARY + "\n").encode("utf-8"),
            "04-education/c.md": ("---\nk: [" + CANARY + "\n---\n").encode("utf-8"),
            "03-knowledge-base/patterns/d.md": (
                "---\ndoc_type: " + CANARY + "\ncatalog_type: unknown\ndoc_role: unknown\n"
                "indexable: false\nindexed: null\n---\n" + CANARY + "\n"
            ).encode("utf-8"),
        })
        report_path = vault.out / "preview.json"
        with caplog.at_level(logging.DEBUG):
            assert tool.main(
                ["--vault-root", str(vault.root), "--run", "4", "--report-path", str(report_path)]
            ) == 0
            assert tool.main(
                ["--vault-root", str(vault.root), "--run", "4", "--apply",
                 "--approved-report", str(report_path)]
            ) == 0
        seen = capsys.readouterr()
        text = " ".join(record.getMessage() for record in caplog.records)
        assert CANARY not in seen.out + seen.err + text + report_path.read_text()

    def test_the_report_carries_only_the_closed_run_fields(self, vault: Vault) -> None:
        vault.seed({"04-education/a.md": tags_only(), "04-education/b.md": b"x\n"})
        report = preview(vault)
        assert report["run"] == RUN and report["mode"] == "preview"
        assert set(entry_for(report, "04-education/a.md")) == {
            "path", "class", "kind", "added", "changes",
        }
        json.dumps(report)

    def test_a_note_with_only_a_canary_in_frontmatter_values_is_labeled_by_folder(
        self, vault: Vault
    ) -> None:
        rel = "01-system-map/clients/x.md"
        vault.seed({rel: tags_only("owner: " + CANARY + "\n")})
        report = apply_run4(vault)
        assert entry_for(report, rel)["kind"] == "N1"
        assert CANARY.encode() in vault.read(rel)


class TestRun4Census:
    def test_the_census_table_copy_gives_each_row_its_triple(self) -> None:
        for _row_id, rel, catalog, role, indexable in EXPECTED_ROWS:
            assert census.folder_triple(rel, {}) == (catalog, role, indexable), rel

    def test_the_census_copy_has_no_row_outside_scope_a(self) -> None:
        for rel in OUT_OF_SCOPE_NOTES:
            assert census.folder_triple(rel, {}) is None
        assert census.folder_triple("01-system-map/misc/x.md", {}) is None

    def test_the_census_applies_the_terminal_override(self) -> None:
        triple = census.folder_triple("03-knowledge-base/decisions/d.md", {"status": "Dropped"})
        assert triple == ("knowledge", "decision", False)

    def test_check_writes_passes_a_clean_run_4_apply(self, vault: Vault) -> None:
        vault.seed({
            "03-knowledge-base/decisions/a.md": tags_only(),
            "04-education/b.md": b"plain\n",
            "03-knowledge-base/patterns/c.md": (
                b"---\ncatalog_type: unknown\ndoc_role: unknown\nindexable: false\n"
                b"indexed: null\n---\nbody\n"
            ),
        })
        report = apply_run4(vault)
        report_path = vault.out / "applied.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = census.check_writes(vault.root, [report_path])
        assert result["checked"] == 3 and result["mismatches"] == 0
        assert result["scope_a_missing_fields"] == 0

    def test_check_writes_counts_notes_still_missing_a_field_before_apply(
        self, vault: Vault
    ) -> None:
        vault.seed({
            "04-education/a.md": tags_only(),
            "04-education/b.md": b"plain\n",
            "00-landing/c.md": b"outside\n",
            "memory/m.md": b"skipped\n",
        })
        report_path = vault.out / "preview.json"
        report_path.write_text(json.dumps(preview(vault)), encoding="utf-8")
        result = census.check_writes(vault.root, [report_path])
        assert result["scope_a_missing_fields"] == 2
        assert result["mismatch_codes"] == {"FIELD_MISSING": 1, "NO_FRONTMATTER": 1}

    def test_check_writes_flags_a_note_that_differs_from_the_folder_row(
        self, vault: Vault
    ) -> None:
        rel = "03-knowledge-base/learnings/s.md"
        vault.seed({rel: tags_only()})
        report_path = vault.out / "applied.json"
        report_path.write_text(json.dumps(apply_run4(vault)), encoding="utf-8")
        vault.write(rel, vault.read(rel).replace(b"doc_role: learning", b"doc_role: review"))
        result = census.check_writes(vault.root, [report_path])
        assert result["mismatch_codes"] == {"TRIPLE_DIFFERS": 1}
        assert result["mismatch_paths"] == [rel]

    def test_an_old_style_report_still_has_no_row_outside_tickets(self, vault: Vault) -> None:
        rel = "04-education/e.md"
        vault.seed({rel: tags_only()})
        apply_run4(vault)
        old_style = {"mode": "preview", "writes": [{"path": rel, "class": "add"}]}
        report_path = vault.out / "old.json"
        report_path.write_text(json.dumps(old_style), encoding="utf-8")
        result = census.check_writes(vault.root, [report_path])
        assert result["mismatch_codes"] == {"NO_KIND_ROW": 1}
        assert "scope_a_missing_fields" not in result

    def test_the_census_default_walk_is_unchanged(self, vault: Vault) -> None:
        vault.seed({"memory/m.md": tags_only(), "04-education/e.md": tags_only()})
        assert list(census.iter_vault_files(vault.root)) == ["04-education/e.md"]
        both = census.iter_vault_files(vault.root, census.RUN4_EXCLUDED_PATH_PREFIXES)
        assert list(both) == ["04-education/e.md"]


REGRESSION_NOTES: Dict[str, bytes] = {
    "02-tickets/T-900/T-900-state.md": b"---\nstatus: ACTIVE\n---\nbody\n",
    "02-tickets/T-900/spec.md": b"---\ndoc_type: ticket_spec\n---\nbody\n",
    "02-tickets/T-900/notes.md": b"no block\n",
    "02-tickets/T-900/design.md": (
        b"---\ncatalog_type: unknown\ndoc_role: unknown\nindexable: false\nindexed: null\n---\nb\n"
    ),
    "02-tickets/T-901/T-901-state.md": (
        b"---\nstatus: cancelled\ncatalog_type: ticket\ndoc_role: state\nindexable: true\n"
        b"indexed: null\n---\nb\n"
    ),
    "03-knowledge-base/decisions/d.md": b"---\ndoc_type: decision\n---\nbody\n",
    "memory/m.md": b"---\ndoc_type: decision\n---\nbody\n",
}
REGRESSION_MODES: List[Optional[int]] = [None, 1, 2, 3]
# Source: the tool at the commit before the earlier change, run once over REGRESSION_NOTES in a clean git vault.
REGRESSION_EXPECTED: Dict[str, Any] = {'1': {'by_class': {'add': 2, 'create': 0, 'flip': 1, 'rewrite': 0},
       'by_kind': {'K2': {'add': 1, 'create': 0, 'flip': 1, 'rewrite': 0},
                   'K5': {'add': 1, 'create': 0, 'flip': 0, 'rewrite': 0}},
       'complete_differs': [],
       'counts': {'already_complete': 1,
                  'changed': 1,
                  'classified': 4,
                  'not_target': 2,
                  'result_false': 1,
                  'result_true': 2,
                  'scanned': 6,
                  'skipped': 0,
                  'written': 2},
       'dispositions': {},
       'exclusions': ['memory/'],
       'flips_by_status': {'cancelled': 1},
       'mode': 'preview',
       'not_labeled': ['05-conversations', '06-chat-threads'],
       'run': 1,
       'skipped': [],
       'skipped_by_reason': {},
       'tree': {'clean': True, 'dirty_count': 0},
       'writes': [{'added': {'catalog_type': 'ticket',
                             'doc_role': 'state',
                             'indexable': True,
                             'indexed': None},
                   'changes': [],
                   'class': 'add',
                   'kind': 'K2',
                   'path': '02-tickets/T-900/T-900-state.md'},
                  {'added': {'catalog_type': 'ticket',
                             'doc_role': 'spec',
                             'indexable': True,
                             'indexed': None},
                   'changes': [],
                   'class': 'add',
                   'kind': 'K5',
                   'path': '02-tickets/T-900/spec.md'},
                  {'added': {},
                   'changes': [['indexable', 'true', 'false']],
                   'class': 'flip',
                   'kind': 'K2',
                   'path': '02-tickets/T-901/T-901-state.md'}]},
 '2': {'by_class': {'add': 0, 'create': 1, 'flip': 0, 'rewrite': 0},
       'by_kind': {'K13': {'add': 0, 'create': 1, 'flip': 0, 'rewrite': 0}},
       'complete_differs': [],
       'counts': {'already_complete': 2,
                  'changed': 0,
                  'classified': 3,
                  'not_target': 3,
                  'result_false': 0,
                  'result_true': 1,
                  'scanned': 6,
                  'skipped': 0,
                  'written': 1},
       'dispositions': {},
       'exclusions': ['memory/'],
       'flips_by_status': {},
       'mode': 'preview',
       'not_labeled': ['05-conversations', '06-chat-threads'],
       'run': 2,
       'skipped': [],
       'skipped_by_reason': {},
       'tree': {'clean': True, 'dirty_count': 0},
       'writes': [{'added': {'catalog_type': 'ticket',
                             'doc_role': 'reference',
                             'indexable': True,
                             'indexed': None},
                   'changes': [],
                   'class': 'create',
                   'kind': 'K13',
                   'path': '02-tickets/T-900/notes.md'}]},
 '3': {'by_class': {'add': 0, 'create': 0, 'flip': 0, 'rewrite': 1},
       'by_kind': {'K6': {'add': 0, 'create': 0, 'flip': 0, 'rewrite': 1}},
       'complete_differs': [],
       'counts': {'already_complete': 1,
                  'changed': 1,
                  'classified': 2,
                  'not_target': 4,
                  'result_false': 0,
                  'result_true': 1,
                  'scanned': 6,
                  'skipped': 0,
                  'written': 0},
       'dispositions': {'none': {'left': 0, 'resolved': 1}},
       'exclusions': ['memory/'],
       'flips_by_status': {},
       'mode': 'preview',
       'not_labeled': ['05-conversations', '06-chat-threads'],
       'run': 3,
       'skipped': [],
       'skipped_by_reason': {},
       'tree': {'clean': True, 'dirty_count': 0},
       'writes': [{'added': {},
                   'changes': [['catalog_type', 'unknown', 'ticket'],
                               ['doc_role', 'unknown', 'design'],
                               ['indexable', 'false', 'true']],
                   'class': 'rewrite',
                   'kind': 'K6',
                   'path': '02-tickets/T-900/design.md'}]},
 'None': {'counts': {'already_complete': 1,
                     'classified': 4,
                     'needing_fields': 3,
                     'not_target': 2,
                     'scanned': 6,
                     'skipped': 0,
                     'writes_indexable': 3,
                     'written': 3},
          'exclusions': ['memory/'],
          'mode': 'preview',
          'rows': {'1': 2, '2': 2, '3': 0, '4': 0},
          'skipped': [],
          'skipped_by_reason': {},
          'unmapped_doc_types': {},
          'writes': [{'added': {'catalog_type': 'ticket',
                                'doc_role': 'state',
                                'indexable': True,
                                'indexed': None},
                      'path': '02-tickets/T-900/T-900-state.md'},
                     {'added': {'catalog_type': 'ticket',
                                'doc_role': 'spec',
                                'indexable': True,
                                'indexed': None},
                      'path': '02-tickets/T-900/spec.md'},
                     {'added': {'catalog_type': 'knowledge',
                                'doc_role': 'decision',
                                'indexable': True,
                                'indexed': None},
                      'path': '03-knowledge-base/decisions/d.md'}]}}


class TestRun4Regression:
    @pytest.mark.parametrize("mode", REGRESSION_MODES)
    def test_the_s257_mode_and_runs_1_to_3_report_as_before(
        self, vault: Vault, capsys: pytest.CaptureFixture, mode: Optional[int]
    ) -> None:
        vault.seed(REGRESSION_NOTES)
        args = ["--vault-root", str(vault.root)]
        if mode is not None:
            args += ["--run", str(mode)]
        assert tool.main(args) == 0
        got = json.loads(capsys.readouterr().out)
        assert got == REGRESSION_EXPECTED[str(mode)]


class TestRun4Standards:
    @pytest.mark.parametrize("path", [TOOL_PATH, CENSUS_PATH])
    def test_the_modules_import_only_the_allowlist(self, path: Path) -> None:
        allowed = {
            "argparse", "dataclasses", "json", "logging", "os", "pathlib", "re", "shutil",
            "subprocess", "sys", "tempfile", "typing", "yaml", "core",
        }
        forbidden = (
            "socket", "ssl", "http", "urllib", "requests", "httpx", "anthropic", "openai",
            "torch", "transformers", "chromadb", "sentence_transformers", "ollama",
        )
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: List[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                assert root in allowed and root not in forbidden, name

    @pytest.mark.parametrize("path", [TOOL_PATH, CENSUS_PATH])
    def test_every_function_has_hints_and_fits_the_line_limit(self, path: Path) -> None:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            assert node.returns is not None, node.name
            for arg in node.args.args + node.args.kwonlyargs:
                assert arg.arg == "self" or arg.annotation is not None, node.name
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            assert length <= MAX_FUNCTION_LINES, node.name

    def test_the_new_test_file_has_a_header(self) -> None:
        head = Path(__file__).read_text(encoding="utf-8").splitlines()[:25]
        for label in ("# Module:", "# Description:", "# Author:", "# Date:", "# Scope:",
                      "# ChangeLog:"):
            assert any(line.startswith(label) for line in head), label

