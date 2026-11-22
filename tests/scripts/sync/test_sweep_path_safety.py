#!/usr/bin/env python3
# Module:      test_sweep_path_safety
# Description: sweep must never write outside the vault. Fields used in a path (id, ticket,
#              source_repo, date) allow only letters, digits, dot, underscore and hyphen;
#              a dots-only value is refused; a symlink that leaves the vault is refused.
#              A refused record is counted as skipped and logged by count only.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       sweep path validation
# Version:     1.0
# ChangeLog:
#   Initial version
import contextlib
import io
import json
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_sync_tools import load_sweep, record, FakeIndex, tree_files  # noqa: E402
from throwaway_home import throwaway_home  # noqa: E402
from connector_helpers import assert_no_network  # noqa: E402


class SweepPathSafety(unittest.TestCase):
    def setUp(self):
        self.sweep = load_sweep()

    def _run(self, env, recs, yes=True):
        staging = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "output" / "knowledge-staging"
        staging.mkdir(parents=True, exist_ok=True)
        for n, rec in enumerate(recs):
            (staging / "rec-{}.json".format(n)).write_text(json.dumps(rec))
        old = dict(os.environ)
        os.environ.update(env)
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.sweep.main(["--yes"] if yes else [], index_factory=FakeIndex)
        finally:
            os.environ.clear()
            os.environ.update(old)
        return out.getvalue(), err.getvalue()

    def _vault_and_outside(self, env):
        vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
        return vault, vault.parent

    def _assert_refused(self, rec, secret="EVILVALUE"):
        with throwaway_home() as (home, env), assert_no_network():
            vault, parent = self._vault_and_outside(env)
            before = set(tree_files(parent))
            out, err = self._run(env, [rec])
            self.assertIn("skipped=1", out)
            self.assertIn("written=0", out)
            self.assertNotIn(secret, out + err)          # count only, never the value
            after = set(tree_files(parent))
            new = [p for p in after - before if "knowledge-staging" not in p]
            self.assertEqual(new, [])

    def test_source_repo_with_dotdot_is_refused(self):
        self._assert_refused(record("a", "repo_doc", source_repo="../../../../EVILVALUE"))

    def test_ticket_with_slash_is_refused(self):
        self._assert_refused(record("a", "approval", ticket="x/../../EVILVALUE"))

    def test_id_with_slash_is_refused(self):
        self._assert_refused(record("a/../../EVILVALUE", "approval"))

    def test_decision_ticket_with_slash_is_refused(self):
        self._assert_refused(record("a", "decision", ticket="../EVILVALUE"))

    def test_date_with_slash_is_refused(self):
        self._assert_refused(record("a", "pattern", date="../EVILVALUE"))

    def test_dots_only_value_is_refused(self):
        self._assert_refused(record("a", "repo_doc", source_repo=".."))
        self._assert_refused(record("a", "repo_doc", source_repo="."))

    def test_space_and_backslash_are_refused(self):
        self._assert_refused(record("a", "repo_doc", source_repo="a b"))
        self._assert_refused(record("a", "repo_doc", source_repo="a\\b"))

    def test_non_string_field_is_refused(self):
        self._assert_refused(record("a", "repo_doc", source_repo=5))

    def test_symlink_out_of_the_vault_is_refused(self):
        with throwaway_home() as (home, env), assert_no_network():
            vault, parent = self._vault_and_outside(env)
            outside = parent / "outside-target"
            outside.mkdir()
            repos = vault / self.sweep.REPOS_DIR
            repos.mkdir(parents=True)
            (repos / "linked.md").symlink_to(outside / "stolen.md")
            out, err = self._run(env, [record("a", "repo_doc", source_repo="linked")])
            self.assertIn("skipped=1", out)
            self.assertFalse((outside / "stolen.md").exists())

    def test_symlinked_folder_out_of_the_vault_is_refused(self):
        with throwaway_home() as (home, env), assert_no_network():
            vault, parent = self._vault_and_outside(env)
            outside = parent / "outside-dir"
            outside.mkdir()
            (vault / self.sweep.KNOWLEDGE_DIR).mkdir(parents=True)
            (vault / self.sweep.PATTERNS_DIR).symlink_to(outside)
            out, err = self._run(env, [record("a", "pattern")])
            self.assertIn("skipped=1", out)
            self.assertEqual(list(outside.iterdir()), [])

    def test_preview_marks_refused_record(self):
        with throwaway_home() as (home, env), assert_no_network():
            out, err = self._run(env, [record("a", "repo_doc", source_repo="../x")], yes=False)
            self.assertIn("refused", out)

    def test_write_vault_doc_checks_fields_itself(self):
        with throwaway_home() as (home, env):
            vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
            with self.assertRaises(ValueError):
                self.sweep.write_vault_doc(record("a", "repo_doc", source_repo="../x"), vault / "x.md")

    def test_normal_dotted_names_still_work(self):
        with throwaway_home() as (home, env), assert_no_network():
            out, err = self._run(env, [record("r.1_a-b", "repo_doc", source_repo="my.repo-1")])
            self.assertIn("written=1", out)
            vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
            self.assertTrue((vault / self.sweep.REPOS_DIR / "my.repo-1.md").exists())


if __name__ == "__main__":
    unittest.main()
