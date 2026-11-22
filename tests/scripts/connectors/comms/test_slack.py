"""
module_name: test_slack.py
description: slack connector. CON-01 to CON-04, rendering, cursor, archive mode, privacy.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. No source test existed for the Slack archive sync.
"""
import json
import pathlib
import sqlite3
import unittest
from datetime import timezone
from urllib.parse import urlparse, parse_qs

from comms_base import Base, make_con_tests, FAKE_ADDRESS, fake_slack_token, fake_credential
from connectors.comms import slack_connector as sl

MARK = "PRIVTEXT-c3d9"
T1 = "1772442000.000100"      # 2026-03-02 09:00 UTC
T2 = "1772442300.000200"
T3 = "1772528400.000300"      # next day
UTC = timezone.utc


def route(history, replies=None):
    def handler(method, url, kw):
        u = urlparse(url)
        q = parse_qs(u.query)
        if u.path.endswith("/users.list"):
            return {"ok": True, "members": [{"id": "U1", "real_name": "Ana Lee"},
                                            {"id": "U2", "name": "bob"}]}
        if u.path.endswith("/conversations.history"):
            return {"ok": True, "messages": history(q)}
        if u.path.endswith("/conversations.replies"):
            return {"ok": True, "messages": (replies or {}).get(q["ts"][0], [])}
        return {"ok": False}
    return handler


def msgs(q):
    out = [{"ts": T1, "user": "U1", "text": "hello <@U2> see <https://x.invalid|docs>",
            "thread_ts": T1, "reply_count": 1},
           {"ts": T3, "user": "U2", "text": "next day"}]
    if "oldest" in q:
        out = [m for m in out if float(m["ts"]) > float(q["oldest"][0])]
    return out


REPLIES = {T1: [{"ts": T1, "user": "U1", "text": "parent"},
                {"ts": T2, "user": "U2", "text": "reply here"}]}


REPLIES_PHI = {T1: [{"ts": T1, "user": "U1", "text": "parent"},
                    {"ts": T2, "user": "U2", "text": "reply MRN 12345678"}]}


class SlackBase(Base):
    NAME = "slack"
    MODULE = sl

    def setUp(self):
        super().setUp()
        self.mock.handler = route(msgs, REPLIES)

    def reached_client(self):
        self.assertTrue(self.mock.calls)
        self.assertTrue(self.mock.calls[0]["url"].startswith(FAKE_ADDRESS + "/users.list"))

    def note(self, *parts):
        return pathlib.Path(self.home, "vault", "05-conversations", "slack", *parts)


ARGS = lambda t: ["--channel", "C1=general", "--tz", "UTC"]  # noqa: E731


class TestCon(make_con_tests(SlackBase, ARGS)):
    pass


class TestText(unittest.TestCase):
    def test_clean_text(self):
        users = {"U2": "Bob"}
        self.assertEqual(sl.clean_text("hi <@U2> <https://a.invalid|label> <https://b.invalid> <#C1|dev>", users),
                         "hi @Bob label https://b.invalid #dev")
        self.assertEqual(sl.clean_text("", users), "")

    def test_slug(self):
        self.assertEqual(sl.slug("Ana Lee!"), "ana-lee")
        self.assertEqual(sl.slug("!!"), "unnamed")

    def test_build_monthly_threads_inline_and_skips_empty(self):
        m = [{"ts": T1, "parent": "", "user": "U1", "text": "top"},
             {"ts": T2, "parent": T1, "user": "U2", "text": "child"},
             {"ts": T3, "parent": "", "user": "U1", "text": ""}]
        by = sl.build_monthly(m, {"U1": "Ana", "U2": "Bob"}, UTC)
        self.assertEqual(list(by), [(2026, 3)])
        lines = by[(2026, 3)]
        self.assertEqual(lines[0], "### 2026-03-02")
        self.assertIn("**[09:00] Ana**: top", lines)
        self.assertTrue(any(l.startswith("  -> **[09:05] Bob**: child") for l in lines))


