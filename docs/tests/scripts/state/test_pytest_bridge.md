---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/state/test_pytest_bridge.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["tests/scripts/state/minipytest.py"]         # source files under test, relative paths from repo root
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

This file is not a test in itself. It is the hook that lets `unittest` discovery run four test modules that are written in the `pytest` style. It imports each listed module, asks the stand-in `minipytest` to turn the module's tests into `unittest` cases, and returns them all as one suite. Without it, discovery would find no cases in those modules.

## Dependencies

**Depends on.**
- Standard library: `importlib`, `sys`, `unittest`, and `pathlib.Path` {src:tests/scripts/state/test_pytest_bridge.py:10-13}.
- [[minipytest]] and [minipytest](minipytest.md), imported inside `load_tests` {src:tests/scripts/state/test_pytest_bridge.py:27}, and its `make_cases` function {src:tests/scripts/state/test_pytest_bridge.py:31}.
- The four modules named in the list: `test_vault_census` (no doc yet, [[test_vault_census]]), [[test_backfill_vault_frontmatter]] and [test_backfill_vault_frontmatter](test_backfill_vault_frontmatter.md), [[test_backfill_ticket_policy]] and [test_backfill_ticket_policy](test_backfill_ticket_policy.md), and [[test_backfill_nonticket_policy]] and [test_backfill_nonticket_policy](test_backfill_nonticket_policy.md) {src:tests/scripts/state/test_pytest_bridge.py:16-21}.

**Used by.** Product code: none (searched `git grep` for `test_pytest_bridge` outside `docs/` on 2026-11-20; the only hits are this file and the comment in `minipytest.py` that names it). Tests and runners: found by the `test_*.py` pattern of [[run]] and [run](run.md) {src:tests/scripts/state/run.sh:6}. The `minipytest` docstring names it as the bridge {src:tests/scripts/state/minipytest.py:13}.

## Behavior

There are no test functions or test classes in this file {src:tests/scripts/state/test_pytest_bridge.py:24-37}. Its work is one function, `load_tests`, which the `unittest` loader calls with the loader, the cases it already found, and the file pattern {src:tests/scripts/state/test_pytest_bridge.py:24}.

1. Put this file's folder at the front of `sys.path` if it is missing, so the modules can be imported by bare name {src:tests/scripts/state/test_pytest_bridge.py:25-26}.
2. Import `minipytest` {src:tests/scripts/state/test_pytest_bridge.py:27} and start an empty `TestSuite` {src:tests/scripts/state/test_pytest_bridge.py:28}.
3. For each module name in the fixed list, import it {src:tests/scripts/state/test_pytest_bridge.py:29-30}, build its cases with `minipytest.make_cases` {src:tests/scripts/state/test_pytest_bridge.py:31}, and add each case to the suite with the loader {src:tests/scripts/state/test_pytest_bridge.py:32}.
4. Return the suite {src:tests/scripts/state/test_pytest_bridge.py:33}. The two other arguments, `standard_tests` and `pattern`, are not read, so any case `unittest` found in this file by itself is dropped {src:tests/scripts/state/test_pytest_bridge.py:24-33}.

Running the file directly calls `unittest.main()`, which uses the same hook {src:tests/scripts/state/test_pytest_bridge.py:36-37}.

**What the generated cases prove.** Each case runs one function or method from the listed modules through `run_one` {src:tests/scripts/state/minipytest.py:437-461}. The bridge itself asserts nothing, so it cannot fail on its own; a failure means one of the generated cases failed, or an import in the list raised.

## Diagram

None: the file is one function with one loop and no branches.

## Notes

- Code and description: the header says "unittest discovery calls load_tests here and gets one case per test function and parameter set" {src:tests/scripts/state/test_pytest_bridge.py:3-4}. True for the listed modules: `make_cases` makes one method per function and parameter set {src:tests/scripts/state/minipytest.py:471-488}. A class-scoped fixture is shared by all methods of a class {src:tests/scripts/state/minipytest.py:475}.
- The module list is hard-coded {src:tests/scripts/state/test_pytest_bridge.py:16-21}. A new `pytest`-style file in this folder is not run until it is added here. A plain `unittest` file such as `test_state_tools.py` does not need the list, because discovery finds its cases itself {src:tests/scripts/state/test_state_tools.py:52}.
- The list names `test_vault_census`, which this batch did not document; its tests are plain classes run only through this bridge {src:tests/scripts/state/test_vault_census.py:316}.
- No error handling around `importlib.import_module` {src:tests/scripts/state/test_pytest_bridge.py:30}: an import failure inside `load_tests` is raised from the hook. This page did not run the loader to see how `unittest` reports it.
- Inputs reaching a file path, shell command, network address or outbound text without a check: the module names in the list are literals, passed to `importlib.import_module` {src:tests/scripts/state/test_pytest_bridge.py:16-21} {src:tests/scripts/state/test_pytest_bridge.py:30}. No external input reaches it. No command or network address is built.
- Shared state: it inserts into the global `sys.path` once and never removes the entry {src:tests/scripts/state/test_pytest_bridge.py:25-26}. It writes no file. The imported test modules add their own atexit cleanup through `make_cases` {src:tests/scripts/state/minipytest.py:468-469}.
- Python version and machine: nothing here depends on a machine path; the folder comes from `__file__` {src:tests/scripts/state/test_pytest_bridge.py:15}. The generated cases need `git` and PyYAML for the backfill tests {src:tests/scripts/state/test_backfill_ticket_policy.py:42} {src:tests/scripts/state/test_backfill_ticket_policy.py:1427-1431}.
