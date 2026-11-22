---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_ground.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/search/ground.py", "scripts/search/router.py", "scripts/search/intent.py"]         # source files under test, relative paths from repo root
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

This file tests `ground.py`, the small script that answers "what do the notes say about this" for a skill. The script prints one state line (ok, partial, empty or unavailable), a collections line, an optional detail line, then passages. The tests cover each state, the wrong-argument case, reading the query from standard input, and how a skill name maps to a search intent.

## Dependencies

**Depends on.**
- Standard library: `pathlib`, `unittest`, `unittest.mock` {src:tests/scripts/search/test_ground.py:11-13}. Helper [[support]] and [support](support.md) for `in_env`, `run_script`, `script_env`, `throwaway_home`, `make_vault`, `HAVE_STORE` and `NOTE` {src:tests/scripts/search/test_ground.py:15-16}.
- Code under test: [[ground]] and [ground](../../../scripts/search/ground.md) {src:tests/scripts/search/test_ground.py:39}, [[router]] and [router](../../../scripts/search/router.md) (`_query_one` and `query_all` are patched) {src:tests/scripts/search/test_ground.py:64} {src:tests/scripts/search/test_ground.py:90}, [[intent]] and [intent](../../../scripts/search/intent.md) (`map_skill`) {src:tests/scripts/search/test_ground.py:113}, and [[build_index]] and [build_index](../../../scripts/search/build_index.md), started as a subprocess to make the index {src:tests/scripts/search/test_ground.py:35}.
- Packages `chromadb` and PyYAML; the class is skipped without them {src:tests/scripts/search/test_ground.py:23}.

**Used by.** Searched with `git grep` for `test_ground` outside `docs/` on 2026-11-20: nothing names it; the folder runner [[run]] and [run](run.md) finds it by pattern {src:tests/scripts/search/run.sh:9}.

## Behavior

**Setup.** Every test in `GroundStates` gets a fresh throwaway home with the synthetic vault written at `<home>/vault`, and `self.env` from `script_env` {src:tests/scripts/search/test_ground.py:26-29}. The throwaway env already points `TOLLGATE_KNOWLEDGE` at that same folder {src:tests/harness/throwaway_home.py:36}. `build()` runs `build_index.py --full --embedder hash` as a subprocess and requires exit code 0 {src:tests/scripts/search/test_ground.py:34-36}. `first_lines` returns the first three output lines {src:tests/scripts/search/test_ground.py:19-20}.

**Tests.**
- `test_unavailable_when_no_index`: with no index built, `ground.py x-dev "retry limit"` exits 0 and prints `STATE: unavailable`, then a line starting `COLLECTIONS:`, then one starting `DETAIL:` {src:tests/scripts/search/test_ground.py:39-44}. The script returns "unavailable" when the index folder is missing and `main` prints the detail whenever it is non-empty {src:scripts/search/ground.py:40-41} {src:scripts/search/ground.py:74-75}.
- `test_ok_prints_passages_with_file_and_heading`: after a build, the query "nightly load retries twice then pages the owner" prints `STATE: ok`, a collections line matching `vault=<n> tickets=<n> references=`, and a passage line starting `[1] notes/alpha.md | ` {src:tests/scripts/search/test_ground.py:48-52}. The script prints passages as `[n] file | heading | collection | score` {src:scripts/search/ground.py:76-77}.
- `test_empty_when_nothing_matches`: the query "pizza topping weather forecast cricket" with skill `x-qa` prints `STATE: empty` and some `DETAIL:` text {src:tests/scripts/search/test_ground.py:56-58}. The state is "empty" when no result clears the embedder's score floor {src:scripts/search/ground.py:53} {src:scripts/search/ground.py:56-57}.
- `test_partial_when_one_collection_fails`: `router._query_one` is replaced by a function that returns an error for the `tickets` collection and calls the real one otherwise; calling `ground.ground` in-process gives state `partial`, a detail that contains `tickets`, and non-empty results {src:tests/scripts/search/test_ground.py:64-75}. The script adds failed names to `failed` and returns "partial" when some, but not all, collections failed {src:scripts/search/router.py:235-239} {src:scripts/search/ground.py:58-59}.
- `test_unavailable_when_every_collection_fails`: every `_query_one` returns an error; state is `unavailable`, results are an empty list, and the detail contains `failed` {src:tests/scripts/search/test_ground.py:82-85}. This matches the "every collection failed" branch {src:scripts/search/ground.py:54-55}.
- `test_unavailable_when_the_search_package_is_missing`: after a build, `router.query_all` is patched to raise `ImportError`; the state is `unavailable` {src:tests/scripts/search/test_ground.py:90-93}. The script wraps the query in a broad `except Exception` that returns "unavailable" {src:scripts/search/ground.py:49-50}.
- `test_wrong_argument_count_still_prints_a_state`: with one argument the script exits 0 and prints `STATE: unavailable` {src:tests/scripts/search/test_ground.py:96-98}, matching the length check {src:scripts/search/ground.py:65-69}.
- `test_q10_dash_reads_the_query_from_stdin`: `ground.ground` is replaced by a recorder, standard input is replaced by text with an apostrophe, `$(x)`, backticks and two lines, and `print` is silenced; `main(["x-dev", "-"])` returns 0 and the recorder saw the one-line query ``it's a $(x) `y` second line`` {src:tests/scripts/search/test_ground.py:103-110}. The script joins the words of standard input when the second argument is `-` {src:scripts/search/ground.py:70}.
- `test_skill_name_picks_an_intent`: `x-dev` maps to `build`, `x-qa` to `verify`, and an unknown suffix to `None` {src:tests/scripts/search/test_ground.py:114-116}. `map_skill` looks up the part after the last dash in the routing file's `skill_map` and returns it only if it is a valid intent {src:scripts/search/intent.py:55-58}.

