---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/chart/run.sh    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "the exec of unittest discover on line 6"    # function or line that executes when the script runs
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

This is the one-command runner for the chart test folder. It finds the folder it lives in, turns off Python bytecode files, and hands control to Python's unittest discovery so every `test_*.py` file in the folder runs with verbose output. It writes nothing itself.

## Dependencies

Depends on:
- `bash`, run through the `#!/usr/bin/env bash` line {src:tests/scripts/chart/run.sh:1}.
- `dirname` and `pwd`, used to find the script's own folder {src:tests/scripts/chart/run.sh:4}.
- The environment variable `TOLLGATE_TEST_PYTHON`, which names the Python program to use; when unset the script uses `python3` {src:tests/scripts/chart/run.sh:6}.
- The Python standard library `unittest` module, called with `-m unittest discover` {src:tests/scripts/chart/run.sh:6}.
- The two test files it finds: [[test_chart_check]] ([test_chart_check](test_chart_check.md)) and [[test_mermaid_block]] ([test_mermaid_block](test_mermaid_block.md)).

Used by:
- Product code: no product script calls it. The system runner calls every area's runner in a loop, and `chart` is one name in that loop {src:tests/system/run.sh:22}, run as `bash "$REPO/tests/scripts/$area/run.sh"` {src:tests/system/run.sh:23}.
- Documentation: `scripts/README.md` says each area has `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- Tests: none (searched `git grep -n "run\.sh"` outside `docs/` on 2026-11-20; the only hits that name this file's path are the two above).

## Behavior

1. `set -u` makes any use of an unset variable an error {src:tests/scripts/chart/run.sh:3}. There is no `set -e`, so a failed command in the script would not stop it; in practice the script has one command that matters, the last one.
2. `DIR` is set to the absolute folder holding the script, taken from `BASH_SOURCE[0]` {src:tests/scripts/chart/run.sh:4}. The `cd` happens inside a command substitution, so the caller's working folder is unchanged.
3. `PYTHONDONTWRITEBYTECODE=1` is exported so child Python processes write no `.pyc` files {src:tests/scripts/chart/run.sh:5}. The Python call also carries `-B`, which does the same for the main process {src:tests/scripts/chart/run.sh:6}.
4. `exec` replaces the shell with Python, so the script's exit code is the exit code of unittest {src:tests/scripts/chart/run.sh:6}. Python runs `unittest discover -s "$DIR" -p 'test_*.py' -v`: start folder is the script's folder, pattern is `test_*.py`, output is verbose {src:tests/scripts/chart/run.sh:6}.
5. With only `-s` given, unittest uses the start folder as the top-level folder and puts it on the import path {src:docs:https://docs.python.org/3/library/unittest.html#unittest-test-discovery}. This is not used here by any import in this folder, but the sibling comms runner relies on it.
6. The pattern matches only files whose names start with `test_`, so helper files in the folder are not collected as tests {src:tests/scripts/chart/run.sh:6}.

## Diagram

None: the script is straight-line, five commands in order with no branches.

## Notes

- Code and description agree: the comment says "Run the tests in this folder." {src:tests/scripts/chart/run.sh:2} and the command runs discovery on this folder {src:tests/scripts/chart/run.sh:6}.
- Unchecked inputs: `TOLLGATE_TEST_PYTHON` is executed as a command with no check on its value {src:tests/scripts/chart/run.sh:6}. It comes from the caller's own environment. No other input reaches a path, a shell command, a network address or outbound text; extra command-line arguments to the script are ignored.
- Shared-file writes: the script writes no file. Bytecode writing is switched off {src:tests/scripts/chart/run.sh:5}. The tests it launches write only inside temporary folders (see the two test pages).
- Needs bash because it uses `BASH_SOURCE` {src:tests/scripts/chart/run.sh:4}.
