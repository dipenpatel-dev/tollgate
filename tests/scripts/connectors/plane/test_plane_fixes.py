# Module:      test_plane_fixes.py
# Description: Tests for the hardening round: create order, comment limit, id parsing, secret patterns, https, ledger file mode.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import contextlib
import dataclasses
import inspect
import io
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from connectors.plane.plane_comment_builder import find_secret_pattern, markdown_to_html
from connectors.plane.plane_drift_checker import run_drift
from connectors.plane.plane_sync_ledger import PlaneSyncLedgerError, SyncLedger, ledger_path, load_ledger, save_ledger
from connectors.plane.plane_ticket_syncer import run_sync
from connectors.plane.plane_work_item_client import PlaneApiError
from connectors.plane.vault_ticket_creator import run_create
from connectors.plane.vault_ticket_files import (
    VaultTicketError, parse_ticket_id, read_state_file, render_initial_state_file, safe_text,
)
from plane_sync_test_support import (
    SYNC_TICKET, CliCase, StubTestCase, SyncTestCase, make_settings, read_template,
)

SPEC = "## Requirements\nR-01 first requirement\n\n## Acceptance Criteria\nAC-01 first criterion\n"
DESIGN = "## Implementation Plan\n\n```mermaid\nflowchart TD\n    start --> finish\n```\n"
PATTERNS = make_settings().secret_patterns


class CreateCase(StubTestCase):
    def create(self, **overrides: str) -> int:
        args = {**self.create_args(), **overrides}
        self.lines = []
        return run_create(self.settings, self.client, self.tickets, self.state,
                          emit=self.lines.append, template_text=read_template(), **args)

    def posts(self) -> int:
        return len(self.stub.calls_matching("POST", "/work-items/"))


class TestCreateFixes(CreateCase):
    def test_f01_ledger_failure_keeps_the_card_and_a_rerun_adopts_it(self) -> None:
        self.state.mkdir()
        blocker = self.state / "T-6"
        blocker.write_text("a file where the ledger folder should be")
        self.assertEqual(self.create(), 2)
        self.assertEqual(self.lines, ["stopped | plane_sync_ledger.json cannot be written; card 6 kept"])
        self.assertNotIn("T-6", self.folder_names())
        blocker.unlink()
        self.assertEqual(self.create(), 0)
        self.assertEqual(self.posts(), 1)
        self.assertEqual(read_state_file(self.tickets / "T-6", "T-6").title, "A new ticket")
        self.assertEqual(load_ledger(ledger_path(self.state, "T-6")).work_item_id, "wi-6")

    def test_f01_the_ledger_is_written_before_the_folder(self) -> None:
        seen: list[bool] = []
        real = save_ledger

        def spy(path: Path, ledger: SyncLedger) -> None:
            seen.append((self.tickets / "T-6").exists())
            real(path, ledger)

        with mock.patch("connectors.plane.vault_ticket_creator.save_ledger", side_effect=spy):
            self.assertEqual(self.create(), 0)
        self.assertEqual(seen, [False])

    def test_f07_a_secret_in_the_title_sends_nothing(self) -> None:
        self.assertEqual(self.create(title="password: Hunter2!Hunter2!!"), 2)
        self.assertEqual(self.lines, ["stopped | secret pattern named_secret_assignment in title; nothing sent"])
        self.assertEqual(self.stub.state.calls, [])
        self.assertEqual(self.folder_names(), [f"T-{n}" for n in range(1, 6)])

    def test_f06_a_priority_with_a_trailing_newline_is_refused(self) -> None:
        render = dict(priority="high\n", scope="s", repo="r", work_type="feature", today="2026-01-02")
        with self.assertRaises(VaultTicketError):
            render_initial_state_file(read_template(), ticket_id="T-9", title="T", **render)
        self.assertEqual(self.create(priority="P2\n"), 2)
        self.assertEqual(self.stub.state.calls, [])


