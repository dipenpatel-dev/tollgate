"""
module_name: test_review_fixes.py
description: Ranking, tier matching, skip folders, links, the knowledge collection, switched-off collections, dead code removal and the prompt hook.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. Covers the review fixes to scripts/search and hooks/pre-submit-vault-inject.sh.
"""
import json
import os
import pathlib
import subprocess
import sys
import unittest

import support
from support import in_env, run_script, script_env, throwaway_home, write

ROOT = support.ROOT
INTENTS = ("ambiguous", "teach", "verify", "build", "decide", "draft")


def filler(vault, count=24):
    """Many decision notes so the vault collection is much bigger than tickets."""
    for i in range(count):
        write(vault / "03-knowledge-base" / "decisions" / f"2026-0{1 + i % 9}-{10 + i}-choice-{i}.md",
              f"# Choice {i}\n\nWe decided on option {i} for the load job. The state of the pipeline stage {i} "
              f"was reviewed and the owner agreed. Status notes and ticket history are kept elsewhere.\n")


class TierMatching(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.env = script_env(env, TOLLGATE_KNOWLEDGE=str(pathlib.Path(self.home) / "vault"))

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def tier(self, path):
        import config
        with in_env(self.env):
            return config.tier_for(path)[0]

    def test_look_alike_words_are_not_misclassified(self):
        for path in ("notes/threadpool-sizing.md", "notes/chatter.md", "notes/chatbot-ideas.md",
                     "notes/circa-2020-review.md", "notes/slackware.md", "notes/meetingplace.md"):
            self.assertEqual(self.tier(path), 2, path)

    def test_whole_words_and_layout_folders_still_match(self):
        self.assertEqual(self.tier("notes/2026-rca-timeout.md"), 1)
        self.assertEqual(self.tier("03-knowledge-base/decisions/x.md"), 1)
        self.assertEqual(self.tier("03-knowledge-base/patterns/x.md"), 1)
        self.assertEqual(self.tier("06-chat-threads/2026-11/day.md"), 3)
        self.assertEqual(self.tier("05-conversations/talk.md"), 3)
        self.assertEqual(self.tier("meetings/standup.md"), 3)
        self.assertEqual(self.tier("00-landing/x.md"), 3)
        self.assertEqual(self.tier("notes/2026-slack-export.md"), 3)

    def test_tier_three_folder_beats_tier_one_word(self):
        self.assertEqual(self.tier("06-chat-threads/2026-11-16-thread-decision-on-cache.md"), 3)
        self.assertEqual(self.tier("05-conversations/pattern-talk.md"), 3)
        self.assertEqual(self.tier("notes/slack-decision-log.md"), 3)


class UnitRanking(unittest.TestCase):
    def test_ticket_id_bonus_needs_a_whole_token(self):
        import router
        cands = [{"doc": "d", "meta": {"file": f}, "raw_score": 0.5, "collection": "tickets"}
                 for f in ("02-tickets/PROJ/PROJ-34/PROJ-34-state.md", "02-tickets/PROJ/PROJ-340/PROJ-340-state.md")]
        out = {c["file"]: c["weighted_score"] for c in router._score_candidates(cands, {"tickets": 1.0}, "status of PROJ-34")}
        self.assertEqual(out["02-tickets/PROJ/PROJ-34/PROJ-34-state.md"], round(0.5 + 0.1, 4))
        self.assertEqual(out["02-tickets/PROJ/PROJ-340/PROJ-340-state.md"], 0.5)

    def test_tier_is_a_small_additive_tie_breaker(self):
        import config
        self.assertEqual(config.TIER_ADJUST[1], 0.0)
        self.assertEqual(config.TIER_ADJUST[2], 0.0)
        self.assertEqual(config.TIER_ADJUST[3], -0.05)

    def test_a_big_collection_cannot_crowd_out_a_small_one(self):
        import router
        cands = [{"doc": "d", "meta": {"file": f"v{i}.md"}, "raw_score": 0.9 - i * 0.001, "collection": "vault"}
                 for i in range(60)]
        cands.append({"doc": "d", "meta": {"file": "02-tickets/T-1/T-1-state.md"}, "raw_score": 0.5,
                      "collection": "tickets"})
        kept = router._score_candidates(cands, {"vault": 1.1, "tickets": 0.9}, "anything")
        self.assertIn("tickets", {c["collection"] for c in kept})
        self.assertLessEqual(sum(1 for c in kept if c["collection"] == "vault"), 20)

    def test_intent_tilt_is_clamped(self):
        import router
        tilts = router._tilts({"vault": 1.0, "tickets": 0.1, "references": 0.0}, ["vault", "tickets", "references"], False)
        self.assertAlmostEqual(tilts["vault"], 1.1)
        self.assertAlmostEqual(tilts["tickets"], 0.92)
        self.assertIsNone(tilts["references"])
        flat = router._tilts({"vault": 1.0, "tickets": 0.1}, ["vault", "tickets"], True)
        self.assertEqual(set(flat.values()), {1.0})

    def test_reranker_ties_are_broken_by_the_weighted_score(self):
        import router

        class AllOnes:
            def predict(self, pairs):
                import numpy
                return numpy.array([1.0] * len(pairs))

        cands = [{"doc": "d", "meta": {"file": f"n{i}.md"}, "collection": "vault", "tier": 2, "tier_label": "DOCUMENTED",
                  "file": f"n{i}.md", "weighted_score": 0.9 - i * 0.1, "raw_score": 0.9} for i in range(4)]
        out = router._finish("q", cands, AllOnes())
        scores = [r["score"] for r in out]
        self.assertEqual(len(set(scores)), 4)
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([r["file"] for r in out], ["n0.md", "n1.md", "n2.md", "n3.md"])

    def test_raw_reranker_logits_are_squeezed_into_range(self):
        import router
        self.assertEqual(router._unit(0.4), 0.4)
        self.assertTrue(0.0 < router._unit(-3.0) < 0.1)
        self.assertTrue(0.9 < router._unit(5.0) < 1.0)

    @unittest.skipUnless(support.HAVE_STORE, "PyYAML is needed to read the routing table: " + support.NOTE)
    def test_dead_code_is_gone(self):
        import config
        import intent
        self.assertFalse(hasattr(intent, "_keyword_heuristic"))
        self.assertFalse(hasattr(intent, "_ask_caller"))
        routing = config.load_routing()
        self.assertNotIn("keyword_signals", routing)
        self.assertIn("situation_map", routing)
        self.assertEqual(intent.classify_intent("anything at all")[0], "ambiguous")
        self.assertEqual(intent.classify_intent("anything", situation="spec_define")[0], "verify")


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class IndexedBehaviour(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.home = pathlib.Path(self.home)
        self.vault = support.make_vault(self.home / "vault")
        self.env = script_env(env, TOLLGATE_KNOWLEDGE=str(self.vault))

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def build(self, full=True):
        import build_index
        with in_env(self.env):
            return build_index.build(full=full, embedder_name="hash")

    def query(self, text, intent):
        import config
        import embedder
        import router
        with in_env(self.env):
            return router.query_all(text, intent=intent, top=5, index_root=config.index_root(),
                                    embedder=embedder.get_embedder("hash"))

    def test_ticket_state_file_ranks_first_under_every_intent(self):
        filler(self.vault)
        write(self.vault / "02-tickets" / "T-002" / "T-002-session-2026-11-10.md",
              "# Session\n\nWe discussed the status of the load job and the state of the retry work today.\n")
        self.build()
        for intent in INTENTS:
            hits = self.query("what is the state of ticket T-001", intent)
            self.assertTrue(hits[0]["file"].endswith("T-001/T-001-state.md"), (intent, [h["file"] for h in hits]))

    def test_a_named_chat_thread_note_is_found(self):
        filler(self.vault)
        write(self.vault / "06-chat-threads" / "2026-11-16-thread-about-client-delivery.md",
              "# Delivery window\n\nThe client asked to move the delivery window to Thursday morning. "
              "We agreed to send the files by nine and confirm by message.\n")
        self.build()
        for intent in INTENTS:
            hits = self.query("find the chat thread about the client delivery window", intent)
            files = [h["file"] for h in hits]
            self.assertIn("06-chat-threads/2026-11-16-thread-about-client-delivery.md", files[:3], (intent, files))

    def test_output_folder_is_not_indexed(self):
        write(self.vault / "output" / "weekly-report.md", "# Report\n\n" + "generated report text here " * 20)
        write(self.vault / "history" / "old.md", "# Old\n\n" + "old text here " * 20)
        write(self.vault / "notes" / "history" / "kept.md", "# Kept\n\n" + "kept text here " * 20)
        import build_index
        with in_env(self.env):
            keys = [k for _p, k, c in build_index.find_source_files() if c == "vault"]
        self.assertNotIn("output/weekly-report.md", keys)
        self.assertNotIn("history/old.md", keys)
        self.assertIn("notes/history/kept.md", keys)

    def test_links_pointing_outside_the_vault_are_skipped(self):
        outside = self.home / "outside"
        write(outside / "secret.md", "# Secret\n\n" + "private words that must not be indexed " * 10)
        os.symlink(outside / "secret.md", self.vault / "notes" / "linked.md")
        os.symlink(self.vault / "notes" / "alpha.md", self.vault / "notes" / "inner-link.md")
        import build_index
        with in_env(self.env):
            keys = [k for _p, k, c in build_index.find_source_files() if c == "vault"]
        self.assertNotIn("notes/linked.md", keys)
        self.assertIn("notes/inner-link.md", keys)

    def test_reference_add_skips_links_pointing_outside_the_folder(self):
        import reference_add
        docs = self.home / "docs"
        write(docs / "a.md", "# A\n\n" + "reference text " * 20)
        write(self.home / "elsewhere.md", "# E\n\n" + "other text " * 20)
        os.symlink(self.home / "elsewhere.md", docs / "b.md")
        with in_env(self.env):
            keys = [k for _p, k in reference_add.collect(docs)]
        self.assertEqual(keys, ["docs/a.md"])

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can read any file")
    def test_one_unreadable_file_does_not_block_orphan_cleanup(self):
        self.build()
        (self.vault / "notes" / "beta.md").unlink()
        alpha = self.vault / "notes" / "alpha.md"
        alpha.write_text(alpha.read_text() + "\nmore\n")
        os.chmod(alpha, 0)
        try:
            summary = self.build(full=False)
        finally:
            os.chmod(alpha, 0o644)
        self.assertEqual(summary["errors"], 1)
        self.assertGreater(summary["orphans_deleted"], 0)

    def test_knowledge_collection_is_queried(self):
        import config
        import embedder
        import router
        self.build()
        with in_env(self.env):
            emb = embedder.get_embedder("hash")
            folder = config.index_root() / "knowledge"
            folder.mkdir(parents=True)
            col = config.chroma_client(folder).get_or_create_collection(
                name="knowledge", metadata={"hnsw:space": "cosine"})
            text = "the zebra crossing sensor pauses every tuesday after the harvest"
            col.upsert(ids=["k1"], documents=[text], embeddings=[emb.encode([text])[0]],
                       metadatas=[{"source_ref": "repo#42", "summary": "zebra sensor", "record_type": "fact",
                                   "source_repo": "repo", "ticket": "", "date": "2026-11-01"}])
            for intent in ("ambiguous", "build"):
                hits = router.query_all("zebra crossing sensor pauses tuesday harvest", intent=intent, top=5,
                                        index_root=config.index_root(), embedder=emb)
                got = [h for h in hits if h["collection"] == "knowledge"]
                self.assertTrue(got, intent)
                self.assertEqual(got[0]["file"], "repo#42")
                self.assertEqual(got[0]["heading"], "zebra sensor")
            self.assertIn("knowledge", router.open_collections(config.index_root()))
            # the build never touches it
            import build_index
            self.assertNotIn("knowledge", build_index.active_collections())
            build_index.build(full=True, embedder_name="hash")
            self.assertEqual(col.count(), 1)

    def test_a_switched_off_collection_is_not_queried(self):
        import config
        import router
        self.build()
        with in_env(self.env):
            folder = config.index_root() / "code"
            folder.mkdir(parents=True)
            config.chroma_client(folder).get_or_create_collection(name="code")
            self.assertNotIn("code", router.open_collections(config.index_root()))

    def test_stale_chunks_are_removed_when_the_state_is_clean(self):
        self.build()
        (self.vault / "notes" / "beta.md").unlink()
        summary = self.build(full=False)
        self.assertGreater(summary["orphans_deleted"], 0)


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class PromptHook(unittest.TestCase):
    """The real hook, the real query script and a hash index. A prompt that starts with dashes must work."""

    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.home = pathlib.Path(self.home)
        self.vault = support.make_vault(self.home / "vault")
        self.env = script_env(env, TOLLGATE_KNOWLEDGE=str(self.vault), TOLLGATE_PYTHON=sys.executable)
        self.assertEqual(run_script("build_index.py", ["--full", "--embedder", "hash"], self.env).returncode, 0)

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def run_hook(self, prompt):
        return subprocess.run([str(ROOT / "hooks" / "pre-submit-vault-inject.sh")], input=json.dumps({"prompt": prompt}),
                              capture_output=True, text=True, env=self.env, timeout=120)

    def test_normal_prompt_gets_context(self):
        proc = self.run_hook("the nightly load retries twice and then pages the owner for every job")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("<vault_context>", proc.stdout)
        self.assertIn("notes/alpha.md", proc.stdout)

    def test_prompt_starting_with_dashes_is_not_read_as_an_option(self):
        proc = self.run_hook("--top the nightly load retries twice and then pages the owner for every job")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("<vault_context>", proc.stdout)
        self.assertIn("notes/alpha.md", proc.stdout)

    def test_query_script_reads_stdin_and_has_no_index_flag(self):
        proc = run_script("query_index.py", ["--stdin", "--min-score", "0.1"], self.env,
                          input_text="--help nightly load retries twice pages the owner\n")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout))
        bad = run_script("query_index.py", ["x", "--index", "/tmp/x"], self.env)
        self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
