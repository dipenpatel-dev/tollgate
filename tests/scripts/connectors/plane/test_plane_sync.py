# Module:      test_plane_sync.py
# Description: Tests for the sync command: description, status, comments, extras, cut, secrets, first sync and the cli.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import contextlib
import dataclasses
import io
import json
import unittest

from connectors.plane.plane_comment_builder import comment_key
from connectors.plane.plane_sync_ledger import PlaneSyncLedgerError, ledger_path, load_ledger, save_ledger
from connectors.plane.plane_ticket_syncer import run_sync
from connectors.plane.plane_work_item_client import PlaneApiError
from plane_stub_server import FailRule
from plane_sync_test_support import FAKE_TOKEN, STATE_BODY, SYNC_TICKET, CliCase, SyncTestCase, state_text

SPEC = "## Requirements\nR-01 first requirement\n\n## Acceptance Criteria\nAC-01 first criterion\n\n## Budget\nx\n"
DESIGN = "## Implementation Plan\n\n```mermaid\nflowchart TD\n    start --> finish\n```\n"
SESSION = "Done: wrote the thing.\n"


def sha_of(text: str) -> str:
    return comment_key(text)


class TestDescription(SyncTestCase):
    def test_first_sync_sends_one_update_ending_with_the_sha_line(self) -> None:
        self.assertEqual(self.sync(), 0)
        updates = self.patches("description_html")
        self.assertEqual(len(updates), 1)
        expected_sha = sha_of(state_text())
        self.assertTrue(updates[0]["description_html"].endswith(f"<p>state-sha: {expected_sha}</p>"))
        self.assertEqual(updates[0]["name"], "Sync ticket")
        self.assertIn("description=updated", self.lines[-1])
        self.assertIn("first_sync=yes", self.lines[-1])

    def test_same_file_sends_zero_updates_the_second_time(self) -> None:
        self.sync()
        before = len(self.stub.state.calls)
        self.assertEqual(self.sync(), 0)
        writes = [c for c in self.stub.state.calls[before:] if c.method != "GET"]
        self.assertEqual(writes, [])
        self.assertIn("description=same", self.lines[-1])

    def test_a_changed_file_sends_one_update(self) -> None:
        self.sync()
        self.write_state(body=STATE_BODY + "More text.\n")
        self.sync()
        self.assertEqual(len(self.patches("description_html")), 2)
        self.assertIn("More text.", self.card().description_html)

    def test_raw_html_in_the_body_is_shown_as_text(self) -> None:
        self.write_state(body="## Current state\n<script>alert(1)</script>\n")
        self.sync()
        self.assertNotIn("<script>", self.card().description_html)

    def test_secret_in_the_state_body_sends_nothing(self) -> None:
        self.write_state(body=f"## Current state\nkey {FAKE_TOKEN}\n")
        self.assertEqual(self.sync(), 2)
        self.assertEqual(self.lines, ["stopped | secret pattern long_mixed_token in description; nothing sent"])
        self.assertEqual(self.patches(), [])
        self.assertEqual(self.comments(), [])
        self.assertNotIn(FAKE_TOKEN, "".join(self.lines))


