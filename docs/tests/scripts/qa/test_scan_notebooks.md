---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/qa/test_scan_notebooks.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/qa/scan_notebooks.py]         # source files under test, relative paths from repo root
tags: []
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
---

## Purpose

This file tests the notebook scanner, a QA tool that counts sensitive-looking patterns in Jupyter notebooks and prints only counts and line numbers, never the notebook text. The tests build a small fake notebook whose "sensitive" values are assembled at run time, so no real secret or personal value is stored in the test file {src:tests/scripts/qa/test_scan_notebooks.py:2} {src:tests/scripts/qa/test_scan_notebooks.py:23-25}. The header states the aim: prove the scanner counts patterns, reports line numbers, and never prints notebook text {src:tests/scripts/qa/test_scan_notebooks.py:6}.

## Dependencies

**Depends on.**
- Standard library imports, as written: `json`, `os`, `pathlib`, `subprocess`, `sys`, `tempfile`, `unittest` {src:tests/scripts/qa/test_scan_notebooks.py:10-16}.
- `scan_notebooks`, imported by bare name after the `scripts/qa` folder is put on the import path {src:tests/scripts/qa/test_scan_notebooks.py:19-21}: [[scan_notebooks]] and [scan_notebooks](../../../scripts/qa/scan_notebooks.md).
- The scanner is also started as a separate process with the current Python and `-B` {src:tests/scripts/qa/test_scan_notebooks.py:80}.
- No test harness module is used: there is no `throwaway_home` here, only a `tempfile` folder per test {src:tests/scripts/qa/test_scan_notebooks.py:72}.

**Used by.**
- Product code: none. Searched with `git grep` for `test_scan_notebooks` outside `docs/` on 2026-11-20; no file names it.
- Found at run time by `unittest discover` in [[run]] [run](run.md) {src:tests/scripts/qa/run.sh:6}, which the end-to-end runner calls {src:tests/system/run.sh:23}.
- Tests: this file is itself a test.

## Behavior

**Fixtures.**
- `FAKE_VALUE`, `FAKE_EMAIL` and `FAKE_ID` are joined from pieces at run time, so the test file holds no value shaped like a secret, an email or an ID {src:tests/scripts/qa/test_scan_notebooks.py:23-25}.
- `make_notebook()` returns a notebook dict with three cells {src:tests/scripts/qa/test_scan_notebooks.py:29-34}.
  - A markdown cell holding the fake email {src:tests/scripts/qa/test_scan_notebooks.py:30}.
  - A code cell with `import os`, a `password = "<fake>"` line, an `owner = "<fake email>"` line, and a saved output that repeats the fake value {src:tests/scripts/qa/test_scan_notebooks.py:31-32}.
  - A code cell, written as one string, with an ID-shaped value, a `print` call and an `s3://` address {src:tests/scripts/qa/test_scan_notebooks.py:33}.

**Class `TestScanLines`.**
- `test_counts_and_line_numbers`: the notebook has 2 code cells and 1 cell with saved output {src:tests/scripts/qa/test_scan_notebooks.py:41-43}. The scanner counts only code cells and counts a cell as having output when its output list is not empty {src:scripts/qa/scan_notebooks.py:78-85}. Line numbers run over the code lines of all code cells joined together, starting at 1 {src:scripts/qa/scan_notebooks.py:83} {src:scripts/qa/scan_notebooks.py:92}. The test expects the secret literal on line 2, the email on line 3, the ID-shaped value on line 4, the `print` call on line 5 and the cloud address on line 6 {src:tests/scripts/qa/test_scan_notebooks.py:45-49}. The matching patterns are {src:scripts/qa/scan_notebooks.py:30} {src:scripts/qa/scan_notebooks.py:31} {src:scripts/qa/scan_notebooks.py:35-37} {src:scripts/qa/scan_notebooks.py:40} {src:scripts/qa/scan_notebooks.py:42}. Only five of the eleven pattern names are asserted.
- `test_markdown_cells_and_saved_output_not_scanned`: the first code line does not hold the fake email, and no scanned line holds the word "saved" {src:tests/scripts/qa/test_scan_notebooks.py:52-54}. The scanner skips cells that are not code and never reads outputs {src:scripts/qa/scan_notebooks.py:78-79}. The first assertion looks only at `lines[:1]` {src:tests/scripts/qa/test_scan_notebooks.py:53}; that is enough here because the markdown cell comes first in the fake notebook {src:tests/scripts/qa/test_scan_notebooks.py:30}.
- `test_clean_notebook_has_zero_counts`: a notebook with `x = 1` gives an empty list for every pattern {src:tests/scripts/qa/test_scan_notebooks.py:57-59} {src:scripts/qa/scan_notebooks.py:91}.
- `test_line_list_is_capped`: 30 code lines each holding the ID-shaped value give `count=30` in the report row, but only `MAX_LINES_SHOWN` line numbers are listed {src:tests/scripts/qa/test_scan_notebooks.py:62-67}. The report prints the full count and the first 12 numbers {src:scripts/qa/scan_notebooks.py:26} {src:scripts/qa/scan_notebooks.py:102-103}.

