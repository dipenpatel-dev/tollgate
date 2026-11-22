---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/state/test_state_tools.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/state/ticket_state_check.py, scripts/state/vault_query.py, scripts/state/retire_session_logs.py, scripts/state/backfill_session_logs.py, scripts/state/backup_index.sh, scripts/state/restore_index.sh, scripts/state/doc_drift_patrol.py, scripts/state/system_progress.py, scripts/state/vault_census.py, scripts/state/backfill_vault_frontmatter.py]         # source files under test, relative paths from repo root
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

This is the test file for the small state scripts: the ticket state checker, the ticket board query, the session log retirement pair, the index backup and restore pair, the doc drift patrol and the system progress report. A last group of tests checks that these tools, plus the two vault frontmatter tools, also find tickets that live under a prefix folder (`02-tickets/PROJ/PROJ-312`) as well as in a flat folder. Every test works on made-up data inside a throwaway home.

## Dependencies

**Depends on.**
- Standard library: `json`, `os`, `pathlib`, `subprocess`, `sys`, `unittest` {src:tests/scripts/state/test_state_tools.py:12-17}.
- The test helper that builds a throwaway home and its environment: [[throwaway_home]] / [throwaway_home](../../harness/throwaway_home.md) {src:tests/scripts/state/test_state_tools.py:26}.
- Scripts imported as modules: [[ticket_state_check]] / [ticket_state_check](../../../scripts/state/ticket_state_check.md), [[doc_drift_patrol]] / [doc_drift_patrol](../../../scripts/state/doc_drift_patrol.md), [[vault_census]] / [vault_census](../../../scripts/state/vault_census.md), [[backfill_vault_frontmatter]] / [backfill_vault_frontmatter](../../../scripts/state/backfill_vault_frontmatter.md) {src:tests/scripts/state/test_state_tools.py:27-30}.
- Scripts started as separate programs: `vault_query.py`, `retire_session_logs.py`, `backfill_session_logs.py`, `system_progress.py`, `ticket_state_check.py`, and the two shell scripts `backup_index.sh` and `restore_index.sh` {src:tests/scripts/state/test_state_tools.py:118} {src:tests/scripts/state/test_state_tools.py:133} {src:tests/scripts/state/test_state_tools.py:146} {src:tests/scripts/state/test_state_tools.py:217} {src:tests/scripts/state/test_state_tools.py:167}. Pages: [[vault_query]] / [vault_query](../../../scripts/state/vault_query.md), [[retire_session_logs]] / [retire_session_logs](../../../scripts/state/retire_session_logs.md), [[backfill_session_logs]] / [backfill_session_logs](../../../scripts/state/backfill_session_logs.md), [[system_progress]] / [system_progress](../../../scripts/state/system_progress.md), [[backup_index]] / [backup_index](../../../scripts/state/backup_index.md), [[restore_index]] / [restore_index](../../../scripts/state/restore_index.md).
- The gate rule constants, imported inside one test: [[gate_rules]] / [gate_rules](../../../hooks/gate_rules.md) {src:tests/scripts/state/test_state_tools.py:98}.
- Programs on the path: `bash` for the two shell scripts {src:tests/scripts/state/test_state_tools.py:167}; the shell scripts themselves call `cp`, `du`, `find` and `date` {src:scripts/state/backup_index.sh:73} {src:scripts/state/backup_index.sh:75} {src:scripts/state/backup_index.sh:59} {src:scripts/state/backup_index.sh:24}.

**Used by.** Searched with `git grep` for the file name outside `docs/` (2026-11-20).
- Product code: none.
- Automation: the state area runner finds it by the pattern `test_*.py` {src:tests/scripts/state/run.sh:6}. The end-to-end runner runs that area script {src:tests/system/run.sh:22-23}.
- Tests: no other test file imports it.

## Behavior

The file has four test classes. Each test makes a throwaway home, builds tickets or an index inside it, runs the tool, and checks the exit code, the output or the files {src:tests/scripts/state/test_state_tools.py:35-40}. The helper `run` adds `PYTHONDONTWRITEBYTECODE=1` and a 60 second limit to every child program {src:tests/scripts/state/test_state_tools.py:36-39}.

