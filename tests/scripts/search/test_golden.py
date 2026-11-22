"""
module_name: test_golden.py
description: SCR-03. The index builds on the synthetic corpus with the fake embedder and the golden questions return the expected files.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version.
"""
import json
import sys
import unittest

import support
from support import CORPUS, GOLDEN, in_env, script_env, throwaway_home

# Floor for the fake (word and trigram) embedder on the hard set: it cannot read meaning, so
# rewordings, negations and absent topics are expected to miss. A real model is held to a higher bar elsewhere.
MIN_HIT_RATE = 0.80
BASIC_PREFIX = "q0"
OFFTOPIC = {f"d{n}" for n in range(27, 33)}


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class GoldenQuestions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._home = throwaway_home()
        cls.home, env = cls._home.__enter__()
        cls.env = script_env(env, TOLLGATE_KNOWLEDGE=str(CORPUS))
        import build_index
        with in_env(cls.env):
            cls.summary = build_index.build(full=True, embedder_name="hash")
            cls.again = build_index.build(embedder_name="hash")
            import eval_rag
            cls.cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
            cls.rows = eval_rag.evaluate(cls.cases, top_k=3)

    @classmethod
    def tearDownClass(cls):
        cls._home.__exit__(None, None, None)

    def test_index_builds_on_the_corpus(self):
        self.assertEqual(self.summary["errors"], 0)
        self.assertEqual(self.summary["embedder"], "hash-v1")
        self.assertGreaterEqual(self.summary["files_indexed"], 20)
        self.assertGreater(self.summary["counts"]["vault"], 0)
        self.assertGreater(self.summary["counts"]["tickets"], 0)

    def test_second_build_changes_nothing(self):
        self.assertEqual(self.again["files_indexed"], 0)
        self.assertEqual(self.again["chunks_added"], 0)
        self.assertEqual(self.again["files_skipped"], self.summary["files_indexed"])

    def test_tickets_use_vault_relative_keys(self):
        import eval_rag
        with in_env(self.env):
            found = eval_rag.default_retrieve("duplicate rows after the nightly retry")
        self.assertTrue(any(f.startswith("02-tickets/EX-101/") for f in found), found)

    def test_basic_questions_all_return_the_expected_file(self):
        basic = [r for r in self.rows if r["id"].startswith(BASIC_PREFIX)]
        self.assertEqual(len(basic), 7)
        misses = [r["id"] for r in basic if r["verdict"] != "PASS"]
        self.assertEqual(misses, [], misses)

    def test_no_critical_question_misses(self):
        risky = [r["id"] for r in self.rows if r["verdict"] == "HALLUCINATION_RISK"]
        self.assertEqual(risky, [], risky)

    def test_off_topic_questions_return_nothing(self):
        bad = [r["id"] for r in self.rows if r["id"].split("-")[0] in OFFTOPIC and r["returned"] != 0]
        self.assertEqual(bad, [], bad)

    def test_hit_rate_floor(self):
        import eval_rag
        summary = eval_rag.summarize(self.rows, 3)
        self.assertGreaterEqual(summary["hit_rate"], MIN_HIT_RATE, summary)

    def test_eval_retrieval_runs_end_to_end(self):
        proc = support.run_script("eval_retrieval.py",
                                  ["--corpus", str(CORPUS), "--golden", str(GOLDEN), "--embedder", "hash",
                                   "--min-hit-rate", "0.0"], self.env)
        self.assertIn("hit@3", proc.stdout, proc.stderr)

    def test_eval_rag_cli_needs_a_question_file(self):
        env = dict(self.env)
        env.pop("TOLLGATE_EVAL_CASES", None)
        proc = support.run_script("eval_rag.py", [], env)
        self.assertEqual(proc.returncode, 2)

    def test_eval_judge_scores_relevance(self):
        import eval_judge
        rows = eval_judge.evaluate(
            [{"id": "a", "question": "retry duplicate rows"}, {"id": "b", "question": "pizza topping", "expect_none": True}],
            lambda q: [{"file": "x", "excerpt": "A retry gave duplicate rows in the table"}][:1] if "retry" in q else [],
            eval_judge.lexical_judge, 0.3, 3)
        self.assertEqual(rows[0]["relevant"], 1)
        self.assertEqual(rows[1]["returned"], 0)
        self.assertEqual(eval_judge.precision(rows), 1.0)


if __name__ == "__main__":
    unittest.main()
