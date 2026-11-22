---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_reference.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/search/reference_add.py", "scripts/search/reference_query.py", "scripts/search/refstore.py", "scripts/search/build_index.py"]         # source files under test, relative paths from repo root
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

This test file checks the reference store: the small side collection where a person adds their own documents with tags, and the query script that finds passages in it. It covers adding with tags, matching by situation, the "no match" and "not set up" answers, replacing a document that is added twice, surviving an index rebuild, and making no network calls. Every document used is made up inside the test file.

## Dependencies

**Depends on.**
- Standard library: `pathlib`, `unittest` {src:tests/scripts/search/test_reference.py:10-11}.
- The shared test helper [[support]] and [support](support.md) for `in_env`, `run_script`, `script_env`, `throwaway_home` and `write` {src:tests/scripts/search/test_reference.py:13-14}. `HAVE_STORE` comes from the same helper and is true only when `chromadb` and `yaml` import {src:tests/scripts/search/support.py:27-32}.
- The throwaway home maker [[throwaway_home]] and [throwaway_home](../../harness/throwaway_home.md), which sets `TOLLGATE_PATHS` inside the fake home {src:tests/harness/throwaway_home.py:41}.
- The network guard [[connector_helpers]] and [connector_helpers](../../harness/connector_helpers.md), imported inside one test {src:tests/scripts/search/test_reference.py:116}.
- Code under test, run as child processes: [[reference_add]] and [reference_add](../../../scripts/search/reference_add.md), [[reference_query]] and [reference_query](../../../scripts/search/reference_query.md) {src:tests/scripts/search/test_reference.py:36} {src:tests/scripts/search/test_reference.py:40}.
- Code under test, imported in the test process: [[refstore]] and [refstore](../../../scripts/search/refstore.md) {src:tests/scripts/search/test_reference.py:91}, [[build_index]] and [build_index](../../../scripts/search/build_index.md) {src:tests/scripts/search/test_reference.py:108}.
- Environment: `TOLLGATE_EMBEDDER=hash` is forced for every child process {src:tests/scripts/search/support.py:37-39}.

**Used by.** Product code: none (searched `git grep` for `test_reference` outside `docs/` on 2026-11-20, nothing but this file names it). Tests and runners: it is found by the `test_*.py` pattern of [[run]] and [run](run.md) {src:tests/scripts/search/run.sh:9}, which the system runner calls for the `search` area {src:tests/system/run.sh:22-23}.

## Behavior

One test class, `ReferenceStore`, is skipped as a whole when `chromadb` or `yaml` is missing {src:tests/scripts/search/test_reference.py:22-23}.

**Setup and teardown.** Each test makes a throwaway home, builds a child-process environment from it, and writes two Markdown files under `docs-to-add/`: a "design" note and a "security" note {src:tests/scripts/search/test_reference.py:24-30}. Teardown deletes the home {src:tests/scripts/search/test_reference.py:32-33}. The helper `add` passes each tag as a `--tag` flag {src:tests/scripts/search/test_reference.py:38-40}.

**Test cases (what each one proves).**

