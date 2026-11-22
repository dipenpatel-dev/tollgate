---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_create.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/vault_ticket_creator.py, scripts/connectors/plane/vault_ticket_files.py, scripts/connectors/plane/plane_sync_ledger.py]         # source files under test, relative paths from repo root
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

Tests for the Plane `create` command, which makes a new card in Plane and then the matching ticket folder in the vault. The tests check the order of the calls, the guard that compares the highest card number in Plane with the highest local ticket number, what happens when a call fails (no retry, nothing half written), and how a re-run adopts a card that was made earlier. They run the real `run_create` function against a local fake Plane server with five existing tickets.

## Dependencies

**Depends on.**
- `run_create` from [[vault_ticket_creator]] ([vault_ticket_creator](../../../../scripts/connectors/plane/vault_ticket_creator.md)), the code under test {src:tests/scripts/connectors/plane/test_plane_create.py:17} {src:tests/scripts/connectors/plane/test_plane_create.py:26}.
- `ledger_path` and `load_ledger` from [[plane_sync_ledger]] ([plane_sync_ledger](../../../../scripts/connectors/plane/plane_sync_ledger.md)) {src:tests/scripts/connectors/plane/test_plane_create.py:15}.
- `PlaneApiError` from [[plane_work_item_client]] ([plane_work_item_client](../../../../scripts/connectors/plane/plane_work_item_client.md)) {src:tests/scripts/connectors/plane/test_plane_create.py:16}.
- `VaultTicketError`, `parse_state_text`, `read_state_file` from [[vault_ticket_files]] ([vault_ticket_files](../../../../scripts/connectors/plane/vault_ticket_files.md)) {src:tests/scripts/connectors/plane/test_plane_create.py:18}.
- `FailRule`, `StubItem` from [[plane_stub_server]] ([plane_stub_server](plane_stub_server.md)) {src:tests/scripts/connectors/plane/test_plane_create.py:19}.
- `StubTestCase`, `read_template`, `make_settings` from [[plane_sync_test_support]] ([plane_sync_test_support](plane_sync_test_support.md)) {src:tests/scripts/connectors/plane/test_plane_create.py:20}.
- Standard library: `dataclasses`, `unittest`, `unittest.mock` {src:tests/scripts/connectors/plane/test_plane_create.py:11-13}.

**Used by.**
- Product code: none. Tests are not imported by product code (searched with `git grep` for the file name outside `docs/`, 2026-11-20).
- Tests (runner): `tests/scripts/connectors/plane/run.sh` finds it with the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}.

## Behavior

**Fixture.** `StubTestCase` starts the stub and makes folders `T-1` to `T-5` in a temp tickets folder, with a matching card for each in the stub {src:tests/scripts/connectors/plane/plane_sync_test_support.py:104-115}. `_create` merges default arguments with overrides and calls `run_create` {src:tests/scripts/connectors/plane/test_plane_create.py:24-27}. The default arguments are prefix `T`, title "A new ticket", priority `P2` {src:tests/scripts/connectors/plane/plane_sync_test_support.py:120-122}.

**Happy path.**
- The calls reach the stub in this order: list projects, list work items, list states, create the card, update the card; the only output line is `created | T-6 | card 6` {src:tests/scripts/connectors/plane/test_plane_create.py:32-42}. The update call is the step that sets the card's external id {src:scripts/connectors/plane/vault_ticket_creator.py:133-136}.
- At the moment the card is created, the tickets folder still holds only `T-1` to `T-5`, and `T-6` exists afterwards {src:tests/scripts/connectors/plane/test_plane_create.py:44-49}. This proves the card is made first and the files second.
- The folder name, the state file's id and title, and the card's external id, name and number all agree; the update body is exactly the external id plus the source name `tollgate`, and the create body is exactly the name and the backlog state id {src:tests/scripts/connectors/plane/test_plane_create.py:51-61}.
- The saved ledger holds the card id `wi-6`, number 6, status word `BACKLOG`, no description hash, no session offsets and no posted keys {src:tests/scripts/connectors/plane/test_plane_create.py:63-67}.
- A second create after a first success makes a second card and folder `T-7` {src:tests/scripts/connectors/plane/test_plane_create.py:117-121}.
- A title with a colon and double quotes is stored and sent unchanged {src:tests/scripts/connectors/plane/test_plane_create.py:158-162}.
- The state file text written for a new ticket parses back with status word `BACKLOG` {src:tests/scripts/connectors/plane/test_plane_create.py:178-181}.

