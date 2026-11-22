---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_ticket_flags.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/search/query_index.py", "scripts/search/vault_health.py", "scripts/search/build_index.py", "commands/tg-ticket.md"]         # source files under test, relative paths from repo root
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

This file tests the two search scripts that the ticket command calls: the query script (`query_index.py`) and the vault health script (`vault_health.py`). It checks that the command file only uses flags those scripts take, that the query output has the expected shape, that both scripts exit with the documented codes when nothing is set up or the index is missing, and that the link resolver accepts ticket IDs and placeholder text. It is one test class with nine test methods, run with the standard `unittest` runner.

## Dependencies

**Depends on.**
- Standard library: `json`, `pathlib`, `re`, `unittest`.
- Test helper `support` (`tests/scripts/search/support.py`): [[support]] (no doc yet). It provides `ROOT`, `run_script`, `script_env` and `throwaway_home`.
- Throwaway home factory (`tests/harness/throwaway_home.py`), imported through `support`: [[throwaway_home]] (no doc yet).
- Product code under test, none of it has a page yet: [[query_index]] (no doc yet), [[vault_health]] (no doc yet), [[build_index]] (no doc yet, used here only to build the index), and the ticket command file `commands/tg-ticket.md`: [[tg-ticket]] (no doc yet).
- The wrapper named in the command's call text, `tg-search`: [[tg-search]] and [tg-search](../../../scripts/search/tg-search.md). The test only reads that text and never runs the wrapper.
- Overview of the folder: [search scripts](../../../scripts/search.md).
- Packages `chromadb` and `PyYAML`, probed by a try-import in `support` {src:tests/scripts/search/support.py:27-32}. Environment: `TOLLGATE_EMBEDDER` is forced to `hash` for every script run {src:tests/scripts/search/support.py:39}, and `TOLLGATE_TEST_PYTHON` picks the interpreter in the runner {src:tests/scripts/search/run.sh:9}.

**Used by.** No product code. The runner `tests/scripts/search/run.sh` finds it with `unittest discover -p 'test_*.py'` {src:tests/scripts/search/run.sh:9}. Searched 2026-11-19: the whole worktree except `.git`, `docs/`, caches and virtual environments for the file name and for `scripts/search/run.sh`; only the file's own header matched. The CI workflow folder `.github` has no line naming `scripts/search` or `TOLLGATE_TEST_PYTHON`, so CI does not run this file.

## Behavior

The class is skipped unless `chromadb` and `PyYAML` import {src:tests/scripts/search/test_ticket_flags.py:20}. Every test gets a throwaway home and a small synthetic vault {src:tests/scripts/search/test_ticket_flags.py:23} {src:tests/scripts/search/test_ticket_flags.py:25}, and the scripts see that vault through `TOLLGATE_KNOWLEDGE` {src:tests/scripts/search/test_ticket_flags.py:26}. The vault has `notes/alpha.md`, `notes/beta.md` and one ticket state file {src:tests/scripts/search/support.py:73} {src:tests/scripts/search/support.py:76} {src:tests/scripts/search/support.py:79}. The helper `build()` runs `build_index.py --full --embedder hash` and requires exit code 0 {src:tests/scripts/search/test_ticket_flags.py:32}.

**Test cases**