class TestStatus(SyncTestCase):
    def test_first_sync_moves_the_card_and_posts_no_status_comment(self) -> None:
        self.sync()
        self.assertEqual(self.card().state_id, "st-ready")
        self.assertEqual(self.comments(), [])
        self.assertIn("status=moved", self.lines[-1])

    def test_first_sync_with_a_card_already_in_place_sends_no_state_update(self) -> None:
        self.card().state_id = "st-ready"
        self.sync()
        self.assertEqual(self.patches("state"), [])

    def test_unchanged_word_posts_nothing(self) -> None:
        self.sync()
        self.sync()
        self.assertEqual(len(self.patches("state")), 1)
        self.assertEqual(self.comments(), [])
        self.assertIn("status=same", self.lines[-1])

    def test_changed_word_moves_the_card_and_posts_one_comment(self) -> None:
        self.sync()
        self.write_state(status="SHIPPED")
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.card().state_id, "st-done")
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("Status: SPEC_APPROVED to SHIPPED (board: Done) (generated)", self.comments()[0]["comment_html"])
        self.sync()
        self.assertEqual(len(self.comments()), 1)

    def test_status_with_trailing_note_is_normalized(self) -> None:
        self.write_state(status="SHIPPED (pushed)")
        self.sync()
        self.assertEqual(self.card().state_id, "st-done")

    def test_unknown_word_is_named_and_the_other_steps_run(self) -> None:
        self.write_state(status="UNMAPPED_WORD")
        self.append_session(SESSION)
        self.sync()
        self.append_session("New work.\n")
        self.write_state(status="UNMAPPED_WORD", body=STATE_BODY + "Changed.\n")
        self.assertEqual(self.sync(), 2)
        self.assertIn("status=unknown:UNMAPPED_WORD", self.lines[-1])
        self.assertIn("description=updated", self.lines[-1])
        self.assertIn("comment=posted", self.lines[-1])
        self.assertEqual(self.patches("state"), [])
        self.assertEqual(self.card().state_id, "st-backlog")

    def test_blocked_word_carries_the_current_state_text(self) -> None:
        self.sync()
        self.write_state(status="QA_BLOCKED")
        self.sync()
        html = self.comments()[0]["comment_html"]
        self.assertIn("QA_BLOCKED (board: Waiting)", html)
        self.assertIn("Current state:", html)
        self.assertIn("Working on the sync step.", html)
        self.assertEqual(self.card().state_id, "st-waiting")

    def test_a_non_blocked_word_has_no_current_state_text(self) -> None:
        self.sync()
        self.write_state(status="SHIPPED")
        self.sync()
        self.assertNotIn("Current state:", self.comments()[0]["comment_html"])

    def test_secret_in_the_status_comment_sends_nothing_and_keeps_the_ledger(self) -> None:
        self.sync()
        body = f"## Current state\nblocked, key {FAKE_TOKEN}\n"
        self.write_state(status="QA_BLOCKED", body=body)
        path = ledger_path(self.state, SYNC_TICKET)
        ledger = load_ledger(path)
        ledger.description_sha = sha_of(state_text(status="QA_BLOCKED", body=body))
        save_ledger(path, ledger)
        self.stub.state.calls.clear()
        self.assertEqual(self.sync(), 2)
        self.assertEqual(self.lines, ["stopped | secret pattern long_mixed_token in status comment; nothing sent"])
        self.assertEqual([c for c in self.stub.state.calls if c.method != "GET"], [])
        self.assertEqual(load_ledger(path).status_word, "SPEC_APPROVED")
        self.assertEqual(self.card().state_id, "st-ready")

    def test_board_status_missing_in_plane_stops(self) -> None:
        settings = dataclasses.replace(self.settings, status_map={**self.settings.status_map, "SHIPPED": "Nowhere"})
        self.write_state(status="SHIPPED")
        self.assertEqual(self.sync(settings=settings), 2)
        self.assertIn("board status Nowhere not found in Plane", self.lines[0])