**TicketStateCheck (state checker).**
- A ticket in state `DEV_COMPLETE` with a block line and the three artifact files at their allowed status values gives exit 0 and the word `ok` {src:tests/scripts/state/test_state_tools.py:53-62}. This proves the artifact rules at {src:scripts/state/ticket_state_check.py:136-142} accept the values from {src:hooks/gate_rules.py:36-38}.
- A ticket in state `IN_DEV` with no `last_block_applied` line, a spec with no Status line and no design file gives exit 1 and the three codes `MISSING_FIELD`, `BAD_STATUS`, `MISSING_FILE` {src:tests/scripts/state/test_state_tools.py:64-74}. The code side is at {src:scripts/state/ticket_state_check.py:130-133} {src:scripts/state/ticket_state_check.py:105} {src:scripts/state/ticket_state_check.py:101}.
- An empty ticket folder gives exit 1, an unknown state value gives `UNKNOWN_STATE`, and two different Status lines give `BAD_STATUS` {src:tests/scripts/state/test_state_tools.py:76-87}. The checker's reading of two different values as malformed is at {src:hooks/gate_rules.py:147-148}.
- A Status line that is not the first content line gives only a warning, so exit stays 0 and `STATUS_NOT_FIRST` is printed {src:tests/scripts/state/test_state_tools.py:89-95} {src:scripts/state/ticket_state_check.py:127-128}.
- The checker's valid state list contains the four state names taken from the gate rules {src:tests/scripts/state/test_state_tools.py:97-100} {src:scripts/state/ticket_state_check.py:38-42}.
- With the loader variables removed the checker exits 2 and says `not set up`; an unknown ticket also exits 2 {src:tests/scripts/state/test_state_tools.py:102-110} {src:scripts/state/ticket_state_check.py:162-168}.

**VaultQueryAndSessionLogs.**
- `vault_query.py board` exits 0 on a vault holding one ticket {src:tests/scripts/state/test_state_tools.py:114-119}. With the loader variables removed it exits 2 with `not set up` {src:tests/scripts/state/test_state_tools.py:121-126} {src:scripts/state/vault_query.py:458-459}.
- `retire_session_logs.py` moves `T-020-session-1.md` into `archive/` and writes `T-020-archive-summary.md` {src:tests/scripts/state/test_state_tools.py:128-138}. The summary name is built at {src:scripts/state/retire_session_logs.py:124}.
- `backfill_session_logs.py` shows the list and, when the answer is `no`, prints `Aborted` and leaves the log in place; with `--yes` it archives the log of a ticket whose state file carries a terminal status {src:tests/scripts/state/test_state_tools.py:140-152} {src:scripts/state/backfill_session_logs.py:168-171}.

**IndexBackup.**
- Backup copies a fake index into a dated folder under `output/index-snapshots/full` and the cache file into `cache`; `--list` prints the date; a restore answered `no` exits 1 and leaves the changed file alone; a restore with `--yes` puts the saved content back {src:tests/scripts/state/test_state_tools.py:163-180}. The folder names come from {src:scripts/state/backup_index.sh:23-26}; the prompt is at {src:scripts/state/restore_index.sh:73-76}.
- Backup with no index prints `nothing to back up` and exits 1 {src:tests/scripts/state/test_state_tools.py:182-186} {src:scripts/state/backup_index.sh:60-61}.

**DriftAndProgress.**
- `refresh_doc` on a page with `update_needed: true` returns true, removes that line and the old date, and on a second call returns false {src:tests/scripts/state/test_state_tools.py:190-198} {src:scripts/state/doc_drift_patrol.py:106-116}. A key set to `None` is dropped from the block {src:scripts/state/doc_drift_patrol.py:96-98}.
- `sync_docs_to_vault` copies `docs/a.md` to `08-reference/repos/repo/a.md` in the throwaway vault {src:tests/scripts/state/test_state_tools.py:200-213} {src:scripts/state/doc_drift_patrol.py:119-127}.
- `system_progress.py --json` exits 0 and prints `layer_1` and a `bloat_pct` under `layer_3` {src:tests/scripts/state/test_state_tools.py:215-221} {src:scripts/state/system_progress.py:161-165}.
- `layer_1_checks` run on the repo root passes the six command existence checks (named `arch command exists` and so on) and the `DOCUMENTED and VALIDATED` check, which proves the check looks for the real `tg-` file names {src:tests/scripts/state/test_state_tools.py:223-228} {src:scripts/state/system_progress.py:65-72}.

