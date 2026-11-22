"""
module_name: test_calendar.py
description: calendar connector. CON-01 to CON-04, API and macOS modes, day cache, privacy.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. No source test existed for the calendar puller.
"""
import json
import pathlib
import subprocess
import unittest

from comms_base import Base, make_con_tests, FAKE_ADDRESS, fake_slack_token, fake_credential
from connectors.comms import calendar_connector as cal

MARK = "PRIVEVENT-91bc"


def api_event(i, title="meeting"):
    return {"id": "e%d" % i, "summary": title,
            "start": {"dateTime": "2026-03-02T09:00:00+00:00"},
            "end": {"dateTime": "2026-03-02T09:30:00+00:00"},
            "attendees": [{"email": "a@example.invalid"}, {"email": "b@example.invalid"}]}


class CalBase(Base):
    NAME = "calendar"
    MODULE = cal

    def setUp(self):
        super().setUp()
        self.mock.handler = lambda m, u, k: {"items": [api_event(1)]}

    def reached_client(self):
        self.assertEqual(len(self.mock.calls), 1)
        self.assertTrue(self.mock.calls[0]["url"].startswith(FAKE_ADDRESS + "/calendars/primary/events?"))


class TestCon(make_con_tests(CalBase, lambda t: ["--date", "2026-03-02", "--tz", "UTC"])):
    pass


def fake_osascript(stdout, rc=0):
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, rc, stdout, "")
    run.calls = calls
    return run


class TestCalendar(CalBase):
    ARGV = ["--date", "2026-03-02", "--tz", "UTC"]

    def test_api_mode_projects_events_into_cache(self):
        self.turn_on()
        self.run_main(self.ARGV + ["--calendar", "team"])
        self.assertIn("/calendars/team/events", self.mock.calls[0]["url"])
        data = self.read_json(".tollgate", "cache", "calendar.json")
        self.assertEqual(data["data"], [{"id": "e1", "summary": "meeting",
                                         "start": "2026-03-02T09:00:00+00:00",
                                         "end": "2026-03-02T09:30:00+00:00",
                                         "attendees_count": 2}])
        self.assertEqual(data["_meta"]["result"], "success")

    def test_two_calendars_dedupe_by_id(self):
        self.turn_on()
        self.run_main(self.ARGV + ["--calendar", "a", "--calendar", "b"])
        self.assertEqual(len(self.mock.calls), 2)
        self.assertEqual(len(self.read_json(".tollgate", "cache", "calendar.json")["data"]), 1)

    def test_same_day_run_reuses_day_copy(self):
        self.turn_on()
        self.run_main(self.ARGV)
        self.run_main(self.ARGV)
        self.assertEqual(len(self.mock.calls), 1)
        self.run_main(self.ARGV + ["--no-day-cache"])
        self.assertEqual(len(self.mock.calls), 2)

    def test_dry_run_does_not_poison_day_copy(self):
        self.turn_on()
        self.run_main(self.ARGV + ["--dry-run"])
        self.assertEqual(self.mock.calls, [])
        self.run_main(self.ARGV)
        self.assertEqual(len(self.mock.calls), 1)

    def test_macos_mode_uses_runner_not_network(self):
        self.turn_on()
        out = "u1\tAlpha\tMonday, March 02, 2026 at 09:00:00 AM\tMonday, March 02, 2026 at 09:30:00 AM\t3\n" \
              "u1\tAlpha\tMonday, March 02, 2026 at 09:00:00 AM\tMonday, March 02, 2026 at 09:30:00 AM\t3\n"
        runner = fake_osascript(out)
        self.run_main(self.ARGV + ["--source", "macos", "--calendar", "Work"], runner=runner)
        self.assertEqual(self.mock.calls, [])
        self.assertIn('"Work"', runner.calls[0][2])
        data = self.read_json(".tollgate", "cache", "calendar.json")["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["start"], "2026-03-02T09:00:00+00:00")
        self.assertEqual(data[0]["attendees_count"], 3)

    def test_parse_rejects_wrong_field_count(self):
        events, reason = cal.parse_osascript_output("a\tb\tc", cal.local_tz("UTC"))
        self.assertEqual(events, [])
        self.assertEqual(reason.value, "schema_invalid")

    def test_macos_failure_is_auth_failed_and_no_cache(self):
        self.turn_on()
        self.run_main(self.ARGV + ["--source", "macos"], runner=fake_osascript("", rc=1))
        self.assertFalse(pathlib.Path(self.home, ".tollgate", "cache", "calendar.json").exists())
        self.assertIn("auth_failed", self.log_text())

    def test_script_text_strips_quotes_from_names(self):
        self.assertIn('{"evil"}', cal.build_applescript(['evil"']))

    def test_secrets_are_redacted_in_place_and_counted_by_label(self):
        tok, cred = fake_slack_token(), fake_credential()
        self.mock.handler = lambda m, u, k: {"items": [api_event(1, title="call %s now" % tok),
                                                       api_event(2, title="login %s ok" % cred)]}
        self.turn_on()
        code, out, err = self.run_main(self.ARGV_SECRETS)
        self.assertEqual(code, 0, err)
        raw = pathlib.Path(self.home, ".tollgate", "cache", "calendar.json").read_text()
        data = json.loads(raw)
        self.assertEqual([r["summary"] for r in data["data"]],
                         ["call [REDACTED:SLACK_TOKEN] now", "login [REDACTED:CREDENTIAL] ok"])
        self.assertIn("2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)", out)
        day = pathlib.Path(self.home, ".tollgate", "state", "calendar", "calendar_2026-03-02.json").read_text()
        for needle in (tok, cred.split("=")[1]):
            self.assert_text_absent(needle, [raw, day, out, err, self.log_text()])

    ARGV_SECRETS = ["--date", "2026-03-02", "--tz", "UTC"]

    def test_titles_never_printed_or_logged(self):
        self.mock.handler = lambda m, u, k: {"items": [api_event(1, title=MARK)]}
        self.turn_on()
        code, out, err = self.run_main(self.ARGV)
        self.assert_text_absent(MARK, [out, err, self.log_text()])

    def test_calendar_choice_is_not_hard_coded(self):
        src = pathlib.Path(cal.__file__).read_text()
        self.assertNotIn("America/", src)


if __name__ == "__main__":
    unittest.main()
