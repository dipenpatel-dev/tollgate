# Module:      test_plane_drift.py
# Description: Tests for the drift command: a clean ticket prints nothing, each mismatch kind prints its own line.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import dataclasses
import unittest

from connectors.plane.plane_drift_checker import run_drift
from plane_sync_test_support import FAKE_TOKEN, SYNC_TICKET, CliCase, SyncTestCase

LOCAL_ONLY_TICKET = "T-4"


class TestDrift(SyncTestCase):
    def drift(self, *ticket_ids: str) -> int:
        self.lines = []
        return run_drift(self.settings, self.client, self.tickets, ticket_ids=ticket_ids or [SYNC_TICKET],
                         emit=self.lines.append)

    def test_a_clean_ticket_prints_nothing_and_exits_0(self) -> None:
        self.sync()
        self.assertEqual(self.drift(), 0)
        self.assertEqual(self.lines, [])

    def test_a_card_missing_for_the_id(self) -> None:
        self.stub.state.items[:] = [i for i in self.stub.state.items if i.number != 5]
        self.assertEqual(self.drift(), 2)
        self.assertEqual(self.lines, ["missing_card | T-5 | no card with that id"])

    def test_wrong_number(self) -> None:
        self.sync()
        self.card().number = 9
        self.assertEqual(self.drift(), 2)
        self.assertEqual(self.lines, ["wrong_number | T-5 | card 9 vault 5"])

    def test_wrong_name(self) -> None:
        self.sync()
        self.card().name = "Other name"
        self.assertEqual(self.drift(), 2)
        self.assertEqual(self.lines, ['wrong_name | T-5 | card "Other name" vault "Sync ticket"'])

    def test_wrong_description_after_the_file_changed(self) -> None:
        self.sync()
        self.write_state(body="## Current state\nChanged after sync.\n")
        self.assertEqual(self.drift(), 2)
        self.assertEqual(len(self.lines), 1)
        self.assertRegex(self.lines[0], r"^wrong_description \| T-5 \| card [0-9a-f]{12} file [0-9a-f]{12}$")

    def test_a_description_with_no_sha_line_is_wrong_not_a_pass(self) -> None:
        self.sync()
        self.card().description_html = "<p>hand written</p>"
        self.assertEqual(self.drift(), 2)
        self.assertRegex(self.lines[0], r"^wrong_description \| T-5 \| card none file [0-9a-f]{12}$")

    def test_the_last_sha_line_counts(self) -> None:
        self.sync()
        self.card().description_html = "<p>state-sha: 000000000000</p>" + self.card().description_html
        self.assertEqual(self.drift(), 0)

    def test_an_unreadable_description_is_never_a_silent_pass(self) -> None:
        self.card().name = "Sync ticket"
        self.assertEqual(self.drift(), 2)
        self.assertEqual(self.lines, ["description_unreadable | T-5 | the read returned no description"])

    def test_several_ids_and_one_list_call_per_project(self) -> None:
        self.write_file_for_other_ticket()
        self.sync()
        self.stub.state.calls.clear()
        self.assertEqual(self.drift(SYNC_TICKET, LOCAL_ONLY_TICKET), 2)
        self.assertEqual(len(self.stub.calls_matching("GET", "/projects/proj-t/work-items/")), 1)
        self.assertEqual(self.lines[0].split(" | ")[:2], ["description_unreadable", "T-4"])

    def write_file_for_other_ticket(self) -> None:
        folder = self.tickets / LOCAL_ONLY_TICKET
        (folder / "T-4-state.md").write_text("---\ntitle: old 4\nstatus: SHIPPED\n---\nbody\n", encoding="utf-8")

    def test_unmapped_prefix_is_skipped(self) -> None:
        self.assertEqual(self.drift("zz-3"), 0)
        self.assertEqual(self.lines, ["skip | prefix zz has no Plane project in the settings"])

    def test_drift_sends_no_write_call(self) -> None:
        self.sync()
        self.stub.state.calls.clear()
        self.drift()
        self.assertEqual([c for c in self.stub.state.calls if c.method != "GET"], [])

    def test_unknown_project_reports_a_missing_card(self) -> None:
        row = dataclasses.replace(self.settings.prefix_table["T"], project_key="NOPE")
        settings = dataclasses.replace(self.settings, prefix_table={"T": row})
        self.lines = []
        code = run_drift(settings, self.client, self.tickets, ticket_ids=[SYNC_TICKET], emit=self.lines.append)
        self.assertEqual((code, self.lines), (2, ["missing_card | T-5 | no card with that id"]))


class TestDriftCli(CliCase):
    def test_drift_through_the_cli(self) -> None:
        self.sync()
        self.assertEqual(self.run_cli(["drift", SYNC_TICKET]), 0)
        self.assertEqual(self.lines, [])
        self.write_state(body="## Current state\nEdited.\n")
        self.assertEqual(self.run_cli(["drift", SYNC_TICKET]), 2)
        self.assertNotIn(FAKE_TOKEN, "".join(self.lines))


if __name__ == "__main__":
    unittest.main()
