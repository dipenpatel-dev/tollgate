#!/usr/bin/env python3
"""Tests for the PHI and secret scan, corrupt state handling and folder naming in
sync_conversations.py and sync_meetings.py. All data is synthetic, every run is in a
throwaway home, and fake keys and fake PHI are built at run time from parts.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove a transcript or meeting note with PHI never reaches the vault (a short record with
no content goes to a quarantine log instead), credentials are redacted before writing, a corrupt
state file is reported and replaced, the state write is atomic, and two meetings with the same
date and title both land in the vault.
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
SYNC = ROOT / "scripts" / "sync"
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "tests" / "hooks"))
sys.path.insert(0, str(ROOT / "scripts" / "sync"))

from throwaway_home import throwaway_home  # noqa: E402
import fake_phi  # noqa: E402
import vault_write_scan  # noqa: E402


def run(args, env):
    return subprocess.run(args, env=dict(env, PYTHONDONTWRITEBYTECODE="1"), capture_output=True,
                          text=True, timeout=120)


def tree_files(folder):
    return sorted(str(p.relative_to(folder)) for p in pathlib.Path(folder).rglob("*") if p.is_file())


def fake_secret() -> str:
    return "sk-" + "ant-" + "FAKEFAKEFAKEFAKEFAKEFAKE1234"


def write_session(folder: pathlib.Path, name: str, user_text: str, assistant_text: str) -> None:
    lines = [
        {"type": "ai-title", "aiTitle": "Demo chat"},
        {"type": "user", "timestamp": "2026-03-05T10:00:00Z", "message": {"content": user_text}},
        {"type": "assistant", "timestamp": "2026-03-05T10:01:00Z",
         "message": {"content": [{"type": "text", "text": assistant_text}]}},
    ]
    (folder / name).write_text("\n".join(json.dumps(x) for x in lines))


class ScanModule(unittest.TestCase):
    def test_clean_text_passes_unchanged(self):
        result = vault_write_scan.scan_text("A plain note about a build plan.")
        self.assertEqual((result.quarantine, result.redacted, result.text),
                         (False, [], "A plain note about a build plan."))

    def test_secret_is_redacted_and_not_returned(self):
        result = vault_write_scan.scan_text("the key is " + fake_secret() + " ok")
        self.assertIn("ANTHROPIC_KEY", result.redacted)
        self.assertNotIn("FAKEFAKE", result.text)
        self.assertIn("[REDACTED:ANTHROPIC_KEY]", result.text)

    def test_phi_is_flagged_with_labels_only(self):
        result = vault_write_scan.scan_text("record " + fake_phi.fake_ssn() + " and " + fake_phi.fake_mrn())
        self.assertTrue(result.quarantine)
        self.assertNotIn(fake_phi.fake_ssn(), result.reason())

    def test_corrupt_state_warns_and_returns_empty(self):
        with throwaway_home() as (home, env):
            path = pathlib.Path(home) / "state.json"
            path.write_text("{not json")
            warnings = []
            self.assertEqual(vault_write_scan.load_json_state(path, warnings.append), {})
            self.assertEqual(len(warnings), 1)
            path.write_text("[1, 2]")
            self.assertEqual(vault_write_scan.load_json_state(path, warnings.append), {})
            self.assertEqual(len(warnings), 2)
            self.assertEqual(vault_write_scan.load_json_state(pathlib.Path(home) / "none.json", warnings.append), {})
            self.assertEqual(len(warnings), 2)

    def test_atomic_write_leaves_no_temp_file_and_replaces_content(self):
        with throwaway_home() as (home, env):
            path = pathlib.Path(home) / "out" / "state.json"
            vault_write_scan.write_json_atomic(path, {"a": 1})
            vault_write_scan.write_json_atomic(path, {"a": 2})
            self.assertEqual(json.loads(path.read_text()), {"a": 2})
            self.assertEqual(os.listdir(path.parent), ["state.json"])


class Conversations(unittest.TestCase):
    def sync(self, env, sessions):
        return run([sys.executable, str(SYNC / "sync_conversations.py"), "--sessions-dir", str(sessions)], env)

    def test_phi_transcript_is_quarantined_and_not_written(self):
        with throwaway_home() as (home, env):
            sessions = pathlib.Path(home) / "sessions"
            sessions.mkdir()
            write_session(sessions, "aaaa1111-0000.jsonl", "Please look at " + fake_phi.fake_ssn() + " and " + fake_phi.fake_mrn(),
                          "I will not store that identifier anywhere at all.")
            write_session(sessions, "bbbb2222-0000.jsonl", "Please explain the plan in simple words",
                          "Here is a plain explanation of the plan.")
            proc = self.sync(env, sessions)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Converted : 1", proc.stdout)
            self.assertIn("Quarantined : 1", proc.stdout)
            conv = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "05-conversations"
            files = tree_files(conv)
            self.assertEqual(len(files), 1)
            self.assertIn("bbbb2222", files[0])
            log = pathlib.Path(env["TOLLGATE_STATE_DIR"]) / "quarantine.log"
            text = log.read_text()
            self.assertIn("aaaa1111-0000.jsonl", text)
            self.assertIn("PHI scan", text)
            self.assertNotIn(fake_phi.fake_ssn(), text)
            self.assertNotIn(fake_phi.fake_ssn(), proc.stdout)
            again = self.sync(env, sessions)
            self.assertIn("Skipped   : 2", again.stdout)

    def test_secret_is_redacted_in_the_written_file(self):
        with throwaway_home() as (home, env):
            sessions = pathlib.Path(home) / "sessions"
            sessions.mkdir()
            write_session(sessions, "cccc3333-0000.jsonl", "My key is " + fake_secret() + " please keep going",
                          "I saw a credential in your message and will ignore it.")
            proc = self.sync(env, sessions)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            conv = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "05-conversations"
            (name,) = tree_files(conv)
            text = (conv / name).read_text()
            self.assertNotIn("FAKEFAKE", text)
            self.assertIn("[REDACTED:ANTHROPIC_KEY]", text)

    def test_corrupt_state_file_is_reported_and_replaced(self):
        with throwaway_home() as (home, env):
            sessions = pathlib.Path(home) / "sessions"
            sessions.mkdir()
            write_session(sessions, "dddd4444-0000.jsonl", "Please explain the plan in simple words",
                          "Here is a plain explanation of the plan.")
            state = pathlib.Path(env["TOLLGATE_STATE_DIR"]) / "sync_conversations_state.json"
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text("{broken")
            proc = self.sync(env, sessions)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("unreadable", proc.stderr)
            self.assertIn("Converted : 1", proc.stdout)
            self.assertEqual(list(json.loads(state.read_text())), ["dddd4444-0000.jsonl"])

    def test_script_has_future_annotations_for_python_39(self):
        text = (SYNC / "sync_conversations.py").read_text()
        self.assertIn("from __future__ import annotations", text)
        self.assertLess(text.index("from __future__ import annotations"), text.index("import json"))


class SessionsFolderName(unittest.TestCase):
    """Claude Code names a project folder by turning every non letter or digit into a dash."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import sync_conversations
        self.mod = sync_conversations

    def test_slug_for_a_path_with_dots_underscores_and_spaces(self):
        self.assertEqual(self.mod.project_slug("/Users/a.b/My_Vault v2/x"), "-Users-a-b-My-Vault-v2-x")
        self.assertEqual(self.mod.project_slug("/tmp/tollgate_test-1.2"), "-tmp-tollgate-test-1-2")

    def test_default_sessions_dir_uses_the_slug_under_the_config_folder(self):
        with throwaway_home() as (home, env):
            vault = pathlib.Path(home) / "my_vault.d"
            saved = dict(os.environ)
            os.environ.clear()
            os.environ.update(env)
            os.environ["TOLLGATE_KNOWLEDGE"] = str(vault)
            os.environ["CLAUDE_CONFIG_DIR"] = str(pathlib.Path(home) / ".claude")
            try:
                got = self.mod.default_sessions_dir()
            finally:
                os.environ.clear()
                os.environ.update(saved)
            self.assertEqual(got, pathlib.Path(home) / ".claude" / "projects" / self.mod.project_slug(vault))
            self.assertNotIn("_", got.name)
            self.assertNotIn(".", got.name)

    def test_a_sessions_line_in_the_paths_file_overrides_the_folder(self):
        with throwaway_home() as (home, env):
            chosen = pathlib.Path(home) / "elsewhere" / "sessions"
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text("sessions: %s\n" % chosen)
            saved = dict(os.environ)
            os.environ.clear()
            os.environ.update(env)
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            try:
                got = self.mod.default_sessions_dir()
            finally:
                os.environ.clear()
                os.environ.update(saved)
            self.assertEqual(got, chosen)


