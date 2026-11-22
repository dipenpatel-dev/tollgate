---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/leak/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "the if test on the first argument, then exec of python3"    # function or line that executes when the script runs
requires: ["bash", "python3"]       # external commands or tools this script depends on
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

This is the one entry point for the leak scanner folder. With no arguments it runs the scanner's unit tests. With `scan` as the first argument it runs the scanner itself against a repo folder. It changes nothing on disk itself.

## Dependencies

**Depends on.**
- [[scan_leaks]] ([scan_leaks](scan_leaks.md)): started by the `scan` branch {src:tests/leak/run.sh:8}.
- [[test_leak]] ([test_leak](test_leak.md)): the only file the test branch finds, because it matches `test_*.py` {src:tests/leak/run.sh:10}.
- `python3` on the PATH and `bash` (the shebang line) {src:tests/leak/run.sh:1}.

**Used by.**
- Product code: none. Searched `git grep` for `leak/run` outside `docs/` (2026-11-20); the only hit is this file's own header comment.
- Tests and CI: not run by any CI workflow (the only workflow file, `.github/workflows/tests.yml`, was read in full and names no leak step). The leak scanner is used from `tests/commands/test_commands.py` by calling `scan_leaks.py` directly, not this script {src:tests/commands/test_commands.py:198}.

## Behavior

The script sets `set -u` only, so an unset variable is an error but a failing command does not stop it {src:tests/leak/run.sh:4}. It finds its own folder from the script path {src:tests/leak/run.sh:5}.

- If the first argument is `scan`, it drops that word and replaces itself with `python3 scan_leaks.py` plus every remaining argument, unchanged {src:tests/leak/run.sh:6-8}. The exit code is therefore the scanner's own: 0 clean, 1 hits, 2 usage error {src:tests/leak/scan_leaks.py:327} {src:tests/leak/scan_leaks.py:314}.
- Otherwise it replaces itself with `python3 -m unittest discover -s <this folder> -p 'test_*.py' -v` {src:tests/leak/run.sh:10}. The exit code is the unittest result.

## Diagram

None: one branch on the first argument, each branch ends in `exec`.

## Notes

**Code and description.**
- The header says the scan form is `scan <repo-folder> [--denylist FILE]` {src:tests/leak/run.sh:3}. The code forwards all arguments, so the scanner's `--allowlist` option works too {src:tests/leak/scan_leaks.py:309}. The header lists only one of the two options.
- Unlike the sibling script for the cache tests, this one does not read `TOLLGATE_TEST_PYTHON`, does not pass `-B` and does not set `PYTHONDONTWRITEBYTECODE` {src:tests/leak/run.sh:10} {src:tests/scripts/cache/run.sh:5-6}. Running the tests here can leave bytecode files in `tests/leak`.

**Unchecked inputs.** Every argument after `scan` reaches the scanner as typed, with no check in this script {src:tests/leak/run.sh:8}. The scanner then reads the named folder, denylist and allowlist (read only). The first argument is compared to the word `scan` and nothing else is validated.

**Shared-file writes.** None by this script. `scan` with no folder after it gives the scanner's usage error (exit 2), since the scanner requires a folder {src:tests/leak/scan_leaks.py:307}. Without a denylist, the scanner prints a warning that the denylist rule is skipped {src:tests/leak/scan_leaks.py:323}.
