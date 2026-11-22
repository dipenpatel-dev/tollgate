"""
module_name: test_internals.py
description: Embedder, chunking, router weights, orphan clean up, index health probes and the opt in model download.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported the index health test (top-K floor and probe run) and added unit checks. Probes are synthetic.
"""
import json
import math
import pathlib
import unittest

import support
from support import in_env, run_script, script_env, throwaway_home, write


class EmbedderAndChunks(unittest.TestCase):
    def test_hash_embedder_is_deterministic_and_normalised(self):
        import embedder
        e = embedder.HashEmbedder()
        a, b = e.encode(["retry the nightly load"]), e.encode(["retry the nightly load"])
        self.assertEqual(a, b)
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in a[0])), 1.0, places=6)
        self.assertNotEqual(a, e.encode(["a different sentence entirely"]))

    def test_similar_text_scores_higher_than_unrelated(self):
        import embedder
        e = embedder.HashEmbedder()
        q, near, far = e.encode(["duplicate rows after retry"])[0], e.encode(["retry made duplicate rows"])[0], e.encode(["pizza topping"])[0]
        dot = lambda x, y: sum(i * j for i, j in zip(x, y))
        self.assertGreater(dot(q, near), dot(q, far) + 0.3)

    def test_get_embedder_names(self):
        import embedder
        self.assertEqual(embedder.get_embedder("hash").name, "hash-v1")
        self.assertEqual(embedder.get_embedder("fake").name, "hash-v1")

    def test_markdown_chunks_follow_headings(self):
        import build_index
        text = "# One\n\n" + "alpha " * 30 + "\n\n## Two\n\n" + "beta " * 30
        chunks = build_index.chunk_markdown(text, "f.md")
        self.assertEqual([c["heading"] for c in chunks], ["One", "Two"])
        self.assertIn("[...]", chunks[1]["content"])

    def test_python_and_sql_chunkers(self):
        import build_index
        py = "import os\n\n" + "def one():\n    return 1  # " + "x" * 80 + "\n\nclass Two:\n    pass  # " + "y" * 80 + "\n"
        self.assertEqual([c["heading"] for c in build_index.chunk_python(py, "f.py")], ["one", "Two"])
        sql = "-- first\nSELECT 1 FROM t WHERE a = 1 AND b = 2 AND c = 3 AND d = 4 AND e = 5 AND f = 6 AND g = 7;\n\n"
        self.assertTrue(build_index.chunk_sql(sql, "f.sql"))

    def test_router_weight_helpers(self):
        import router
        out = router._tilts({"vault": 1.0, "tickets": 0.5}, ["vault", "tickets"], False)
        self.assertTrue(all(0.9 <= v <= 1.1 for v in out.values()))
        ranked = [{"collection": "vault", "score": 1.0 - i / 10} for i in range(4)] + [{"collection": "tickets", "score": 0.1}]
        top = router._enforce_collection_distribution(ranked, 2, 4)
        self.assertEqual(len(top), 4)
        self.assertIn("tickets", {r["collection"] for r in top})

    def test_tier_words(self):
        import config
        self.assertEqual(config.tier_for("notes/2026-decision-null.md")[0], 1)
        self.assertEqual(config.tier_for("meetings/standup.md")[0], 3)
        self.assertEqual(config.tier_for("notes/plain.md")[0], 2)

    def test_download_model_does_nothing_without_the_flag(self):
        with throwaway_home() as (_home, env):
            proc = run_script("download_model.py", [], script_env(env))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Nothing downloaded", proc.stdout)

    def test_rebuild_script_uses_the_path_loader(self):
        text = (support.SEARCH / "rebuild.sh").read_text(encoding="utf-8")
        self.assertIn("tg_path", text)


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class IndexMaintenance(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.vault = support.make_vault(pathlib.Path(self.home) / "vault")
        self.env = script_env(env, TOLLGATE_KNOWLEDGE=str(self.vault))

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def test_deleted_file_leaves_no_chunks(self):
        import build_index
        import router
        with in_env(self.env):
            build_index.build(full=True, embedder_name="hash")
            (self.vault / "notes" / "beta.md").unlink()
            summary = build_index.build(embedder_name="hash")
            files = {m["file"] for m in router.open_collections(__import__("config").index_root())["vault"].get()["metadatas"]}
        self.assertGreater(summary["orphans_deleted"], 0)
        self.assertNotIn("notes/beta.md", files)

    def test_file_edited_below_the_minimum_loses_its_old_chunks(self):
        import build_index
        import config
        import router
        with in_env(self.env):
            build_index.build(full=True, embedder_name="hash")
            note = self.vault / "notes" / "beta.md"
            note.write_text("# Beta\n\ntiny\n", encoding="utf-8")
            __import__("os").utime(note, (1, 1))
            build_index.build(embedder_name="hash")
            files = {m["file"] for m in router.open_collections(config.index_root())["vault"].get()["metadatas"]}
        self.assertNotIn("notes/beta.md", files)
        self.assertIn("notes/alpha.md", files)

    def test_source_limited_full_run_does_not_rewrite_the_marker(self):
        import build_index
        import config
        import embedder
        with in_env(self.env):
            build_index.build(full=True, embedder_name="hash")
            root = config.index_root()
            embedder.write_marker(root, type("E", (), {"name": "other-model"})())
            with self.assertRaises(ValueError):
                build_index.build(only="vault", full=True, embedder_name="hash")
            self.assertEqual(embedder.read_marker(root), "other-model")
            build_index.build(full=True, embedder_name="hash")
            self.assertEqual(embedder.read_marker(root), "hash-v1")

    def test_source_limited_run_writes_the_marker_when_none_exists(self):
        import build_index
        import config
        import embedder
        with in_env(self.env):
            build_index.build(only="vault", full=True, embedder_name="hash")
            self.assertEqual(embedder.read_marker(config.index_root()), "hash-v1")

    def test_tickets_are_not_indexed_twice(self):
        import build_index
        with in_env(self.env):
            summary = build_index.build(full=True, embedder_name="hash")
            keys = [k for _p, k, c in build_index.find_source_files() if c == "vault"]
        self.assertTrue(all("02-tickets" not in k for k in keys), keys)
        self.assertGreater(summary["counts"]["tickets"], 0)

    def test_health_check_top_k_floor(self):
        import check_index_health
        self.assertGreaterEqual(check_index_health.TOP_K, 60)

    def test_health_check_probes(self):
        write(pathlib.Path(self.home) / ".tollgate" / "index_health.json", json.dumps([
            {"label": "alpha", "file_contains": "alpha", "query": "nightly load retries twice and pages the owner"},
        ]))
        self.assertEqual(run_script("build_index.py", ["--full", "--embedder", "hash"], self.env).returncode, 0)
        proc = run_script("check_index_health.py", ["--no-report"], self.env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS", proc.stdout)
        write(pathlib.Path(self.home) / ".tollgate" / "index_health.json", json.dumps([
            {"label": "absent", "file_contains": "no-such-file", "query": "nightly load"}]))
        self.assertEqual(run_script("check_index_health.py", ["--no-report"], self.env).returncode, 1)

    def test_health_check_without_an_index_fails_cleanly(self):
        proc = run_script("check_index_health.py", ["--no-report"], self.env)
        self.assertEqual(proc.returncode, 1)

    def test_health_report_is_written_to_the_logs_folder(self):
        self.assertEqual(run_script("build_index.py", ["--full", "--embedder", "hash"], self.env).returncode, 0)
        proc = run_script("check_index_health.py", [], self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(list((pathlib.Path(self.home) / ".tollgate" / "logs").glob("index-health-*.json")))

    def test_rebuild_script_runs(self):
        import subprocess
        env = dict(self.env)
        env["TOLLGATE_PYTHON"] = __import__("sys").executable
        env["TOLLGATE_HOME"] = str(support.ROOT)
        proc = subprocess.run(["bash", str(support.SEARCH / "rebuild.sh"), "--embedder", "hash"],
                              capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"embedder": "hash-v1"', proc.stdout)


if __name__ == "__main__":
    unittest.main()


class SearchLayoutAndOptionalCollections(unittest.TestCase):
    """Chat-thread tier, meeting chunking, vault skip folders, and the optional code and standards collections."""

    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.home = pathlib.Path(self.home)
        self.vault = support.make_vault(self.home / "vault")
        self.env = script_env(env, TOLLGATE_KNOWLEDGE=str(self.vault))

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def _keys(self, collection=None):
        import build_index
        return sorted(k for _p, k, c in build_index.find_source_files() if collection is None or c == collection)

    def test_chat_threads_are_tier_three(self):
        import config
        self.assertEqual(config.tier_for("06-chat-threads/2026-11/day.md")[0], 3)
        self.assertEqual(config.tier_for("notes/plain.md")[0], 2)
        self.assertIn("chat", config.load_routing()["tiers"][3])
        self.assertIn("thread", config.load_routing()["tiers"][3])

    def test_meeting_files_are_split_by_size(self):
        import build_index
        import config
        body = "\n\n".join(f"Paragraph {i}. " + "words " * 60 for i in range(40))
        write(self.vault / "meetings" / "standup.md", "# Standup\n\n" + body)
        write(self.vault / "notes" / "long.md", "# Long\n\n" + body)
        with in_env(self.env):
            meeting, _t = build_index.read_chunks(self.vault / "meetings" / "standup.md", "meetings/standup.md", "vault")
            other, _t = build_index.read_chunks(self.vault / "notes" / "long.md", "notes/long.md", "vault")
        self.assertGreater(len(meeting), 3)
        self.assertEqual(len(other), 1)
        self.assertLessEqual(max(len(c["content"]) for c in meeting), config.MAX_CHUNK_CHARS)

    def test_meetings_outside_the_vault_are_indexed_and_split(self):
        import build_index
        outside = self.home / "meet"
        write(outside / "m.md", "# M\n\n" + "\n\n".join("para %d %s" % (i, "text " * 60) for i in range(30)))
        env = dict(self.env, TOLLGATE_PATHS=str(self.home / "paths.yaml"))
        write(self.home / "paths.yaml", "meetings: %s\n" % outside)
        with in_env(env):
            self.assertIn("meetings/m.md", self._keys("vault"))
            chunks, _t = build_index.read_chunks(outside / "m.md", "meetings/m.md", "vault")
        self.assertGreater(len(chunks), 3)

    def test_vault_walk_skips_top_level_archive_work_and_landing(self):
        for folder in ("archive", "work", "00-landing", "output", "notes/work", "kept"):
            write(self.vault / folder / "x.md", "# X\n\n" + "some text here " * 20)
        with in_env(self.env):
            keys = self._keys("vault")
        self.assertIn("kept/x.md", keys)
        for gone in ("archive/x.md", "work/x.md", "00-landing/x.md", "output/x.md"):
            self.assertNotIn(gone, keys)
        # only the top level is skipped: a deeper folder of the same name stays indexed
        self.assertIn("notes/work/x.md", keys)

    def test_extra_skip_variable_still_works(self):
        write(self.vault / "scratch" / "x.md", "# X\n\n" + "some text here " * 20)
        with in_env(dict(self.env, TOLLGATE_INDEX_SKIP="scratch")):
            self.assertNotIn("scratch/x.md", self._keys("vault"))
        with in_env(self.env):
            self.assertIn("scratch/x.md", self._keys("vault"))

    def test_code_and_standards_are_off_by_default(self):
        import build_index
        import config
        # The throwaway home sets TOLLGATE_CODE_DIR to an empty folder: that is still off.
        with in_env(self.env):
            self.assertEqual(build_index.active_collections(), list(config.COLLECTION_NAMES))
            summary = build_index.build(full=True, embedder_name="hash")
            index_root = config.index_root()
            self.assertEqual(sorted(summary["counts"]), sorted(config.COLLECTION_NAMES))
            self.assertFalse((index_root / "code").exists())
            self.assertFalse((index_root / "standards").exists())
            self.assertEqual(self._keys("code") + self._keys("standards"), [])

    def test_asking_for_an_off_collection_stops_cleanly(self):
        proc = run_script("build_index.py", ["--source", "standards", "--embedder", "hash"], self.env)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("standards is off", proc.stderr)

    def test_code_collection_follows_the_repos_path(self):
        import build_index
        import config
        code = self.home / "code"
        write(code / "repo" / "a.py", "def load():\n    return 'retry the nightly load twice and page the owner on failure'\n")
        write(code / "repo" / "b.md", "# Notes\n\n" + "plain words in a markdown note " * 10)
        write(code / "repo" / "c.yaml", "key: value\n" + "more: lines of yaml config here\n" * 8)
        write(code / "repo" / "d.sql", "select 1 as one from some_table where the_value = 1 and other_value = 2;\n")
        write(code / "repo" / "e.txt", "text files are not code " * 10)
        write(code / "repo" / "node_modules" / "f.py", "def skipped():\n    return 'x' * 100 + 'padding padding padding padding'\n")
        write(code / "repo" / ".venv" / "g.py", "def skipped():\n    return 'x' * 100 + 'padding padding padding padding'\n")
        write(code / "repo" / "__pycache__" / "h.py", "def skipped():\n    return 'x' * 100 + 'padding padding padding padding'\n")
        write(code / "repo" / ".terraform" / "i.md", "# skipped\n\n" + "padding " * 30)
        with in_env(self.env):
            self.assertEqual(build_index.active_collections(), list(config.COLLECTION_NAMES) + ["code"])
            keys = self._keys("code")
            summary = build_index.build(full=True, embedder_name="hash")
        self.assertEqual(keys, ["repos/repo/a.py", "repos/repo/b.md", "repos/repo/c.yaml", "repos/repo/d.sql"])
        self.assertGreater(summary["counts"]["code"], 0)
        self.assertNotIn("standards", summary["counts"])

    def test_code_inside_the_vault_stays_off(self):
        import build_index
        inside = self.vault / "mirror"
        write(inside / "a.py", "def f():\n    return 'padding padding padding padding padding padding padding padding'\n")
        with in_env(dict(self.env, TOLLGATE_CODE_DIR=str(inside))):
            self.assertNotIn("code", build_index.active_collections())
            self.assertEqual(self._keys("code"), [])

    def test_standards_collection_follows_the_standards_path(self):
        import build_index
        import config
        std = self.home / "std"
        write(std / "naming.md", "# Naming\n\n" + "use snake case for every column name " * 6)
        write(std / "commands" / "skipped.md", "# Skipped\n\n" + "padding " * 30)
        write(std / ".git" / "skipped.md", "# Skipped\n\n" + "padding " * 30)
        write(std / "code.py", "def f():\n    return 'padding padding padding padding padding padding padding'\n")
        write(self.home / "paths.yaml", "standards: %s\n" % std)
        with in_env(dict(self.env, TOLLGATE_PATHS=str(self.home / "paths.yaml"))):
            self.assertEqual(build_index.active_collections(), list(config.COLLECTION_NAMES) + ["standards"])
            keys = self._keys("standards")
            summary = build_index.build(full=True, embedder_name="hash")
        self.assertEqual(keys, ["standards/naming.md"])
        self.assertGreater(summary["counts"]["standards"], 0)
        self.assertNotIn("code", summary["counts"])

    def test_optional_collections_are_queried_only_when_built(self):
        import build_index
        import config
        import router
        write(self.home / "code" / "repo" / "a.py",
              "def load():\n    return 'the nightly load retries twice and then pages the owner for every job'\n")
        with in_env(self.env):
            build_index.build(full=True, embedder_name="hash")
            cols = router.open_collections(config.index_root())
            hits = router.query_all("nightly load retries twice", intent="build", top=10,
                                    index_root=config.index_root(), embedder=__import__("embedder").get_embedder("hash"))
        self.assertIn("code", cols)
        self.assertNotIn("standards", cols)
        self.assertIn("code", {h["collection"] for h in hits})