class TestComments(SyncTestCase):
    def test_new_text_posts_one_comment_and_a_second_run_posts_none(self) -> None:
        self.sync()
        self.append_session(SESSION)
        self.sync()
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("wrote the thing", self.comments()[0]["comment_html"])
        self.assertIn("T-5-session-2026-01-02.md", self.comments()[0]["comment_html"])
        self.assertIn("comment=posted", self.lines[-1])
        self.sync()
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("comment=none", self.lines[-1])

    def test_only_the_new_part_is_posted_next_time(self) -> None:
        self.sync()
        self.append_session(SESSION)
        self.sync()
        self.append_session("Second part.\n")
        self.sync()
        self.assertEqual(len(self.comments()), 2)
        self.assertNotIn("wrote the thing", self.comments()[1]["comment_html"])
        self.assertIn("Second part.", self.comments()[1]["comment_html"])

    def test_the_comment_carries_source_and_a_dedup_key(self) -> None:
        self.sync()
        self.append_session(SESSION)
        self.sync()
        comment = self.comments()[0]
        self.assertEqual(comment["external_source"], "tollgate")
        self.assertRegex(comment["external_id"], r"^[0-9a-f]{12}$")
        ledger = load_ledger(ledger_path(self.state, SYNC_TICKET))
        self.assertIn(comment["external_id"], ledger.posted_keys)

    def test_raw_html_in_session_text_is_shown_as_text(self) -> None:
        self.sync()
        self.append_session("see <img src=x onerror=alert(1)>\n")
        self.sync()
        self.assertNotIn("<img", self.comments()[0]["comment_html"])

    def test_first_sync_without_a_ledger_posts_no_old_text(self) -> None:
        self.append_session(SESSION)
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.comments(), [])
        self.assertIn("first_sync=yes", self.lines[-1])
        self.assertIn("comment=none", self.lines[-1])

    def test_deleted_ledger_does_not_repost_history(self) -> None:
        self.sync()
        self.append_session(SESSION)
        self.sync()
        ledger_path(self.state, SYNC_TICKET).unlink()
        self.sync()
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("first_sync=yes", self.lines[-1])

    def test_from_start_posts_existing_text_once(self) -> None:
        self.append_session(SESSION)
        self.assertEqual(self.sync(from_start=True), 0)
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("wrote the thing", self.comments()[0]["comment_html"])
        self.sync()
        self.assertEqual(len(self.comments()), 1)

    def test_from_start_is_refused_when_a_ledger_exists(self) -> None:
        self.sync()
        self.assertEqual(self.sync(from_start=True), 2)
        self.assertIn("--from-start", self.lines[0])

    def test_text_over_the_limit_is_cut_with_the_pointer(self) -> None:
        settings = dataclasses.replace(self.settings, comment_max_chars=300)
        self.sync(settings=settings)
        self.append_session("word " * 400)
        self.sync(settings=settings)
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("(cut; full text in the T-5 files in the vault)", self.comments()[0]["comment_html"])
        self.assertIn("cut=yes", self.lines[-1])
        ledger = load_ledger(ledger_path(self.state, SYNC_TICKET))
        self.assertEqual(ledger.session_offsets["T-5-session-2026-01-02.md"], len("word " * 400))
        self.sync(settings=settings)
        self.assertEqual(len(self.comments()), 1)

    def test_secret_in_the_session_text_posts_nothing_and_keeps_offsets(self) -> None:
        self.sync()
        offsets = load_ledger(ledger_path(self.state, SYNC_TICKET)).session_offsets
        self.append_session(f"token pasted: {FAKE_TOKEN}\n")
        self.assertEqual(self.sync(), 2)
        self.assertEqual(self.lines, ["stopped | secret pattern long_mixed_token in comment text; nothing posted"])
        self.assertEqual(self.comments(), [])
        self.assertEqual(load_ledger(ledger_path(self.state, SYNC_TICKET)).session_offsets, offsets)
        self.assertNotIn(FAKE_TOKEN, "".join(self.lines))

    def test_after_the_text_is_edited_out_the_next_sync_posts(self) -> None:
        self.sync()
        self.append_session(f"token pasted: {FAKE_TOKEN}\n")
        self.sync()
        (self.folder / "T-5-session-2026-01-02.md").write_text("Clean text now.\n", encoding="utf-8")
        self.assertEqual(self.sync(), 0)
        self.assertEqual(len(self.comments()), 1)

    def test_named_assignment_and_key_block_are_blocked_too(self) -> None:
        self.sync()
        self.append_session("password: " + "hunter2hunter2hunter2\n")
        self.assertEqual(self.sync(), 2)
        self.assertIn("named_secret_assignment", self.lines[0])
        (self.folder / "T-5-session-2026-01-02.md").write_text("-----BEGIN " + "PRIVATE KEY-----\n", encoding="utf-8")
        self.assertEqual(self.sync(), 2)
        self.assertIn("private_key_block", self.lines[0])