class Meetings(unittest.TestCase):
    def sync(self, env, src, *extra):
        return run([sys.executable, str(SYNC / "sync_meetings.py"), "--source", str(src), *extra], env)

    @staticmethod
    def name(title, hhmm="13:29", date="2026-04-07", copy=""):
        stamp = date.replace("-", " ") + " " + hhmm
        return f"{date} - {title} - {stamp} PDT - Notes by Gemini{copy}.md"

    def meetings(self, env):
        return pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "meetings"

    def test_same_date_and_title_keeps_both_meetings(self):
        with throwaway_home() as (home, env):
            src = pathlib.Path(home) / "exports"
            src.mkdir()
            (src / self.name("Weekly Sync", "09:00")).write_text("# Weekly Sync\nmorning notes\n")
            (src / self.name("Weekly Sync", "13:29")).write_text("# Weekly Sync\nafternoon notes\n")
            (src / self.name("Weekly Sync", "13:29", copy=" (1)")).write_text("# Weekly Sync\nafternoon notes\n")
            proc = self.sync(env, src)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            root = self.meetings(env) / "2026" / "04"
            folders = sorted(p.name for p in root.iterdir())
            self.assertEqual(folders, ["2026-04-07_weekly-sync", "2026-04-07_weekly-sync_1329"])
            texts = {f: (root / f / "notes.md").read_text() for f in folders}
            self.assertIn("morning", texts["2026-04-07_weekly-sync"])
            self.assertIn("afternoon", texts["2026-04-07_weekly-sync_1329"])
            again = self.sync(env, src, "--full")
            self.assertEqual(sorted(p.name for p in root.iterdir()), folders)
            self.assertIn("Synced: 0", again.stdout)

    def test_same_time_and_title_gets_a_number(self):
        with throwaway_home() as (home, env):
            src = pathlib.Path(home) / "exports"
            src.mkdir()
            (src / self.name("Review", "10:00")).write_text("# Review\nfirst\n")
            (src / self.name("Review", "10:00", date="2026-04-07").replace("Notes by Gemini", "Notes by Gemini (2)")
             ).write_text("# Review\nsecond copy\n")
            proc = self.sync(env, src)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            root = self.meetings(env) / "2026" / "04"
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["2026-04-07_review"])

    def test_empty_slug_gets_a_fallback_name(self):
        with throwaway_home() as (home, env):
            src = pathlib.Path(home) / "exports"
            src.mkdir()
            (src / self.name("!!!")).write_text("# Notes\nbody\n")
            proc = self.sync(env, src)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            root = self.meetings(env) / "2026" / "04"
            self.assertEqual([p.name for p in root.iterdir()], ["2026-04-07_untitled-meeting"])

    def test_corrupt_state_is_reported_and_replaced(self):
        with throwaway_home() as (home, env):
            src = pathlib.Path(home) / "exports"
            src.mkdir()
            (src / self.name("Weekly Sync")).write_text("# Weekly Sync\nbody\n")
            meetings = self.meetings(env)
            meetings.mkdir(parents=True)
            (meetings / ".sync-state.json").write_text("not json at all")
            proc = self.sync(env, src)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("unreadable", proc.stderr)
            state = json.loads((meetings / ".sync-state.json").read_text())
            self.assertIn(self.name("Weekly Sync"), state)
            self.assertEqual([f for f in os.listdir(meetings) if f.endswith(".tmp")], [])

    def test_phi_note_is_quarantined_and_not_written(self):
        with throwaway_home() as (home, env):
            src = pathlib.Path(home) / "exports"
            src.mkdir()
            (src / self.name("Case Review")).write_text(
                "# Case Review\nPatient " + fake_phi.fake_mrn() + " ssn " + fake_phi.fake_ssn() + "\n")
            (src / self.name("Planning", "15:00")).write_text("# Planning\nplain plan\n")
            proc = self.sync(env, src)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Quarantined (PHI): 1", proc.stdout)
            meetings = self.meetings(env)
            files = tree_files(meetings)
            self.assertFalse(any("case-review" in f for f in files), files)
            self.assertTrue(any("planning" in f for f in files), files)
            log = (meetings / ".quarantine.log").read_text()
            self.assertIn("Notes by Gemini.md", log)
            self.assertNotIn(fake_phi.fake_ssn(), log)
            self.assertNotIn(fake_phi.fake_ssn(), proc.stdout)

    def test_secret_in_a_note_is_redacted(self):
        with throwaway_home() as (home, env):
            src = pathlib.Path(home) / "exports"
            src.mkdir()
            (src / self.name("Ops")).write_text("# Ops\nuse key " + fake_secret() + " for the job\n")
            proc = self.sync(env, src)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            notes = self.meetings(env) / "2026" / "04" / "2026-04-07_ops" / "notes.md"
            text = notes.read_text()
            self.assertNotIn("FAKEFAKE", text)
            self.assertIn("[REDACTED:ANTHROPIC_KEY]", text)

    def test_curated_folder_is_still_never_overwritten(self):
        with throwaway_home() as (home, env):
            src = pathlib.Path(home) / "exports"
            src.mkdir()
            (src / self.name("Weekly Sync")).write_text("# Weekly Sync\nbody\n")
            curated = self.meetings(env) / "2026" / "04" / "2026-04-07_weekly-sync"
            curated.mkdir(parents=True)
            (curated / "notes.md").write_text("curated\n")
            proc = self.sync(env, src)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual((curated / "notes.md").read_text(), "curated\n")
            self.assertEqual([p.name for p in curated.parent.iterdir()], ["2026-04-07_weekly-sync"])


if __name__ == "__main__":
    unittest.main()