1. `test_command_file_uses_only_flags_the_scripts_accept`: reads `commands/tg-ticket.md` {src:tests/scripts/search/test_ticket_flags.py:35}, collects every `tg-search query` and `tg-search health` call up to the end of the line {src:tests/scripts/search/test_ticket_flags.py:37}, requires at least one call per tool {src:tests/scripts/search/test_ticket_flags.py:38}, and requires the flags in each call to be a subset of `{"--top"}` {src:tests/scripts/search/test_ticket_flags.py:40}. The command file holds one query call and one health call {src:commands/tg-ticket.md:69} {src:commands/tg-ticket.md:80}. The scripts do take `--top` {src:scripts/search/query_index.py:41} {src:scripts/search/vault_health.py:227}. The test proves the command file has no other flag. It does not read the scripts' own argument parsers, so it would still pass if a script dropped `--top`.
2. `test_query_index_top`: builds the index, runs the query with `--top 8`, and requires exit 0, between 1 and 8 rows, and the keys `file`, `heading`, `excerpt`, `score`, `tier`, `tier_label` and `collection` on the first row {src:tests/scripts/search/test_ticket_flags.py:44} {src:tests/scripts/search/test_ticket_flags.py:47} {src:tests/scripts/search/test_ticket_flags.py:48}. Those are the keys the script copies into its output {src:scripts/search/query_index.py:70}. A second run with `--top 1` must print exactly one `"file"` key {src:tests/scripts/search/test_ticket_flags.py:49}. The limit comes from the router, which cuts the ambiguous result list to `top` {src:scripts/search/router.py:251} {src:scripts/search/router.py:199}, and the script sends the query as ambiguous when no intent is given {src:scripts/search/query_index.py:61}. Rows below the score floor are dropped first {src:scripts/search/query_index.py:71}, so a non-empty result needs the hash embedder to score the notes above that floor. This was not run here because `chromadb` is missing on this machine {unverified}.
3. `test_query_index_other_flags`: with `--top 3 --min-score 0.0 --intent decide` the output must be a non-empty list {src:tests/scripts/search/test_ticket_flags.py:53} {src:tests/scripts/search/test_ticket_flags.py:56}. With `--situation support_triage` the test only checks exit 0 {src:tests/scripts/search/test_ticket_flags.py:57} {src:tests/scripts/search/test_ticket_flags.py:58}. With `--min-score 0.99` the query `retry` must return `[]` {src:tests/scripts/search/test_ticket_flags.py:59} {src:tests/scripts/search/test_ticket_flags.py:60}; the floor is applied in the script {src:scripts/search/query_index.py:60} {src:scripts/search/query_index.py:71}. The situation name is mapped in `routing.yaml` {src:scripts/search/routing.yaml:29}.
4. `test_query_index_not_set_up`: with no index built, the script must exit 2 and print `not set up` {src:tests/scripts/search/test_ticket_flags.py:64}. The script prints that when the index folder is missing or holds no collection folder {src:scripts/search/query_index.py:54} {src:scripts/search/query_index.py:55} {src:scripts/search/query_index.py:56}.
5. `test_vault_health_report_and_exit_code`: after a build, the report must contain the title, `Dead links: 1 missing targets` and `2x  [[missing-note-one]]`, and the script must exit 0 {src:tests/scripts/search/test_ticket_flags.py:69} {src:tests/scripts/search/test_ticket_flags.py:70} {src:tests/scripts/search/test_ticket_flags.py:71} {src:tests/scripts/search/test_ticket_flags.py:72}. The dead link is written twice in `beta.md` {src:tests/scripts/search/support.py:78}. The script counts distinct missing targets and prints the reference count {src:scripts/search/vault_health.py:184} {src:scripts/search/vault_health.py:213} {src:scripts/search/vault_health.py:215}, and exits 0 only when links are not degraded, the index is fresh and the index store exists {src:scripts/search/vault_health.py:243}.
6. `test_vault_health_json`: with `--json`, `dead_links.total_missing` must be 1 and `index.chroma_exists` true {src:tests/scripts/search/test_ticket_flags.py:78} {src:tests/scripts/search/test_ticket_flags.py:79}. The script prints those two keys {src:scripts/search/vault_health.py:240} {src:scripts/search/vault_health.py:184} {src:scripts/search/vault_health.py:196}.
7. `test_vault_health_flags_a_missing_index`: with no build, exit code 1 and the text `search unavailable` {src:tests/scripts/search/test_ticket_flags.py:83} {src:tests/scripts/search/test_ticket_flags.py:84}. The script adds that line when the store file is missing {src:scripts/search/vault_health.py:219} {src:scripts/search/vault_health.py:220}, and the same missing store forces exit 1 {src:scripts/search/vault_health.py:243}.
8. `test_vault_health_not_set_up`: with `TOLLGATE_KNOWLEDGE` removed, exit 2 and `not set up` {src:tests/scripts/search/test_ticket_flags.py:88} {src:tests/scripts/search/test_ticket_flags.py:90}. The loader raises `NotSetUp` for the vault name when the variable and the paths file give nothing {src:scripts/core/paths.py:100}, and the script turns that into exit 2 {src:scripts/search/vault_health.py:231} {src:scripts/search/vault_health.py:232} {src:scripts/search/vault_health.py:233}.
9. `test_ticket_links_and_placeholders_resolve`: imports `vault_health` in the test process {src:tests/scripts/search/test_ticket_flags.py:93} and calls `_resolve_wikilink` with empty lookup tables for the first four targets {src:tests/scripts/search/test_ticket_flags.py:94} {src:tests/scripts/search/test_ticket_flags.py:97}. `T-009` must resolve (ticket ID rule {src:scripts/search/vault_health.py:136}), `path/to/file` must resolve (listed placeholder {src:scripts/search/vault_health.py:98} {src:scripts/search/vault_health.py:34}), `two words` must resolve (a space is not a valid link target {src:scripts/search/vault_health.py:120}), and `nothing-here` must not resolve {src:tests/scripts/search/test_ticket_flags.py:97} {src:scripts/search/vault_health.py:162}. A fifth call passes `nothing-here` again, this time with a file set that holds the string `nothing-here`, and it must resolve {src:tests/scripts/search/test_ticket_flags.py:98}. That works through the full path rule, which looks for the vault folder joined with the target in the file set {src:scripts/search/vault_health.py:146}. In the test process the vault folder is still the start value `Path(".")`, because `_setup` is not called {src:scripts/search/vault_health.py:26} {src:scripts/search/vault_health.py:53}, so the joined path is just `nothing-here`. The pair of calls shows that a name found in the file set resolves and one that is not found does not.

