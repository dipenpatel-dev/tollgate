---
doc_type: config
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: config         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/fixtures/tickets/vault_board/02-tickets/board-mappings/board-a.yaml"    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
format: "yaml"         # yaml | toml | json | env
governs: "test data: board map for the vault_board fixture vault, read by vault_query.py"        # what component or behavior this config controls
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

Board map for the small fixture vault `tests/fixtures/tickets/vault_board/`. It tells the ticket board tool that keys starting with `EX` or `OT` come from an outside board named `board-a`, and how that board's status words map to Tollgate statuses. It sits at the exact place the tool looks: a `board-mappings` folder inside the `02-tickets` folder of the vault {src:scripts/state/vault_query.py:37} {src:scripts/state/vault_query.py:471}. Its content is byte-identical to `tests/fixtures/tickets/board_mappings/board-a.yaml` (checked with `cmp`, 2026-11-20), documented in [[board-a]] / [board-a](../../../board_mappings/board-a.md).

## Dependencies

**Depends on.** Nothing; plain keys, no file names.

**Used by.** Searched the whole worktree except `docs/` with `git grep` for `vault_board`, `board-a` and `board-mappings` (2026-11-20).
- Product code: `scripts/state/vault_query.py` reads every `*.yaml` in `<tickets folder>/board-mappings` when run with `--tickets-dir tests/fixtures/tickets/vault_board/02-tickets` {src:scripts/state/vault_query.py:441} {src:scripts/state/vault_query.py:471} {src:scripts/state/vault_query.py:141-143}. That is the only way it is reached; the path is a convention, not written anywhere in the repo.
- Tests: none. No test or script names `vault_board` (searched). The tests that call the board tool build their own vault in a temporary folder {src:tests/scripts/state/test_state_tools.py:114-119}.

## Behavior

Same four keys as the sibling copy. Each key and the line that reads it:
- `board_id`: the name the map is stored under; the file name is used if the key is missing {src:scripts/state/vault_query.py:144-145}.
- `prefix_patterns` (`EX`, `OT`): exact match of the key prefix (text before the first dash) against the list {src:scripts/state/vault_query.py:193} {src:scripts/state/vault_query.py:197-199}.
- `on_absent: warn`: status words missing from the map give `UNRESOLVED` with a warning; the value `reject` would give `INVALID` {src:scripts/state/vault_query.py:173} {src:scripts/state/vault_query.py:176-184}.
- `status_map`: exact, case-sensitive lookup of the raw status; the mapped word is returned as is {src:scripts/state/vault_query.py:172} {src:scripts/state/vault_query.py:174-175}. Entries: `ORIENT_COMPLETE` and `COMMITTED` to `OPEN`; `SCOPE_PENDING_CLARIFICATION` to `PARKED`; `IMPLEMENTATION_COMPLETE` and `DEV_COMPLETE` to `DEV_COMPLETE`; `QA_BLOCKED` to itself; `IN_PROGRESS` to `UNRESOLVED` {src:tests/fixtures/tickets/vault_board/02-tickets/board-mappings/board-a.yaml:7-13}.

A raw status whose first word is the shipped marker followed by more words skips the map {src:scripts/state/vault_query.py:166-171}.

Effect on the neighbouring fixture tickets: the tickets in this vault are `TG-001` and `TG-002` {src:tests/fixtures/tickets/vault_board/02-tickets/TG-001/TG-001-state.md:2}. The prefix `TG` is not in this file, and is not a standalone prefix either (`T` plus the vault config value, see [[vault-config]] / [vault-config](../vault-config.md)) {src:scripts/state/vault_query.py:38} {src:scripts/state/vault_query.py:467-470}. By the code, `TG-001` therefore resolves to `UNRESOLVED` with the message that the prefix has no board mapping {src:scripts/state/vault_query.py:200-203}. The map is only exercised by `EX` or `OT` tickets, and this vault holds none. This is read from the code, not run.

## Diagram

Skipped: a flat file with no environment branches.

## Notes

- The file is unused by any automated test; the code reading the keys is covered only by temporary vaults in other tests {src:tests/scripts/state/test_state_tools.py:114-119}.
- `prefix_patterns` is an exact list, not a pattern, despite the name {src:scripts/state/vault_query.py:198}.
- Hand-written parser: split at the first `:`, quotes stripped at both ends only {src:scripts/state/vault_query.py:73-77} {src:scripts/state/vault_query.py:46-49}.
- Inputs reaching paths, commands or network: none; values are text labels printed by the tool {src:scripts/state/vault_query.py:175}.
- Shared file writes: none; read only {src:scripts/state/vault_query.py:116-118}.
