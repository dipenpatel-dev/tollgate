---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/cron/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
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

This is the runner for the cron script tests. It finds the folder it lives in and runs every `test_*.py` file there with Python's `unittest`, with verbose output. Today the folder holds one test file, `test_cron_tools.py`. The script produces no files; its exit status is the test result.

## Dependencies

**Depends on.**
- `bash`, as the script's interpreter {src:tests/scripts/cron/run.sh:1}.
- The folder's own test files, found by the pattern `test_*.py` {src:tests/scripts/cron/run.sh:6}. At the time of writing that is [[test_cron_tools]] [test_cron_tools](test_cron_tools.md), written in the same batch; `ls tests/scripts/cron` on 2026-11-20 shows no other test file.
- `python3`, or the program named by the environment variable `TOLLGATE_TEST_PYTHON` {src:tests/scripts/cron/run.sh:6}, and its `unittest` module.
- The environment variable `PYTHONDONTWRITEBYTECODE`, which the script sets itself {src:tests/scripts/cron/run.sh:5}.

**Used by.**
- Product code: none. Searched with `git grep` for `run.sh` and for `tests/scripts/cron` outside `docs/` on 2026-11-20.
- The end-to-end runner loops over the script areas, `cron` among them, and runs each area's `run.sh` {src:tests/system/run.sh:22-23}.
- The scripts README tells readers that each area has a `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- Tests: none call it directly. The runner page for the end-to-end suite has no doc yet (no `docs/tests/system` folder).

## Behavior

1. `set -u` makes the script stop on an unset variable {src:tests/scripts/cron/run.sh:3}. There is no `set -e`.
2. `DIR` is set to the folder that holds the script, taken from `BASH_SOURCE` and made absolute; the `cd` runs in a sub-shell, so the caller's folder is unchanged {src:tests/scripts/cron/run.sh:4}.
3. `PYTHONDONTWRITEBYTECODE=1` is exported so no `.pyc` files are written {src:tests/scripts/cron/run.sh:5}.
4. The shell is replaced (`exec`) by `python3 -B -m unittest discover -s "$DIR" -p 'test_*.py' -v`. `TOLLGATE_TEST_PYTHON` replaces `python3` when it is set and not empty {src:tests/scripts/cron/run.sh:6}. Because of `exec`, the exit code of the script is the exit code of `unittest`: 0 when all tests pass, non-zero otherwise.
5. Command-line arguments are not forwarded; `"$@"` does not appear {src:tests/scripts/cron/run.sh:6}. So you cannot pick one test or one module through this script.

## Diagram

None: the script is a straight line of four commands with no branches.

## Notes

- **Code and description.** The header comment says "Run the cron script tests" {src:tests/scripts/cron/run.sh:2}. The code runs every `test_*.py` in the folder, so it would also run any test file added later. No disagreement today.
- **Unchecked inputs.** `TOLLGATE_TEST_PYTHON` is executed as a program with no check on its value {src:tests/scripts/cron/run.sh:6}. A value with arguments inside it, such as `python3 -X dev`, would be read as one program name and fail, because the expansion is quoted. The folder path comes from the script's own location {src:tests/scripts/cron/run.sh:4}, not from input.
- **Writes to shared files.** The script writes nothing itself, and byte-code writing is switched off twice, by the variable and by `-B` {src:tests/scripts/cron/run.sh:5} {src:tests/scripts/cron/run.sh:6}. The tests it starts write into throwaway homes only, apart from the real-environment reads described on the test page.
- **Run from anywhere.** Because `DIR` comes from `BASH_SOURCE`, the script works from any current folder. `unittest discover -s` treats that folder as the start and top level, so test files import their repo helpers through their own `sys.path` edits rather than through the runner {src:tests/scripts/cron/test_cron_tools.py:26-27}.
- **Python version.** The script needs no particular version; the tests it runs use `Path.is_relative_to`, which needs Python 3.9 or later {src:tests/scripts/cron/test_cron_tools.py:248}; the 3.12 minimum covers that.
