# Module:      test_plane_cli.py
# Description: Tests for the command line: create confirmation, exit codes, settings and folders from the path loader.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from connectors import registry
from connectors.plane import cli
from connectors.plane.plane_sync_ledger import PlaneSyncLedgerError
from core.paths import get_path
from plane_stub_server import FailRule, StubItem
from plane_sync_test_support import EXAMPLE_SETTINGS, FAKE_TOKEN, SYNC_TICKET, CliCase

CREATE_ARGV = ["create", "--prefix", "T", "--title", "From the cli", "--priority", "P2",
               "--scope", "scripts", "--repo", "demo-repo", "--type", "feature"]


class TestCreateConfirmation(CliCase):
    def test_create_with_no_flag_and_no_terminal_refuses_and_calls_nothing(self) -> None:
        self.assertEqual(self.run_cli(CREATE_ARGV), 2)
        self.assertEqual(len(self.lines), 1)
        self.assertIn("pass --yes", self.lines[0])
        self.assertEqual(self.stub.state.calls, [])
        self.assertEqual(self.folder_names(), [f"T-{n}" for n in range(1, 6)])

    def test_create_with_yes_runs_with_no_terminal(self) -> None:
        self.assertEqual(self.run_cli(CREATE_ARGV + ["--yes"]), 0)
        self.assertEqual(self.lines, ["created | T-6 | card 6"])
        self.assertIn("T-6", self.folder_names())
        self.assertNotIn(FAKE_TOKEN, "".join(self.lines))

    def test_a_terminal_answer_of_yes_runs_it_and_the_question_comes_before_any_call(self) -> None:
        asked: list[tuple[str, int]] = []

        def confirm(question: str) -> str:
            asked.append((question, len(self.stub.state.calls)))
            return "y"

        with mock.patch.object(registry, "interactive", lambda env=None: True):
            self.assertEqual(self.run_cli(CREATE_ARGV, confirm=confirm), 0)
        self.assertEqual(len(asked), 1)
        self.assertIn("From the cli", asked[0][0])
        self.assertEqual(asked[0][1], 0)
        self.assertIn("T-6", self.folder_names())

    def test_a_terminal_answer_of_no_or_blank_stops_with_no_call(self) -> None:
        for answer in ("n", "", "maybe"):
            with mock.patch.object(registry, "interactive", lambda env=None: True):
                self.assertEqual(self.run_cli(CREATE_ARGV, confirm=lambda question, a=answer: a), 2)
            self.assertEqual(self.lines, ["stopped | create was not confirmed"])
        self.assertEqual(self.stub.state.calls, [])

    def test_sync_and_drift_never_ask(self) -> None:
        asked: list[str] = []
        with mock.patch.object(registry, "interactive", lambda env=None: True):
            self.run_cli(["drift", SYNC_TICKET], confirm=lambda question: asked.append(question) or "y")
        self.assertEqual(asked, [])


class TestExitCodes(CliCase):
    def test_plane_failure_is_exit_3_with_one_line(self) -> None:
        self.stub.state.fail_rules.append(FailRule("GET", "/projects/", 500))
        self.assertEqual(self.run_cli(CREATE_ARGV + ["--yes"]), 3)
        self.assertEqual(self.lines, ["stopped | GET projects/ failed: status 500 (unexpected status)"])

    def test_guard_stop_is_exit_2(self) -> None:
        (self.tickets / "T-9").mkdir()
        self.assertEqual(self.run_cli(CREATE_ARGV + ["--yes"]), 2)
        self.assertEqual(self.lines, ["stopped | Plane highest 5, local highest 9"])

    def test_corrupt_ledger_error_is_exit_2(self) -> None:
        with mock.patch("connectors.plane.cli.run_create", side_effect=PlaneSyncLedgerError("x is not valid JSON")):
            self.assertEqual(self.run_cli(CREATE_ARGV + ["--yes"]), 2)
        self.assertEqual(self.lines, ["stopped | x is not valid JSON"])

    def test_a_settings_problem_is_exit_1_naming_the_key(self) -> None:
        self.assertEqual(self.run_cli(["drift", SYNC_TICKET], settings=None), 1)
        self.assertTrue(self.lines[0].startswith("stopped | settings problem: "))

    def test_unknown_command_is_exit_2(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_cli(["nope"]), 2)

    def test_the_key_never_appears_in_output_or_files(self) -> None:
        self.stub.state.fail_rules.append(FailRule("POST", "/work-items/", 500))
        self.run_cli(CREATE_ARGV + ["--yes"])
        self.stub.state.fail_rules.clear()
        self.run_cli(CREATE_ARGV + ["--yes"])
        self.assertNotIn(FAKE_TOKEN, "\n".join(self.lines))
        for root in (self.tickets, self.state, Path(self.home)):
            for path in root.rglob("*"):
                if path.is_file():
                    self.assertNotIn(FAKE_TOKEN.encode(), path.read_bytes(), str(path))


class TestPathLoaderUse(CliCase):
    """The settings file and the ticket and state folders come from the paths file and the path loader."""

    def test_settings_and_folders_are_found_without_flags(self) -> None:
        settings_file = Path(self.env["TOLLGATE_PATHS"]).parent / "plane-sync.json"
        data = json.loads(EXAMPLE_SETTINGS.read_text(encoding="utf-8"))
        data.update(workspace_slug="ws-test", min_seconds_between_calls=0, prefix_table={"T": {"number_width": 1}})
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(json.dumps(data), encoding="utf-8")
        with mock.patch.dict(os.environ, self.env):
            tickets = get_path("tickets")
            folder = tickets / "T-3"
            folder.mkdir(parents=True)
            (folder / "T-3-state.md").write_text("---\ntitle: old 3\nstatus: SPEC_APPROVED\n---\nbody\n", encoding="utf-8")
            self.lines = []
            code = cli.main(["sync", "T-3"], env=self.env, out=self.lines.append, allow_insecure_http=True)
            ledger = get_path("state") / "plane" / "T-3" / "plane_sync_ledger.json"
        self.assertEqual((code, self.lines[-1].split(" | ")[0]), (0, "synced"))
        self.assertTrue(ledger.is_file())
        self.assertTrue(self.stub.state.items[2].description_html.endswith("</p>"))

    def test_the_settings_flag_wins_over_the_default_file(self) -> None:
        data = json.loads(EXAMPLE_SETTINGS.read_text(encoding="utf-8"))
        data.update(workspace_slug="ws-test", min_seconds_between_calls=0, prefix_table={"T": {}})
        flagged = Path(self.home) / "elsewhere.json"
        flagged.write_text(json.dumps(data), encoding="utf-8")
        self.stub.state.items.append(StubItem("wi-7", 7, "extra", "T-7"))
        code = cli.main(["--settings", str(flagged), "drift", "zz-1"], env=self.env, tickets_root=self.tickets,
                        state_root=self.state, out=self.lines.append, allow_insecure_http=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.lines, ["skip | prefix zz has no Plane project in the settings"])


if __name__ == "__main__":
    unittest.main()
