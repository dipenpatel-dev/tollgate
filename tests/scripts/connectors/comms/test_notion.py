"""
module_name: test_notion.py
description: notion connector (new, no source file). CON-01 to CON-04, page and database notes, privacy.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version.
"""
import json
import pathlib
import unittest

from comms_base import Base, make_con_tests, FAKE_ADDRESS, fake_slack_token, fake_credential
from connectors.comms import notion_connector as nt

PID = "abcd1234-0000-4000-8000-000000000001"
MARK = "PRIVPAGE-5e5e"


def rt(text):
    return [{"plain_text": text}]


def block(kind, text, **extra):
    d = {"type": kind, "id": "b-" + text[:3], kind: {"rich_text": rt(text)}}
    d.update(extra)
    return d


def handler_for(title="Weekly notes", blocks=None, children=None):
    blocks = blocks if blocks is not None else [block("heading_1", "Agenda"),
                                                block("bulleted_list_item", "item one"),
                                                block("to_do", "ship", )]
    for b in blocks:
        if b["type"] == "to_do":
            b["to_do"]["checked"] = True
    children = children or {}

    def handler(method, url, kw):
        if "/pages/" in url:
            return {"id": PID, "properties": {"Name": {"type": "title", "title": rt(title)}}}
        if "/databases/" in url and url.endswith("/query"):
            return {"results": [{"properties": {"N": {"type": "title", "title": rt("row a")}}},
                                {"properties": {"N": {"type": "title", "title": rt("row b")}}}],
                    "has_more": False}
        if "/databases/" in url:
            return {"title": rt("Tasks")}
        if "/blocks/" in url:
            bid = url.split("/blocks/")[1].split("/")[0]
            return {"results": children.get(bid, blocks if bid == PID else []), "has_more": False}
        return {}
    return handler


class NoteBase(Base):
    NAME = "notion"
    MODULE = nt

    def setUp(self):
        super().setUp()
        self.mock.handler = handler_for()

    def reached_client(self):
        self.assertTrue(self.mock.calls)
        self.assertEqual(self.mock.calls[0]["url"], FAKE_ADDRESS + "/pages/" + PID)

    def notes(self, folder):
        d = pathlib.Path(self.home, "vault", folder)
        return sorted(d.glob("*.md")) if d.exists() else []


class TestCon(make_con_tests(NoteBase, lambda t: ["page", PID])):
    pass


class TestNotion(NoteBase):
    def test_page_becomes_markdown_under_references_by_default(self):
        self.turn_on()
        code, out, err = self.run_main(["page", PID])
        self.assertEqual(code, 0, err)
        files = self.notes("references")
        self.assertEqual([f.name for f in files], ["weekly-notes-abcd1234.md"])
        text = files[0].read_text()
        self.assertIn("# Weekly notes", text)
        self.assertIn("# Agenda", text)
        self.assertIn("- item one", text)
        self.assertIn("- [x] ship", text)

    def test_into_meetings(self):
        self.turn_on()
        self.run_main(["page", PID, "--into", "meetings"])
        self.assertEqual(len(self.notes("meetings")), 1)
        self.assertEqual(self.notes("references"), [])

    def test_rerun_overwrites_same_file(self):
        self.turn_on()
        self.run_main(["page", PID])
        self.run_main(["page", PID])
        self.assertEqual(len(self.notes("references")), 1)

    def test_nested_children_are_read(self):
        parent = block("bulleted_list_item", "parent", has_children=True, id="kid1")
        self.mock.handler = handler_for(blocks=[parent, block("divider", ""), block("quote", "q")],
                                        children={"kid1": [block("bulleted_list_item", "nested")]})
        self.turn_on()
        self.run_main(["page", PID])
        self.assertIn("  - nested", self.notes("references")[0].read_text())

    def test_database_lists_row_titles(self):
        self.turn_on()
        self.run_main(["database", PID])
        text = self.notes("references")[0].read_text()
        self.assertIn("- row a", text)
        self.assertIn("- row b", text)
        self.assertEqual([c["method"] for c in self.mock.calls], ["GET", "POST"])

    def test_headers_carry_token_and_version(self):
        self.turn_on()
        self.run_main(["page", PID])
        h = self.mock.calls[0]["kwargs"]["headers"]
        self.assertEqual(h["Authorization"], "Bearer " + self.secret)
        self.assertEqual(h["Notion-Version"], nt.API_VERSION)

    def test_bad_id_refused_before_any_call(self):
        self.turn_on()
        code, out, err = self.run_main(["page", "../x?y"])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.mock.calls, [])

    def test_failure_writes_no_note(self):
        self.mock.handler = lambda m, u, k: []
        self.turn_on()
        self.run_main(["page", PID])
        self.assertEqual(self.notes("references"), [])
        self.assertIn("schema_invalid", self.log_text())

    def test_s1_lines_and_title_with_personal_id_are_not_written(self):
        blocks = [block("heading_1", "Agenda"), block("bulleted_list_item", "SSN 123-45-6789"),
                  block("quote", "safe line")]
        self.mock.handler = handler_for(title="Notes MRN 12345678", blocks=blocks)
        self.turn_on()
        self.run_main(["page", PID])
        text = self.notes("references")[0].read_text()
        self.assertIn("safe line", text)
        self.assertNotIn("123-45-6789", text)
        self.assertNotIn("12345678", text)
        self.assertNotIn("12345678", self.notes("references")[0].name)

    def test_secrets_are_redacted_in_title_name_and_lines_and_counted(self):
        tok, cred = fake_slack_token(), fake_credential()
        blocks = [block("heading_1", "Agenda"), block("bulleted_list_item", "use " + cred + " here"),
                  block("quote", "safe line")]
        self.mock.handler = handler_for(title="Notes " + tok, blocks=blocks)
        self.turn_on()
        code, out, err = self.run_main(["page", PID])
        self.assertEqual(code, 0, err)
        note = self.notes("references")[0]
        text = note.read_text()
        self.assertIn("# Notes [REDACTED:SLACK_TOKEN]", text)
        self.assertIn("- use [REDACTED:CREDENTIAL] here", text)
        self.assertIn("safe line", text)
        self.assertIn("2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)", out)
        for needle in (tok, cred.split("=")[1]):
            self.assert_text_absent(needle, [text, note.name, out, err, self.log_text()])

    def test_phi_drops_are_counted_in_the_log_and_the_run_line(self):
        blocks = [block("heading_1", "Agenda"), block("bulleted_list_item", "SSN 123-45-6789"),
                  block("quote", "safe line")]
        self.mock.handler = handler_for(title="Notes MRN 12345678", blocks=blocks)
        self.turn_on()
        code, out, err = self.run_main(["page", PID])
        self.assertEqual(code, 0, err)
        self.assertIn("2 phi dropped", out)
        last = json.loads(self.log_text().strip().splitlines()[-1])
        self.assertEqual(last["reject_count"], 2)

    def test_titles_never_printed_or_logged(self):
        self.mock.handler = handler_for(title=MARK)
        self.turn_on()
        code, out, err = self.run_main(["page", PID])
        self.assert_text_absent(MARK, [out, err, self.log_text()])
        self.assertEqual(len(self.notes("references")), 1)


if __name__ == "__main__":
    unittest.main()