**NestedTicketFolders (prefix folder layout).**
- The checker finds `02-tickets/PROJ/PROJ-312` and also a lower-case prefix folder `ex` for `EX-4`; the test only requires that the words `not found` are absent {src:tests/scripts/state/test_state_tools.py:238-250}. The folder lookup that makes this work matches the prefix without regard to case {src:scripts/core/paths.py:237-262}.
- `vault_query.py board` lists `T-312` under `[BACKLOG]`, `ticket T-312` shows `status: BACKLOG`, and the prefix folder `T` is not listed as a ticket {src:tests/scripts/state/test_state_tools.py:252-267}.
- `backfill_session_logs.py --yes` archives the log of a nested terminal ticket {src:tests/scripts/state/test_state_tools.py:269-276}.
- `vault_census.split_ticket_path` gives the same folder, depth, middle folders and name for the nested and the flat form of a state path; `expected_triple` gives `("ticket", "state", True)` for the nested state file and role `spec` for the nested spec; loose files and files outside the tickets folder are unchanged {src:tests/scripts/state/test_state_tools.py:278-292}. Code: {src:scripts/state/vault_census.py:317-330}.
- `backfill_vault_frontmatter.is_ticket_state_path` accepts the flat and nested state file, rejects the nested spec and an `archive/` state file, and `_ticket_parts` returns the folder `PROJ-312` with middle `("archive",)` {src:tests/scripts/state/test_state_tools.py:294-301} {src:scripts/state/backfill_vault_frontmatter.py:420-428} {src:scripts/state/backfill_vault_frontmatter.py:720-735}.
- In both the census and the backfill tool, the folder rows come from the layout: they list `01-system-map/platform-learning/` and `03-knowledge-base/decisions/`, hold no `System-notes` or `/sql/` prefix, and the only excluded prefix is `memory/` {src:tests/scripts/state/test_state_tools.py:303-309} {src:scripts/state/vault_census.py:78} {src:scripts/state/backfill_vault_frontmatter.py:96}.
- `system_progress.py` reads the memory folder of the layout: a 2048 byte `MEMORY.md` gives `memory_kb` of at least 2.0 {src:tests/scripts/state/test_state_tools.py:311-318} {src:scripts/state/system_progress.py:98}.

## Diagram

None: the file is a list of independent tests with the same setup (a throwaway home); there are no mock chains.

## Notes

- **Code and description.** The docstring says the file covers six tools: ticket state check, vault query, session log retirement, index backup and restore, doc drift patrol and system progress {src:tests/scripts/state/test_state_tools.py:2-3}. It also tests `vault_census`, `backfill_vault_frontmatter` and `backfill_session_logs` (the batch retirement, not the single one) {src:tests/scripts/state/test_state_tools.py:140-152} {src:tests/scripts/state/test_state_tools.py:278-309}. The header `Purpose` says the tests prove tools write only where they should {src:tests/scripts/state/test_state_tools.py:8-9}; no test searches the home for stray files, and the files named in assertions are the only ones looked at. The `Date:` header line is empty {src:tests/scripts/state/test_state_tools.py:6}.
- **Names that claim more than they check.** `test_backfill_needs_yes_and_reads_only_the_loader_folders` only checks the `Aborted` text and the archive result, not which folders were read {src:tests/scripts/state/test_state_tools.py:140-152}. `test_backup_and_restore_stay_inside_the_loader_folders` checks the snapshot folder and the restore result, not that nothing was written elsewhere {src:tests/scripts/state/test_state_tools.py:163-180}.
- **Weak assertions.** The board test checks only the exit code {src:tests/scripts/state/test_state_tools.py:118-119}. The two nested checker tests do not check the exit code {src:tests/scripts/state/test_state_tools.py:238-250}. The `ok` check is a substring test on the output {src:tests/scripts/state/test_state_tools.py:62}. The refresh test checks the old date is gone but not that today's date was written {src:tests/scripts/state/test_state_tools.py:197} {src:scripts/state/doc_drift_patrol.py:114}.
- **Machine and version dependence.** The system progress tests run against the real repo root passed with `--root`, read only, so the keys checked must exist in the current repo layout {src:tests/scripts/state/test_state_tools.py:217} {src:tests/scripts/state/test_state_tools.py:316}. The restore and backup tests need `bash`, `cp`, `du`, `find` on the path. The nested checker test relies on `gate_rules` being importable because `ticket_state_check` was imported first at module level {src:tests/scripts/state/test_state_tools.py:27} {src:tests/scripts/state/test_state_tools.py:98}. No Python 3.10 only syntax is used in the test file itself.
- **Inputs without a check.** Every path, key and answer given to a child program is built by the test from its own throwaway home; no input reaches a network address, and no command runs through a shell (the helper passes a list) {src:tests/scripts/state/test_state_tools.py:36-39}. The `--tree` path for the retire script is passed as given {src:tests/scripts/state/test_state_tools.py:135}.
- **Shared file writes.** None outside the throwaway home. Two tests change `os.environ` of the test process and put it back in a `finally` block {src:tests/scripts/state/test_state_tools.py:205-211}. Neither is atomic or locked, but the unittest runner runs tests one at a time.
