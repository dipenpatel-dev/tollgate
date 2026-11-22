---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/harness/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "exec python3 -m unittest discover (line 5)"    # function or line that executes when the script runs
requires: [bash, dirname, python3]         # external commands or tools this script depends on
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

A five-line launcher that runs the unit tests of the test harness (the throwaway home, the real-state guard and the connector helpers) from any folder. It prints each test name as it runs and ends with the test result as its own exit status. It writes no files of its own.

## Dependencies

External commands: `bash`, `dirname` and `python3` from the `PATH` {src:tests/harness/run.sh:1} {src:tests/harness/run.sh:4} {src:tests/harness/run.sh:5}. The only test file it finds is `tests/harness/test_harness.py` ([[test_harness]] and [test_harness](test_harness.md)), because it is the only file in the folder that matches the pattern {src:tests/harness/run.sh:5} {src:tests/harness/test_harness.py:25}.

**Used by.** Searched with `git grep` over the whole repo except `docs/` and the harness folder (2026-11-20, patterns `harness/run.sh` and `tests/harness`). No product code, workflow or other runner calls it. Not in the CI workflow, which runs the hook tests, the hook inventory check, the hook unit tests and the installer tests {src:.github/workflows/tests.yml:29} {src:.github/workflows/tests.yml:32} {src:.github/workflows/tests.yml:35} {src:.github/workflows/tests.yml:38}. Not in the system runner, whose list of script areas does not include the harness {src:tests/system/run.sh:22}. Only people run it by hand. The harness overview page tells them to ({src:docs/tests/harness.md:5}): [[harness]] and [harness](../harness.md).

## Behavior

1. `set -u` makes any use of an unset variable an error; `set -e` is not set, so a failing command does not stop the script by itself {src:tests/harness/run.sh:3}.
2. `DIR` is the folder that holds the script itself, worked out from `BASH_SOURCE[0]` with a `cd` inside a command substitution, so the script can be started from any working folder {src:tests/harness/run.sh:4}.
3. `exec` replaces the shell with `python3 -m unittest discover` over `DIR`, matching files named `test_*.py`, in verbose mode {src:tests/harness/run.sh:5}. Because of `exec`, the exit status of the script is the exit status of the test run: zero when all tests pass, non-zero otherwise.
4. Command-line arguments are not passed on: line 5 has no `"$@"`, so `run.sh -k name` runs everything {src:tests/harness/run.sh:5}.

## Diagram

None: straight-line script with no branches.

## Notes

- **Description versus code.** The header comment says "Run the harness tests." {src:tests/harness/run.sh:2} That matches line 5. No disagreement found.
- **Python choice.** It uses whatever `python3` is first on the `PATH` {src:tests/harness/run.sh:5}. The system runner lets a caller pick the interpreter with `TOLLGATE_TEST_PYTHON` {src:tests/system/run.sh:16}; this launcher has no such override.
- **Bytecode files.** It does not set `PYTHONDONTWRITEBYTECODE` or pass `-B`, so a run can leave `__pycache__` folders next to the harness files. The system runner sets the variable {src:tests/system/run.sh:12}. This is the only write the launcher can cause, it goes into the repo checkout, and nothing locks it.
- **Unchecked inputs.** The script reads no input. `DIR` is quoted {src:tests/harness/run.sh:5}, and it is derived from the script's own location {src:tests/harness/run.sh:4}. No value reaches a file path, shell command or network address without a check, apart from the `PATH` lookup of `python3`.
- **File mode.** Committed as executable (git mode 100755), so it can be started as `tests/harness/run.sh` {src:tests/harness/run.sh:1}.
