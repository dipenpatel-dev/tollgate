---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/core/run.sh    # relative path from repo root, e.g., scripts/setup.sh
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

The one command that runs the tests for the core scripts (`scripts/core`). It lives in the test folder `tests/scripts/core`, finds its own folder, turns off Python bytecode files, and hands over to Python's built-in test runner, which runs every file matching `test_*.py` there with one line per test.

## Dependencies

**Depends on.**
- `bash`, named in the first line {src:tests/scripts/core/run.sh:1}.
- `dirname` and `pwd` to find its own folder {src:tests/scripts/core/run.sh:5}.
- A Python interpreter: the program named by the environment variable `TOLLGATE_TEST_PYTHON`, else `python3` {src:tests/scripts/core/run.sh:6}.
- The test files in the same folder: [[test_bootstrap]] / [test_bootstrap](test_bootstrap.md), [[test_no_literal_paths]] / [test_no_literal_paths](test_no_literal_paths.md), [[test_paths]] / [test_paths](test_paths.md), [[test_tg_ticket_dir]] / [test_tg_ticket_dir](test_tg_ticket_dir.md) and [[test_vault_git]] / [test_vault_git](test_vault_git.md) {src:tests/scripts/core/run.sh:6} (the `test_*.py` files in the folder were listed 2026-11-20; each has a page).

**Used by.** Searched with `git grep` for `run.sh` and the folder path, excluding `docs/` (2026-11-20).
- Automation: the end-to-end runner loops over areas and runs `bash $REPO/tests/scripts/$area/run.sh` for each; `core` is the first area in its list {src:tests/system/run.sh:22-23}.
- Documentation: `scripts/README.md` says each area has a `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- The GitHub workflow runs only the hook and installer runners, not this one {src:.github/workflows/tests.yml:29} {src:.github/workflows/tests.yml:38}.
- Tests: `test_bootstrap.py` calls a script named `run.sh`, but it is the one in `scripts/core`, not this one {src:tests/scripts/core/test_bootstrap.py:24} {src:tests/scripts/core/test_bootstrap.py:103}.

## Behavior

1. `set -u` makes any use of an unset variable an error {src:tests/scripts/core/run.sh:3}. There is no `set -e`; the last step is `exec`, so it does not matter.
2. `PYTHONDONTWRITEBYTECODE=1` is exported so no `.pyc` files are written {src:tests/scripts/core/run.sh:4}.
3. `DIR` becomes the absolute folder of the script, using `BASH_SOURCE[0]`, so the script can be started from any working directory {src:tests/scripts/core/run.sh:5}.
4. The shell is replaced by Python with `exec`, running `unittest discover` with start folder `DIR`, pattern `test_*.py`, flags `-B` and `-v` {src:tests/scripts/core/run.sh:6}. Because of `exec`, the script's exit code is the test run's exit code, which the end-to-end runner treats as a failure when non-zero {src:tests/system/run.sh:23-25}.

Side effects: none of its own. The tests that call the real scripts do so inside a throwaway home {src:tests/scripts/core/test_bootstrap.py:101-103}.

## Diagram

None: the script is a straight line of four steps with no branch.

## Notes

- **Code and description.** The header says "Run the scripts/core tests" {src:tests/scripts/core/run.sh:2}. It runs the tests for `scripts/core`, which sit under `tests/scripts/core`; it does not run `scripts/core` itself. A reader may confuse it with `scripts/core/run.sh`, a different script that takes `all`, `sweep`, `index` or `lint` {src:scripts/core/run.sh:7}.
- **Ordering difference.** In this file the bytecode export comes before the `DIR` line {src:tests/scripts/core/run.sh:4-5}; the connector runners do it the other way round {src:tests/scripts/connectors/run.sh:4-5}. No effect on behavior.
- **Unchecked inputs.** The program named by `TOLLGATE_TEST_PYTHON` is executed as is, with no check {src:tests/scripts/core/run.sh:6}. It comes from the caller's own environment. The script's arguments are not passed on (no `"$@"`), so naming one test file runs the whole folder {src:tests/scripts/core/run.sh:6}. No input reaches a file path, network address or outbound text.
- **Writes to shared files.** None.
- **Assumptions.** Needs bash and a Python with `unittest`. The script does not check that the interpreter can import the core scripts.
