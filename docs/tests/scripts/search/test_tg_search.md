---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_tg_search.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-19
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/search/tg-search]         # source files under test, relative paths from repo root
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

This file tests the `tg-search` wrapper without running any real search tool. It checks which script each tool name picks, that arguments and stdin pass through, that the exit code is kept, which Python is chosen, and what a bad tool name does. A fake Python, written as a small shell script, records what it receives, so nothing real runs {src:tests/scripts/search/test_tg_search.py:26-29}.

## Dependencies

**Depends on.**
- Standard library only: `os`, `pathlib`, `shutil`, `stat`, `subprocess`, `tempfile`, `unittest` {src:tests/scripts/search/test_tg_search.py:12-18}.
- The program under test, `scripts/search/tg-search`: [[tg-search]] / [tg-search](../../../scripts/search/tg-search.md) {src:tests/scripts/search/test_tg_search.py:21}.
- The folder `scripts/search`, used to build the expected script paths {src:tests/scripts/search/test_tg_search.py:22}.
- `/bin/sh` for the fake Python {src:tests/scripts/search/test_tg_search.py:26}.

**Used by.** No product code. The file is picked up by the standard `unittest` run for `tests/`. No other file names it (searched the repo excluding `.git`, `docs/` and the `.x` backup, 2026-11-19).

## Behavior

**Fixture.** `setUp` makes a temporary folder, removed after each test {src:tests/scripts/search/test_tg_search.py:34} {src:tests/scripts/search/test_tg_search.py:35}. It writes the fake Python there and makes it executable {src:tests/scripts/search/test_tg_search.py:37-39}. The fake writes its first argument, each remaining argument, and stdin to the file named by `FAKE_OUT` {src:tests/scripts/search/test_tg_search.py:27}, then exits with `FAKE_EXIT` or 0 {src:tests/scripts/search/test_tg_search.py:28}.

**Runner.** `run_wrapper` copies the environment without `TOLLGATE_PYTHON` and `TOLLGATE_PATHS` {src:tests/scripts/search/test_tg_search.py:43}. It then sets `TOLLGATE_PYTHON` to the fake (or a given path), the output file, the exit code, and `HOME` to the temporary folder {src:tests/scripts/search/test_tg_search.py:44-45}. It runs the wrapper with a 30 second limit {src:tests/scripts/search/test_tg_search.py:47-48}.

**Tests.**
- Each of the four tool names makes the fake receive the matching script path next to the wrapper {src:tests/scripts/search/test_tg_search.py:55-58}. The expected names are in the `TOOLS` table {src:tests/scripts/search/test_tg_search.py:23-24}.
- Arguments pass through unchanged, including one with a space and an empty one {src:tests/scripts/search/test_tg_search.py:61-64}.
- Stdin reaches the tool {src:tests/scripts/search/test_tg_search.py:67-68}.
- Exit codes 0, 1, 3 and 42 come back unchanged {src:tests/scripts/search/test_tg_search.py:71-72}.
- An unknown tool exits 2, prints the usage and the bad word on stderr, prints nothing on stdout, and never runs the fake {src:tests/scripts/search/test_tg_search.py:75-80}.
- No arguments exits 2 with the usage {src:tests/scripts/search/test_tg_search.py:83-85}.
- A script file name such as `query_index.py` is refused with exit 2 {src:tests/scripts/search/test_tg_search.py:88}.
- Running from another working folder still finds the sibling script {src:tests/scripts/search/test_tg_search.py:91-95}.
- With `TOLLGATE_PYTHON` pointing at a missing file, and a venv in a state folder named by a paths file, the wrapper uses the venv Python {src:tests/scripts/search/test_tg_search.py:99-102} {src:tests/scripts/search/test_tg_search.py:106-109}. The paths file is `state: <folder>` {src:tests/scripts/search/test_tg_search.py:105}.
- The wrapper is executable and its first 20 lines hold an `# Author:` line and a `ChangeLog` line {src:tests/scripts/search/test_tg_search.py:112-115}.

## Diagram

None: the fixture is one fake program and one temporary folder, with no mock chain.

## Notes

**Test and its own description disagree.**
- The comment says the case is a `TOLLGATE_PYTHON` that is "not executable" {src:tests/scripts/search/test_tg_search.py:98}. The test passes a path that does not exist {src:tests/scripts/search/test_tg_search.py:106}. A file that exists but lacks the execute bit is not tested.
- The test name says it checks the fall back to the venv "then python3" {src:tests/scripts/search/test_tg_search.py:97}. Only the venv step is checked. No test removes the venv as well, so the last step, bare `python3` {src:scripts/search/tg-search:48}, has no test here.
- The header says the tests cover "the Python choice" {src:tests/scripts/search/test_tg_search.py:4}. That holds for two of the three choices (the configured one at line 44, the venv at line 106).

**Other gaps.**
- No test checks the exact usage text for the no-argument case beyond the `usage: tg-search` prefix {src:tests/scripts/search/test_tg_search.py:85}.
- The another-folder test does not clear `TOLLGATE_PATHS` or set `FAKE_EXIT` {src:tests/scripts/search/test_tg_search.py:92}. It is safe only because `TOLLGATE_PYTHON` is set and executable, so the state lookup never runs.
- The test sends no argument that looks like shell code, so quoting of odd arguments is checked only in `tests/commands/test_commands.py` {src:tests/commands/test_commands.py:359}.

**Unchecked inputs.** The test builds all paths and environment values itself. None comes from outside the test, so no input reaches a command or path unchecked.

**Shared files.** Writes go only to a fresh temporary folder per test {src:tests/scripts/search/test_tg_search.py:34}, so two tests never share a file.
