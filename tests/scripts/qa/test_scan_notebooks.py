#!/usr/bin/env python3
"""Tests for scan_notebooks: a synthetic notebook with a fake sensitive value built at run time.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove the scanner counts patterns, reports line numbers, and never prints notebook text.
Change log:
  - First version.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
QA_DIR = ROOT / "scripts" / "qa"
sys.path.insert(0, str(QA_DIR))
import scan_notebooks  # noqa: E402

FAKE_VALUE = "hunter" + "-" + "zz" + str(4217)          # built at run time, not a real secret
FAKE_EMAIL = "someone" + "@" + "example" + "." + "test"
FAKE_ID = "-".join(["123", "45", "6789"])


def make_notebook(extra_cells=()):
    cells = [
        {"cell_type": "markdown", "source": ["# heading with " + FAKE_EMAIL]},
        {"cell_type": "code", "source": ["import os\n", f"password = \"{FAKE_VALUE}\"\n", f"owner = \"{FAKE_EMAIL}\"\n"],
         "outputs": [{"text": ["saved " + FAKE_VALUE]}]},
        {"cell_type": "code", "source": f"ident = '{FAKE_ID}'\nprint(ident)\npath = 's3://bucket/key'\n", "outputs": []},
    ]
    cells.extend(extra_cells)
    return {"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}


class TestScanLines(unittest.TestCase):
    def test_counts_and_line_numbers(self):
        lines, code_cells, with_output = scan_notebooks.cell_sources(make_notebook())
        self.assertEqual(code_cells, 2)
        self.assertEqual(with_output, 1)
        hits = scan_notebooks.scan_lines(lines)
        self.assertEqual(hits["hardcoded_secret_literal"], [2])
        self.assertEqual(hits["email"], [3])
        self.assertEqual(hits["ssn_like"], [4])
        self.assertEqual(hits["output_exposure_calls"], [5])
        self.assertEqual(hits["uri_cloud_storage"], [6])

    def test_markdown_cells_and_saved_output_not_scanned(self):
        lines, _c, _o = scan_notebooks.cell_sources(make_notebook())
        self.assertNotIn(FAKE_EMAIL, "".join(lines[:1]))
        self.assertEqual(sum(1 for l in lines if "saved" in l), 0)

    def test_clean_notebook_has_zero_counts(self):
        clean = {"cells": [{"cell_type": "code", "source": ["x = 1\n"], "outputs": []}]}
        lines, _c, _o = scan_notebooks.cell_sources(clean)
        self.assertTrue(all(not v for v in scan_notebooks.scan_lines(lines).values()))

    def test_line_list_is_capped(self):
        many = {"cells": [{"cell_type": "code", "source": "".join(f"a{i} = '{FAKE_ID}'\n" for i in range(30))}]}
        lines, c, o = scan_notebooks.cell_sources(many)
        report = "\n".join(scan_notebooks.format_report("n", lines, c, o))
        row = [r for r in report.splitlines() if r.strip().startswith("ssn_like")][0]
        self.assertIn("count=30", row)
        self.assertEqual(len(row.split("lines=")[1].split(",")), scan_notebooks.MAX_LINES_SHOWN)


class TestScanCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        (self.dir / "a.ipynb").write_text(json.dumps(make_notebook()))
        (self.dir / "broken.ipynb").write_text("{ not json")

    def run_cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", str(QA_DIR / "scan_notebooks.py"), *args],
                              capture_output=True, text=True, env=env)

    def test_folder_scan_never_prints_values(self):
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout + proc.stderr
        for secret in (FAKE_VALUE, FAKE_EMAIL, FAKE_ID, "bucket"):
            self.assertNotIn(secret, out)
        self.assertIn("== a.ipynb: 2 code cells", out)
        self.assertIn("hardcoded_secret_literal count=1", " ".join(out.split()))
        self.assertIn("broken.ipynb: not readable", out)

    def test_single_file(self):
        proc = self.run_cli(str(self.dir / "a.ipynb"))
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("broken", proc.stdout)

    def test_missing_path_exits_two(self):
        self.assertEqual(self.run_cli(str(self.dir / "none")).returncode, 2)

    def test_nothing_written_to_disk(self):
        before = sorted(p.name for p in self.dir.iterdir())
        self.run_cli(str(self.dir))
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), before)


class TestSeam(unittest.TestCase):
    def test_custom_source_plugs_in(self):
        class Fake(scan_notebooks.NotebookSource):
            def iter_notebooks(self):
                yield "remote-1", make_notebook()

        report = scan_notebooks.scan_source(Fake())
        self.assertTrue(report[0].startswith("== remote-1"))

    def test_base_is_an_interface(self):
        with self.assertRaises(NotImplementedError):
            scan_notebooks.NotebookSource().iter_notebooks()


if __name__ == "__main__":
    unittest.main()
