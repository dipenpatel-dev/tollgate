---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_index_health.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/search/check_index_health.py", "scripts/search/build_index.py"]         # source files under test, relative paths from repo root
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

This file tests the index health check in two ways: the search window it uses must stay wide, and two probe questions about known documents must pass against an index built from the synthetic corpus. It is the smaller of two places that test the health check; the other is [[test_internals]] and [test_internals](test_internals.md).

## Dependencies

**Depends on.**
- Standard library: `json`, `pathlib`, `unittest` {src:tests/scripts/search/test_index_health.py:10-12}. Helper [[support]] and [support](support.md) for `in_env`, `script_env`, `throwaway_home`, `write`, `HAVE_STORE`, `NOTE` and `CORPUS` {src:tests/scripts/search/test_index_health.py:14-15}.
- Code under test: [[check_index_health]] and [check_index_health](../../../scripts/search/check_index_health.md) (`TOP_K`, `run_checks`) {src:tests/scripts/search/test_index_health.py:21-22} {src:tests/scripts/search/test_index_health.py:31-34}, and [[build_index]] and [build_index](../../../scripts/search/build_index.md) (`build`) {src:tests/scripts/search/test_index_health.py:30-33}.
- Data: the corpus folder `tests/rag_eval/corpus` {src:tests/scripts/search/test_index_health.py:29}. The probes look for file names containing `null-encounter-date` and `idempotent-append` {src:tests/scripts/search/test_index_health.py:35-36}; the corpus holds files with those names (`03-knowledge-base/decisions/2026-01-10-null-encounter-date.md` and `03-knowledge-base/patterns/2026-03-01-idempotent-append.md`, listed 2026-11-20).
- Packages `chromadb` and PyYAML for the second class {src:tests/scripts/search/test_index_health.py:25}.

**Used by.** Searched with `git grep` for `test_index_health` outside `docs/` on 2026-11-20: nothing names it; the folder runner [[run]] and [run](run.md) finds it by pattern {src:tests/scripts/search/run.sh:9}.

## Behavior

- `WindowFloor.test_top_k_is_wide_enough`: imports the check and asserts `TOP_K >= 60` {src:tests/scripts/search/test_index_health.py:21-22}. The constant is 60 today {src:scripts/search/check_index_health.py:29}. This class has no skip marker, and the module's top-level imports do not need `chromadb` (they are `argparse`, `json`, `os`, `pathlib`, `sys`, `datetime`, `config`, `embedder`, `refstore`) {src:scripts/search/check_index_health.py:16-27}, so it runs on any Python that has the repo scripts on the path.
- `ProbesOnSyntheticIndex.test_probes_pass_on_the_corpus`: in a throwaway home with `TOLLGATE_KNOWLEDGE` set to the corpus, builds a full hash-embedder index, then runs two probes, `decision` (query "missing encounter date decision", file name contains `null-encounter-date`) and `pattern` (query "avoid duplicate rows on retry", file name contains `idempotent-append`) {src:tests/scripts/search/test_index_health.py:28-37}. It asserts the report's `passed` is true and that the report holds exactly 2 checks {src:tests/scripts/search/test_index_health.py:38-39}.
- How the code decides: for each probe it queries each collection with up to `TOP_K` results, keeps those whose file name contains the probe text (case-insensitive), and sorts by score {src:scripts/search/check_index_health.py:49-58}. A probe passes when at least one result was found and the best score is at least the embedder's floor {src:scripts/search/check_index_health.py:84-85}. The report passes only if every probe passes {src:scripts/search/check_index_health.py:89}.

## Diagram

None: a single build and a single call, with no mock chain.

## Notes

- Code and description: the test docstring says a healthy passage "ranked 11th overall must not be hidden by a narrow window" {src:tests/scripts/search/test_index_health.py:20}, and the code comment says the check "filters by file after the global top-K" {src:scripts/search/check_index_health.py:29}. The code takes the top `TOP_K` results of each collection on its own, not of all collections together {src:scripts/search/check_index_health.py:49-53}. So the window is per collection, not global. The header says the three named documents are "replaced by synthetic probes" {src:tests/scripts/search/test_index_health.py:3}; the two probes are named for corpus files, which is true.
- The header `date:` field is empty {src:tests/scripts/search/test_index_health.py:5}.
- Test quality: the floor test passes for any value of 60 or more, so it cannot detect a window that is wide but wrong in another way. The probe test uses `file_contains` as a substring, so `null-encounter-date` also matches the revised decision `2026-06-18-null-encounter-date-revised.md`; the test would pass if either file ranks, which is weaker than "the named document". It does not test the failing case; failing probes are tested in [[test_internals]] (`test_health_check_probes`) {src:tests/scripts/search/test_internals.py:158-160}.
- Unused imports: `pathlib` {src:tests/scripts/search/test_index_health.py:11} and `write` {src:tests/scripts/search/test_index_health.py:15} are imported but no line in the file uses them (searched the file 2026-11-20).
- The `TOP_K` floor is also asserted in `test_internals.py` {src:tests/scripts/search/test_internals.py:146-148}, so the same check runs twice under discovery.
- No test here depends on a machine path or the Python version; the corpus path comes from the repo root {src:tests/scripts/search/support.py:20}.
- Inputs without a check: none in this file; the probes are literals. The code under test reads probe text from a JSON file and uses it as a search string and a file-name filter with no check beyond requiring two non-empty keys {src:scripts/search/check_index_health.py:43}.
- Shared-file writes: this test writes no report file; it calls `run_checks` directly, and `run_checks` itself writes nothing {src:scripts/search/check_index_health.py:62-90}. The build writes the index into a temp home, one writer, no lock.
