"""
module_name: test_commits.py
description: git-commits connector. CON-01 to CON-04, repo discovery, parsing, privacy.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. No source test existed for the commits puller.
"""
import json
import os
import pathlib
import subprocess
import unittest

from comms_base import Base, make_con_tests, FAKE_ADDRESS, fake_slack_token, fake_credential
from connectors.comms import commits_connector as cm

SEP = cm.SEP
MARK = "PRIVSUBJECT-77de"


def line(sha="a" * 40, subject="change"):
    return SEP.join((sha, "2026-03-02T09:00:00+00:00", "Fixture User", subject))


class GitBase(Base):
    NAME = "git-commits"
    MODULE = cm

    def setUp(self):
        super().setUp()
        self.repo = pathlib.Path(self.home, "work", "alpha")
        (self.repo / ".git").mkdir(parents=True)
        self.runner_calls = []
        self.stdout = line()

    def runner(self, argv, **kw):
        self.runner_calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, self.stdout, "")

    def reached_client(self):
        self.assertEqual(len(self.runner_calls), 1)
        self.assertEqual(self.mock.calls, [])     # no key, no network: local git only


class TestCon(make_con_tests(
        GitBase,
        lambda t: ["--root", str(t.repo)],
        lambda t: {"runner": t.runner})):
    pass


class TestCommits(GitBase):
    def run_roots(self, *roots, **kw):
        argv = []
        for r in roots:
            argv += ["--root", str(r)]
        return self.run_main(argv, runner=self.runner, **kw)

    def test_writes_cache_and_uses_local_word_as_key(self):
        self.assertEqual(self.turn_on(key="local"), 0)
        self.run_roots(self.repo)
        data = self.read_json(".tollgate", "cache", "commits.json")
        self.assertEqual(data["data"][0]["repo"], "alpha")
        self.assertEqual(data["_meta"]["result"], "success")
        self.assertEqual(self.mock.calls, [])

    def test_root_without_git_walks_children_once(self):
        parent = self.repo.parent
        (parent / "beta" / ".git").mkdir(parents=True)
        (parent / "plain").mkdir()
        self.assertEqual([p.name for p in cm.resolve_repos(parent)], ["alpha", "beta"])
        self.assertEqual([p.name for p in cm.resolve_repos(self.repo)], ["alpha"])
        self.assertEqual(cm.resolve_repos(parent / "missing"), [])

    def test_address_gives_roots_and_flag_overrides(self):
        self.turn_on(address=str(self.repo))
        self.run_main([], runner=self.runner)
        self.assertEqual(len(self.runner_calls), 1)
        c = cm.CommitsClient(os.pathsep.join(["/x", "/y"]), "k", None)
        self.assertEqual(c.roots([]), ["/x", "/y"])
        self.assertEqual(c.roots(["/z"]), ["/z"])

    def test_local_address_uses_repos_path(self):
        c = cm.CommitsClient("local", "k", None)
        old = os.environ.get("TOLLGATE_CODE_DIR")
        os.environ["TOLLGATE_CODE_DIR"] = "/somewhere"
        try:
            self.assertEqual(c.roots([]), ["/somewhere"])
        finally:
            if old is None:
                del os.environ["TOLLGATE_CODE_DIR"]
            else:
                os.environ["TOLLGATE_CODE_DIR"] = old

    def test_parse_line_shape(self):
        self.assertIsNone(cm.parse_line("only\x1ftwo", "r"))
        self.assertEqual(cm.parse_line(line(), "r")["author"], "Fixture User")

    def test_all_repos_failing_is_failed_and_no_cache(self):
        self.turn_on()

        def bad(argv, **kw):
            return subprocess.CompletedProcess(argv, 128, "", "boom")
        self.run_main(["--root", str(self.repo)], runner=bad)
        self.assertFalse(pathlib.Path(self.home, ".tollgate", "cache", "commits.json").exists())
        self.assertIn("api_4xx", self.log_text())

    def test_one_bad_repo_is_degraded(self):
        (self.repo.parent / "beta" / ".git").mkdir(parents=True)
        self.turn_on()

        def mixed(argv, **kw):
            rc = 1 if argv[2].endswith("beta") else 0
            return subprocess.CompletedProcess(argv, rc, line(), "")
        self.run_main(["--root", str(self.repo.parent)], runner=mixed)
        data = self.read_json(".tollgate", "cache", "commits.json")
        self.assertEqual(data["_meta"]["result"], "degraded")
        self.assertEqual(len(data["data"]), 1)

    def test_secrets_are_redacted_in_place_and_counted_by_label(self):
        tok, cred = fake_slack_token(), fake_credential()
        self.stdout = "\n".join((line("a" * 40, "fix %s now" % tok), line("b" * 40, "login %s ok" % cred)))
        self.turn_on()
        code, out, err = self.run_roots(self.repo)
        self.assertEqual(code, 0, err)
        raw = pathlib.Path(self.home, ".tollgate", "cache", "commits.json").read_text()
        subjects = [r["subject"] for r in json.loads(raw)["data"]]
        self.assertEqual(subjects, ["fix [REDACTED:SLACK_TOKEN] now", "login [REDACTED:CREDENTIAL] ok"])
        self.assertIn("2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)", out)
        for needle in (tok, cred.split("=")[1]):
            self.assert_text_absent(needle, [raw, out, err, self.log_text()])

    def test_subjects_never_printed_or_logged(self):
        self.stdout = line(subject=MARK)
        self.turn_on()
        code, out, err = self.run_roots(self.repo)
        self.assert_text_absent(MARK, [out, err, self.log_text()])

    def test_dry_run_runs_no_git(self):
        self.turn_on()
        self.run_main(["--dry-run"], runner=self.runner)
        self.assertEqual(self.runner_calls, [])
        self.assertEqual(len(self.read_json(".tollgate", "cache", "commits.json")["data"]), 2)


if __name__ == "__main__":
    unittest.main()
