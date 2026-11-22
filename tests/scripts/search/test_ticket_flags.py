"""
module_name: test_ticket_flags.py
description: The flags the ticket command passes to query_index.py and vault_health.py, plus the not set up paths.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.1
change_log:
  1.0.1: Read commands/tg-ticket.md and match the tg-search query and health calls.
  1.0.0: Initial version.
"""
import json
import pathlib
import re
import unittest

import support
from support import ROOT, run_script, script_env, throwaway_home


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class TicketCommandFlags(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.vault = support.make_vault(pathlib.Path(self.home) / "vault")
        self.env = script_env(env, TOLLGATE_KNOWLEDGE=str(self.vault))

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def build(self):
        self.assertEqual(run_script("build_index.py", ["--full", "--embedder", "hash"], self.env).returncode, 0)

    def test_command_file_uses_only_flags_the_scripts_accept(self):
        text = (ROOT / "commands" / "tg-ticket.md").read_text(encoding="utf-8")
        for tool in ("query", "health"):
            calls = re.findall(r"tg-search " + tool + r"\b[^\n`]*", text)
            self.assertTrue(calls, tool)
            for call in calls:
                self.assertTrue(set(re.findall(r"--[a-z-]+", call)) <= {"--top"}, call)

    def test_query_index_top(self):
        self.build()
        proc = run_script("query_index.py", ["retry limit nightly load owner", "--top", "8"], self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = json.loads(proc.stdout)
        self.assertTrue(0 < len(rows) <= 8)
        self.assertTrue({"file", "heading", "excerpt", "score", "tier", "tier_label", "collection"} <= set(rows[0]))
        self.assertEqual(run_script("query_index.py", ["retry limit nightly load owner", "--top", "1"], self.env).stdout.count('"file"'), 1)

    def test_query_index_other_flags(self):
        self.build()
        proc = run_script("query_index.py", ["duplicate rows retry", "--top", "3", "--min-score", "0.0",
                                             "--intent", "decide"], self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout))
        proc = run_script("query_index.py", ["duplicate rows retry", "--situation", "support_triage"], self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        high = run_script("query_index.py", ["retry", "--min-score", "0.99"], self.env)
        self.assertEqual(json.loads(high.stdout), [])

    def test_query_index_not_set_up(self):
        proc = run_script("query_index.py", ["anything", "--top", "8"], self.env)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (2, "not set up"))

    def test_vault_health_report_and_exit_code(self):
        self.build()
        proc = run_script("vault_health.py", ["--top", "5"], self.env)
        self.assertIn("VAULT HEALTH", proc.stdout)
        self.assertIn("Dead links: 1 missing targets", proc.stdout)
        self.assertIn("2x  [[missing-note-one]]", proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_vault_health_json(self):
        self.build()
        proc = run_script("vault_health.py", ["--json", "--top", "1"], self.env)
        data = json.loads(proc.stdout)
        self.assertEqual(data["dead_links"]["total_missing"], 1)
        self.assertTrue(data["index"]["chroma_exists"])

    def test_vault_health_flags_a_missing_index(self):
        proc = run_script("vault_health.py", ["--top", "5"], self.env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("search unavailable", proc.stdout)

    def test_vault_health_not_set_up(self):
        env = dict(self.env)
        env.pop("TOLLGATE_KNOWLEDGE")
        proc = run_script("vault_health.py", ["--top", "5"], env)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (2, "not set up"))

    def test_ticket_links_and_placeholders_resolve(self):
        import vault_health
        self.assertTrue(vault_health._resolve_wikilink("T-009", set(), {}, set()))
        self.assertTrue(vault_health._resolve_wikilink("path/to/file", set(), {}, set()))
        self.assertTrue(vault_health._resolve_wikilink("two words", set(), {}, set()))
        self.assertFalse(vault_health._resolve_wikilink("nothing-here", set(), {}, set()))
        self.assertTrue(vault_health._resolve_wikilink("nothing-here", {"nothing-here"}, {}, set()))


if __name__ == "__main__":
    unittest.main()
