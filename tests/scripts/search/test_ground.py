"""
module_name: test_ground.py
description: ground.py prints one of four states, then a collections line, an optional detail line, then passages.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.1.0: Added the Q-10 stdin query test.
  1.0.0: Initial version.
"""
import pathlib
import unittest
from unittest import mock

import support
from support import in_env, run_script, script_env, throwaway_home


def first_lines(text, n=3):
    return text.splitlines()[:n]


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class GroundStates(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.vault = support.make_vault(pathlib.Path(self.home) / "vault")
        self.env = script_env(env)

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def build(self):
        proc = run_script("build_index.py", ["--full", "--embedder", "hash"], self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_unavailable_when_no_index(self):
        out = run_script("ground.py", ["x-dev", "retry limit"], self.env)
        self.assertEqual(out.returncode, 0)
        lines = first_lines(out.stdout)
        self.assertEqual(lines[0], "STATE: unavailable")
        self.assertTrue(lines[1].startswith("COLLECTIONS:"))
        self.assertTrue(lines[2].startswith("DETAIL:"))

    def test_ok_prints_passages_with_file_and_heading(self):
        self.build()
        out = run_script("ground.py", ["x-dev", "nightly load retries twice then pages the owner"], self.env)
        lines = out.stdout.splitlines()
        self.assertEqual(lines[0], "STATE: ok", out.stdout)
        self.assertRegex(lines[1], r"^COLLECTIONS: vault=\d+ tickets=\d+ references=")
        self.assertTrue(any(l.startswith("[1] notes/alpha.md | ") for l in lines), out.stdout)

    def test_empty_when_nothing_matches(self):
        self.build()
        out = run_script("ground.py", ["x-qa", "pizza topping weather forecast cricket"], self.env)
        self.assertEqual(out.stdout.splitlines()[0], "STATE: empty")
        self.assertIn("DETAIL:", out.stdout)

    def test_partial_when_one_collection_fails(self):
        self.build()
        import ground
        import router
        real = router._query_one

        def flaky(name, collection, vec, top_k, emb):
            if name == "tickets":
                return (name, [], RuntimeError("boom"))
            return real(name, collection, vec, top_k, emb)

        with in_env(self.env), mock.patch.object(router, "_query_one", flaky):
            state, line, detail, results = ground.ground("x-dev", "nightly load retries twice then pages the owner")
        self.assertEqual(state, "partial")
        self.assertIn("tickets", detail)
        self.assertTrue(results)

    def test_unavailable_when_every_collection_fails(self):
        self.build()
        import ground
        import router

        with in_env(self.env), mock.patch.object(router, "_query_one", lambda n, c, v, k, e: (n, [], RuntimeError("x"))):
            state, _line, detail, results = ground.ground("x-dev", "retry")
        self.assertEqual((state, results), ("unavailable", []))
        self.assertIn("failed", detail)

    def test_unavailable_when_the_search_package_is_missing(self):
        import ground
        import router
        with in_env(self.env), mock.patch.object(router, "query_all", side_effect=ImportError("no chromadb")):
            self.build()
            state, _l, detail, _r = ground.ground("x-dev", "retry")
        self.assertEqual(state, "unavailable")

    def test_wrong_argument_count_still_prints_a_state(self):
        out = run_script("ground.py", ["only-one"], self.env)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.splitlines()[0], "STATE: unavailable")

    def test_q10_dash_reads_the_query_from_stdin(self):
        import ground
        seen = {}
        def fake(skill, query, *a, **k):
            seen["q"] = query
            return "empty", "none", "", []
        with mock.patch.object(ground, "ground", side_effect=fake), \
                mock.patch("sys.stdin", __import__("io").StringIO("it's a $(x) `y`\nsecond line\n")), \
                mock.patch("builtins.print"):
            self.assertEqual(ground.main(["x-dev", "-"]), 0)
        self.assertEqual(seen["q"], "it's a $(x) `y` second line")

    def test_skill_name_picks_an_intent(self):
        from intent import map_skill
        self.assertEqual(map_skill("x-dev"), "build")
        self.assertEqual(map_skill("x-qa"), "verify")
        self.assertIsNone(map_skill("x-unknown"))


if __name__ == "__main__":
    unittest.main()
