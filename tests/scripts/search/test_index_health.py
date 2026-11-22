"""
module_name: test_index_health.py
description: Ported index health test. The probe window must stay wide, and a healthy synthetic index passes its probes.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the personal health test. The three named documents are replaced by synthetic probes in a throwaway index.
"""
import json
import pathlib
import unittest

import support
from support import in_env, script_env, throwaway_home, write


class WindowFloor(unittest.TestCase):
    def test_top_k_is_wide_enough(self):
        """A healthy passage ranked 11th overall must not be hidden by a narrow window (keep at 60 or more)."""
        import check_index_health
        self.assertGreaterEqual(check_index_health.TOP_K, 60)


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class ProbesOnSyntheticIndex(unittest.TestCase):
    def test_probes_pass_on_the_corpus(self):
        with throwaway_home() as (home, env):
            env = script_env(env, TOLLGATE_KNOWLEDGE=str(support.CORPUS))
            import build_index
            import check_index_health
            with in_env(env):
                build_index.build(full=True, embedder_name="hash")
                report = check_index_health.run_checks([
                    {"label": "decision", "file_contains": "null-encounter-date", "query": "missing encounter date decision"},
                    {"label": "pattern", "file_contains": "idempotent-append", "query": "avoid duplicate rows on retry"},
                ])
        self.assertTrue(report["passed"], json.dumps(report))
        self.assertEqual(len(report["checks"]), 2)


if __name__ == "__main__":
    unittest.main()