1. `test_not_set_up_without_a_store`: with nothing added, a query exits 2 and prints exactly `not set up` {src:tests/scripts/search/test_reference.py:42-45}. The script does this when `open_references` returns no collection {src:scripts/search/reference_query.py:37-41} and `main` turns that into exit 2 {src:scripts/search/reference_query.py:67-69}. A missing path setup raises `NotSetUp` and gives the same text and exit code {src:scripts/search/reference_query.py:61-63}, so the test cannot tell the two causes apart.
2. `test_add_then_match_prints_source_and_tag`: adding the `design` folder with tags `design` and `patterns` prints `tags: design,patterns`, and a query then prints `source: design/seams.md` and `tag: design,patterns` {src:tests/scripts/search/test_reference.py:47-54}. The key starts with the folder name {src:scripts/search/reference_add.py:45}, the tags are cleaned and sorted {src:scripts/search/refstore.py:64-66}, and the output line is built here {src:scripts/search/reference_query.py:75}.
3. `test_no_match_exits_zero`: a query of unrelated words prints `no match` and exits 0 {src:tests/scripts/search/test_reference.py:56-60}, matching the code path for an empty result {src:scripts/search/reference_query.py:70-72}. Whether the words fall under the score floor depends on the hash embedder, whose floor is 0.1 {src:scripts/search/embedder.py:45}.
4. `test_situation_maps_to_tags_from_references_yaml`: the test writes `references.yaml` next to the paths file, mapping `dev_implement` to `security` and `spec_define` to `design` {src:tests/scripts/search/test_reference.py:62-66}. A `dev_implement` query finds `secrets.md` and not `seams.md` {src:tests/scripts/search/test_reference.py:67-69}. A design-flavoured query under `dev_implement` finds nothing, and the same query under `spec_define` finds `seams.md` {src:tests/scripts/search/test_reference.py:70-73}. The filter keeps only chunks that carry at least one wanted tag {src:scripts/search/router.py:242-245}, and the file sits next to the paths file {src:scripts/search/refstore.py:24-29}.
5. `test_missing_map_searches_all_references`: with no map file and the situation `qa_review`, the security note is still found {src:tests/scripts/search/test_reference.py:75-79}. A missing situation gives no tags, and no tags means no filter {src:scripts/search/reference_query.py:44} {src:scripts/search/reference_query.py:46-47}.
6. `test_stakes_changes_the_floor`: runs a `low` and a `high` query and asserts only that both exit 0 {src:tests/scripts/search/test_reference.py:81-86}. The intended effect is a shift of +0.1 for low and -0.05 for high {src:scripts/search/config.py:130} added to the floor {src:scripts/search/reference_query.py:45}. See Notes: this test cannot detect a wrong shift.
7. `test_re_adding_replaces_instead_of_duplicating`: adding the same folder twice leaves one chunk in the collection {src:tests/scripts/search/test_reference.py:88-93}. The add step deletes the old chunks of a file before inserting {src:scripts/search/build_index.py:383}.
8. `test_a_single_file_can_be_added`: adding one file with the tag `Security Basics` succeeds and the output contains `security-basics` {src:tests/scripts/search/test_reference.py:95-98}. The tag is lower-cased and spaces become hyphens {src:scripts/search/refstore.py:60-61}.
9. `test_bad_path_and_empty_folder`: a missing path and an empty folder both exit 1 {src:tests/scripts/search/test_reference.py:100-104}. The first is the `path not found` branch {src:scripts/search/reference_add.py:77-79}, the second is the `nothing to add` branch {src:scripts/search/reference_add.py:87-89}.
10. `test_rebuild_keeps_added_references`: after a full rebuild with the hash embedder the chunk count is unchanged {src:tests/scripts/search/test_reference.py:106-113}. A full build deletes only chunks whose origin is `build` {src:scripts/search/build_index.py:454-457}, while added chunks carry origin `add` {src:scripts/search/reference_add.py:66}.
11. `test_no_network_in_add_and_query`: `reference_add.add` and `reference_query.search` run inside `assert_no_network`, and the search returns something {src:tests/scripts/search/test_reference.py:115-123}. The guard blocks `connect`, `connect_ex` and `getaddrinfo` and fails if any is called {src:tests/harness/connector_helpers.py:67-89}.
12. `test_situation_file_parser`: `a: [x, y]` and `b: z   # note` parse; a commented line and an empty list `d: []` are dropped; a missing file gives `{}` {src:tests/scripts/search/test_reference.py:125-130}. The parser strips the comment at the first ` #` {src:scripts/search/refstore.py:50}, drops names with no tags {src:scripts/search/refstore.py:55-56}, and returns `{}` when the file cannot be read {src:scripts/search/refstore.py:44-47}.

## Diagram

None: the file has one test class with independent tests and a simple setup, so no fixture chain needs a picture.

## Notes

- Code and description: the description says the file covers "no network" and "not set up" {src:tests/scripts/search/test_reference.py:3}. Both are covered. The only mismatch is the test name `test_stakes_changes_the_floor` {src:tests/scripts/search/test_reference.py:81}: it asserts only exit codes {src:tests/scripts/search/test_reference.py:85-86}, so a stakes shift that did nothing would still pass.
- A test that cannot fail on the thing it names: the stakes test above. It passes if both queries merely run.
- Fragile expectations: `test_no_match_exits_zero` and the `no match` line in test 4 rely on the hash embedder scoring those words under 0.1 {src:tests/scripts/search/test_reference.py:58-60} {src:tests/scripts/search/test_reference.py:70-71}. `test_re_adding_replaces_instead_of_duplicating` expects exactly one chunk {src:tests/scripts/search/test_reference.py:93}, which holds only while the design note stays one chunk under the chunker {src:scripts/search/config.py:70}.
- Machine and Python dependence: no machine path is hard-coded; the home is made by `tempfile` {src:tests/harness/throwaway_home.py:51}. The child scripts run with `sys.executable` {src:tests/scripts/search/support.py:46}. The tests need `chromadb` and `yaml` or they skip {src:tests/scripts/search/test_reference.py:22}. No Python-version feature is used beyond the scripts' own `from __future__ import annotations` {src:scripts/search/reference_add.py:16}.
- Inputs reaching a file path, shell command, network address or outbound text without a check: the test passes only paths it built itself to the scripts {src:tests/scripts/search/test_reference.py:40}. The code under test passes the `PATH` argument straight to `pathlib` with `expanduser` and no further check {src:scripts/search/reference_add.py:76}. The `--query` text goes to the embedder and prints no outbound text beyond local stdout. No network address is built from any input.
- Writes to shared files: none by the test. It writes only inside the throwaway home and removes it {src:tests/scripts/search/test_reference.py:32-33}. The scripts under test write `add_state.json` and the marker file with plain `write_text`, non-atomic, and nothing stops two writers at once {src:scripts/search/build_index.py:360-361} {src:scripts/search/embedder.py:151-153}.
