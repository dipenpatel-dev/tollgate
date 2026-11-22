---
doc_type: config
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: config         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/fixtures/tickets/vault_mixed/02-tickets/vault-config.yaml"    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
format: "yaml"         # yaml | toml | json | env
governs: "which ticket prefix the ticket board tool treats as a standalone (local) prefix"        # what component or behavior this config controls
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

Test data, one line long. It is the vault settings file of the small sample vault `vault_mixed`, which holds three sample ticket folders (`TG-001`, `BAD-001` and `ABD-002`, the last an empty folder kept by a `.gitkeep` file). The one setting names a local ticket prefix. The sample vault itself is mainly used for its ticket state files, one of which is deliberately malformed; see [[validation]] and [validation](../../../../../scripts/validation.md) {src:docs/scripts/validation.md:13}.

## Dependencies

**Depends on.** Nothing. It is a single `key: value` line {src:tests/fixtures/tickets/vault_mixed/02-tickets/vault-config.yaml:1}.

**Used by.** Searched with `git grep` for `vault_mixed`, `vault-config` and `local_prefix` over the whole repo except `docs/` (2026-11-20).
- Product code that reads a file with this name: `scripts/state/vault_query.py`, which looks for `vault-config.yaml` inside the tickets folder it is given {src:scripts/state/vault_query.py:36} {src:scripts/state/vault_query.py:122}, and reads the key `local_prefix` {src:scripts/state/vault_query.py:467}. No other product file reads `local_prefix`. Its page: [[vault_query]] and [vault_query](../../../../../scripts/state/vault_query.md).
- Tests: no test or script names `vault_mixed` (search above), and no test passes this folder to `vault_query`. The folder is only reached as part of the whole `tests/fixtures/tickets` tree, which `tests/scripts/validation/test_validate_state_files.py` scans for state files {src:tests/scripts/validation/test_validate_state_files.py:19} {src:tests/scripts/validation/test_validate_state_files.py:42}. That scan looks only at `.md` files with `state` in the name {src:scripts/validation/validate_state_files.py:55}, so this YAML file is never read by it.
- A twin file with the same content exists at `tests/fixtures/tickets/vault_board/02-tickets/vault-config.yaml` {src:tests/fixtures/tickets/vault_board/02-tickets/vault-config.yaml:1}.

## Behavior

One key.

- **`local_prefix: mine`** {src:tests/fixtures/tickets/vault_mixed/02-tickets/vault-config.yaml:1}.
  - **Read at:** `vault_query.py` {src:scripts/state/vault_query.py:467}. The loader parses a top-level line with a colon into a key and a value, and strips matching quotes from the value {src:scripts/state/vault_query.py:94} {src:scripts/state/vault_query.py:98}.
  - **Effect:** the value is added to the set of standalone prefixes next to the built-in prefix `T` {src:scripts/state/vault_query.py:38} {src:scripts/state/vault_query.py:468} {src:scripts/state/vault_query.py:469}. A ticket whose id starts with a standalone prefix has its status checked against the tool's own list of allowed statuses {src:scripts/state/vault_query.py:193} {src:scripts/state/vault_query.py:194} {src:scripts/state/vault_query.py:195}. A ticket with any other prefix is looked up in the board mapping files and is reported as unresolved if none matches {src:scripts/state/vault_query.py:196} {src:scripts/state/vault_query.py:200}.
  - **Default if absent:** an empty string, which adds no prefix {src:scripts/state/vault_query.py:467} {src:scripts/state/vault_query.py:469}. If the whole file is missing, the tool prints a message and treats only `T` as standalone {src:scripts/state/vault_query.py:124} {src:scripts/state/vault_query.py:125} {src:scripts/state/vault_query.py:128}.
  - **Active here?** Not for the sample tickets. Their prefixes are `TG`, `BAD` and `ABD` (from the folder names), and none is `mine`, so the setting changes how no sample ticket here is judged. The value would matter only for a ticket id such as `mine-7`.

Other keys: the file has none, and the loader would accept more, but `vault_query.py` reads no other key from this file (searched `config.get` in the file, 2026-11-20) {src:scripts/state/vault_query.py:464}.

## Diagram

None: a single-line file with no sections or branches.

## Notes

- **Description versus code.** The file has no comment or description, so there is nothing to disagree with. The tool's own message for a missing file says it treats "the ticket prefix as the only standalone prefix" {src:scripts/state/vault_query.py:39}, while the code defaults to the prefix `T` {src:scripts/state/vault_query.py:38}. The wording is loose, the behavior is as described above.
- **Fixture not exercised.** No test runs the ticket board tool against this folder (searched, 2026-11-20), so the effect of `local_prefix: mine` in `vault_mixed` is not tested here. A change to this file would not fail any test.
- **Parser limits.** The simple parser takes any non-indented line with a colon as a key and skips lines that start with a space or tab {src:scripts/state/vault_query.py:86} {src:scripts/state/vault_query.py:89} {src:scripts/state/vault_query.py:90}. A top-level line without a colon raises an error that the loader reports as "malformed" {src:scripts/state/vault_query.py:92} {src:scripts/state/vault_query.py:93} {src:scripts/state/vault_query.py:131} {src:scripts/state/vault_query.py:132}.
- **Unchecked inputs.** The value `mine` is only compared to the part of a ticket id before the first `-` {src:scripts/state/vault_query.py:193} {src:scripts/state/vault_query.py:194}. It never reaches a file path, shell command, network address or outbound text, and no check on its value exists or is needed.
- **Shared file writes.** None. `vault_query` is documented as read only {src:scripts/state/vault_query.py:6}, and this fixture is never written by any test found in the search above.
