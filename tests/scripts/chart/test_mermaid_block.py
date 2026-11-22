#!/usr/bin/env python3
"""Tests for mermaid_block: list, extract to standard output, range errors.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove blocks are found and extracted without fence markers.
Change log:
  - First version.
"""
import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "chart"))
import mermaid_block  # noqa: E402

FENCE = "`" * 3
DOC = ("## First\n" + FENCE + "mermaid\nflowchart TD\n  A --> B\n" + FENCE + "\n"
       "## Second\n" + FENCE + "mermaid\nflowchart TD\n  subgraph S\n  C --> D\n  end\n" + FENCE + "\n")


def call(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mermaid_block.main(args)
    return code, out.getvalue(), err.getvalue()


class TestMermaidBlock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = pathlib.Path(self.tmp.name) / "d.md"
        self.file.write_text(DOC)

    def test_list(self):
        code, out, _ = call([str(self.file)])
        self.assertEqual(code, 0)
        self.assertIn("1. First", out)
        self.assertIn("2. Second", out)
        self.assertIn("[has subgraph]", out)

    def test_extract_stdout(self):
        code, out, _ = call([str(self.file), "1", "--stdout"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "flowchart TD\n  A --> B")
        self.assertNotIn(FENCE, out)

    def test_range_and_missing(self):
        self.assertEqual(call([str(self.file), "9", "--stdout"])[0], 1)
        self.assertEqual(call([str(self.file) + ".none"])[0], 1)
        empty = pathlib.Path(self.tmp.name) / "e.md"
        empty.write_text("nothing")
        self.assertEqual(call([str(empty)])[0], 1)

    def test_no_clipboard_falls_back(self):
        original = mermaid_block.clipboard_command
        mermaid_block.clipboard_command = lambda: None
        try:
            code, out, err = call([str(self.file), "1"])
        finally:
            mermaid_block.clipboard_command = original
        self.assertEqual(code, 0)
        self.assertIn("Clipboard unavailable", err)
        self.assertIn("A --> B", out)


if __name__ == "__main__":
    unittest.main()