## Diagram

None: the tests patch one function at a time, so there is no chain of mocks to draw.

## Notes

- Code and description: the header says the script prints "one of four states, then a collections line, an optional detail line, then passages" {src:tests/scripts/search/test_ground.py:3}. The code agrees: four states {src:scripts/search/ground.py:39} {src:scripts/search/ground.py:57} {src:scripts/search/ground.py:59} {src:scripts/search/ground.py:60}, and the detail line is printed only when non-empty {src:scripts/search/ground.py:74-75}. The header's own version fields disagree: `version: 1.0.0` {src:tests/scripts/search/test_ground.py:6} but the change log lists 1.1.0 {src:tests/scripts/search/test_ground.py:8}. The `date:` field is empty {src:tests/scripts/search/test_ground.py:5}. The label "Q-10" {src:tests/scripts/search/test_ground.py:8} is not explained in the file.
- Weak or narrow assertions: `test_unavailable_when_the_search_package_is_missing` reads `detail` but never asserts on it {src:tests/scripts/search/test_ground.py:92-93}, and the failure it simulates is a patched `query_all` after a real index exists, not a missing package at import time (the import path at the top of `ground` is not exercised) {src:scripts/search/ground.py:34-39}. `test_q10...` asserts only the cleaned query, not the printed output {src:tests/scripts/search/test_ground.py:110}, and the shell-looking characters in its input are safe only because `ground` never passes the query to a shell (it passes it to `router.query_all`) {src:scripts/search/ground.py:47-48}.
- `test_ok_prints_passages...` depends on the embedder scoring the alpha note above its floor with the hash embedder and on the synthetic text in `make_vault` {src:tests/scripts/search/support.py:73-75}; changing that text could break it.
- `GroundStates` is skipped when the store packages are missing {src:tests/scripts/search/test_ground.py:23}; `test_wrong_argument_count...`, `test_q10...` and `test_skill_name...` need no index but are skipped with the class.
- No test depends on a machine path or the Python version; everything is under a temp folder from `throwaway_home`.
- Inputs without a check: the query text reaches the embedder and the index lookup with no length or content check {src:scripts/search/ground.py:70-71}; the skill name is used only as a lookup key {src:scripts/search/intent.py:56-57}. The tests add no new path, command or network input.
- Shared-file writes: the build writes the index in the temp home; one writer per test, no lock, not atomic.
- Not tested: three or more arguments; the case where the index folder exists but holds no collection folder; the score floor value itself.