class TestSlack(SlackBase):
    def test_s1_message_with_personal_id_is_not_written(self):
        self.mock.handler = route(lambda q: [
            {"ts": T1, "user": "U1", "text": "ok keep", "thread_ts": T1, "reply_count": 1},
            {"ts": T3, "user": "U1", "text": "patient SSN 123-45-6789 here"}], REPLIES_PHI)
        self.turn_on()
        self.run_main(ARGS(self))
        text = self.note("channels", "general", "2026-03-general.md").read_text()
        self.assertIn("ok keep", text)
        self.assertNotIn("123-45-6789", text)
        self.assertNotIn("12345678", text)

    def test_secrets_are_redacted_in_place_and_counted_by_label(self):
        tok, cred = fake_slack_token(), fake_credential()
        self.mock.handler = route(lambda q: [
            {"ts": T1, "user": "U1", "text": "deploy with %s now" % tok},
            {"ts": T3, "user": "U2", "text": "login %s ok" % cred}])
        self.turn_on()
        code, out, err = self.run_main(ARGS(self))
        self.assertEqual(code, 0, err)
        text = self.note("channels", "general", "2026-03-general.md").read_text()
        self.assertIn("deploy with [REDACTED:SLACK_TOKEN] now", text)
        self.assertIn("login [REDACTED:CREDENTIAL] ok", text)
        self.assertIn("2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)", out)
        self.assert_text_absent(tok, [text, out, err, self.log_text()])
        self.assert_text_absent(cred.split("=")[1], [text, out, err, self.log_text()])

    def test_phi_drops_are_counted_in_the_log_and_the_run_line(self):
        self.mock.handler = route(lambda q: [
            {"ts": T1, "user": "U1", "text": "ok keep", "thread_ts": T1, "reply_count": 1},
            {"ts": T3, "user": "U1", "text": "patient SSN 123-45-6789 here"}], REPLIES_PHI)
        self.turn_on()
        code, out, err = self.run_main(ARGS(self))
        self.assertEqual(code, 0, err)
        self.assertIn("phi_dropped=2", out)
        self.assertIn("0 secrets redacted", out)
        last = json.loads(self.log_text().strip().splitlines()[-1])
        self.assertEqual(last["reject_count"], 2)

    def test_api_mode_writes_monthly_note_with_thread(self):
        self.turn_on()
        code, out, err = self.run_main(ARGS(self))
        self.assertEqual(code, 0, err)
        text = self.note("channels", "general", "2026-03-general.md").read_text()
        self.assertIn("# #general - 2026 March", text)
        self.assertIn("Channel ID: C1", text)
        self.assertIn("**[09:00] Ana Lee**: hello @bob see docs", text)
        self.assertIn("  -> **[09:05] bob**: reply here", text)
        self.assertNotIn("parent", text)           # the parent copy in replies is skipped

    def test_cursor_in_state_folder_and_second_run_adds_nothing(self):
        self.turn_on()
        self.run_main(ARGS(self))
        cur = pathlib.Path(self.home, ".tollgate", "state", "slack", "cursor.json")
        self.assertEqual(json.loads(cur.read_text()), {"C1": float(T3)})
        before = self.note("channels", "general", "2026-03-general.md").read_text()
        self.mock.calls.clear()
        self.run_main(ARGS(self))
        history = [c for c in self.mock.calls if "conversations.history" in c["url"]][0]
        self.assertIn("oldest=" + "%.6f" % float(T3), history["url"])
        self.assertEqual(self.note("channels", "general", "2026-03-general.md").read_text(), before)

    def test_full_ignores_cursor(self):
        self.turn_on()
        self.run_main(ARGS(self))
        self.mock.calls.clear()
        self.run_main(ARGS(self) + ["--full"])
        history = [c for c in self.mock.calls if "conversations.history" in c["url"]][0]
        self.assertNotIn("oldest", history["url"])

    def test_dm_goes_to_dms_folder(self):
        self.turn_on()
        self.run_main(["--dm", "D1=Ana Lee", "--tz", "UTC"])
        self.assertTrue(self.note("dms", "ana-lee", "2026-03-ana-lee.md").exists())

    def test_channels_come_only_from_flags(self):
        self.turn_on()
        code, out, err = self.run_main([])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.mock.calls, [])
        self.assertIn("--channel", str(code))
        self.assertNotIn("C0", pathlib.Path(sl.__file__).read_text().replace("C0-9", ""))

    def test_api_failure_for_one_channel_is_degraded_and_continues(self):
        base = self.mock.handler

        def handler(m, u, k):
            if "channel=CBAD" in u and "history" in u:
                return {"ok": False}
            return base(m, u, k)
        self.mock.handler = handler
        self.turn_on()
        self.run_main(["--channel", "CBAD=bad", "--channel", "C1=general", "--tz", "UTC"])
        self.assertTrue(self.note("channels", "general", "2026-03-general.md").exists())
        self.assertIn("degraded", self.log_text())

    def test_archive_mode_reads_sqlite_and_finds_dms(self):
        db = pathlib.Path(self.home, "archive.sqlite")
        con = sqlite3.connect(str(db))
        con.executescript("""
            CREATE TABLE S_USER (ID TEXT, USERNAME TEXT, DATA TEXT);
            CREATE TABLE CHANNEL (ID TEXT, DATA TEXT);
            CREATE TABLE MESSAGE (ID INTEGER PRIMARY KEY, CHANNEL_ID TEXT, TS TEXT,
                                  PARENT_ID TEXT, IS_PARENT INT, TXT TEXT, DATA TEXT);""")
        con.execute("INSERT INTO S_USER VALUES ('U1','ana','{\"real_name\":\"Ana Lee\"}')")
        con.execute("INSERT INTO CHANNEL VALUES ('D9','{\"is_im\":1,\"user\":\"U1\"}')")
        con.execute("INSERT INTO CHANNEL VALUES ('C1','{}')")
        for ch, ts, parent, txt in (("C1", T1, None, "top"), ("C1", T2, T1, "kid"), ("D9", T3, None, "dm text")):
            con.execute("INSERT INTO MESSAGE (CHANNEL_ID,TS,PARENT_ID,TXT,DATA) VALUES (?,?,?,?,?)",
                        (ch, ts, parent, txt, '{"user":"U1"}'))
        con.commit()
        con.close()
        self.turn_on()
        self.mock.calls.clear()
        self.run_main(["--archive", str(db), "--channel", "C1=general", "--tz", "UTC"])
        self.assertEqual(self.mock.calls, [])
        self.assertIn("-> **[09:05] Ana Lee**: kid", self.note("channels", "general", "2026-03-general.md").read_text())
        self.assertTrue(self.note("dms", "ana-lee", "2026-03-ana-lee.md").exists())

    def test_text_never_printed_or_logged(self):
        self.mock.handler = route(lambda q: [{"ts": T1, "user": "U1", "text": MARK}])
        self.turn_on()
        code, out, err = self.run_main(ARGS(self))
        self.assert_text_absent(MARK, [out, err, self.log_text()])
        self.assertIn(MARK, self.note("channels", "general", "2026-03-general.md").read_text())
        self.assertIn("messages=1", out)


if __name__ == "__main__":
    unittest.main()