## Diagram

None: this is one class with a throwaway home and a small vault, and every test builds its own state, so there is no fixture chain worth drawing.

## Notes

**Tests that prove less than they seem to.** The old last line of the ticket links test, an assertion on a set literal, is gone; the last line is now a real check {src:tests/scripts/search/test_ticket_flags.py:98}. That check passes only because the vault folder is `Path(".")` in the test process {src:scripts/search/vault_health.py:26}, so it would stop passing if the test called the script's setup first or if the module's start value changed. The `--situation support_triage` call only checks the exit code {src:tests/scripts/search/test_ticket_flags.py:58}. A wrong or unknown situation name also exits 0, because the classifier falls back to ambiguous {src:scripts/search/intent.py:42}, so a typo in the situation map would not fail this case.

**Skips.** The class decorator skips all nine tests when `chromadb` or `PyYAML` is missing {src:tests/scripts/search/test_ticket_flags.py:20}, including the five that never build the index: the command file check, the not set up check for the query script, the missing index check for the health script, the not set up check for the health script, and the link resolver check. Running the file with the default `python3` on this machine (3.12.7, no `chromadb`) on 2026-11-19 gave 9 skipped and 0 run.

**Description versus code.** The `make_vault` docstring says the vault holds "one conversation note with a dead link" {src:tests/scripts/search/support.py:71}. The code writes no conversation note: the dead link sits in `notes/beta.md` {src:tests/scripts/search/support.py:76} {src:tests/scripts/search/support.py:78}. The test name `test_command_file_uses_only_flags_the_scripts_accept` also promises more than the check does (see case 1).

**Machine path dependence.** `vault_health.py` skips a note when any part of its absolute path starts with a dot {src:scripts/search/vault_health.py:69}, and when any part is named `worktrees` or `.git` {src:scripts/search/vault_health.py:27} {src:scripts/search/vault_health.py:67}. The throwaway home is made with `tempfile.mkdtemp` {src:tests/harness/throwaway_home.py:51}, so on a machine whose temp folder sits under a dotted or `worktrees` folder every note is skipped, the dead link count is 0 and the report and JSON tests fail. The health script also reads the store file name `chroma.sqlite3` {src:scripts/search/vault_health.py:194}, so a `chromadb` version that renames that file would break the exit code test. The index age test uses a 25 hour limit {src:scripts/search/vault_health.py:28}, which a fresh build never reaches.

**Python version dependence.** `vault_health.py` has no `from __future__ import annotations` and writes `list[Path]`, `set[str]` and `dict[str, str]` in signatures that Python evaluates when the function is defined {src:scripts/search/vault_health.py:63} {src:scripts/search/vault_health.py:75} {src:scripts/search/vault_health.py:86}. Those need Python 3.9 or newer, which the 3.12 minimum covers. Below 3.9 the four tests that run the health script and the in-process link test (which imports the module) would fail. `query_index.py` uses the future import {src:scripts/search/query_index.py:17}. The test file itself has no version specific syntax.

**Inputs without a check.** The inputs are fixed strings in the test and paths built from the repo root {src:tests/scripts/search/support.py:18}. Scripts are started with an argument list, so no shell parses them {src:tests/scripts/search/support.py:46}. Nothing reaches a network address or outbound text.

**Writes to shared files.** None. All writes go to a temp folder made per test {src:tests/harness/throwaway_home.py:51} and removed on exit {src:tests/harness/throwaway_home.py:59}, so two tests never write the same file. The in-process import in case 9 does not call the script's setup function, so it does not change the module's folder state.
