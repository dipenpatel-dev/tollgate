---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/run.sh    # relative path from repo root, e.g., scripts/setup.sh
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

The one command that runs the connector framework tests: the test files that sit directly in `tests/scripts/connectors`. It finds its own folder, turns off Python bytecode files, and hands over to Python's built-in test runner, which runs every file matching `test_*.py` with one line per test.

## Dependencies

**Depends on.**
- `bash`, named in the first line {src:tests/scripts/connectors/run.sh:1}.
- `dirname` and `pwd` to find its own folder {src:tests/scripts/connectors/run.sh:4}.
- A Python interpreter: the program named by the environment variable `TOLLGATE_TEST_PYTHON`, else `python3` {src:tests/scripts/connectors/run.sh:6}.
- The test files in the same folder: [[test_connectors]] / [test_connectors](test_connectors.md), [[test_connectors_hardening]] / [test_connectors_hardening](test_connectors_hardening.md), [[test_redirect_settings]] / [test_redirect_settings](test_redirect_settings.md) {src:tests/scripts/connectors/run.sh:6}.

**Used by.** Searched with `git grep` for `run.sh` and the folder path, excluding `docs/` (2026-11-20).
- Automation: the end-to-end runner loops over areas that include `connectors` and runs `bash $REPO/tests/scripts/$area/run.sh` for each {src:tests/system/run.sh:22-23}.
- Documentation: `scripts/README.md` says each area has a `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- The GitHub workflow runs only the hook and installer runners, not this one {src:.github/workflows/tests.yml:29} {src:.github/workflows/tests.yml:38}.
- Tests: no test calls this script.

## Behavior

1. `set -u` makes any use of an unset variable an error {src:tests/scripts/connectors/run.sh:3}. There is no `set -e`; the last step is `exec`, so it does not matter.
2. `DIR` becomes the absolute folder of the script, using `BASH_SOURCE[0]`, so the script can be started from any working directory {src:tests/scripts/connectors/run.sh:4}.
3. `PYTHONDONTWRITEBYTECODE=1` is exported so no `.pyc` files are written {src:tests/scripts/connectors/run.sh:5}.
4. The shell is replaced by Python with `exec`, running `unittest discover` with start folder `DIR`, pattern `test_*.py`, flags `-B` (no bytecode) and `-v` (verbose) {src:tests/scripts/connectors/run.sh:6}. Because of `exec`, the script's exit code is the test run's exit code, which the end-to-end runner treats as a failure when non-zero {src:tests/system/run.sh:23-25}.
5. The test files import their helpers by plain module name, for example `fake_connector` {src:tests/scripts/connectors/test_connectors.py:27}; they add their own folder to the module path first {src:tests/scripts/connectors/test_connectors.py:21}.

Side effects: none of its own. The tests write only inside temporary folders they delete {src:tests/harness/throwaway_home.py:51-59}.

## Diagram

None: the script is a straight line of four steps with no branch.

## Notes

- **Code and description.** The header says "Run the connector framework tests" {src:tests/scripts/connectors/run.sh:2}. The code runs the files directly in this folder. The three sub-areas have their own runners {src:tests/scripts/connectors/plane/run.sh:6} {src:tests/scripts/connectors/comms/run.sh:6} {src:tests/scripts/connectors/data/run.sh:6}, and the end-to-end runner calls each one separately {src:tests/system/run.sh:22}. Whether this runner also reaches into the sub-folders depends on how the Python version treats folders without `__init__.py`; none of the three sub-folders has one (searched the tracked file list, 2026-11-20) [uncertain: not run].
- **Unchecked inputs.** The program named by `TOLLGATE_TEST_PYTHON` is executed as is, with no check {src:tests/scripts/connectors/run.sh:6}. It comes from the caller's own environment. The script's arguments are not passed on (no `"$@"`), so naming one test file runs the whole folder {src:tests/scripts/connectors/run.sh:6}. No input reaches a file path, network address or outbound text.
- **Writes to shared files.** None.
- **Assumptions.** Needs bash and a Python with `unittest`. The suite binds local servers on `127.0.0.1` {src:tests/scripts/connectors/test_redirect_settings.py:32}, so it needs loopback networking.
- **Same name elsewhere.** `scripts/core/run.sh` is a different script with its own arguments {src:scripts/core/run.sh:7}.
