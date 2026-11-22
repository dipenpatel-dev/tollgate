---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/data/run.sh    # relative path from repo root, e.g., scripts/setup.sh
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

The one command that runs every test in the data connector test folder (the Databricks connector and the secrets tool). It finds its own folder, turns off Python bytecode files, and hands over to Python's built-in test runner, which finds all `test_*.py` files in that folder and prints a line per test.

## Dependencies

**Depends on.**
- `bash` (the script starts with a bash shebang) {src:tests/scripts/connectors/data/run.sh:1}.
- `dirname` and `pwd` to find its own folder {src:tests/scripts/connectors/data/run.sh:4}.
- A Python interpreter: the program named in the environment variable `TOLLGATE_TEST_PYTHON`, else `python3` {src:tests/scripts/connectors/data/run.sh:6}.
- The test files in the same folder, matched by `test_*.py` {src:tests/scripts/connectors/data/run.sh:6}: [[test_databricks]] / [test_databricks](test_databricks.md) and [[test_secrets_tool]] / [test_secrets_tool](test_secrets_tool.md).

**Used by.** Searched the repo with `git grep` for `run.sh` and `TOLLGATE_TEST_PYTHON`, excluding `docs/` (2026-11-20).
- Automation: the system test runner loops over a fixed list of areas that includes `connectors/data` {src:tests/system/run.sh:21} and runs `bash $REPO/tests/scripts/$area/run.sh` for each {src:tests/system/run.sh:22}. It treats a non-zero exit as a failure {src:tests/system/run.sh:24}.
- Documentation: `scripts/README.md` says each area has a `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- The GitHub workflow runs only the hook and installer runners, not this one {src:.github/workflows/tests.yml:29} {src:.github/workflows/tests.yml:38}.
- Sibling runners with the same four working lines: [[run]] for comms ([run](../comms/run.md)) and for plane ([run](../plane/run.md)).

## Behavior

1. `set -u` makes any use of an unset variable an error {src:tests/scripts/connectors/data/run.sh:3}. There is no `set -e`, but the last step is `exec`, so it does not matter.
2. `DIR` becomes the absolute folder of the script, using `BASH_SOURCE[0]`, so the script can be started from any working directory {src:tests/scripts/connectors/data/run.sh:4}.
3. `PYTHONDONTWRITEBYTECODE=1` is exported so no `.pyc` files are created in the repo {src:tests/scripts/connectors/data/run.sh:5}.
4. The shell is replaced by Python with `exec`, running `unittest discover` with start folder `DIR`, pattern `test_*.py`, flags `-B` (no bytecode) and `-v` (verbose) {src:tests/scripts/connectors/data/run.sh:6}. Because of `exec`, the exit code of the script is the exit code of the test run.
5. The folder holds two matching files, `test_databricks.py` and `test_secrets_tool.py` (listed 2026-11-20), so the run covers those two only.

Side effects: none of its own. It writes no file.

## Diagram

None: the script is a straight line of four steps with no branch.

## Notes

- **Code and description.** The header says "Run the connector framework tests" {src:tests/scripts/connectors/data/run.sh:2}. The code runs the tests in its own folder, which are the Databricks and secrets tool tests {src:tests/scripts/connectors/data/run.sh:6}. The framework tests (CON-01 to CON-04 for the fake connector) are in a different file one level up, `tests/scripts/connectors/test_connectors.py`, started by `tests/scripts/connectors/run.sh` {src:tests/scripts/connectors/run.sh:6}. The comms runner's header names its own folder instead {src:tests/scripts/connectors/comms/run.sh:2}, so this header looks copied from the parent runner and was not updated.
- **Unchecked inputs.** The program named by `TOLLGATE_TEST_PYTHON` is executed as is, with no check on its value {src:tests/scripts/connectors/data/run.sh:6}. It comes from the caller's own environment. The script's own arguments are not passed on (there is no `"$@"`), so `run.sh test_databricks` still runs the whole folder {src:tests/scripts/connectors/data/run.sh:6}. No input reaches a file path, network address or outbound text.
- **Writes to shared files.** None.
- **Assumptions.** Needs bash and a Python with `unittest` (standard library). The script does not check that the interpreter can import the connector code. The tests in this folder walk the whole repo tree and the throwaway home looking for a secret value {src:tests/scripts/connectors/data/test_databricks.py:121-130}, so a run takes longer as the repo grows.
