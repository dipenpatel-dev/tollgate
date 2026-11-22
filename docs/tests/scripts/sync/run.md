---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/sync/run.sh    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "exec of python -m unittest discover (the last line)"    # function or line that executes when the script runs
requires: [bash, dirname, pwd, python3]       # external commands or tools this script depends on
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

The one command that runs the tests for the sync scripts (`scripts/sync`). It sits in the test folder `tests/scripts/sync`, finds its own folder, turns off Python bytecode files, and hands over to Python's built-in test runner, which runs every file there matching `test_*.py` with one line per test.

## Dependencies

**Depends on.**
- `bash`, named in the first line {src:tests/scripts/sync/run.sh:1}.
- `dirname` and `pwd` to find its own folder {src:tests/scripts/sync/run.sh:4}.
- A Python interpreter: the program named by the environment variable `TOLLGATE_TEST_PYTHON`, else `python3` {src:tests/scripts/sync/run.sh:6}.
- The test files in the same folder: [[test_sweep_path_safety]] / [test_sweep_path_safety](test_sweep_path_safety.md), [[test_sync_tools]] / [test_sync_tools](test_sync_tools.md) and [[test_sync_vault_scan]] / [test_sync_vault_scan](test_sync_vault_scan.md) {src:tests/scripts/sync/run.sh:6}. The folder was listed on 2026-11-20 and holds only those three test files.

**Used by.** Searched with `git grep` for `sync/run.sh` and the area name outside `docs/` (2026-11-20).
- Automation: the end-to-end runner loops over areas and runs `bash $REPO/tests/scripts/$area/run.sh` for each; `sync` is in its list {src:tests/system/run.sh:22-23}.
- Documentation: `scripts/README.md` says each area has a `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- The GitHub workflow runs only the hook and installer runners, not this one {src:.github/workflows/tests.yml:29} {src:.github/workflows/tests.yml:38}.
- Tests: none call this script.

## Behavior

1. `set -u` makes any use of an unset variable an error {src:tests/scripts/sync/run.sh:3}. There is no `set -e`; the last step is `exec`, so it does not matter.
2. `DIR` becomes the absolute folder of the script, using `BASH_SOURCE[0]`, so the script can be started from any working directory {src:tests/scripts/sync/run.sh:4}.
3. `PYTHONDONTWRITEBYTECODE=1` is exported so no `.pyc` files are written {src:tests/scripts/sync/run.sh:5}.
4. The shell is replaced by Python with `exec`, running `unittest discover` with start folder `DIR`, pattern `test_*.py`, flags `-B` and `-v` {src:tests/scripts/sync/run.sh:6}. Because of `exec`, the script's exit code is the test run's exit code, which the end-to-end runner treats as a failure when non-zero {src:tests/system/run.sh:23-25}.

Side effects: none of its own. The tests it starts work in a throwaway home {src:tests/scripts/sync/test_sync_tools.py:3}.

## Diagram

None: the script is a straight line of four steps with no branch.

## Notes

- **Code and description.** The header says "Run the sync script tests" {src:tests/scripts/sync/run.sh:2}. It runs the tests for the sync scripts, not the scripts. It does not say that one test (the real index field check) needs the `chromadb` package, while the search area runner says so in its header {src:tests/scripts/sync/test_sync_tools.py:95-101} {src:tests/scripts/search/run.sh:3}. Without the package, that test errors; the runner does not set `TOLLGATE_TEST_PYTHON` for you.
- **Unchecked inputs.** The program named by `TOLLGATE_TEST_PYTHON` is executed as is, with no check {src:tests/scripts/sync/run.sh:6}. It comes from the caller's own environment. The script's arguments are not passed on (no `"$@"`), so naming one test file runs the whole folder {src:tests/scripts/sync/run.sh:6}. No input reaches a file path, network address or outbound text.
- **Writes to shared files.** None.
- **Assumptions.** Needs bash and a Python with `unittest`. The script does not check that the interpreter has `PyYAML` or `chromadb`.