**Class `TestScanCli`.**
- `setUp` makes a temp folder with `a.ipynb` (the fake notebook as JSON) and `broken.ipynb` (the text `{ not json`) {src:tests/scripts/qa/test_scan_notebooks.py:72-76}. `run_cli` starts `scan_notebooks.py` as a process with `PYTHONDONTWRITEBYTECODE` set {src:tests/scripts/qa/test_scan_notebooks.py:79-81}.
- `test_folder_scan_never_prints_values`: exit 0; none of the fake value, email, ID or the word `bucket` appears in stdout plus stderr; stdout has `== a.ipynb: 2 code cells`, a `hardcoded_secret_literal count=1` row (after collapsing spaces), and `broken.ipynb: not readable` {src:tests/scripts/qa/test_scan_notebooks.py:85-91}. The scanner prints only a header, counts and line numbers {src:scripts/qa/scan_notebooks.py:100} {src:scripts/qa/scan_notebooks.py:103}, and reports a file that fails to read or parse as unreadable {src:scripts/qa/scan_notebooks.py:66-69} {src:scripts/qa/scan_notebooks.py:111}.
- `test_single_file`: scanning `a.ipynb` alone exits 0 and the output does not mention `broken` {src:tests/scripts/qa/test_scan_notebooks.py:94-96}. A file path is scanned as the only file {src:scripts/qa/scan_notebooks.py:64}.
- `test_missing_path_exits_two`: a path that does not exist exits 2 {src:tests/scripts/qa/test_scan_notebooks.py:99} {src:scripts/qa/scan_notebooks.py:122-124}.
- `test_nothing_written_to_disk`: the folder's list of names is the same before and after a scan {src:tests/scripts/qa/test_scan_notebooks.py:102-104}. The scanner only prints {src:scripts/qa/scan_notebooks.py:125-126}.

**Class `TestSeam`** (the scanner reads notebooks through a source class that other code can replace).
- `test_custom_source_plugs_in`: a subclass of `NotebookSource` that yields one notebook labelled `remote-1` gives a report whose first line starts with `== remote-1` {src:tests/scripts/qa/test_scan_notebooks.py:109-114} {src:scripts/qa/scan_notebooks.py:107-115}.
- `test_base_is_an_interface`: calling `iter_notebooks` on the base class raises `NotImplementedError` {src:tests/scripts/qa/test_scan_notebooks.py:117-118} {src:scripts/qa/scan_notebooks.py:53-54}.

## Diagram

None: one fake notebook and one temp folder per test, no mock chains. The only stand-in is the `Fake` subclass in the seam test {src:tests/scripts/qa/test_scan_notebooks.py:109}.

## Notes

- **Code and description.** No disagreement found between the test header {src:tests/scripts/qa/test_scan_notebooks.py:6} and the tests. The scanner's docstring says nothing is written to disk and saved outputs are counted, not read {src:scripts/qa/scan_notebooks.py:4-8}; the code matches both {src:scripts/qa/scan_notebooks.py:84-85} {src:scripts/qa/scan_notebooks.py:125-126}.
- **Weak or missing checks.**
  - Six patterns have no positive test: `digit_run_7_plus`, `digit_list_literal`, `date_literal`, `connection_string_marker`, `secret_store_call` and `uri_mount_or_volume` {src:scripts/qa/scan_notebooks.py:32-34} {src:scripts/qa/scan_notebooks.py:38-39} {src:scripts/qa/scan_notebooks.py:41}.
  - The "never prints values" test checks four specific strings only {src:tests/scripts/qa/test_scan_notebooks.py:87-88}. Other notebook text would not be caught by it.
  - The "nothing written" test lists only top-level names in the folder {src:tests/scripts/qa/test_scan_notebooks.py:102-104}, so a change to a file's content, or a file in a sub-folder, would pass.
  - Valid JSON that is not an object, for example a file holding `[]`, is not tested. The scanner calls `.get` on whatever it parsed {src:scripts/qa/scan_notebooks.py:110}, which a list does not have; the parse step only catches bad JSON and read errors {src:scripts/qa/scan_notebooks.py:68}. I read this and did not run it.
  - Label shortening to 24 characters {src:scripts/qa/scan_notebooks.py:27} {src:scripts/qa/scan_notebooks.py:67} has no test.
- **Machine and version dependence.** None on a machine path: the scripts folder is found from `__file__` {src:tests/scripts/qa/test_scan_notebooks.py:18-19}. The in-process import of `scan_notebooks` would write a `__pycache__` folder under `scripts/qa` if the runner did not set `PYTHONDONTWRITEBYTECODE` {src:tests/scripts/qa/test_scan_notebooks.py:21} {src:tests/scripts/qa/run.sh:5}. The scanner uses `from __future__ import annotations` {src:scripts/qa/scan_notebooks.py:17}, kept from when the minimum was 3.9; it is not needed on 3.12.
- **Inputs that reach paths or commands.** In the scanner, the command-line path is checked only for existence and is then read as a file or walked for `*.ipynb` files, with no size limit and no check on where it points {src:scripts/qa/scan_notebooks.py:122} {src:scripts/qa/scan_notebooks.py:64-67}. No shell command is built, and nothing is sent over a network. In the tests every path is a constant or a temp folder {src:tests/scripts/qa/test_scan_notebooks.py:72-76}.
- **Writes to shared files.** The tests write only `a.ipynb` and `broken.ipynb` into their own temp folder, which is deleted by `addCleanup` {src:tests/scripts/qa/test_scan_notebooks.py:73} {src:tests/scripts/qa/test_scan_notebooks.py:75-76}. The writes are plain `write_text`, not atomic, and nothing shared is touched.
- **Header.** The `Date:` field of the header is empty {src:tests/scripts/qa/test_scan_notebooks.py:5}.
