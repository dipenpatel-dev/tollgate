---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/cache/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "the final exec line that runs unittest discover"    # function or line that executes when the script runs
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

This script runs the tests that sit in its own folder, which are the cache script tests. It is a three-line launcher: it finds its folder, turns off bytecode files and hands over to the standard `unittest` runner.

## Dependencies

**Depends on.**
- [[test_cache]] ([test_cache](test_cache.md)): the only `test_*.py` file in the folder, found by the discovery pattern {src:tests/scripts/cache/run.sh:6}.
- `python3`, or the program named in the environment variable `TOLLGATE_TEST_PYTHON` {src:tests/scripts/cache/run.sh:6}.
- `bash` (shebang) {src:tests/scripts/cache/run.sh:1}.

**Used by.**
- Product code: none (searched `git grep` for `cache/run`, 2026-11-20).
- Tests and CI: not called by any other file in the repo, and no CI workflow names it (`.github/workflows/tests.yml` was read in full). It is a manual entry point. Sibling folders carry an identical launcher line, for example `tests/scripts/core/run.sh:6`.

## Behavior

- `set -u` makes an unset variable an error; there is no `set -e` {src:tests/scripts/cache/run.sh:3}.
- It sets `DIR` to the folder the script lives in, whatever the caller's working folder is {src:tests/scripts/cache/run.sh:4}.
- It exports `PYTHONDONTWRITEBYTECODE=1`, and also passes `-B`, so no `__pycache__` files are written {src:tests/scripts/cache/run.sh:5} {src:tests/scripts/cache/run.sh:6}.
- It replaces itself (`exec`) with the chosen Python running `-m unittest discover -s <folder> -p 'test_*.py' -v`, so the exit code is the unittest result and output is verbose {src:tests/scripts/cache/run.sh:6}.

## Diagram

None: straight-line script with no branches.

## Notes

**Code and description.** The header comment says "Run the tests in this folder" {src:tests/scripts/cache/run.sh:2}, and the code does exactly that. No disagreement.

**Unchecked inputs.** `TOLLGATE_TEST_PYTHON` is used as the command to run with no check on its value {src:tests/scripts/cache/run.sh:6}. Anything placed there runs. This is a test-runner variable set by the developer, not an outside input, but there is no validation. Extra arguments passed to the script are ignored, because the final line does not use `$@`.

**Shared-file writes.** None by the script. The tests it starts write only into temporary homes (see [[test_cache]]).

**Machine dependence.** Test discovery uses the folder path of the script, so it runs the same from any directory. The code the tests cover needs Python 3.8 or later, because `Path.unlink(missing_ok=True)` was added in 3.8 {src:scripts/cache/cache_write.py:32}. The repo's stated minimum is 3.12 {src:tests/system/run.sh:8}, which is above that.
