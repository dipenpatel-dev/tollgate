---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/qa/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "exec python3 -B -m unittest discover (line 6)"    # function or line that executes when the script runs
requires: [bash, python3, unittest]       # external commands or tools this script depends on
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

This is the runner for the QA script tests. It finds the folder it lives in and runs every `test_*.py` file there with Python's `unittest`, with verbose output. Today the folder holds one test file, `test_scan_notebooks.py`. The script produces no files; its exit status is the test result.

## Dependencies

**Depends on.**
- `bash`, as the script's interpreter {src:tests/scripts/qa/run.sh:1}.
- The folder's own test files, found by the pattern `test_*.py` {src:tests/scripts/qa/run.sh:6}. At the time of writing that is [[test_scan_notebooks]] [test_scan_notebooks](test_scan_notebooks.md), written in the same batch; `ls tests/scripts/qa` on 2026-11-20 shows no other test file.
- `python3`, or the program named by the environment variable `TOLLGATE_TEST_PYTHON` {src:tests/scripts/qa/run.sh:6}, and its `unittest` module.
- The environment variable `PYTHONDONTWRITEBYTECODE`, which the script sets itself {src:tests/scripts/qa/run.sh:5}.

**Used by.**
- Product code: none. Searched with `git grep` for `run.sh` and for `tests/scripts/qa` outside `docs/` on 2026-11-20.
- The end-to-end runner loops over the script areas, `qa` among them, and runs each area's `run.sh` {src:tests/system/run.sh:22-23}.
- The scripts README tells readers that each area has a `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- Tests: none call it directly. The runner page for the end-to-end suite has no doc yet (no `docs/tests/system` folder).

## Behavior

1. `set -u` makes the script stop on an unset variable {src:tests/scripts/qa/run.sh:3}. There is no `set -e`.
2. `DIR` is set to the folder that holds the script, taken from `BASH_SOURCE` and made absolute; the `cd` runs in a sub-shell, so the caller's folder is unchanged {src:tests/scripts/qa/run.sh:4}.
3. `PYTHONDONTWRITEBYTECODE=1` is exported so no `.pyc` files are written {src:tests/scripts/qa/run.sh:5}.
4. The shell is replaced (`exec`) by `python3 -B -m unittest discover -s "$DIR" -p 'test_*.py' -v`. `TOLLGATE_TEST_PYTHON` replaces `python3` when it is set and not empty {src:tests/scripts/qa/run.sh:6}. Because of `exec`, the exit code of the script is the exit code of `unittest`: 0 when all tests pass, non-zero otherwise.
5. Command-line arguments are not forwarded; `"$@"` does not appear {src:tests/scripts/qa/run.sh:6}. So you cannot pick one test or one module through this script.

## Diagram

None: the script is a straight line of four commands with no branches.

## Notes

- **Code and description.** The header comment says "Run the tests in this folder" {src:tests/scripts/qa/run.sh:2}. The code does that. No disagreement. The file is the same as the cron runner except for that comment; the two are separate copies, not shared code {src:tests/scripts/cron/run.sh:2}.
- **Unchecked inputs.** `TOLLGATE_TEST_PYTHON` is executed as a program with no check on its value {src:tests/scripts/qa/run.sh:6}. A value with arguments inside it, such as `python3 -X dev`, would be read as one program name and fail, because the expansion is quoted. The folder path comes from the script's own location {src:tests/scripts/qa/run.sh:4}, not from input.
- **Writes to shared files.** The script writes nothing itself, and byte-code writing is switched off twice, by the variable and by `-B` {src:tests/scripts/qa/run.sh:5} {src:tests/scripts/qa/run.sh:6}. The test file in this folder imports `scan_notebooks` in the test process {src:tests/scripts/qa/test_scan_notebooks.py:21}, so the byte-code switch is what keeps a `__pycache__` out of `scripts/qa`.
- **Run from anywhere.** Because `DIR` comes from `BASH_SOURCE`, the script works from any current folder. The test file finds the repo through its own `__file__` and `sys.path` edit {src:tests/scripts/qa/test_scan_notebooks.py:18-20}.
- **Python version.** The script needs no particular version. The scanner under test uses `from __future__ import annotations` {src:scripts/qa/scan_notebooks.py:17}, kept from when the minimum was 3.9; it is not needed on 3.12.
