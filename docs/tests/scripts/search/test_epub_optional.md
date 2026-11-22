---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_epub_optional.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/search/build_index.py]         # source files under test, relative paths from repo root
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

Two tests that show the search index builder still works when the epub library `ebooklib` is not installed. A missing library gives a clear hint, and a build skips epub files with one warning while it indexes everything else. The test file's own description says the same {src:tests/scripts/search/test_epub_optional.py:2}.

## Dependencies

**Depends on.**
- Standard library: `pathlib`, `sys`, `unittest`, `unittest.mock` {src:tests/scripts/search/test_epub_optional.py:10} {src:tests/scripts/search/test_epub_optional.py:11} {src:tests/scripts/search/test_epub_optional.py:12} {src:tests/scripts/search/test_epub_optional.py:13}.
- The shared search test helpers: `support`, with `in_env`, `script_env`, `throwaway_home` and `write` {src:tests/scripts/search/test_epub_optional.py:15} {src:tests/scripts/search/test_epub_optional.py:16}. [[support]] / [support](support.md); [[throwaway_home]] / [throwaway_home](../../harness/throwaway_home.md).
- Inside the tests, the modules `build_index`, `config` and `router` from `scripts/search`, put on the import path by `support` {src:tests/scripts/search/test_epub_optional.py:43} {src:tests/scripts/search/test_epub_optional.py:49} {src:tests/scripts/search/test_epub_optional.py:50} {src:tests/scripts/search/test_epub_optional.py:51}. [[build_index]] / [build_index](../../../scripts/search/build_index.md).
- `chromadb` and `pyyaml`: the whole class is skipped when they are not importable {src:tests/scripts/search/test_epub_optional.py:30}.

**Used by.** Run by `tests/scripts/search/run.sh`, which calls `unittest discover` over its folder with `test_*.py` {src:tests/scripts/search/run.sh:9}. That runner is not a step of the CI workflow (searched `.github/workflows/tests.yml` for `scripts/search`, 2026-11-21). Searched `git grep test_epub_optional` outside `docs/` (2026-11-21): nothing else names it.

## Behavior

Helper `_BlockEpub` is a context manager that sets `ebooklib` and `ebooklib.epub` to `None` in `sys.modules`, so an import of either raises `ImportError` even when the library is installed {src:tests/scripts/search/test_epub_optional.py:19-27}. `setUp` makes a throwaway home, a synthetic vault under it, an environment pointing `TOLLGATE_KNOWLEDGE` at that vault, and a file `book.epub` that holds the text "not a real epub" {src:tests/scripts/search/test_epub_optional.py:33-37}. `tearDown` closes the throwaway home {src:tests/scripts/search/test_epub_optional.py:40}.

| Test | What it proves |
|---|---|
| `test_missing_library_gives_a_hint_to_the_epub_requirements_file` | With the library blocked, `build_index.chunk_epub` raises `ImportError`, and the message contains `requirements-epub.txt` {src:tests/scripts/search/test_epub_optional.py:44} {src:tests/scripts/search/test_epub_optional.py:46}. The code re-raises with the hint after a failed import {src:scripts/search/build_index.py:195} {src:scripts/search/build_index.py:196}. |
| `test_build_skips_epub_with_one_log_line_and_keeps_other_files` | The test adds two epub entries, `refs/one.epub` and `refs/two.epub`, both pointing at the same fake file, to what `find_source_files` returns {src:tests/scripts/search/test_epub_optional.py:52-58}. It runs a full build with the hash embedder while capturing warnings {src:tests/scripts/search/test_epub_optional.py:58-60}. It asserts that exactly one captured line mentions epub, that the line holds `requirements-epub.txt`, that `notes/alpha.md` is in the index, and that `refs/one.epub` is not {src:tests/scripts/search/test_epub_optional.py:62-66}. The code logs the warning once per run and skips the file {src:scripts/search/build_index.py:477} {src:scripts/search/build_index.py:478} {src:scripts/search/build_index.py:479} {src:scripts/search/build_index.py:480}. |

## Diagram

None needed: the two tests share one setup and do not chain.

## Notes

- In the setup run for this page the whole class was skipped, because this machine's `python3` has no `chromadb` (run 2026-11-21: `OK (skipped=2)`). The claims above come from reading the test and `build_index.py`, not from a passing run. Set `TOLLGATE_TEST_PYTHON` to a Python with the libraries to run them {src:tests/scripts/search/support.py:34}.
- The second test does not check the summary counts, nor that the skipped epub is left out of the build state, so it does not prove the file is read again once the library is installed {src:tests/scripts/search/test_epub_optional.py:62-66}.
- The test counts any captured line that contains `epub` in lower case; a second, unrelated warning that mentions epub would also count {src:tests/scripts/search/test_epub_optional.py:62}.
- The test never runs with the library present, so the happy path of `chunk_epub` is not covered here (searched the file for a real epub, 2026-11-21).
- The test file header uses a different header layout than the other test files and gives no Date {src:tests/scripts/search/test_epub_optional.py:3}.
- Inputs reaching a path, command, network address or outbound text: only temp paths built from the throwaway home; no network call, no shell command. Writes to shared files: the vector store and state files are written inside the throwaway home only {src:tests/scripts/search/test_epub_optional.py:33} {src:tests/scripts/search/test_epub_optional.py:36}.
