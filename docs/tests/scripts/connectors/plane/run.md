---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/run.sh    # relative path from repo root, e.g., scripts/setup.sh
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

The one command that runs every test in the plane connector test folder. It finds its own folder, turns off Python bytecode files, and hands over to Python's built-in test runner, which finds all `test_*.py` files in the folder and runs them with a line per test.

## Dependencies

**Depends on.**
- `bash` (the script starts with a bash shebang) {src:tests/scripts/connectors/plane/run.sh:1}.
- `dirname` and `pwd` to find its own folder {src:tests/scripts/connectors/plane/run.sh:4}.
- A Python interpreter: the program named in the environment variable `TOLLGATE_TEST_PYTHON`, else `python3` {src:tests/scripts/connectors/plane/run.sh:6}.
- The test files in the same folder, matched by the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}, for example [[test_plane_cli]] / [test_plane_cli](test_plane_cli.md), [[test_plane_client]] / [test_plane_client](test_plane_client.md), [[test_plane_comment_builder]] / [test_plane_comment_builder](test_plane_comment_builder.md), [[test_plane_connector]] / [test_plane_connector](test_plane_connector.md).

**Used by.** Searched the repo with `git grep` for `run.sh` and the folder path, excluding `docs/` (2026-11-20).
- Automation: the end-to-end runner loops over a list of areas that includes `connectors/plane` and runs `bash $REPO/tests/scripts/$area/run.sh` for each {src:tests/system/run.sh:22-23}.
- Documentation: `scripts/README.md` says each area has a `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- The GitHub workflow runs only the hook and installer runners, not this one {src:.github/workflows/tests.yml:29} {src:.github/workflows/tests.yml:38}.
- The sibling runner for the framework tests {src:tests/scripts/connectors/run.sh:6} is a separate script. The plane folder holds no `__init__.py` (listed 2026-11-20); whether that runner reaches into this folder was not tested.

## Behavior

1. `set -u` makes any use of an unset variable an error {src:tests/scripts/connectors/plane/run.sh:3}. There is no `set -e`, but the last step is `exec`, so it does not matter.
2. `DIR` becomes the absolute folder of the script, using `BASH_SOURCE[0]`, so the script can be started from any working directory {src:tests/scripts/connectors/plane/run.sh:4}.
3. `PYTHONDONTWRITEBYTECODE=1` is exported so no `.pyc` files are created in the repo {src:tests/scripts/connectors/plane/run.sh:5}.
4. The shell is replaced by Python with `exec`, running `unittest discover` with start folder `DIR`, pattern `test_*.py`, flags `-B` (no bytecode) and `-v` (verbose) {src:tests/scripts/connectors/plane/run.sh:6}. Because of `exec`, the exit code of the script is the exit code of the test run: 0 when all pass, non-zero otherwise (the runner's own rule; see the end-to-end runner, which treats non-zero as failure {src:tests/system/run.sh:23-25}).
5. Because the start folder is also the top folder for discovery, the tests import their helpers by plain module name, such as `plane_sync_test_support` {src:tests/scripts/connectors/plane/test_plane_cli.py:10}.

Side effects: none of its own. It writes no file; the tests create and remove temporary folders themselves {src:tests/scripts/connectors/plane/plane_sync_test_support.py:109-111}.

## Diagram

None: the script is a straight line of five steps with no branch.

## Notes

- **Code and description.** The header says "Run the plane connector tests" {src:tests/scripts/connectors/plane/run.sh:2}. The code does that and nothing else. No disagreement found.
- **Unchecked inputs.** The program named by `TOLLGATE_TEST_PYTHON` is executed as is, with no check on its value {src:tests/scripts/connectors/plane/run.sh:6}. It comes from the caller's own environment. The script's own arguments are not passed on: there is no `"$@"`, so `run.sh test_plane_cli` runs the whole folder, not one file {src:tests/scripts/connectors/plane/run.sh:6}. No input reaches a file path, network address or outbound text.
- **Writes to shared files.** None.
- **Assumptions.** Needs bash and a Python with `unittest` (standard library). The script does not check that the interpreter can import the connector code. The suite starts local servers on `127.0.0.1` {src:tests/scripts/connectors/plane/plane_stub_server.py:177}, so it needs loopback networking.
