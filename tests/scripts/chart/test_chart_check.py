#!/usr/bin/env python3
"""Tests for chart_check: good and bad synthetic documents, exit codes, widening, no text leak.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove the chart rules are enforced and findings never repeat document text.
Change log:
  - First version.
"""
import importlib.machinery
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
CHART_DIR = ROOT / "scripts" / "chart"
CHECK = CHART_DIR / "chart_check"
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(CHART_DIR))
sys.path.insert(0, str(ROOT / "scripts"))
from throwaway_home import throwaway_home  # noqa: E402

FENCE = "`" * 3


def chart(body):
    return f"{FENCE}mermaid\n{body}\n{FENCE}\n"


GOOD_DOC = ("# Title\n\nSome text.\n\n"
            + chart('flowchart TD\n  A["Read input"] --> B["Write output"]')
            + "\nMore text.\n\n"
            + chart("sequenceDiagram\n  A->>B: hello"))
BAD_DOC = ("# Title\n\n"
           + chart("stateDiagram-v2\n  [*] --> One")
           + chart("pie title Pets\n  \"Dogs\": 3")
           + chart("flowchart TD\n  A((round)) --> B"))
SECRET_WORD = "zebra" + "quartz"


def load_module():
    loader = importlib.machinery.SourceFileLoader("chart_check_mod", str(CHECK))
    spec = importlib.util.spec_from_loader("chart_check_mod", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def run(args, env=None):
    base = dict(os.environ)
    base["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        base.update(env)
    return subprocess.run([sys.executable, "-B", str(CHECK)] + args, capture_output=True, text=True, env=base)


class TestChartCheckCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def doc(self, text, name="doc.md"):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_executable_with_shebang(self):
        self.assertTrue(os.access(CHECK, os.X_OK))
        self.assertTrue(CHECK.read_text().startswith("#!/usr/bin/env python3"))

    def test_good_document_exits_zero(self):
        proc = run(["--role", "document-writer", self.doc(GOOD_DOC)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_bad_document_exits_one_with_clear_message(self):
        proc = run(["--role", "document-writer", self.doc(BAD_DOC)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("chart 1 (line 3): this chart type is not allowed here", proc.stdout)
        self.assertIn("not a known chart type", proc.stdout)
        self.assertIn("circle, hexagon or stadium", proc.stdout)
        self.assertIn("Allowed here: class, flowchart, sequence.", proc.stdout)

    def test_findings_never_repeat_document_text(self):
        text = chart(f'stateDiagram-v2\n  [*] --> {SECRET_WORD}')
        proc = run(["--role", "document-writer", self.doc(text)])
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn(SECRET_WORD, proc.stdout + proc.stderr)

    def test_er_blocked_without_ticket_flag(self):
        text = chart("erDiagram\n  A ||--o{ B : has")
        proc = run(["--role", "document-writer", self.doc(text)])
        self.assertEqual(proc.returncode, 1)

    def test_er_allowed_when_ticket_touches_data_model(self):
        text = chart("erDiagram\n  A ||--o{ B : has")
        with throwaway_home() as (home, env):
            state = pathlib.Path(home) / "vault" / "02-tickets" / "TG" / "TG-5"
            state.mkdir(parents=True)
            (state / "TG-5-state.md").write_text("---\nticket_id: TG-5\nstatus: OPEN\ntouches_data_model: true\n---\n")
            doc = pathlib.Path(home) / "d.md"
            doc.write_text(text)
            on = run(["--role", "document-writer", "--ticket", "TG-5", str(doc)], env=env)
            self.assertEqual(on.returncode, 0, on.stdout + on.stderr)
            (state / "TG-5-state.md").write_text("---\nticket_id: TG-5\nstatus: OPEN\ntouches_data_model: \"true\"\n---\n")
            quoted = run(["--role", "document-writer", "--ticket", "TG-5", str(doc)], env=env)
            self.assertEqual(quoted.returncode, 1)
            (state / "TG-5-state.md").write_text("---\nticket_id: TG-5\nstatus: OPEN\ntouches_data_model: false\n---\n")
            off = run(["--role", "document-writer", "--ticket", "TG-5", str(doc)], env=env)
            self.assertEqual(off.returncode, 1)
            missing = run(["--role", "document-writer", "--ticket", "TG-9", str(doc)], env=env)
            self.assertEqual(missing.returncode, 1)

    def test_ticket_state_is_found_flat_and_under_a_lowercase_prefix_folder(self):
        text = chart("erDiagram\n  A ||--o{ B : has")
        body = "---\nticket_id: %s\nstatus: OPEN\ntouches_data_model: true\n---\n"
        with throwaway_home() as (home, env):
            tickets = pathlib.Path(home) / "vault" / "02-tickets"
            for rel, key in (("TG-6", "TG-6"), ("tg/TG-7", "TG-7")):
                folder = tickets / rel
                folder.mkdir(parents=True)
                (folder / (key + "-state.md")).write_text(body % key)
            doc = pathlib.Path(home) / "d.md"
            doc.write_text(text)
            for key in ("TG-6", "TG-7"):
                proc = run(["--role", "document-writer", "--ticket", key, str(doc)], env=env)
                self.assertEqual(proc.returncode, 0, key + proc.stdout + proc.stderr)

    def test_ticket_folder_linked_outside_the_tickets_folder_is_not_used(self):
        text = chart("erDiagram\n  A ||--o{ B : has")
        with throwaway_home() as (home, env):
            outside = pathlib.Path(home) / "outside" / "TG-8"
            outside.mkdir(parents=True)
            (outside / "TG-8-state.md").write_text("---\ntouches_data_model: true\n---\n")
            tickets = pathlib.Path(home) / "vault" / "02-tickets"
            tickets.mkdir(parents=True)
            (tickets / "TG-8").symlink_to(outside, target_is_directory=True)
            doc = pathlib.Path(home) / "d.md"
            doc.write_text(text)
            proc = run(["--role", "document-writer", "--ticket", "TG-8", str(doc)], env=env)
            self.assertEqual(proc.returncode, 1)

    def test_ticket_without_setup_exits_two(self):
        with throwaway_home() as (home, env):
            env = {k: v for k, v in env.items() if k != "TOLLGATE_KNOWLEDGE"}
            env["TOLLGATE_KNOWLEDGE"] = ""
            doc = pathlib.Path(home) / "d.md"
            doc.write_text(GOOD_DOC)
            base = dict(os.environ)
            base.update(env)
            base.pop("TOLLGATE_PATHS", None)
            proc = subprocess.run([sys.executable, "-B", str(CHECK), "--role", "document-writer", "--ticket", "TG-5", str(doc)],
                                  capture_output=True, text=True, env=base)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("could not finish", proc.stderr)

    def test_bad_ticket_key_exits_two(self):
        proc = run(["--role", "document-writer", "--ticket", "../x", self.doc(GOOD_DOC)])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ticket key is not valid", proc.stderr)

    def test_unknown_role_exits_two(self):
        proc = run(["--role", "no-such-role", self.doc(GOOD_DOC)])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown role", proc.stderr)

    def test_missing_file_exits_two(self):
        proc = run(["--role", "document-writer", str(self.dir / "absent.md")])
        self.assertEqual(proc.returncode, 2)

    def test_no_args_exits_two(self):
        self.assertEqual(run([]).returncode, 2)

    def test_require_chart(self):
        path = self.doc("just text\n")
        self.assertEqual(run(["--role", "document-writer", path]).returncode, 0)
        proc = run(["--role", "document-writer", "--require-chart", path])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no chart", proc.stdout)

    def test_exception_line(self):
        ok = chart("stateDiagram-v2\n  %% exception: the states are the point\n  [*] --> One")
        empty = chart("stateDiagram-v2\n  %% exception:\n  [*] --> One")
        self.assertEqual(run(["--role", "document-writer", self.doc(ok)]).returncode, 0)
        proc = run(["--role", "document-writer", self.doc(empty)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("exception line has no reason", proc.stdout)

    def test_custom_rules_file(self):
        rules = self.dir / "rules.json"
        rules.write_text('{"types": {"flowchart": {"keywords": ["flowchart"]}}, "roles": {"r": []}}')
        proc = run(["--role", "r", "--rules", str(rules), self.doc(GOOD_DOC)])
        self.assertEqual(proc.returncode, 1)
        rules.write_text("not json")
        self.assertEqual(run(["--role", "r", "--rules", str(rules), self.doc(GOOD_DOC)]).returncode, 2)


class TestChartCheckRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()
        cls.rules = cls.mod.load_rules()
        cls.allowed = cls.mod.allowed_for_role(cls.rules, "document-writer")

    def check(self, text, require=False):
        return self.mod.check_charts(text, self.allowed, self.rules, require)

    def reasons(self, text):
        return [f[2] for f in self.check(text)]

    def test_extract_charts_crlf_tilde_and_quoted(self):
        crlf = "x\r\n" + chart("flowchart TD\n  A --> B").replace("\n", "\r\n")
        self.assertEqual(len(self.mod.extract_charts(crlf)), 1)
        tilde = "~~~mermaid\nflowchart TD\n  A --> B\n~~~\n"
        self.assertEqual(len(self.mod.extract_charts(tilde)), 1)
        quoted = "> " + FENCE + "mermaid\n> flowchart TD\n>   A --> B\n> " + FENCE + "\n"
        self.assertEqual(len(self.mod.extract_charts(quoted)), 1)
        other = FENCE + "python\nprint(1)\n" + FENCE + "\n"
        self.assertEqual(self.mod.extract_charts(other), [])
        unclosed = FENCE + "mermaid\nflowchart TD\n  A --> B\n"
        self.assertEqual(self.mod.extract_charts(unclosed), [])

    def test_title_block_and_comments_skipped_when_naming_type(self):
        body = "---\ntitle: X\n---\n%% note\nclassDiagram\n  class A"
        self.assertEqual(self.mod.chart_type(body, self.rules), "class")

    def test_node_cap(self):
        edges = "\n".join(f"  N{i} --> N{i + 1}" for i in range(13))
        self.assertIn("too_many_nodes", self.reasons(chart("flowchart TD\n" + edges)))
        small = "\n".join(f"  N{i} --> N{i + 1}" for i in range(5))
        self.assertEqual(self.reasons(chart("flowchart TD\n" + small)), [])

    def test_style_line_and_host_address(self):
        self.assertIn("style_line_used", self.reasons(chart("flowchart TD\n  A --> B\n  style A fill:#fff")))
        self.assertIn("host_address", self.reasons(chart('flowchart TD\n  A["10.0.0.1"] --> B')))

    def test_quoted_label_does_not_trigger_shape_rule(self):
        self.assertEqual(self.reasons(chart('flowchart TD\n  A["call f((x))"] --> B')), [])

    def test_cylinder_and_diamond_allowed(self):
        self.assertEqual(self.reasons(chart("flowchart TD\n  A[(Store)] --> B{Gate}")), [])

    def test_read_flags_only_true_word(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "s.md"
            p.write_text("---\ntouches_data_model: true # note\nother: maybe\n---\n")
            flags = self.mod.read_flags(p)
            self.assertIs(flags["touches_data_model"], True)
            self.assertNotIn("other", flags)


if __name__ == "__main__":
    unittest.main()
