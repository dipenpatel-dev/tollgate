# Module:      test_plane_vault_files.py
# Description: Tests for vault_ticket_files and plane_sync_ledger over temporary folders.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import json
import tempfile
import unittest
from pathlib import Path

from connectors.plane.plane_sync_ledger import PlaneSyncLedgerError, SyncLedger, ledger_path, load_ledger, save_ledger
from connectors.plane.plane_sync_settings import PrefixRow
from connectors.plane.vault_ticket_files import (
    VaultFolderExistsError, VaultTicketError, format_ticket_id, highest_local_ticket_number,
    normalize_status_word, parse_state_text, read_state_file, render_initial_state_file,
    session_log_files, ticket_folder, write_new_ticket_folder,
)
from plane_sync_test_support import read_template

ROW = PrefixRow("T", r"^T-(\d+)$", 1)
RENDER = dict(priority="P2", scope="scripts", repo="demo-repo", work_type="feature", today="2026-01-02")


class TestVaultFiles(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_highest_local_number_ignores_other_names_and_files(self) -> None:
        base = self.root / "tickets"
        for name in ("T-3", "T-12", "T-9", "notes", "T-x", "ZZ-99"):
            (base / name).mkdir(parents=True)
        (base / "T-500").write_text("a file, not a folder")
        self.assertEqual(highest_local_ticket_number(ROW, self.root / "tickets"), 12)

    def test_highest_is_zero_for_no_folder_or_no_match(self) -> None:
        self.assertEqual(highest_local_ticket_number(ROW, self.root / "tickets"), 0)
        (self.root / "tickets").mkdir(parents=True)
        self.assertEqual(highest_local_ticket_number(ROW, self.root / "tickets"), 0)

    def test_format_ticket_id_pads_to_width(self) -> None:
        self.assertEqual(format_ticket_id("T", 7, ROW), "T-7")
        self.assertEqual(format_ticket_id("T", 7, PrefixRow("T", "y", 3)), "T-007")
        self.assertEqual(ticket_folder("T-7", self.root), self.root / "T-7")

    def test_highest_local_number_counts_flat_and_nested_tickets(self) -> None:
        base = self.root / "tickets"
        for name in ("T-3", "T/T-40", "t/T-41", "T/notes", "Z/T-99", "T/T-x"):
            (base / name).mkdir(parents=True)
        self.assertEqual(highest_local_ticket_number(ROW, base), 41)

    def test_ticket_folder_finds_a_nested_ticket(self) -> None:
        base = self.root / "tickets"
        (base / "T" / "T-7").mkdir(parents=True)
        self.assertEqual(ticket_folder("T-7", base), base / "T" / "T-7")

    def test_a_new_ticket_goes_under_an_existing_prefix_folder_else_flat(self) -> None:
        base = self.root / "tickets"
        (base / "T").mkdir(parents=True)
        self.assertEqual(ticket_folder("T-8", base), base / "T" / "T-8")
        self.assertEqual(ticket_folder("Q-1", base), base / "Q-1")

    def test_write_new_ticket_folder_works_under_a_prefix_folder(self) -> None:
        base = self.root / "tickets"
        (base / "T").mkdir(parents=True)
        path = write_new_ticket_folder(ticket_folder("T-9", base), "x", "T-9")
        self.assertEqual(path, base / "T" / "T-9" / "T-9-state.md")

    def test_normalize_status_word(self) -> None:
        self.assertEqual(normalize_status_word("SPEC_APPROVED"), "SPEC_APPROVED")
        self.assertEqual(normalize_status_word("  Spec approved (2026-01-02)"), "SPEC_APPROVED")
        self.assertEqual(normalize_status_word("QA-APPROVED - by someone"), "QA_APPROVED")
        self.assertEqual(normalize_status_word("done"), "DONE")

    def test_parse_state_text_reads_title_status_and_body(self) -> None:
        text = '---\ntitle: "T: one"\nstatus: BACKLOG\nticket: T-1\n---\n# body\nline\n'
        state = parse_state_text(text, "x.md")
        self.assertEqual((state.title, state.status_word, state.ticket_id), ("T: one", "BACKLOG", "T-1"))
        self.assertEqual(state.body_text, "# body\nline\n")
        self.assertEqual(state.raw_text, text)

    def test_parse_state_text_errors_name_source_and_key(self) -> None:
        with self.assertRaises(VaultTicketError) as no_front:
            parse_state_text("no frontmatter", "a.md")
        self.assertIn("a.md", str(no_front.exception))
        with self.assertRaises(VaultTicketError) as no_title:
            parse_state_text("---\nstatus: X\n---\n", "b.md")
        self.assertIn("b.md", str(no_title.exception))
        self.assertIn("title", str(no_title.exception))
        with self.assertRaises(VaultTicketError):
            parse_state_text("---\ntitle: 5\nstatus: X\n---\n", "c.md")

    def test_title_with_colon_and_quote_is_stored_and_read_back_equal(self) -> None:
        title = 'Fix "quote": colon, and # hash \\ slash'
        text = render_initial_state_file(read_template(), ticket_id="T-9", title=title, **RENDER)
        self.assertEqual(parse_state_text(text, "n.md").title, title)

    def test_rendered_state_file_has_every_template_key(self) -> None:
        text = render_initial_state_file(read_template(), ticket_id="T-9", title="T", **RENDER)
        state = parse_state_text(text, "n.md")
        self.assertEqual((state.ticket_id, state.status_word), ("T-9", "BACKLOG"))
        for key in ("doc_type: ticket_state", "type: ticket_state", "task_type: feature", "priority: P2",
                    "opened: 2026-01-02", "last_updated: 2026-01-02", 
                    "catalog_type: ticket", "doc_role: state", "indexable: true"):
            self.assertIn(key, text)
        for heading in ("## Current state", "## Scope", "## Why", "## Decisions",
                        "## Noticed not done", "## Status history"):
            self.assertIn(heading, text)

    def test_unknown_placeholder_and_unsafe_word_raise(self) -> None:
        with self.assertRaises(VaultTicketError):
            render_initial_state_file("{surprise}", ticket_id="T-9", title="T", **RENDER)
        with self.assertRaises(VaultTicketError):
            render_initial_state_file("{title}", ticket_id="T-9", title="T", **{**RENDER, "priority": "P2\nx: y"})

    def test_braces_in_a_title_do_not_trigger_the_placeholder_check(self) -> None:
        text = render_initial_state_file(read_template(), ticket_id="T-9", title="use {title} here", **RENDER)
        self.assertEqual(parse_state_text(text, "n.md").title, "use {title} here")

    def test_write_new_ticket_folder_is_create_only(self) -> None:
        folder = self.root / "tickets" / "T-4"
        path = write_new_ticket_folder(folder, "first", "T-4")
        self.assertEqual(path.name, "T-4-state.md")
        with self.assertRaises(VaultFolderExistsError):
            write_new_ticket_folder(folder, "second", "T-4")
        self.assertEqual(path.read_text(), "first")

    def test_read_state_file_and_missing_file(self) -> None:
        folder = self.root / "tickets" / "T-4"
        write_new_ticket_folder(folder, '---\ntitle: "T"\nstatus: BACKLOG\n---\nbody', "T-4")
        self.assertEqual(read_state_file(folder, "T-4").title, "T")
        with self.assertRaises(VaultTicketError) as caught:
            read_state_file(folder, "T-5")
        self.assertIn("T-5-state.md", str(caught.exception))

    def test_session_log_files_sorted_by_name(self) -> None:
        folder = self.root / "T-4"
        folder.mkdir()
        for name in ("T-4-session-2026-01-03.md", "T-4-session-2026-01-02.md", "T-4-state.md", "T-4-spec.md"):
            (folder / name).write_text("x")
        names = [p.name for p in session_log_files(folder, "T-4")]
        self.assertEqual(names, ["T-4-session-2026-01-02.md", "T-4-session-2026-01-03.md"])
        self.assertEqual(session_log_files(self.root / "none", "T-4"), [])

    def test_status_line_in_the_body_is_used_when_the_frontmatter_has_none(self) -> None:
        text = "---\ntitle: Plain\n---\n# body\nStatus: DESIGN_APPROVED\n"
        self.assertEqual(parse_state_text(text, "x.md").status_word, "DESIGN_APPROVED")

    def test_a_status_line_inside_a_code_fence_does_not_count(self) -> None:
        text = "---\ntitle: Plain\n---\n```\nStatus: FAKE\n```\n"
        with self.assertRaises(VaultTicketError):
            parse_state_text(text, "x.md")

    def test_frontmatter_status_wins_over_the_body_line(self) -> None:
        text = "---\ntitle: Plain\nstatus: SPEC_APPROVED\n---\nStatus: OTHER\n"
        self.assertEqual(parse_state_text(text, "x.md").status_word, "SPEC_APPROVED")

    def test_a_broken_frontmatter_line_is_an_error_naming_the_file(self) -> None:
        with self.assertRaises(VaultTicketError) as caught:
            parse_state_text("---\nthis is not a key\n---\n", "z.md")
        self.assertIn("z.md", str(caught.exception))

    def test_the_ticket_folder_is_the_tickets_folder_then_the_key(self) -> None:
        folder = ticket_folder("T-7", self.root)
        self.assertEqual(folder.name, "T-7")
        path = write_new_ticket_folder(folder, "x", "T-7")
        self.assertEqual(path, folder / "T-7-state.md")


class TestLedger(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name)
        self.path = ledger_path(self.state, "T-4")
        self.ledger = SyncLedger("T-4", "proj", "wi-4", 4, None, "BACKLOG", {"a.md": 3}, ["k1"])

    def test_path_is_under_output_ticket_folder(self) -> None:
        self.assertEqual(self.path, self.state / "T-4" / "plane_sync_ledger.json")

    def test_absent_ledger_loads_as_none(self) -> None:
        self.assertIsNone(load_ledger(self.path))

    def test_round_trip_and_overwrite_leaves_no_temp_file(self) -> None:
        save_ledger(self.path, self.ledger)
        self.assertEqual(load_ledger(self.path), self.ledger)
        self.ledger.description_sha = "abc123abc123"
        save_ledger(self.path, self.ledger)
        self.assertEqual(load_ledger(self.path).description_sha, "abc123abc123")
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["plane_sync_ledger.json"])

    def test_invalid_json_raises_and_leaves_file_untouched(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(PlaneSyncLedgerError):
            load_ledger(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{not json")

    def test_missing_key_and_wrong_type_raise(self) -> None:
        self.path.parent.mkdir(parents=True)
        data = {"ticket_id": "T-4", "project_id": "p", "work_item_id": "w", "number": 4,
                "description_sha": None, "status_word": None, "session_offsets": {}, "posted_keys": []}
        broken = {k: v for k, v in data.items() if k != "posted_keys"}
        self.path.write_text(json.dumps(broken), encoding="utf-8")
        with self.assertRaises(PlaneSyncLedgerError) as missing:
            load_ledger(self.path)
        self.assertIn("posted_keys", str(missing.exception))
        self.path.write_text(json.dumps({**data, "number": "four"}), encoding="utf-8")
        with self.assertRaises(PlaneSyncLedgerError):
            load_ledger(self.path)


if __name__ == "__main__":
    unittest.main()
