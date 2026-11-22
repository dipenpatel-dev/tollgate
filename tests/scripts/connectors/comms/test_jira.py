"""
module_name: test_jira.py
description: jira connector. CON-01 to CON-04, paging, projection, caps, privacy.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. The source test file for this area covers a different
    report script that is not part of this port; these cases follow the puller.
"""
import base64
import json
import pathlib
import unittest

from comms_base import (Base, RoutedClient, make_con_tests, FAKE_ADDRESS, ROOT,
                        fake_slack_token, fake_credential)
from connectors.comms import jira_connector as jira

MARK = "PRIVTITLE-4f2a"


def issue(n, summary=None, assignee="Some One"):
    return {"key": "T-%d" % n, "fields": {
        "summary": summary or "task number %d" % n,
        "status": {"name": "To Do"}, "priority": {"name": "Low"},
        "updated": "2026-01-01T00:00:00.000+0000",
        "assignee": {"displayName": assignee, "emailAddress": "x@example.invalid"}}}


def pages(*batches):
    """Handler giving each page in turn; page n has nextPageToken tok<n+1>."""
    state = {"i": 0}

    def handler(method, url, kw):
        i = state["i"]
        state["i"] += 1
        last = i >= len(batches) - 1
        out = {"issues": batches[i], "isLast": last}
        if not last:
            out["nextPageToken"] = "tok%d" % (i + 1)
        return out
    return handler


class JiraBase(Base):
    NAME = "jira"
    MODULE = jira

    def reached_client(self):
        self.assertEqual(len(self.mock.calls), 1)
        self.assertEqual(self.mock.calls[0]["url"], FAKE_ADDRESS + "/rest/api/3/search/jql")

    def setUp(self):
        super().setUp()
        self.mock.handler = pages([issue(1)])


class TestCon(make_con_tests(JiraBase, lambda t: [])):
    pass


class TestJira(JiraBase):
    def test_writes_cache_in_daily_brief_format(self):
        self.turn_on()
        code, out, err = self.run_main([])
        self.assertEqual(code, 0)
        data = self.read_json(".tollgate", "cache", "jira.json")
        self.assertEqual(set(data["_meta"]), {"pulled_at", "result", "reason", "reject_count"})
        self.assertEqual(data["_meta"]["result"], "success")
        self.assertEqual(data["data"][0], {
            "key": "T-1", "summary": "task number 1", "status": "To Do", "priority": "Low",
            "updated": "2026-01-01T00:00:00.000+0000", "assignee": "Some One"})
        self.assertNotIn("emailAddress", json.dumps(data))

    def test_pagination_follows_token_until_last(self):
        self.mock.handler = pages([issue(1)], [issue(2)], [issue(3)])
        self.turn_on()
        self.run_main([])
        self.assertEqual(len(self.mock.calls), 3)
        sent = json.loads(self.mock.calls[1]["kwargs"]["data"])
        self.assertEqual(sent["nextPageToken"], "tok1")
        self.assertEqual(len(self.read_json(".tollgate", "cache", "jira.json")["data"]), 3)

    def test_query_comes_from_flag(self):
        self.turn_on()
        self.run_main(["--jql", "project = ZZZ"])
        self.assertEqual(json.loads(self.mock.calls[0]["kwargs"]["data"])["jql"], "project = ZZZ")

    def test_login_token_key_uses_basic_and_plain_key_uses_bearer(self):
        self.turn_on(key="who@example.invalid:" + self.secret)
        self.run_main([])
        h = self.mock.calls[0]["kwargs"]["headers"]["Authorization"]
        self.assertEqual(h, "Basic " + base64.b64encode(
            ("who@example.invalid:" + self.secret).encode()).decode())
        self.store.set("jira", self.secret)
        self.mock.calls.clear()
        self.mock.handler = pages([issue(1)])
        self.run_main([])
        self.assertEqual(self.mock.calls[0]["kwargs"]["headers"]["Authorization"],
                         "Bearer " + self.secret)

    def test_size_cap_gives_degraded(self):
        old = jira.MAX_TOTAL
        jira.MAX_TOTAL = 2
        try:
            self.mock.handler = pages([issue(1), issue(2), issue(3)])
            self.turn_on()
            self.run_main([])
        finally:
            jira.MAX_TOTAL = old
        data = self.read_json(".tollgate", "cache", "jira.json")
        self.assertEqual(data["_meta"]["result"], "degraded")
        self.assertEqual(len(data["data"]), 2)

    def test_bad_shape_fails_and_writes_no_cache(self):
        self.mock.handler = lambda m, u, k: {"issues": "nope", "isLast": True}
        self.turn_on()
        code, out, err = self.run_main([])
        self.assertEqual(code, 0)
        self.assertFalse((__import__("pathlib").Path(self.home) / ".tollgate" / "cache" / "jira.json").exists())
        self.assertIn("schema_invalid", self.log_text())

    def test_wrong_type_in_nested_field_is_schema_failure(self):
        bad = issue(1)
        bad["fields"]["status"] = "string"
        self.assertIsNone(jira.project_issue(bad))
        self.assertIsNone(jira.project_issue({"key": "T-1"}))

    def test_identifier_in_record_is_dropped_and_counted(self):
        ssn = "-".join(("123", "45", "6789"))
        self.mock.handler = pages([issue(1), issue(2, summary="has " + ssn)])
        self.turn_on()
        self.run_main([])
        data = self.read_json(".tollgate", "cache", "jira.json")
        self.assertEqual(data["_meta"]["reject_count"], 1)
        self.assertEqual(data["_meta"]["result"], "degraded")
        self.assertEqual(len(data["data"]), 1)

    def test_secrets_are_redacted_in_place_and_counted_by_label(self):
        tok, cred = fake_slack_token(), fake_credential()
        self.mock.handler = pages([issue(1, summary="see %s now" % tok),
                                   issue(2, summary="login %s ok" % cred)])
        self.turn_on()
        code, out, err = self.run_main([])
        self.assertEqual(code, 0, err)
        raw = pathlib.Path(self.home, ".tollgate", "cache", "jira.json").read_text()
        data = json.loads(raw)
        self.assertEqual([r["summary"] for r in data["data"]],
                         ["see [REDACTED:SLACK_TOKEN] now", "login [REDACTED:CREDENTIAL] ok"])
        self.assertIn("2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)", out)
        for needle in (tok, cred.split("=")[1]):
            self.assert_text_absent(needle, [raw, out, err, self.log_text()])

    def test_titles_never_printed_or_logged(self):
        self.mock.handler = pages([issue(1, summary=MARK)])
        self.turn_on()
        code, out, err = self.run_main([])
        self.assert_text_absent(MARK, [out, err, self.log_text()])
        self.assertIn("1 records", out)

    def test_dry_run_writes_fixture_without_network(self):
        self.turn_on()
        self.mock.calls.clear()
        self.run_main(["--dry-run"])
        self.assertEqual(self.mock.calls, [])
        self.assertEqual(len(self.read_json(".tollgate", "cache", "jira.json")["data"]), 2)

    def test_error_status_logs_reason_only(self):
        class Bad(RoutedClient):
            def request(self, method, url, **kw):
                self.calls.append({"method": method, "url": url, "kwargs": kw})
                return {"status": 503, "body": MARK}
        from connectors import registry
        self.mock = Bad()
        registry.set_http_factory(lambda: self.mock)
        self.turn_on()
        code, out, err = self.run_main([])
        self.assertIn("api_5xx", self.log_text())
        self.assert_text_absent(MARK, [out, err, self.log_text()])


if __name__ == "__main__":
    unittest.main()
