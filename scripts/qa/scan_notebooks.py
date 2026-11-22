#!/usr/bin/env python3
"""
module_name: scan_notebooks.py
description: Scan notebooks for sensitive content. Prints counts and line numbers only, never
             notebook text. Nothing is written to disk. Notebooks come from a NotebookSource
             (a folder of .ipynb files here; a remote workspace connector plugs in later).
             A zero count is not proof a notebook is clean: the patterns cannot see names or
             plain-word lists. Saved cell outputs are counted, not read.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Generic port. Source is a seam; local folder source included; patterns made vendor neutral.
usage:
  scan_notebooks.py PATH            PATH is a .ipynb file or a folder of them
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Dict, Iterable, List, Pattern, Tuple

MAX_LINES_SHOWN = 12
LABEL_LENGTH = 24

PATTERNS: Dict[str, Pattern[str]] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "digit_run_7_plus": re.compile(r"\b\d{7,}\b"),
    "digit_list_literal": re.compile(r"\b\d{5,}\s*,\s*\d{5,}"),
    "date_literal": re.compile(r"\b(19|20)\d{2}-\d{2}-\d{2}\b"),
    "hardcoded_secret_literal": re.compile(
        r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|account[_-]?key|client[_-]?secret)\w*\s*[=:]\s*[\"'][^\"']{4,}[\"']"
    ),
    "connection_string_marker": re.compile(r"(?i)(AccountKey=|DefaultEndpointsProtocol|sig=|SharedAccessSignature)"),
    "secret_store_call": re.compile(r"(dbutils\.secrets\.get|get_secret\()"),
    "uri_cloud_storage": re.compile(r"\b(s3a?|gs|abfss?|wasbs?)://"),
    "uri_mount_or_volume": re.compile(r"(dbfs:/|/dbfs/|/mnt/|[/]Volumes[/])"),
    "output_exposure_calls": re.compile(r"\b(print\(|display\(|\.show\(|\.collect\(|\.toPandas\()"),
}


class NotebookSource:
    """What the scanner needs from any source: (label, notebook dict) pairs.

    A connector (a remote workspace, a job runner) subclasses this and yields the
    notebooks it exports. The scanner never learns where they came from.
    """

    def iter_notebooks(self) -> Iterable[Tuple[str, dict]]:
        raise NotImplementedError


class LocalFolderSource(NotebookSource):
    """Reads .ipynb files from a file or a folder."""

    def __init__(self, path):
        self.path = pathlib.Path(path)

    def iter_notebooks(self) -> Iterable[Tuple[str, dict]]:
        files = [self.path] if self.path.is_file() else sorted(self.path.rglob("*.ipynb"))
        for file in files:
            try:
                yield file.name[:LABEL_LENGTH], json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                yield file.name[:LABEL_LENGTH], {"_unreadable": True}


def cell_sources(notebook: dict) -> Tuple[List[str], int, int]:
    """Return (code lines, code cell count, count of cells that hold saved output)."""
    lines: List[str] = []
    cells_with_output = 0
    code_cells = 0
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        code_cells += 1
        source = cell.get("source", [])
        text = source if isinstance(source, str) else "".join(source)
        lines.extend(text.splitlines())
        if cell.get("outputs"):
            cells_with_output += 1
    return lines, code_cells, cells_with_output


def scan_lines(lines: List[str]) -> Dict[str, List[int]]:
    """Return {pattern name: [line numbers]}. Never returns the matching text."""
    hits: Dict[str, List[int]] = {name: [] for name in PATTERNS}
    for number, line in enumerate(lines, start=1):
        for name, pattern in PATTERNS.items():
            if pattern.search(line):
                hits[name].append(number)
    return hits


def format_report(label: str, lines: List[str], code_cells: int, with_output: int) -> List[str]:
    out = [f"== {label}: {code_cells} code cells, {len(lines)} lines, {with_output} cells hold saved output"]
    for name, numbers in scan_lines(lines).items():
        shown = ",".join(str(n) for n in numbers[:MAX_LINES_SHOWN])
        out.append(f"  {name:<26} count={len(numbers):<4} lines={shown or '-'}")
    return out


def scan_source(source: NotebookSource) -> List[str]:
    report: List[str] = []
    for label, notebook in source.iter_notebooks():
        if notebook.get("_unreadable"):
            report.append(f"== {label}: not readable (not scanned)")
            continue
        lines, code_cells, with_output = cell_sources(notebook)
        report.extend(format_report(label, lines, code_cells, with_output))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Count sensitive-content patterns in notebooks.")
    parser.add_argument("path", help="A .ipynb file or a folder of notebooks")
    args = parser.parse_args(argv)
    if not pathlib.Path(args.path).exists():
        print("No such path", file=sys.stderr)
        return 2
    for line in scan_source(LocalFolderSource(args.path)):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
