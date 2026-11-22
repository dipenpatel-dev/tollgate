#!/usr/bin/env python3
"""Tests for the small state scripts: ticket_state_check, vault_query, session log
retirement, index backup and restore, doc drift patrol, system_progress.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove each tool works on synthetic data inside a throwaway home and writes
only where it should.
Change log:
  - First version.
"""
import json
import os
import pathlib
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STATE = ROOT / "scripts" / "state"
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(STATE))

from throwaway_home import throwaway_home  # noqa: E402
import ticket_state_check  # noqa: E402
import doc_drift_patrol  # noqa: E402
import vault_census  # noqa: E402
import backfill_vault_frontmatter  # noqa: E402

FILLER = "line\n"


def run(args, env, input_text=None):
    proc = subprocess.run(
        args, env=dict(env, PYTHONDONTWRITEBYTECODE="1"), input=input_text,
        capture_output=True, text=True, timeout=60,
    )
    return proc


def make_ticket(tickets, key, state, files=None):
    folder = tickets / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (key + "-state.md")).write_text(state)
    for name, text in (files or {}).items():
        (folder / (key + "-" + name)).write_text(text)
    return folder


class TicketStateCheck(unittest.TestCase):
    def test_complete_ticket_is_ok(self):
        with throwaway_home() as (home, env):
            tickets = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
            make_ticket(tickets, "T-001",
                        "Status: DEV_COMPLETE\nlast_block_applied: B-03\n",
                        {"spec.md": "Status: APPROVED\n", "design.md": "Status: DESIGN_APPROVED\n",
                         "edge-case-validation.md": "Status: DOCUMENTED\n"})
            proc = run([sys.executable, str(STATE / "ticket_state_check.py"), "T-001"], env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("ok", proc.stdout)

    def test_missing_fields_are_flagged(self):
        with throwaway_home() as (home, env):
            tickets = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
            make_ticket(tickets, "T-002", "Status: IN_DEV\n",
                        {"spec.md": "# no status here\n"})
            proc = run([sys.executable, str(STATE / "ticket_state_check.py"), "T-002", "--json"], env)
            self.assertEqual(proc.returncode, 1)
            codes = [f["code"] for f in json.loads(proc.stdout)["findings"]]
            self.assertIn("MISSING_FIELD", codes)    # last_block_applied
            self.assertIn("BAD_STATUS", codes)       # spec has no Status line
            self.assertIn("MISSING_FILE", codes)     # design file absent

    def test_state_file_missing_and_bad_values(self):
        with throwaway_home() as (home, env):
            tickets = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
            (tickets / "T-003").mkdir(parents=True)
            self.assertEqual(
                run([sys.executable, str(STATE / "ticket_state_check.py"), "T-003"], env).returncode, 1)
            make_ticket(tickets, "T-004", "Status: HALF_DONE\n")
            out = run([sys.executable, str(STATE / "ticket_state_check.py"), "T-004"], env)
            self.assertEqual(out.returncode, 1)
            self.assertIn("UNKNOWN_STATE", out.stdout)
            make_ticket(tickets, "T-005", "Status: ROUTED\nStatus: QA_BLOCKED\n")
            self.assertIn("BAD_STATUS", run([sys.executable, str(STATE / "ticket_state_check.py"), "T-005"], env).stdout)

    def test_status_not_first_is_a_warning_only(self):
        with throwaway_home() as (home, env):
            tickets = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
            make_ticket(tickets, "T-006", "Some notes first\nStatus: ROUTED\n")
            proc = run([sys.executable, str(STATE / "ticket_state_check.py"), "T-006"], env)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("STATUS_NOT_FIRST", proc.stdout)

    def test_valid_states_use_the_gate_constants(self):
        import gate_rules
        for name in ("STATE_SPEC_APPROVED", "STATE_DESIGN_APPROVED", "STATE_IN_DEV", "STATE_DEV_COMPLETE"):
            self.assertIn(getattr(gate_rules, name), ticket_state_check.VALID_STATES)

    def test_not_set_up_and_unknown_ticket(self):
        with throwaway_home() as (home, env):
            env = {k: v for k, v in env.items() if k not in ("TOLLGATE_KNOWLEDGE", "TOLLGATE_PATHS")}
            proc = run([sys.executable, str(STATE / "ticket_state_check.py"), "T-001"], env)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not set up", proc.stderr)
        with throwaway_home() as (home, env):
            proc = run([sys.executable, str(STATE / "ticket_state_check.py"), "T-999"], env)
            self.assertEqual(proc.returncode, 2)


class VaultQueryAndSessionLogs(unittest.TestCase):
    def test_vault_query_reads_tickets_from_the_loader(self):
        with throwaway_home() as (home, env):
            tickets = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
            make_ticket(tickets, "T-010", "---\nstatus: OPEN\ntitle: first\n---\nStatus: OPEN\n")
            proc = run([sys.executable, str(STATE / "vault_query.py"), "board"], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_vault_query_not_set_up(self):
        with throwaway_home() as (home, env):
            env = {k: v for k, v in env.items() if k not in ("TOLLGATE_KNOWLEDGE", "TOLLGATE_PATHS")}
            proc = run([sys.executable, str(STATE / "vault_query.py"), "board"], env)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not set up", proc.stderr)

    def test_retire_moves_logs_into_archive(self):
        with throwaway_home() as (home, env):
            tree = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets" / "T-020"
            tree.mkdir(parents=True)
            (tree / "T-020-session-1.md").write_text("log\n")
            proc = run([sys.executable, str(STATE / "retire_session_logs.py"), "--ticket", "T-020",
                        "--terminal-status", "SHIPPED 2026-01-01", "--close-date", "2026-01-01",
                        "--outcome-sentence", "Done.", "--tree", str(tree)], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((tree / "archive" / "T-020-session-1.md").exists())
            self.assertTrue((tree / "archive" / "T-020-archive-summary.md").exists())

    def test_backfill_needs_yes_and_reads_only_the_loader_folders(self):
        with throwaway_home() as (home, env):
            tree = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets" / "T-030"
            tree.mkdir(parents=True)
            (tree / "T-030-state.md").write_text("---\nticket: T-030\nterminal_status: SHIPPED 2026-02-02\n---\n")
            (tree / "T-030-session-1.md").write_text("log\n")
            script = str(STATE / "backfill_session_logs.py")
            declined = run([sys.executable, script], env, input_text="no\n")
            self.assertIn("Aborted", declined.stdout)
            self.assertTrue((tree / "T-030-session-1.md").exists())
            done = run([sys.executable, script, "--yes"], env)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertTrue((tree / "archive" / "T-030-session-1.md").exists())


class IndexBackup(unittest.TestCase):
    def _index(self, env):
        index = pathlib.Path(env["HOME"]) / ".tollgate" / "index"
        (index / "vault").mkdir(parents=True)
        (index / "vault" / "chroma.sqlite3").write_text("fake")
        (index / "context_cache.json").write_text('{"a": 1}')
        return index

    def test_backup_and_restore_stay_inside_the_loader_folders(self):
        with throwaway_home() as (home, env):
            index = self._index(env)
            snaps = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "output" / "index-snapshots"
            proc = run(["bash", str(STATE / "backup_index.sh")], env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            days = list((snaps / "full").iterdir())
            self.assertEqual(len(days), 1)
            self.assertTrue((snaps / "cache").is_dir())
            listing = run(["bash", str(STATE / "backup_index.sh"), "--list"], env)
            self.assertIn(days[0].name, listing.stdout)
            (index / "vault" / "chroma.sqlite3").write_text("changed")
            declined = run(["bash", str(STATE / "restore_index.sh"), days[0].name], env, input_text="no\n")
            self.assertEqual(declined.returncode, 1)
            self.assertEqual((index / "vault" / "chroma.sqlite3").read_text(), "changed")
            ok = run(["bash", str(STATE / "restore_index.sh"), days[0].name, "--yes"], env)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertEqual((index / "vault" / "chroma.sqlite3").read_text(), "fake")

    def test_backup_without_an_index_fails_cleanly(self):
        with throwaway_home() as (home, env):
            proc = run(["bash", str(STATE / "backup_index.sh")], env)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("nothing to back up", proc.stdout)


class DriftAndProgress(unittest.TestCase):
    def test_refresh_doc_clears_the_marker(self):
        with throwaway_home() as (home, env):
            doc = pathlib.Path(home) / "doc.md"
            doc.write_text("---\ntitle: x\nupdate_needed: true\nlast_updated: 2000-01-01\n---\nbody\n")
            self.assertTrue(doc_drift_patrol.refresh_doc(doc))
            text = doc.read_text()
            self.assertNotIn("update_needed", text)
            self.assertNotIn("2000-01-01", text)
            self.assertFalse(doc_drift_patrol.refresh_doc(doc))

    def test_vault_mirror_goes_to_the_loader_vault(self):
        with throwaway_home() as (home, env):
            docs = pathlib.Path(home) / "repo" / "docs"
            docs.mkdir(parents=True)
            (docs / "a.md").write_text("x\n")
            old = dict(os.environ)
            os.environ.update(env)
            try:
                doc_drift_patrol.sync_docs_to_vault(docs, "repo")
            finally:
                os.environ.clear()
                os.environ.update(old)
            mirror = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "08-reference" / "repos" / "repo" / "a.md"
            self.assertTrue(mirror.exists())

    def test_system_progress_json(self):
        with throwaway_home() as (home, env):
            proc = run([sys.executable, str(STATE / "system_progress.py"), "--json", "--root", str(ROOT)], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertIn("layer_1", data)
            self.assertIn("bloat_pct", data["layer_3"])

    def test_system_progress_layer_1_counts_the_real_command_files(self):
        import system_progress
        checks = {c.name: c.passed for c in system_progress.layer_1_checks(ROOT)}
        for name in ("arch", "dev", "qa", "spec", "close", "handoff"):
            self.assertTrue(checks[name + " command exists"], name)
        self.assertTrue(checks["dev command names DOCUMENTED and VALIDATED"])


class NestedTicketFolders(unittest.TestCase):
    """A vault may keep tickets at 02-tickets/PREFIX/KEY. Every state tool must find them."""

    def _nested(self, env, key="PROJ-312", state="---\nticket: PROJ-312\nstatus: OPEN\ntitle: nested\n---\nStatus: OPEN\n"):
        tickets = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
        return make_ticket(tickets / key.split("-")[0], key, state)

    def test_ticket_state_check_finds_a_nested_ticket(self):
        with throwaway_home() as (home, env):
            self._nested(env, "PROJ-312", "Status: SPEC_APPROVED\n")
            proc = run([sys.executable, str(STATE / "ticket_state_check.py"), "PROJ-312"], env)
            self.assertNotIn("not found", proc.stderr)
            self.assertIn("PROJ-312", proc.stdout)

    def test_ticket_state_check_finds_a_nested_ticket_with_a_lowercase_prefix_folder(self):
        with throwaway_home() as (home, env):
            tickets = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
            make_ticket(tickets / "ex", "EX-4", "Status: SPEC_APPROVED\n")
            proc = run([sys.executable, str(STATE / "ticket_state_check.py"), "EX-4"], env)
            self.assertNotIn("not found", proc.stderr)

    def test_vault_query_board_and_ticket_find_a_nested_ticket(self):
        with throwaway_home() as (home, env):
            self._nested(env, "T-312", "---\nticket: T-312\nstatus: BACKLOG\ntitle: nested\n---\nbody\n")
            board = run([sys.executable, str(STATE / "vault_query.py"), "board"], env)
            self.assertEqual(board.returncode, 0, board.stderr)
            self.assertIn("[BACKLOG]\n  T-312", board.stdout)
            one = run([sys.executable, str(STATE / "vault_query.py"), "ticket", "T-312"], env)
            self.assertNotIn("not found", one.stdout)
            self.assertIn("status: BACKLOG", one.stdout)

    def test_vault_query_does_not_treat_a_prefix_folder_as_a_ticket(self):
        with throwaway_home() as (home, env):
            self._nested(env, "T-312", "---\nticket: T-312\nstatus: BACKLOG\n---\nbody\n")
            board = run([sys.executable, str(STATE / "vault_query.py"), "board"], env)
            self.assertNotIn("(absent)", board.stdout)
            self.assertNotIn("  T (", board.stdout)

    def test_backfill_session_logs_finds_a_nested_terminal_ticket(self):
        with throwaway_home() as (home, env):
            folder = self._nested(env, "PROJ-330",
                                  "---\nticket: PROJ-330\nterminal_status: SHIPPED 2026-02-02\n---\n")
            (folder / "PROJ-330-session-1.md").write_text("log\n")
            proc = run([sys.executable, str(STATE / "backfill_session_logs.py"), "--yes"], env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue((folder / "archive" / "PROJ-330-session-1.md").exists())

    def test_vault_census_reads_the_ticket_folder_below_a_prefix_folder(self):
        nested = vault_census.split_ticket_path("02-tickets/PROJ/PROJ-312/PROJ-312-state.md")
        flat = vault_census.split_ticket_path("02-tickets/PROJ-312/PROJ-312-state.md")
        self.assertEqual(nested.folder, "proj-312")
        self.assertEqual((nested.folder, nested.depth, nested.middle, nested.name),
                         (flat.folder, flat.depth, flat.middle, flat.name))
        self.assertEqual(vault_census.expected_triple("02-tickets/PROJ/PROJ-312/PROJ-312-state.md", {}),
                         ("ticket", "state", True))
        self.assertEqual(vault_census.expected_triple("02-tickets/PROJ/PROJ-312/PROJ-312-spec.md", {})[1], "spec")
        self.assertEqual(vault_census.expected_triple("02-tickets/PROJ/PROJ-312/archive/PROJ-312-old.md", {})[0],
                         "ticket")

    def test_vault_census_flat_paths_and_loose_files_are_unchanged(self):
        self.assertEqual(vault_census.split_ticket_path("02-tickets/sprints/plan.md").folder, "sprints")
        self.assertIsNone(vault_census.split_ticket_path("03-knowledge-base/x.md"))

    def test_backfill_tool_reads_a_nested_state_file(self):
        tool = backfill_vault_frontmatter
        self.assertTrue(tool.is_ticket_state_path("02-tickets/PROJ/PROJ-312/PROJ-312-state.md"))
        self.assertTrue(tool.is_ticket_state_path("02-tickets/PROJ-312/PROJ-312-state.md"))
        self.assertFalse(tool.is_ticket_state_path("02-tickets/PROJ/PROJ-312/PROJ-312-spec.md"))
        self.assertFalse(tool.is_ticket_state_path("02-tickets/PROJ/PROJ-312/archive/PROJ-312-state.md"))
        folder, middle, name = tool._ticket_parts("02-tickets/PROJ/PROJ-312/archive/PROJ-312-old.md")
        self.assertEqual((folder, middle, name), ("PROJ-312", ("archive",), "PROJ-312-old.md"))

    def test_census_and_backfill_folder_rows_come_from_the_layout(self):
        for module in (vault_census, backfill_vault_frontmatter):
            prefixes = [prefix for row in module.FOLDER_ROWS for prefix in row.prefixes]
            self.assertIn("01-system-map/platform-learning/", prefixes)
            self.assertIn("03-knowledge-base/decisions/", prefixes)
            self.assertFalse([p for p in prefixes if "System-notes" in p or "/sql/" in p])
            self.assertEqual(module.EXCLUDED_PATH_PREFIXES, ("memory/",))

    def test_system_progress_reads_the_memory_folder_of_the_layout(self):
        with throwaway_home() as (home, env):
            memory = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "memory"
            memory.mkdir(parents=True)
            (memory / "MEMORY.md").write_text("x" * 2048)
            proc = run([sys.executable, str(STATE / "system_progress.py"), "--json", "--root", str(ROOT)], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertGreaterEqual(json.loads(proc.stdout)["layer_3"]["memory_kb"], 2.0)


if __name__ == "__main__":
    unittest.main()
