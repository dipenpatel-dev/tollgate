---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/state/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "exec of python3 -m unittest discover (last line)"    # function or line that executes when the script runs
requires: ["bash", "dirname", "pwd", "python3 (or TOLLGATE_TEST_PYTHON)"]       # external commands or tools this script depends on
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

This is the runner for the state script test folder. It points the standard `unittest` discovery at the folder it sits in and sets one environment variable so the tests never write bytecode files. It has no logic of its own beyond that. Because most of the tests in this folder are written in the `pytest` style, the discovery run depends on the bridge module to turn them into `unittest` cases.

## Dependencies

**Depends on.**
- Programs: `bash`, `dirname` and `pwd` (used on the `DIR=` line) {src:tests/scripts/state/run.sh:4}, and an interpreter named by `TOLLGATE_TEST_PYTHON`, falling back to `python3` {src:tests/scripts/state/run.sh:6}.
- Environment variable `TOLLGATE_TEST_PYTHON` (optional) {src:tests/scripts/state/run.sh:6}.
- The test files it discovers in the same folder {src:tests/scripts/state/run.sh:6}: [[test_pytest_bridge]] and [test_pytest_bridge](test_pytest_bridge.md) is the one that supplies the `pytest`-style tests, using [[minipytest]] and [minipytest](minipytest.md). The test pages in this folder are [[test_backfill_vault_frontmatter]] and [test_backfill_vault_frontmatter](test_backfill_vault_frontmatter.md), [[test_backfill_ticket_policy]] and [test_backfill_ticket_policy](test_backfill_ticket_policy.md), and [[test_backfill_nonticket_policy]] and [test_backfill_nonticket_policy](test_backfill_nonticket_policy.md). `test_state_tools.py` is also picked up by the pattern; it holds plain `unittest.TestCase` classes {src:tests/scripts/state/test_state_tools.py:52}, and its page is [[test_state_tools]] and [test_state_tools](test_state_tools.md). `test_vault_census.py` is picked up too and is run through the bridge ([[test_vault_census]], no doc yet).
- It has the same shape as the search runner [[run]] and [run](../search/run.md).

**Used by.** Product code: none (searched `git grep` for `scripts/state/run`, `state/run.sh` and `run.sh` outside `docs/` on 2026-11-20). Runners and documentation: the system runner loops over a list of areas that includes `state` and calls `tests/scripts/$area/run.sh` for each {src:tests/system/run.sh:22-23}; the scripts README says each area has such a runner {src:scripts/README.md:31}. The sibling runners under `tests/scripts/*/run.sh` are separate files, not callers.

## Behavior

1. `set -u` makes the use of an unset variable an error {src:tests/scripts/state/run.sh:3}. There is no `set -e`; only the last command decides the exit code, and that command replaces the shell (step 4).
2. `DIR` is set to the absolute folder of the script, found from `BASH_SOURCE[0]` {src:tests/scripts/state/run.sh:4}.
3. It exports `PYTHONDONTWRITEBYTECODE=1` {src:tests/scripts/state/run.sh:5}.
4. It then replaces itself with `python -B -m unittest discover -s "$DIR" -p 'test_*.py' -v` {src:tests/scripts/state/run.sh:6}. `-B` again stops bytecode writing, `-s` is the start folder, `-p` is the file pattern and `-v` prints each test name {src:tests/scripts/state/run.sh:6}. Because of `exec`, the exit code is whatever `unittest` returns, and the script forwards no arguments: anything given to `run.sh` is ignored {src:tests/scripts/state/run.sh:6}.
5. The test classes in the three `test_backfill_*` modules are plain classes, not `unittest.TestCase` subclasses, for example `TestFolderRows` {src:tests/scripts/state/test_backfill_nonticket_policy.py:188}. Discovery therefore imports those modules and finds no cases in them directly; their cases arrive through `load_tests` in the bridge {src:tests/scripts/state/test_pytest_bridge.py:24-33}.

## Diagram

None: the script is straight-line, four commands in order.

## Notes

- Code and description: the header says "Run the state script tests." {src:tests/scripts/state/run.sh:2}. True. The scripts README adds that tests "run in a throwaway home" {src:scripts/README.md:31}; this runner does not make a throwaway home {src:tests/scripts/state/run.sh:3-6}. Isolation is done inside the tests, with pytest-style `tmp_path` folders and a git setup that points `HOME` at an empty folder {src:tests/scripts/state/test_backfill_ticket_policy.py:1401-1415}. Tests that use only `tmp_path` do not change `HOME`.
- Unlike the search runner, this one does not export `TOLLGATE_EMBEDDER` (the state tests do not use an embedder); it exports only the bytecode setting {src:tests/scripts/state/run.sh:5}.
- Unchecked input: `TOLLGATE_TEST_PYTHON` is used as the program to run with no check on its value {src:tests/scripts/state/run.sh:6}. It comes from the person running the tests. No other input reaches a path, command or network address.
- Writes to shared files: none by this script. `PYTHONDONTWRITEBYTECODE` and `-B` keep Python from writing `.pyc` files {src:tests/scripts/state/run.sh:5}.
- It uses `BASH_SOURCE`, a bash variable {src:tests/scripts/state/run.sh:4}, so it needs `bash`. The first line asks for `bash` through `env` {src:tests/scripts/state/run.sh:1}. This page did not test it under another shell.
