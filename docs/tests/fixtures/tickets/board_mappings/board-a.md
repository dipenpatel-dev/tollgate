---
doc_type: config
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: config         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/fixtures/tickets/board_mappings/board-a.yaml"    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
format: "yaml"         # yaml | toml | json | env
governs: "test data: how an external board's ticket prefixes and statuses map to Tollgate statuses in vault_query.py"        # what component or behavior this config controls
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

Sample board map used as test data. It says that tickets whose key starts with `EX` or `OT` belong to an outside board called `board-a`, and how that board's status words turn into Tollgate status words. The format is read by the ticket board tool `vault_query.py` {src:scripts/state/vault_query.py:137-148}. This copy is byte-identical to the one under `tests/fixtures/tickets/vault_board/02-tickets/board-mappings/` (checked with `cmp`, 2026-11-20), documented in [[board-a]] / [board-a](../vault_board/02-tickets/board-mappings/board-a.md).

## Dependencies

**Depends on.** Nothing. The file is plain keys; it does not name other files.

**Used by.** Searched the whole worktree except `docs/` with `git grep` for `board_mappings`, `board-a`, `board-mappings` and `vault_board` (2026-11-20).
- Product code: none reads this exact file. `vault_query.py` loads every `*.yaml` in a folder named `board-mappings` (hyphen) inside the tickets folder {src:scripts/state/vault_query.py:37} {src:scripts/state/vault_query.py:471} {src:scripts/state/vault_query.py:141}. This file sits in a folder named `board_mappings` (underscore) directly under `tests/fixtures/tickets/`. Even with `--tickets-dir tests/fixtures/tickets` the tool would look for `board-mappings`, not this folder {src:scripts/state/vault_query.py:441} {src:scripts/state/vault_query.py:471}.
- Tests: none. No test names this folder or file (searched).

## Behavior

The keys, and the code that reads each one. The parser is a small hand-written reader, not a YAML library: top-level `key: value` lines, and indented `- item` lists or `key: value` maps below a key with no value {src:scripts/state/vault_query.py:80-104} {src:scripts/state/vault_query.py:52-77}.

- `board_id: board-a` is the name the map is stored under; when missing, the file name without extension is used {src:scripts/state/vault_query.py:144-145}. Nothing else reads the id.
- `prefix_patterns` (list `EX`, `OT`): a ticket belongs to this board when the part of its key before the first dash is in the list {src:scripts/state/vault_query.py:193} {src:scripts/state/vault_query.py:197-199}. The match is an exact string match, not a pattern; the name suggests wildcards that the code does not support {src:scripts/state/vault_query.py:198}. A key with a prefix of `T` or the vault's local prefix is treated as a standalone ticket first and never reaches the board maps {src:scripts/state/vault_query.py:194-195}.
- `on_absent: warn` decides what happens for a status word not in `status_map`. `reject` gives the status `INVALID` with an error; any other value, including `warn` and a missing key (default `warn`), gives `UNRESOLVED` with a warning text {src:scripts/state/vault_query.py:173} {src:scripts/state/vault_query.py:176-184}. In this file the value is `warn`, so unmapped statuses become `UNRESOLVED`.
- `status_map` (seven entries): the raw status from the ticket state file is looked up as written, same letter case, and the mapped word is returned unchanged {src:scripts/state/vault_query.py:172} {src:scripts/state/vault_query.py:174-175}. Mapped values are not checked against the standard status list {src:scripts/state/vault_query.py:175}. The entries here: `ORIENT_COMPLETE` and `COMMITTED` map to `OPEN`; `SCOPE_PENDING_CLARIFICATION` to `PARKED`; `IMPLEMENTATION_COMPLETE` and `DEV_COMPLETE` to `DEV_COMPLETE`; `QA_BLOCKED` to itself; `IN_PROGRESS` to `UNRESOLVED` {src:tests/fixtures/tickets/board_mappings/board-a.yaml:7-13}.

A raw status whose first word is the shipped marker followed by more words is handled before the map and returns the shipped value with a warning, whatever the map says {src:scripts/state/vault_query.py:166-171}.

Which tickets this fixture is meant for: `state_ex_unmapped.md` has an `EX-001` key and a status word that is not in the map {src:tests/fixtures/tickets/state_ex_unmapped.md:2-3}. No test reads it together with this map (searched).

## Diagram

Skipped: a flat file with no environment branches.

## Notes

- Dead copy. No code or test reads this file (see Used by). The working copy for manual runs of the board tool is the one under `vault_board/02-tickets/board-mappings/`, which has identical content and the folder name the tool expects {src:scripts/state/vault_query.py:471}.
- Hand-written parser limits: a map entry is split at the first `:`, quotes are stripped at both ends only, and nesting deeper than one level is not understood {src:scripts/state/vault_query.py:73-77} {src:scripts/state/vault_query.py:46-49}.
- Inputs reaching paths, commands or network: none; it is data. Values from `status_map` are used only as text labels in output {src:scripts/state/vault_query.py:175}.
- Shared file writes: none; the tool only reads this file {src:scripts/state/vault_query.py:116-118}.