**Number guard.**
- If Plane's highest number (7) is above the local highest (5), the command exits 2, sends no create call, prints both numbers and leaves the folders alone {src:tests/scripts/connectors/plane/test_plane_create.py:69-74}. The same message is built by the guard {src:scripts/connectors/plane/vault_ticket_creator.py:87-88}.
- If Plane is behind local (a card removed), it also stops {src:tests/scripts/connectors/plane/test_plane_create.py:76-80}.
- If a local folder `T-6` already exists, the command stops, names the numbers, and the existing file inside is untouched {src:tests/scripts/connectors/plane/test_plane_create.py:123-129}.

**Failures and re-runs.**
- An unreachable Plane (stub stopped) raises `PlaneApiError` and writes no folder and no state folder {src:tests/scripts/connectors/plane/test_plane_create.py:82-88}.
- A 500 on the create call is not retried (exactly one POST) and writes nothing {src:tests/scripts/connectors/plane/test_plane_create.py:90-95}.
- If the update call fails once, nothing is written locally; the re-run finds the card by title, finishes the update and writes the folder, with still only one POST in total {src:tests/scripts/connectors/plane/test_plane_create.py:97-105}.
- If writing the folder fails, the command stops with `state file for T-6 cannot be written; card 6 kept`, and the re-run adopts the card and writes the folder {src:tests/scripts/connectors/plane/test_plane_create.py:107-115}. The code reports the error and keeps the card here {src:scripts/connectors/plane/vault_ticket_creator.py:143-144}.
- A card that matches the title but has no external id is adopted; if its folder already exists the command stops naming the card and makes no POST {src:tests/scripts/connectors/plane/test_plane_create.py:131-138}.
- Two cards matching the title stop the command and the message lists both numbers {src:tests/scripts/connectors/plane/test_plane_create.py:140-145}. A matching card that is not the next number also stops {src:tests/scripts/connectors/plane/test_plane_create.py:147-151}.

**Input checks.**
- A prefix with no Plane project prints the skip line, exits 2 and makes no call {src:tests/scripts/connectors/plane/test_plane_create.py:153-156}.
- A 256-character title, and a priority containing a newline and a colon, each exit 2 with no Plane call {src:tests/scripts/connectors/plane/test_plane_create.py:164-168}.
- A board status that Plane does not have (`Nowhere`) stops before the create call {src:tests/scripts/connectors/plane/test_plane_create.py:170-176}.

## Diagram

None: no test setup here has a fixture chain that the Behavior section does not already cover.

## Notes

- **Description versus code.** The header matches the tests: card first, number guard, stop without retry, adopt on re-run {src:tests/scripts/connectors/plane/test_plane_create.py:2}. The header Scope line says real HTTP goes to the local stub on `127.0.0.1` {src:tests/scripts/connectors/plane/test_plane_create.py:5}; that holds, since the client is built with a `StubHttp` that refuses other hosts {src:tests/scripts/connectors/plane/plane_sync_test_support.py:68-69} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:87-94}. No disagreement found.
- **Weak or indirect checks.** `test_unreachable_plane_writes_nothing` asserts `self.state` does not exist {src:tests/scripts/connectors/plane/test_plane_create.py:88}; this is true because the temp folder never creates it, so it only proves nothing wrote there. The order test splits each path with `split("/", 5)[-1]`, which ties it to the stub's URL layout {src:tests/scripts/connectors/plane/test_plane_create.py:34}.
- **Coverage gaps.** No test here covers the ledger write failure (that is in `test_plane_fixes`, see [[test_plane_fixes]] ([test_plane_fixes](test_plane_fixes.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:54-65}). No test here covers a secret in the title; `test_plane_fixes` does {src:tests/scripts/connectors/plane/test_plane_fixes.py:79-83}.
- **Machine and version dependence.** The two tests that call `run_create` directly after patching use string module paths such as `connectors.plane.vault_ticket_creator.write_new_ticket_folder` {src:tests/scripts/connectors/plane/test_plane_create.py:108}, so renaming that import in the product module breaks the patch. The file has no machine-specific paths. Its only generic annotation is a local variable, which Python does not evaluate when the function runs {src:tests/scripts/connectors/plane/test_plane_create.py:45}.
- **Unchecked inputs.** Titles, priorities and prefixes are fixed strings in the test. No input reaches a shell command or a real network address; the only address is the local stub {src:tests/scripts/connectors/plane/plane_sync_test_support.py:44}.
- **Shared file writes.** The tests write only inside temp folders removed at cleanup {src:tests/scripts/connectors/plane/plane_sync_test_support.py:109-111}. `test_existing_folder_stops_naming_the_card_and_overwrites_nothing` checks the code under test does not overwrite an existing file {src:tests/scripts/connectors/plane/test_plane_create.py:123-129}. Nothing in the tests checks two writers at once.
