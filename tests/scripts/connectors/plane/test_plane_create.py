# Module:      test_plane_create.py
# Description: Tests for the create command against the stub: card first, number guard, stop without retry, adopt on re-run.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import dataclasses
import unittest
from unittest import mock

from connectors.plane.plane_sync_ledger import ledger_path, load_ledger
from connectors.plane.plane_work_item_client import PlaneApiError
from connectors.plane.vault_ticket_creator import run_create
from connectors.plane.vault_ticket_files import VaultTicketError, parse_state_text, read_state_file
from plane_stub_server import FailRule, StubItem
from plane_sync_test_support import StubTestCase, read_template, make_settings


class TestCreate(StubTestCase):
    def _create(self, **overrides: str) -> int:
        args = {**self.create_args(), **overrides}
        return run_create(self.settings, self.client, self.tickets, self.state,
                          emit=self.lines.append, template_text=read_template(), **args)

    def _posts(self) -> int:
        return len(self.stub.calls_matching("POST", "/work-items/"))

    def test_calls_run_in_order_then_files(self) -> None:
        self.assertEqual(self._create(), 0)
        order = [(c.method, c.path.split("/", 5)[-1]) for c in self.stub.state.calls]
        self.assertEqual(order, [
            ("GET", "projects/"),
            ("GET", "projects/proj-t/work-items/"),
            ("GET", "projects/proj-t/states/"),
            ("POST", "projects/proj-t/work-items/"),
            ("PATCH", "projects/proj-t/work-items/wi-6/"),
        ])
        self.assertEqual(self.lines, ["created | T-6 | card 6"])

    def test_card_is_created_before_any_file_exists(self) -> None:
        seen: list[list[str]] = []
        self.stub.state.on_create = lambda: seen.append(self.folder_names())
        self.assertEqual(self._create(), 0)
        self.assertEqual(seen, [["T-1", "T-2", "T-3", "T-4", "T-5"]])
        self.assertIn("T-6", self.folder_names())

    def test_number_folder_state_file_and_card_agree(self) -> None:
        self._create(title="Card name")
        folder = self.tickets / "T-6"
        state = read_state_file(folder, "T-6")
        card = self.stub.state.items[-1]
        self.assertEqual((state.ticket_id, state.title), ("T-6", "Card name"))
        self.assertEqual((card.external_id, card.name, card.number), ("T-6", "Card name", 6))
        patch = self.stub.calls_matching("PATCH", "/wi-6/")[0].body
        self.assertEqual(patch, {"external_id": "T-6", "external_source": "tollgate"})
        self.assertEqual(self.stub.calls_matching("POST", "/work-items/")[0].body,
                         {"name": "Card name", "state": "st-backlog"})

    def test_ledger_is_saved_with_card_ids(self) -> None:
        self._create()
        ledger = load_ledger(ledger_path(self.state, "T-6"))
        self.assertEqual((ledger.work_item_id, ledger.number, ledger.status_word), ("wi-6", 6, "BACKLOG"))
        self.assertEqual((ledger.description_sha, ledger.session_offsets, ledger.posted_keys), (None, {}, []))

    def test_guard_mismatch_sends_no_create_and_names_both_numbers(self) -> None:
        self.stub.state.items.append(StubItem("wi-7", 7, "extra", "T-7"))
        self.assertEqual(self._create(), 2)
        self.assertEqual(self._posts(), 0)
        self.assertEqual(self.lines, ["stopped | Plane highest 7, local highest 5"])
        self.assertEqual(self.folder_names(), [f"T-{n}" for n in range(1, 6)])

    def test_plane_behind_local_also_stops(self) -> None:
        self.stub.state.items.pop()
        self.assertEqual(self._create(), 2)
        self.assertEqual(self._posts(), 0)
        self.assertIn("Plane highest 4, local highest 5", self.lines[0])

    def test_unreachable_plane_writes_nothing(self) -> None:
        self.stub.stop()
        with self.assertRaises(PlaneApiError):
            run_create(self.settings, self.client, self.tickets, self.state,
                       emit=self.lines.append, template_text=read_template(), **self.create_args())
        self.assertEqual(self.folder_names(), [f"T-{n}" for n in range(1, 6)])
        self.assertFalse(self.state.exists())

    def test_create_500_is_not_retried_and_writes_nothing(self) -> None:
        self.stub.state.fail_rules.append(FailRule("POST", "/work-items/", 500))
        with self.assertRaises(PlaneApiError):
            self._create()
        self.assertEqual(self._posts(), 1)
        self.assertEqual(self.folder_names(), [f"T-{n}" for n in range(1, 6)])

    def test_failed_external_id_update_then_rerun_adopts_the_card(self) -> None:
        self.stub.state.fail_rules.append(FailRule("PATCH", "/wi-6/", 500, remaining=1))
        with self.assertRaises(PlaneApiError):
            self._create()
        self.assertEqual(self.folder_names(), [f"T-{n}" for n in range(1, 6)])
        self.assertEqual(self._create(), 0)
        self.assertEqual(self._posts(), 1)
        self.assertEqual(self.stub.state.items[-1].external_id, "T-6")
        self.assertIn("T-6", self.folder_names())

    def test_failed_folder_write_then_rerun_adopts_and_writes_the_folder(self) -> None:
        with mock.patch("connectors.plane.vault_ticket_creator.write_new_ticket_folder",
                        side_effect=VaultTicketError("state file for T-6 cannot be written")):
            self.assertEqual(self._create(), 2)
        self.assertEqual(self.lines[-1], "stopped | state file for T-6 cannot be written; card 6 kept")
        self.assertEqual(self.stub.state.items[-1].external_id, "T-6")
        self.assertEqual(self._create(), 0)
        self.assertEqual(self._posts(), 1)
        self.assertEqual(read_state_file(self.tickets / "T-6", "T-6").title, "A new ticket")

    def test_second_create_after_success_makes_the_next_card(self) -> None:
        self.assertEqual(self._create(), 0)
        self.assertEqual(self._create(), 0)
        self.assertEqual(self._posts(), 2)
        self.assertIn("T-7", self.folder_names())

    def test_existing_folder_stops_naming_the_card_and_overwrites_nothing(self) -> None:
        folder = self.tickets / "T-6"
        folder.mkdir()
        (folder / "keep.md").write_text("mine")
        self.assertEqual(self._create(), 2)
        self.assertEqual(self.lines, ["stopped | Plane highest 5, local highest 6"])
        self.assertEqual((folder / "keep.md").read_text(), "mine")

    def test_existing_folder_for_an_adopted_card_is_named(self) -> None:
        self.stub.state.items.append(StubItem("wi-6", 6, "A new ticket", None))
        with mock.patch("connectors.plane.vault_ticket_creator.highest_local_ticket_number", return_value=5):
            folder = self.tickets / "T-6"
            folder.mkdir()
            self.assertEqual(self._create(), 2)
        self.assertEqual(self.lines, ["stopped | folder for T-6 exists; card 6 kept"])
        self.assertEqual(self._posts(), 0)

    def test_two_matching_cards_stop_and_list_numbers(self) -> None:
        self.stub.state.items.append(StubItem("wi-6", 6, "A new ticket", None))
        self.stub.state.items.append(StubItem("wi-7", 7, "A new ticket", None))
        self.assertEqual(self._create(), 2)
        self.assertEqual(self.lines, ["stopped | several cards match the title: 6, 7"])
        self.assertEqual(self._posts(), 0)

    def test_matching_card_that_is_not_the_next_number_stops(self) -> None:
        self.stub.state.items.append(StubItem("wi-6", 6, "A new ticket", None))
        self.stub.state.items.append(StubItem("wi-7", 7, "other", "T-7"))
        self.assertEqual(self._create(), 2)
        self.assertIn("card 6 matches the title but Plane highest 7, local highest 5", self.lines[0])

    def test_unmapped_prefix_prints_skip_line_exit_2_and_makes_no_call(self) -> None:
        self.assertEqual(self._create(prefix="zz"), 2)
        self.assertEqual(self.lines, ["skip | prefix zz has no Plane project in the settings"])
        self.assertEqual(self.stub.state.calls, [])

    def test_title_with_colon_and_quote_survives_and_check_runs_before_any_card(self) -> None:
        title = 'Fix: the "quoted" thing'
        self.assertEqual(self._create(title=title), 0)
        self.assertEqual(read_state_file(self.tickets / "T-6", "T-6").title, title)
        self.assertEqual(self.stub.state.items[-1].name, title)

    def test_title_that_cannot_be_stored_makes_no_plane_call(self) -> None:
        self.assertEqual(self._create(title="x" * 256), 2)
        self.assertIn("title cannot be stored", self.lines[0])
        self.assertEqual(self._create(priority="P2\nbad: key"), 2)
        self.assertEqual(self.stub.state.calls, [])

    def test_missing_board_status_stops_before_create(self) -> None:
        settings = dataclasses.replace(make_settings(), new_ticket_board_status="Nowhere")
        code = run_create(settings, self.client, self.tickets, self.state, emit=self.lines.append,
                          template_text=read_template(), **self.create_args())
        self.assertEqual(code, 2)
        self.assertEqual(self.lines, ["stopped | board status Nowhere not found"])
        self.assertEqual(self._posts(), 0)

    def test_state_file_text_for_new_ticket_parses(self) -> None:
        self._create()
        text = (self.tickets / "T-6" / "T-6-state.md").read_text(encoding="utf-8")
        self.assertEqual(parse_state_text(text, "x").status_word, "BACKLOG")


if __name__ == "__main__":
    unittest.main()
