---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
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

This is the runner for the search test folder. It points the standard `unittest` discovery at the folder it sits in and sets two environment variables so the tests never write bytecode and always use the fake (hash) embedder. It has no logic of its own beyond that.

## Dependencies

**Depends on.**
- Programs: `bash`, `dirname` and `pwd` (inside the `DIR=` line) {src:tests/scripts/search/run.sh:6}, and an interpreter named by `TOLLGATE_TEST_PYTHON`, falling back to `python3` {src:tests/scripts/search/run.sh:9}.
- Environment variable `TOLLGATE_TEST_PYTHON` (optional) {src:tests/scripts/search/run.sh:9}.
- The test files it discovers in the same folder: [[support]] and [support](support.md) is the shared helper, and the test pages are [[test_embedder_profile]] and [test_embedder_profile](test_embedder_profile.md), [[test_golden]] and [test_golden](test_golden.md), [[test_ground]] and [test_ground](test_ground.md), [[test_index_health]] and [test_index_health](test_index_health.md), [[test_internals]] and [test_internals](test_internals.md), [[test_ticket_flags]] and [test_ticket_flags](test_ticket_flags.md), [[test_review_fixes]] and [test_review_fixes](test_review_fixes.md), [[test_tg_search]] and [test_tg_search](test_tg_search.md). `test_reference.py` is also in the folder and is picked up by the same pattern, but its page is not in this batch (no doc yet).

**Used by.** Searched with `git grep` for `search/run.sh`, `tests/scripts/search` and `*/run.sh` outside `docs/` on 2026-11-20: no product code, installer line, command file or other runner names this script. It is started by hand. The sibling runners in `tests/scripts/*/run.sh` are separate files with the same last line, not callers.

## Behavior

1. `set -u` makes any use of an unset variable an error {src:tests/scripts/search/run.sh:5}. There is no `set -e`, so only the last command decides the exit code, and that command replaces the shell (step 4).
2. `DIR` is set to the absolute folder of the script itself, found from `BASH_SOURCE[0]` {src:tests/scripts/search/run.sh:6}.
3. It exports `PYTHONDONTWRITEBYTECODE=1` {src:tests/scripts/search/run.sh:7} and `TOLLGATE_EMBEDDER=hash` {src:tests/scripts/search/run.sh:8}.
4. It then replaces itself with `python -B -m unittest discover -s "$DIR" -p 'test_*.py' -v` {src:tests/scripts/search/run.sh:9}. The `-B` flag again stops bytecode writing, `-s` names the start folder, `-p` is the file pattern and `-v` prints each test name {src:tests/scripts/search/run.sh:9}. Because of `exec`, the exit code is whatever unittest returns, and the script takes no arguments of its own; any arguments are ignored (they are not forwarded).
5. The `TOLLGATE_EMBEDDER=hash` export is a second guard: every script the tests start, and every in-process test, also gets the same value from `script_env` {src:tests/scripts/search/support.py:39}, and `in_env` replaces the whole environment anyway {src:tests/scripts/search/support.py:54-55}.

## Diagram

None: the script is straight-line, four commands in order.

## Notes

- Code and description disagree: the header says that without `TOLLGATE_TEST_PYTHON` "the tests fall back to python3 and skip when chromadb is missing" {src:tests/scripts/search/run.sh:3-4}. The fallback to `python3` is true {src:tests/scripts/search/run.sh:9}. The skip is only true for tests that carry `skipUnless(support.HAVE_STORE, ...)`, for example `GoldenQuestions` {src:tests/scripts/search/test_golden.py:24} and `GroundStates` {src:tests/scripts/search/test_ground.py:23}. The classes `OneModelPerIndex` {src:tests/scripts/search/test_embedder_profile.py:108} and `SearchLayoutAndOptionalCollections` {src:tests/scripts/search/test_internals.py:187} have no skip marker and build a real index, so with no `chromadb` they would be expected to error, not skip. This was read, not run (the brief forbids running the suites).
- The comment "(read only use)" is unclear; the script itself never writes anything outside the interpreter's own behavior {src:tests/scripts/search/run.sh:9}.
- Unchecked input: `TOLLGATE_TEST_PYTHON` is used as the program to run with no check on its value {src:tests/scripts/search/run.sh:9}. It comes from the person running the tests, so this is a local trust assumption, not an outside input. No other input reaches a path, command or network address.
- Writes to shared files: none by this script. `PYTHONDONTWRITEBYTECODE` and `-B` keep Python from writing `.pyc` files {src:tests/scripts/search/run.sh:7}.
- Because the pattern is `test_*.py`, the stray file `tests/scripts/search/test_tg_search.py.x` (untracked in git on 2026-11-20) is not discovered.