class TestSyncFixes(SyncTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_file("T-5-spec.md", SPEC)
        self.write_file("T-5-design.md", DESIGN)

    def test_f02_a_missing_extras_note_posts_once(self) -> None:
        for _ in range(3):
            self.sync(extras="dev")
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("comment=none", self.lines[-1])

    def test_f03_escape_heavy_text_ends_within_the_limit_as_html(self) -> None:
        self.sync()
        self.append_session("a<b && c>d\n" * 1400)
        self.assertEqual(self.sync(), 0)
        html = self.comments()[0]["comment_html"]
        self.assertLessEqual(len(html), self.settings.comment_max_chars)
        self.assertIn("cut=yes", self.lines[-1])
        self.assertIn("(cut; full text in the T-5 files in the vault)", html)

    def test_f03_extras_larger_than_the_limit_leave_session_text_visible(self) -> None:
        self.write_file("T-5-spec.md", "## Requirements\n" + "requirement line\n" * 3000 + "\n## Acceptance Criteria\nx\n")
        self.sync()
        self.append_session("visible session words\n")
        self.assertEqual(self.sync(extras="spec"), 0)
        html = self.comments()[0]["comment_html"]
        self.assertIn("visible session words", html)
        self.assertLessEqual(len(html), self.settings.comment_max_chars)
        self.assertIn("cut=yes", self.lines[-1])

    def test_f03_extras_alone_may_use_the_whole_limit(self) -> None:
        self.write_file("T-5-spec.md", "## Requirements\n" + "requirement line\n" * 850 + "\n## Acceptance Criteria\nx\n")
        self.sync()
        self.assertEqual(self.sync(extras="spec"), 0)
        self.assertGreater(len(self.comments()[0]["comment_html"]), self.settings.comment_max_chars // 2)
        self.assertIn("cut=no", self.lines[-1])

    def test_f03_a_tiny_limit_still_posts_the_pointer_within_the_limit(self) -> None:
        settings = dataclasses.replace(self.settings, comment_max_chars=80)
        self.sync(settings=settings)
        self.append_session("a<b && c>d\n" * 50)
        self.assertEqual(self.sync(settings=settings), 0)
        self.assertLessEqual(len(self.comments()[0]["comment_html"]), 80)
        self.assertIn("cut=yes", self.lines[-1])

    def test_f13_the_status_comment_key_is_saved_right_after_the_post(self) -> None:
        self.sync()
        self.write_state(status="SHIPPED")
        snapshots: list[tuple[str | None, int]] = []
        real = save_ledger

        def spy(path: Path, ledger: SyncLedger) -> None:
            snapshots.append((ledger.status_word, len(ledger.posted_keys)))
            real(path, ledger)

        with mock.patch("connectors.plane.plane_ticket_syncer.save_ledger", side_effect=spy):
            self.sync()
        self.assertIn(("SPEC_APPROVED", 1), snapshots)
        self.assertEqual(snapshots[-1], ("SHIPPED", 1))

    def test_f15a_a_posted_session_key_blocks_a_second_post_and_offsets_advance(self) -> None:
        self.sync()
        self.append_session("Done: wrote the thing.\n")
        self.sync()
        path = ledger_path(self.state, SYNC_TICKET)
        ledger = load_ledger(path)
        ledger.session_offsets = {}
        save_ledger(path, ledger)
        self.assertEqual(self.sync(), 0)
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("comment=none", self.lines[-1])
        self.assertEqual(load_ledger(path).session_offsets["T-5-session-2026-01-02.md"], len("Done: wrote the thing.\n"))

    def test_f15b_a_posted_status_key_blocks_a_second_status_comment(self) -> None:
        self.sync()
        self.write_state(status="SHIPPED")
        self.sync()
        path = ledger_path(self.state, SYNC_TICKET)
        ledger = load_ledger(path)
        ledger.status_word = "SPEC_APPROVED"
        save_ledger(path, ledger)
        self.assertEqual(self.sync(), 0)
        self.assertEqual(len(self.comments()), 1)
        self.assertEqual(load_ledger(path).status_word, "SHIPPED")

    def test_f15c_when_both_parts_are_empty_the_offsets_are_still_saved(self) -> None:
        self.sync()
        self.append_session("\n\n   \n")
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.comments(), [])
        offsets = load_ledger(ledger_path(self.state, SYNC_TICKET)).session_offsets
        self.assertEqual(offsets["T-5-session-2026-01-02.md"], len("\n\n   \n"))


class TestTicketIdFixes(SyncTestCase):
    BAD_IDS = ("T-339\n", "T-٣٣٩", "T-1/../x", "T-", "", "T-339 ")

    def test_parse_ticket_id(self) -> None:
        self.assertEqual(parse_ticket_id("T-339"), ("T", 339))
        self.assertEqual(parse_ticket_id("zz-1"), ("zz", 1))
        for bad in self.BAD_IDS:
            self.assertIsNone(parse_ticket_id(bad), repr(bad))

    def test_f05_sync_stops_with_exit_2_on_a_bad_id_and_makes_no_call(self) -> None:
        for bad in self.BAD_IDS:
            self.lines = []
            code = run_sync(self.settings, self.client, self.tickets, self.state, ticket_id=bad,
                            extras=None, emit=self.lines.append)
            self.assertEqual(code, 2, repr(bad))
            self.assertEqual(len(self.lines), 1)
            self.assertTrue(self.lines[0].startswith("stopped | not a ticket id: "))
            self.assertNotIn("\n", self.lines[0])
        self.assertEqual(self.stub.state.calls, [])

    def test_f05_a_known_format_with_an_unmapped_prefix_is_a_skip(self) -> None:
        self.lines = []
        code = run_sync(self.settings, self.client, self.tickets, self.state, ticket_id="proj-339",
                        extras=None, emit=self.lines.append)
        self.assertEqual((code, self.lines), (0, ["skip | prefix proj has no Plane project in the settings"]))

    def test_f05_drift_stops_with_exit_2_on_a_bad_id(self) -> None:
        self.lines = []
        code = run_drift(self.settings, self.client, self.tickets, ticket_ids=["T-339\n"], emit=self.lines.append)
        self.assertEqual((code, self.lines), (2, ["stopped | not a ticket id: T-339"]))

    def test_safe_text_removes_controls_and_caps_the_length(self) -> None:
        self.assertEqual(safe_text("a\nb\x1b[0m\x07c"), "ab[0mc")
        self.assertEqual(len(safe_text("x" * 200)), 80)


class TestCliGateOrder(CliCase):
    def test_f04_unmapped_prefix_is_a_skip_for_sync_and_drift_with_no_card_call(self) -> None:
        skip = ["skip | prefix zz has no Plane project in the settings"]
        self.assertEqual(self.run_cli(["sync", "zz-1"]), 0)
        self.assertEqual(self.lines, skip)
        self.assertEqual(self.run_cli(["drift", "zz-1", "zz-2"]), 0)
        self.assertEqual(self.lines, skip * 2)
        self.assertEqual(self.stub.state.calls, [])

    def test_f04_create_with_an_unmapped_prefix_is_exit_2(self) -> None:
        argv = ["create", "--prefix", "zz", "--title", "T", "--priority", "P2", "--scope", "s",
                "--repo", "r", "--type", "feature", "--yes"]
        self.assertEqual(self.run_cli(argv), 2)
        self.assertEqual(self.lines, ["skip | prefix zz has no Plane project in the settings"])

    def test_f04_a_bad_id_is_exit_2(self) -> None:
        self.assertEqual(self.run_cli(["sync", "T-1/../x"]), 2)
        self.assertEqual(self.lines, ["stopped | not a ticket id: T-1/../x"])

    def test_the_connector_off_wins_over_every_other_check(self) -> None:
        self.turn_off()
        for argv in (["sync", SYNC_TICKET], ["drift", SYNC_TICKET, "zz-1"], ["sync", "zz-1"]):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(self.run_cli(argv), 2)
            self.assertIn("plane: not set up", err.getvalue())
        self.assertEqual(self.stub.state.calls, [])

    def test_f11_the_cli_refuses_an_http_address(self) -> None:
        self.assertEqual(self.run_cli(["sync", SYNC_TICKET], allow_insecure_http=False), 1)
        self.assertEqual(self.lines, ["stopped | the connector address must start with https://"])
        self.assertEqual(self.stub.state.calls, [])

    def test_d03_help_exits_0_and_a_usage_error_exits_2(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.run_cli(["--help"]), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_cli([]), 2)

    def test_d04_run_sync_has_no_today_parameter(self) -> None:
        self.assertNotIn("today", inspect.signature(run_sync).parameters)


class TestDriftNamePrinting(SyncTestCase):
    def drift_lines(self) -> list[str]:
        lines: list[str] = []
        run_drift(self.settings, self.client, self.tickets, ticket_ids=[SYNC_TICKET], emit=lines.append)
        return lines

    def test_f10_control_characters_and_newlines_are_removed_from_the_card_name(self) -> None:
        self.sync()
        self.card().name = "Bad\nname\x1b[2J\x07 end"
        self.assertEqual(self.drift_lines(), ['wrong_name | T-5 | card "Badname[2J end" vault "Sync ticket"'])

    def test_f10_a_long_card_name_is_capped_at_80_characters(self) -> None:
        self.sync()
        self.card().name = "x" * 200
        self.assertEqual(self.drift_lines(), [f'wrong_name | T-5 | card "{"x" * 80}" vault "Sync ticket"'])


class TestPatterns(unittest.TestCase):
    CASES = {
        "client_secret": "client_secret: " + "a" * 20,
        "export_password": "export DB_PASSWORD=" + "b" * 20,
        "admin_key": "SERVICE_API_KEY=" + "c" * 20,
        "json_password": '{"password": "' + "d" * 20 + '"}',
        "punctuation_password": "password: Hunter2!Hunter2!!",
        "url_credentials": "postgres://user:pass@host/db",
        "bearer": "Authorization: Bearer " + "e" * 30,
        "aws": "AK" + "IA" + "IOSFODNN7" + "EXAMPLE",
        "github_lowercase": "ghp_" + "a" * 36,
        "slack": "xoxb-" + "1234567890-abcdefghij",
    }

    def test_f08_each_common_shape_is_caught(self) -> None:
        for name, text in self.CASES.items():
            with self.subTest(name):
                self.assertIsNotNone(find_secret_pattern(text, PATTERNS))

    def test_f08_plain_prose_and_urls_are_not_caught(self) -> None:
        for text in ("the token budget is fine", "see https://example.invalid/path/page", "token: ok", "a password rule"):
            with self.subTest(text):
                self.assertIsNone(find_secret_pattern(text, PATTERNS))

    def test_f08_a_long_run_of_word_characters_scans_fast(self) -> None:
        self.assertIsNone(find_secret_pattern("a-" * 20000, {"n": PATTERNS["named_secret_assignment"]}))

    def test_f09_markdown_images_render_no_img_tag_but_links_stay(self) -> None:
        html = markdown_to_html("![x](https://example.invalid/p.png) and [link](https://example.invalid/a)")
        self.assertNotIn("<img", html)
        self.assertIn('<a href="https://example.invalid/a">link</a>', html)


class TestErrorShape(unittest.TestCase):
    def test_d02_the_api_error_has_no_reason_attribute_and_keeps_its_message(self) -> None:
        error = PlaneApiError("GET", "projects/", 500, "unexpected status")
        self.assertFalse(hasattr(error, "reason"))
        self.assertEqual(str(error), "GET projects/ failed: status 500 (unexpected status)")


class TestLedgerFile(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = ledger_path(Path(temp.name), "T-4")
        self.ledger = SyncLedger("T-4", "proj", "wi-4", 4, None, "BACKLOG", {}, [])

    def test_f12_the_ledger_file_is_private_to_the_owner(self) -> None:
        save_ledger(self.path, self.ledger)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_f12_a_failed_replace_removes_the_temp_file(self) -> None:
        with mock.patch("connectors.plane.plane_sync_ledger.os.replace", side_effect=OSError("boom")):
            with self.assertRaises(PlaneSyncLedgerError):
                save_ledger(self.path, self.ledger)
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_f12_temp_names_are_not_predictable(self) -> None:
        names: list[str] = []
        real_open = os.open

        def spy(path: str, *args: int) -> int:
            names.append(str(path))
            return real_open(path, *args)

        with mock.patch("connectors.plane.plane_sync_ledger.os.open", side_effect=spy):
            save_ledger(self.path, self.ledger)
            save_ledger(self.path, self.ledger)
        self.assertEqual(len(set(names)), 2)
        self.assertNotEqual(names[0], str(self.path) + ".tmp")


class TestStubCap(StubTestCase):
    def test_f14_the_stub_answers_500_after_its_request_cap(self) -> None:
        self.stub.state.request_cap = 2
        self.client.list_projects()
        self.client.list_projects()
        with self.assertRaises(PlaneApiError) as caught:
            self.client.list_projects()
        self.assertEqual(caught.exception.status, 500)
        self.assertEqual(len(self.stub.state.calls), 3)


if __name__ == "__main__":
    unittest.main()
