#!/usr/bin/env python3
"""Tests for the sync scripts: sweep, lint_wikilinks, sync_conversations, sync_meetings,
sync_repos. All data is synthetic and every run happens in a throwaway home.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove each sync tool writes only into the folders the path loader returns, that
sweep never opens the index without --yes, and that the real state is unchanged.
Change log:
  - First version.
  - Added a test that the real index step writes the build_index chunk fields.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
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
sys.path.insert(0, str(ROOT / "scripts"))

from throwaway_home import throwaway_home  # noqa: E402
from connector_helpers import assert_no_network  # noqa: E402
from real_guard import RealStateGuard  # noqa: E402


def load_sweep():
    loader = importlib.machinery.SourceFileLoader("tg_sweep", str(SYNC / "sweep"))
    spec = importlib.util.spec_from_loader("tg_sweep", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run(args, env, input_text=None):
    return subprocess.run(args, env=dict(env, PYTHONDONTWRITEBYTECODE="1"), input=input_text,
                          capture_output=True, text=True, timeout=120)


def tree_files(folder):
    return sorted(str(p.relative_to(folder)) for p in pathlib.Path(folder).rglob("*") if p.is_file())


def record(rid="r1", kind="decision", **extra):
    base = {"id": rid, "date": "2026-01-02", "ticket": "T-001", "record_type": kind,
            "source_repo": "demo", "source_ref": "ref-" + rid,
            "summary": "A short summary", "detail": "Some detail text for " + rid,
            "tags": [], "session_type": "interactive", "vault_status": "staged"}
    base.update(extra)
    return base


class FakeIndex:
    def __init__(self, fail_ids=()):
        self.synced = []
        self.fail_ids = fail_ids

    def sync(self, rec):
        if rec["id"] in self.fail_ids:
            raise RuntimeError("fake failure")
        self.synced.append(rec["id"])


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.sweep = load_sweep()

    def _stage(self, env, records):
        staging = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "output" / "knowledge-staging"
        staging.mkdir(parents=True)
        for rec in records:
            (staging / "{}-{}.json".format(rec["ticket"], rec["id"])).write_text(json.dumps(rec))
        return staging

    def _call(self, argv, env, factory):
        old = dict(os.environ)
        os.environ.update(env)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = self.sweep.main(argv, index_factory=factory)
        finally:
            os.environ.clear()
            os.environ.update(old)
        return code, out.getvalue()

    def test_chroma_index_writes_the_build_index_chunk_fields(self):
        with throwaway_home() as (home, env), assert_no_network():
            env = dict(env, TOLLGATE_EMBEDDER="hash")
            old = dict(os.environ)
            os.environ.update(env)
            try:
                index = self.sweep.ChromaIndex()
                index.sync(record("m1"))
                got = index._collection.get(ids=["m1"], include=["metadatas"])["metadatas"][0]
            finally:
                os.environ.clear()
                os.environ.update(old)
            for key in ("file", "heading", "source", "embedding_model", "truncated", "origin", "tags"):
                self.assertIn(key, got)
            self.assertEqual(got["file"], "ref-m1")
            self.assertEqual(got["source"], "knowledge")
            self.assertEqual(got["embedding_model"], "hash-v1")
            self.assertEqual(got["source_repo"], "demo")

    def test_preview_prints_the_plan_and_touches_nothing(self):
        with throwaway_home() as (home, env), assert_no_network():
            staging = self._stage(env, [record("a"), record("b", "approval")])
            vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
            before = tree_files(vault)
            calls = []
            code, out = self._call([], env, lambda: calls.append("opened") or FakeIndex())
            self.assertEqual(code, 0)
            self.assertEqual(calls, [])                      # the index factory was never called
            self.assertEqual(tree_files(vault), before)      # nothing written anywhere
            self.assertIn("plan:", out)
            self.assertIn("preview only", out)
            self.assertIn("processed=2 written=0 synced=0 partial=0 skipped=0", out)
            self.assertEqual(len(list(staging.glob("*.json"))), 2)

    def test_yes_writes_vault_notes_and_indexes(self):
        with throwaway_home() as (home, env), assert_no_network():
            staging = self._stage(env, [record("a"), record("b", "approval"), record("c", "pattern"),
                                        record("d", "repo_doc")])
            index = FakeIndex()
            code, out = self._call(["--yes"], env, lambda: index)
            vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
            self.assertEqual(code, 0)
            self.assertIn("processed=4 written=4 synced=4 partial=0 skipped=0", out)
            self.assertEqual(sorted(index.synced), ["a", "b", "c", "d"])
            self.assertTrue((vault / "03-knowledge-base/decisions/2026-01-02-T-001.md").exists())
            # no folder for T-001 yet: the approval goes to the prefix folder
            self.assertTrue((vault / "02-tickets/T/T-001/approval-b.md").exists())
            self.assertFalse((vault / "02-tickets/T-001").exists())
            self.assertTrue((vault / "03-knowledge-base/patterns/2026-01-02-T-001.md").exists())
            self.assertTrue((vault / "01-system-map/repos/demo.md").exists())
            self.assertEqual(list(staging.glob("*.json")), [])
            # everything written is inside the vault
            self.assertTrue(all(not f.startswith("..") for f in tree_files(vault)))

    def test_approval_goes_to_the_ticket_folder_that_already_exists(self):
        for existing in ("02-tickets/T-001", "02-tickets/T/T-001"):
            with throwaway_home() as (home, env), assert_no_network():
                vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
                (vault / existing).mkdir(parents=True)
                self._stage(env, [record("b", "approval")])
                code, out = self._call(["--yes"], env, lambda: FakeIndex())
                self.assertEqual(code, 0)
                self.assertTrue((vault / existing / "approval-b.md").exists())

    def test_index_failure_keeps_the_record_for_retry_and_never_writes_twice(self):
        with throwaway_home() as (home, env):
            staging = self._stage(env, [record("a")])
            code, out = self._call(["--yes"], env, lambda: FakeIndex(fail_ids=("a",)))
            self.assertIn("written=1 synced=0 partial=1", out)
            kept = json.loads(next(staging.glob("*.json")).read_text())
            self.assertEqual(kept["vault_status"], "vault_written")
            index = FakeIndex()
            code, out = self._call(["--yes"], env, lambda: index)
            self.assertIn("written=0 synced=1 partial=0", out)
            self.assertEqual(index.synced, ["a"])
            note = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "03-knowledge-base/decisions/2026-01-02-T-001.md"
            self.assertEqual(note.read_text().count("<!-- id:a -->"), 1)

    def test_missing_index_library_is_a_partial_not_a_crash(self):
        with throwaway_home() as (home, env):
            self._stage(env, [record("a")])

            def broken():
                raise ImportError("no index library")
            code, out = self._call(["--yes"], env, broken)
            self.assertEqual(code, 0)
            self.assertIn("partial=1", out)

    def test_duplicate_ids_are_skipped(self):
        with throwaway_home() as (home, env):
            staging = self._stage(env, [record("a")])
            (staging / "T-002-a.json").write_text(json.dumps(record("a", ticket="T-002")))
            code, out = self._call(["--yes"], env, lambda: FakeIndex())
            self.assertIn("processed=1 written=1 synced=1 partial=0 skipped=1", out)

    def test_corrupt_and_invalid_files_are_skipped(self):
        with throwaway_home() as (home, env):
            staging = self._stage(env, [record("a")])
            (staging / "bad.json").write_text("{not json")
            (staging / "short.json").write_text(json.dumps({"id": "x"}))
            code, out = self._call(["--yes"], env, lambda: FakeIndex())
            self.assertIn("processed=1", out)

    def test_nothing_staged_and_not_set_up(self):
        with throwaway_home() as (home, env):
            code, out = self._call([], env, FakeIndex)
            self.assertEqual(code, 0)
            self.assertIn("nothing staged", out)
        with throwaway_home() as (home, env):
            bare = {k: v for k, v in env.items() if k not in ("TOLLGATE_KNOWLEDGE", "TOLLGATE_PATHS")}
            proc = run([str(SYNC / "sweep")], bare)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not set up", proc.stderr)

    def test_command_line_preview_leaves_the_real_state_alone(self):
        with throwaway_home() as (home, env):
            self._stage(env, [record("a")])
            before = tree_files(env["TOLLGATE_KNOWLEDGE"])
            with RealStateGuard(vault_path=env["TOLLGATE_KNOWLEDGE"]):
                proc = run([str(SYNC / "sweep")], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(tree_files(env["TOLLGATE_KNOWLEDGE"]), before)
            self.assertFalse((pathlib.Path(home) / ".tollgate" / "index").exists())


class LintAndConversations(unittest.TestCase):
    def test_lint_wikilinks_converts_and_keeps_state_in_the_state_folder(self):
        with throwaway_home() as (home, env):
            vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
            (vault / "a.md").write_text("see [the note](b.md) and [b](b.md#sec) and [web](https://x.test)\n")
            (vault / "b.md").write_text("body\n")
            dry = run([sys.executable, str(SYNC / "lint_wikilinks.py"), "--dry-run"], env)
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertIn("(b.md)", (vault / "a.md").read_text())
            real = run([sys.executable, str(SYNC / "lint_wikilinks.py")], env)
            self.assertEqual(real.returncode, 0, real.stderr)
            text = (vault / "a.md").read_text()
            self.assertIn("[[b|the note]]", text)
            self.assertIn("[[b#sec]]", text)
            self.assertIn("(https://x.test)", text)
            state = pathlib.Path(env["TOLLGATE_STATE_DIR"]) / "lint_wikilinks_state.json"
            self.assertTrue(state.exists())
            self.assertFalse(any(".json" in f for f in tree_files(vault)))   # no state inside the vault

    def test_sync_conversations_writes_only_conversations_and_state(self):
        with throwaway_home() as (home, env):
            sessions = pathlib.Path(home) / "sessions"
            sessions.mkdir()
            lines = [
                {"type": "ai-title", "aiTitle": "Demo chat"},
                {"type": "user", "timestamp": "2026-03-05T10:00:00Z",
                 "message": {"content": "Please explain the plan in simple words"}},
                {"type": "assistant", "timestamp": "2026-03-05T10:01:00Z",
                 "message": {"content": [{"type": "text", "text": "Here is a plain explanation of the plan."}]}},
            ]
            (sessions / "abcd1234-0000.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
            before = tree_files(sessions)
            proc = run([sys.executable, str(SYNC / "sync_conversations.py"), "--sessions-dir", str(sessions)], env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Converted : 1", proc.stdout)
            self.assertEqual(tree_files(sessions), before)       # the session folder is read only
            conv = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "05-conversations"
            files = tree_files(conv)
            self.assertEqual(len(files), 1)
            self.assertIn("auto-abcd1234", files[0])
            self.assertTrue((pathlib.Path(env["TOLLGATE_STATE_DIR"]) / "sync_conversations_state.json").exists())
            again = run([sys.executable, str(SYNC / "sync_conversations.py"), "--sessions-dir", str(sessions)], env)
            self.assertIn("Skipped   : 1", again.stdout)

    def test_sync_conversations_not_set_up(self):
        with throwaway_home() as (home, env):
            bare = {k: v for k, v in env.items() if k not in ("TOLLGATE_KNOWLEDGE", "TOLLGATE_PATHS")}
            proc = run([sys.executable, str(SYNC / "sync_conversations.py")], bare)
            self.assertEqual(proc.returncode, 2)


class MeetingsAndRepos(unittest.TestCase):
    def test_sync_meetings_never_overwrites_curated_notes(self):
        with throwaway_home() as (home, env):
            src = pathlib.Path(home) / "exports"
            src.mkdir()
            name = "2026-04-07 - Weekly Sync - 2026 04 07 13:29 PDT - Notes by Gemini.md"
            (src / name).write_text("<style>x</style>\n# Weekly Sync\nIt&#39;s fine\n")
            script = str(SYNC / "sync_meetings.py")
            proc = run([sys.executable, script, "--source", str(src)], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            notes = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "meetings/2026/04/2026-04-07_weekly-sync/notes.md"
            self.assertEqual(notes.read_text(), "# Weekly Sync\nIt's fine")
            notes.write_text("curated\n")
            run([sys.executable, script, "--source", str(src), "--full"], env)
            self.assertEqual(notes.read_text(), "curated\n")

    def test_sync_meetings_needs_a_source(self):
        with throwaway_home() as (home, env):
            proc = run([sys.executable, str(SYNC / "sync_meetings.py")], env)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not set up", proc.stderr)

    def test_sync_repos_clones_and_updates_a_local_repo_without_network(self):
        with throwaway_home() as (home, env), assert_no_network():
            origin = pathlib.Path(home) / "origin"
            git = ["git", "-c", "user.name=tg", "-c", "user.email=tg@example.invalid"]
            run(["git", "init", "-q", "-b", "main", str(origin)], env)
            (origin / "f.txt").write_text("one\n")
            run(git + ["-C", str(origin), "add", "."], env)
            run(git + ["-C", str(origin), "commit", "-q", "-m", "first"], env)
            state = pathlib.Path(env["TOLLGATE_STATE_DIR"])
            state.mkdir(parents=True, exist_ok=True)
            (state / "repos.list").write_text("# mirror list\nmirror {}\n".format(origin))
            first = run(["bash", str(SYNC / "sync_repos.sh")], env)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            mirror = pathlib.Path(env["TOLLGATE_CODE_DIR"]) / "mirror"
            self.assertEqual((mirror / "f.txt").read_text(), "one\n")
            (origin / "f.txt").write_text("two\n")
            run(git + ["-C", str(origin), "commit", "-q", "-am", "second"], env)
            second = run(["bash", str(SYNC / "sync_repos.sh")], env)
            self.assertIn("Pulled 1 new commit", second.stdout)
            self.assertEqual((mirror / "f.txt").read_text(), "two\n")

    def test_sync_repos_without_a_list_does_nothing(self):
        with throwaway_home() as (home, env):
            proc = run(["bash", str(SYNC / "sync_repos.sh")], env)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("nothing to sync", proc.stdout)


if __name__ == "__main__":
    unittest.main()
