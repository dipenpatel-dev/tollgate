---
doc_type: config
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: config         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/fixtures/tickets/vault_board/02-tickets/vault-config.yaml"    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
format: "yaml"         # yaml | toml | json | env
governs: "test data: which ticket key prefix vault_query.py treats as a local, standalone prefix in the vault_board fixture vault"        # what component or behavior this config controls
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

One-line vault settings file for the fixture vault `tests/fixtures/tickets/vault_board/`. It names the prefix of the vault owner's own tickets, so the ticket board tool knows which keys are local and need no board map. The tool looks for a file with this name directly inside the tickets folder {src:scripts/state/vault_query.py:36} {src:scripts/state/vault_query.py:122}.

## Dependencies

**Depends on.** Nothing.

**Used by.** Searched the whole worktree except `docs/` with `git grep` for `vault-config`, `local_prefix` and `vault_board` (2026-11-20).
- Product code: `scripts/state/vault_query.py` reads it through `load_vault_config`, which parses it and hands back the keys {src:scripts/state/vault_query.py:121-134}; `main` calls it for the tickets folder {src:scripts/state/vault_query.py:464}. It is reached only when the tool is run with `--tickets-dir tests/fixtures/tickets/vault_board/02-tickets` {src:scripts/state/vault_query.py:441} {src:scripts/state/vault_query.py:452-453}.
- Tests: none. Nothing names `vault_board` (searched). The only other copy of this file is `tests/fixtures/tickets/vault_mixed/02-tickets/vault-config.yaml`, which also reads `local_prefix: mine` (searched). Two sibling pages: [[board-a]] / [board-a](board-mappings/board-a.md).

## Behavior

The file has a single key.
- `local_prefix: mine`. `main` reads `local_prefix` from the loaded config, defaulting to an empty string {src:scripts/state/vault_query.py:467}. Standalone prefixes are `T` always, plus this value when it is not empty {src:scripts/state/vault_query.py:38} {src:scripts/state/vault_query.py:468-470}. A ticket whose key prefix (text before the first dash) is in that set is checked against the standard status list and never looked up in a board map {src:scripts/state/vault_query.py:193-195} {src:scripts/state/vault_query.py:151-158}. With the value `mine`, a ticket such as `mine-12` is standalone.

Other behavior of the loader that the file triggers:
- When the file is missing, `load_vault_config` returns an empty config and an error text that ends "treating the ticket prefix as the only standalone prefix"; `main` prints each error to standard error and goes on {src:scripts/state/vault_query.py:124-128} {src:scripts/state/vault_query.py:39} {src:scripts/state/vault_query.py:465-466}.
- A parse error gives an empty config and a "malformed" message {src:scripts/state/vault_query.py:129-133}.
- No other key is read: `main` only calls `config.get("local_prefix", "")` {src:scripts/state/vault_query.py:467}.

## Diagram

Skipped: a one-key file.

## Notes

- The value `mine` does not match the tickets in this vault, which are `TG-001` and `TG-002` {src:tests/fixtures/tickets/vault_board/02-tickets/TG-001/TG-001-state.md:2} {src:tests/fixtures/tickets/vault_board/02-tickets/TG-002/TG-002-state.md:2}. `TG` is neither `T` nor `mine`, and the board map covers only `EX` and `OT` {src:tests/fixtures/tickets/vault_board/02-tickets/board-mappings/board-a.yaml:2-4}, so by the code both tickets resolve to `UNRESOLVED` with a "no board mapping" message {src:scripts/state/vault_query.py:200-203}. This is read from the code, not run. If the fixture was meant to show a local prefix in use, the value or the ticket keys look out of step `[uncertain: intent not stated anywhere]`.
- The code expects `local_prefix` as a plain top-level `key: value` line {src:scripts/state/vault_query.py:94-98}. Quotes around the value are removed {src:scripts/state/vault_query.py:46-49}.
- Inputs reaching paths, commands or network: none; the value is used only as a set member compared with a ticket prefix {src:scripts/state/vault_query.py:468-470}.
- Shared file writes: none; read only {src:scripts/state/vault_query.py:116-118}.
