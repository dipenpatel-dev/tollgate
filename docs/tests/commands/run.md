---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/commands/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "exec python3 -B -m unittest discover"    # function or line that executes when the script runs
requires: [bash, dirname, python3]       # external commands or tools this script depends on
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

The launcher for the command file tests. It starts Python's test discovery on its own folder, so every `test_*.py` file next to it runs, and it keeps Python from leaving compiled cache files in the repo.

## Dependencies

**Depends on.**
- `bash` {src:tests/commands/run.sh:1} and `dirname` {src:tests/commands/run.sh:5}.
- `python3` on `PATH` {src:tests/commands/run.sh:7}.
- The test file in the same folder, found by the pattern `test_*.py` {src:tests/commands/run.sh:7}. Page: [[test_commands]] / [test_commands](test_commands.md).
- The environment variable `TOLLGATE_REQUIRE_SCRIPTS` is not read here. The test file reads it {src:tests/commands/test_commands.py:224}.
- Overview page for this test area: [[commands]] / [commands](../commands.md).

**Used by.**
- Product code: none.
- It is named in the test file's own header {src:tests/commands/test_commands.py:3}. No other file in the repo calls it (searched `git grep` for `tests/commands` and `test_commands`, excluding `docs/`, 2026-11-20).

## Behavior

1. `set -u` makes an unset variable an error. There is no `-e`, so a failed command does not stop the script by itself {src:tests/commands/run.sh:4}.
2. It works out its own folder {src:tests/commands/run.sh:5}.
3. It sets `PYTHONDONTWRITEBYTECODE=1` for the Python process {src:tests/commands/run.sh:6}.
4. It replaces itself with `python3 -B -m unittest discover -s <folder> -p 'test_*.py' -v`, so the exit code is the test run's exit code {src:tests/commands/run.sh:7}. `-B` is the command-line twin of the environment setting in the previous step.

## Diagram

Skipped: straight-line script with no branches.

## Notes

- The header comment says the script runs "CMD-01 to CMD-05" {src:tests/commands/run.sh:2}. The test file also holds classes for the quoting test, the fixed prefix and the vault git step, which discovery runs too {src:tests/commands/test_commands.py:320} {src:tests/commands/test_commands.py:365} {src:tests/commands/test_commands.py:413}.
- The usage line shows `TOLLGATE_REQUIRE_SCRIPTS=1` before `bash` {src:tests/commands/run.sh:3}. That works because the variable is passed through to the Python process.
- No check exists on the environment or the arguments; arguments are ignored. Nothing reaches a file path, shell command or network address from outside.
- The script writes no file. The tests it starts write only to temporary folders.
- `python3` is whichever the `PATH` finds first, so the Python version is not fixed {src:tests/commands/run.sh:7}.