class TestExtras(SyncTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_file("T-5-spec.md", SPEC)
        self.write_file("T-5-design.md", DESIGN)
        self.sync()

    def test_spec_extras_hold_requirements_criteria_and_diagram(self) -> None:
        self.append_session(SESSION)
        self.assertEqual(self.sync(extras="spec"), 0)
        self.assertEqual(len(self.comments()), 1)
        html = self.comments()[0]["comment_html"]
        for part in ("R-01 first requirement", "AC-01 first criterion", "start --&gt; finish", "wrote the thing"):
            self.assertIn(part, html)
        self.assertNotIn("Budget", html)

    def test_extras_twice_with_no_new_session_text_posts_once(self) -> None:
        self.sync(extras="spec")
        self.assertEqual(len(self.comments()), 1)
        self.sync(extras="spec")
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("comment=none", self.lines[-1])

    def test_extras_are_not_repeated_with_later_session_text(self) -> None:
        self.sync(extras="spec")
        self.append_session(SESSION)
        self.sync(extras="spec")
        self.assertEqual(len(self.comments()), 2)
        self.assertNotIn("R-01 first requirement", self.comments()[1]["comment_html"])

    def test_changed_spec_posts_the_extras_again(self) -> None:
        self.sync(extras="spec")
        self.write_file("T-5-spec.md", SPEC.replace("first requirement", "second requirement"))
        self.sync(extras="spec")
        self.assertEqual(len(self.comments()), 2)

    def test_long_session_log_is_cut_and_the_extras_stay_whole(self) -> None:
        self.append_session("filler line of text\n" * 2000)
        self.assertEqual(self.sync(extras="spec"), 0)
        html = self.comments()[0]["comment_html"]
        self.assertIn("cut=yes", self.lines[-1])
        self.assertIn("(cut; full text in the T-5 files in the vault)", html)
        for part in ("R-01 first requirement", "AC-01 first criterion", "start --&gt; finish"):
            self.assertIn(part, html)
        body_text = self.comments()[0]["comment_html"]
        self.assertLess(len(body_text), self.settings.comment_max_chars * 2)

    def test_dev_extras_hold_the_validation_results(self) -> None:
        self.write_file("T-5-edge-case-validation.md", "---\nstatus: VALIDATED\n---\n# Results\nscenario 1 PASS\n")
        self.sync(extras="dev")
        html = self.comments()[0]["comment_html"]
        self.assertIn("scenario 1 PASS", html)
        self.assertNotIn("status: VALIDATED", html)
        self.sync(extras="dev")
        self.assertEqual(len(self.comments()), 1)

    def test_a_missing_extras_file_is_named_and_posts_once(self) -> None:
        self.sync(extras="dev")
        self.assertIn("(extras: T-5-edge-case-validation.md not found)", self.comments()[0]["comment_html"])
        ledger = load_ledger(ledger_path(self.state, SYNC_TICKET))
        self.assertEqual(len(ledger.posted_keys), 1)

    def test_secret_in_the_extras_posts_nothing(self) -> None:
        self.write_file("T-5-spec.md", "## Requirements\n" + FAKE_TOKEN + "\n")
        self.assertEqual(self.sync(extras="spec"), 2)
        self.assertEqual(self.comments(), [])


class TestSyncEdges(SyncTestCase):
    def test_unmapped_prefix_is_skipped_with_exit_0_and_no_calls(self) -> None:
        lines: list[str] = []
        code = run_sync(self.settings, self.client, self.tickets, self.state, ticket_id="zz-3",
                        extras=None, emit=lines.append)
        self.assertEqual((code, lines), (0, ["skip | prefix zz has no Plane project in the settings"]))
        self.assertEqual(self.stub.state.calls, [])

    def test_no_card_stops_with_exit_2(self) -> None:
        self.stub.state.items[:] = [i for i in self.stub.state.items if i.number != 5]
        self.assertEqual(self.sync(), 2)
        self.assertEqual(self.lines, ["stopped | no card for T-5"])

    def test_invalid_ledger_raises_and_leaves_the_file_alone(self) -> None:
        path = ledger_path(self.state, SYNC_TICKET)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(PlaneSyncLedgerError):
            self.sync()
        self.assertEqual(path.read_text(encoding="utf-8"), "{not json")
        self.assertEqual(self.stub.state.calls, [])

    def test_a_failed_post_does_not_move_the_offsets(self) -> None:
        self.sync()
        offsets = load_ledger(ledger_path(self.state, SYNC_TICKET)).session_offsets
        self.append_session(SESSION)
        self.stub.state.fail_rules.append(FailRule("POST", "/comments/", 500))
        with self.assertRaises(PlaneApiError):
            self.sync()
        self.assertEqual(load_ledger(ledger_path(self.state, SYNC_TICKET)).session_offsets, offsets)
        self.assertEqual(len(self.stub.calls_matching("POST", "/comments/")), 1)


class TestSyncCli(CliCase):
    def test_sync_through_the_cli(self) -> None:
        self.append_session(SESSION)
        self.assertEqual(self.run_cli(["sync", SYNC_TICKET, "--from-start"]), 0)
        self.assertEqual(len(self.comments()), 1)
        self.assertEqual(self.run_cli(["sync", SYNC_TICKET, "--extras", "spec"]), 0)
        self.assertNotIn(FAKE_TOKEN, json.dumps(self.lines))

    def test_sync_with_the_connector_off_makes_no_call(self) -> None:
        self.turn_off()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = self.run_cli(["sync", SYNC_TICKET])
        self.assertEqual(code, 2)
        self.assertIn("plane: not set up", err.getvalue())
        self.assertEqual(self.stub.state.calls, [])

    def test_unknown_extras_value_is_a_usage_error(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = self.run_cli(["sync", SYNC_TICKET, "--extras", "other"])
        self.assertEqual(code, 2)

    def test_plane_failure_is_exit_3(self) -> None:
        self.stub.state.fail_rules.append(FailRule("GET", "/projects/", 500))
        self.assertEqual(self.run_cli(["sync", SYNC_TICKET]), 3)


if __name__ == "__main__":
    unittest.main()
