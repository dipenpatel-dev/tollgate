---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_drift.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/plane_drift_checker.py, scripts/connectors/plane/cli.py]         # source files under test, relative paths from repo root
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

Tests for the Plane `drift` command, which compares a ticket in the vault with its Plane card and reports each difference on its own line without changing anything. A clean ticket prints nothing and exits 0; each kind of mismatch (missing card, wrong number, wrong name, wrong description, unreadable description) prints a line with its own label and exits 2. A last class runs the command through the command line wrapper.

## Dependencies

**Depends on.**
- `run_drift` from [[plane_drift_checker]] ([plane_drift_checker](../../../../scripts/connectors/plane/plane_drift_checker.md)), the code under test {src:tests/scripts/connectors/plane/test_plane_drift.py:14} {src:tests/scripts/connectors/plane/test_plane_drift.py:23}.
- `FAKE_TOKEN`, `SYNC_TICKET`, `CliCase`, `SyncTestCase` from [[plane_sync_test_support]] ([plane_sync_test_support](plane_sync_test_support.md)) {src:tests/scripts/connectors/plane/test_plane_drift.py:15}. The command line class also exercises [[cli]] ([cli](../../../../scripts/connectors/plane/cli.md)) through `run_cli` {src:tests/scripts/connectors/plane/plane_sync_test_support.py:209-214}.
- The `sync` helper of the support module, used to bring the card to a known good state before each test {src:tests/scripts/connectors/plane/plane_sync_test_support.py:157-163}.
- Standard library: `dataclasses`, `unittest` {src:tests/scripts/connectors/plane/test_plane_drift.py:11-12}.

**Used by.**
- Product code: none. Tests are not imported by product code (searched with `git grep` for the file name outside `docs/`, 2026-11-20).
- Tests (runner): `tests/scripts/connectors/plane/run.sh` finds it with the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}.

## Behavior

**Fixture.** `SyncTestCase` adds a state file for `T-5` on top of the five stub cards {src:tests/scripts/connectors/plane/plane_sync_test_support.py:139-142}. The local `drift` helper calls `run_drift` with the given ids (default `T-5`) and collects output lines {src:tests/scripts/connectors/plane/test_plane_drift.py:21-24}.

**What each test proves.**
- Clean ticket: after a `sync`, `drift` exits 0 and prints nothing {src:tests/scripts/connectors/plane/test_plane_drift.py:26-29}.
- Missing card: with the `T-5` card removed from the stub, the output is exactly `missing_card | T-5 | no card with that id` and the exit is 2 {src:tests/scripts/connectors/plane/test_plane_drift.py:31-34}.
- Wrong number: card number changed to 9 gives `wrong_number | T-5 | card 9 vault 5` {src:tests/scripts/connectors/plane/test_plane_drift.py:36-40}.
- Wrong name: card name changed gives a line with both names in quotes {src:tests/scripts/connectors/plane/test_plane_drift.py:42-46}.
- Wrong description: after the state file text changes, one `wrong_description` line shows two 12-character hex values, the card's and the file's {src:tests/scripts/connectors/plane/test_plane_drift.py:48-53}.
- A card description with no `state-sha` line is reported as wrong, with `card none`, never treated as a pass {src:tests/scripts/connectors/plane/test_plane_drift.py:55-59}.
- If several `state-sha` lines exist, the last one decides: a stale hash placed first is ignored and drift stays 0 {src:tests/scripts/connectors/plane/test_plane_drift.py:61-64}.
- A card with no description at all (never synced) gives `description_unreadable | T-5 | the read returned no description`, so a missing description is never a silent pass {src:tests/scripts/connectors/plane/test_plane_drift.py:66-69}. The stub's default description is `None` {src:tests/scripts/connectors/plane/plane_stub_server.py:52}.
- Several ids: for `T-5` and `T-4`, there is exactly one list call for the project, and the first output line is for `T-4` with `description_unreadable` {src:tests/scripts/connectors/plane/test_plane_drift.py:71-77}.
- Unmapped prefix `zz`: prints the skip line and exits 0 {src:tests/scripts/connectors/plane/test_plane_drift.py:83-85}.
- No writes: after clearing the call record, a drift run sends only GET calls {src:tests/scripts/connectors/plane/test_plane_drift.py:87-91}.
- Unknown project key: with the settings pointing at project `NOPE`, the result is the missing-card line and exit 2 {src:tests/scripts/connectors/plane/test_plane_drift.py:93-98}.
- Through the command line: clean gives 0 and no lines; after the state file is edited it gives 2, and the fake token does not appear in any output line {src:tests/scripts/connectors/plane/test_plane_drift.py:101-108}.

## Diagram

None: no test setup here has a fixture chain that the Behavior section does not already cover.

## Notes

- **Description versus code.** The header says "a clean ticket prints nothing, each mismatch kind prints its own line" {src:tests/scripts/connectors/plane/test_plane_drift.py:2}. The tests match it for the kinds listed above. The header Scope line says real HTTP goes to the local stub on `127.0.0.1` {src:tests/scripts/connectors/plane/test_plane_drift.py:5}, which holds for the support module's client {src:tests/scripts/connectors/plane/plane_sync_test_support.py:68-69}.
- **Setup that no assertion reads.** `write_file_for_other_ticket` writes a state file for `T-4` with a status value that Plane never sees in this test {src:tests/scripts/connectors/plane/test_plane_drift.py:79-81}. The test that uses it expects `description_unreadable` for `T-4` because the stub card has no description {src:tests/scripts/connectors/plane/test_plane_drift.py:77}, so that status value is not checked by any assertion.
- **Weak check.** `test_a_card_missing_for_the_id` and `test_unknown_project_reports_a_missing_card` both pass if the code prints the same label for two different causes; the second does not check that the project lookup was the cause {src:tests/scripts/connectors/plane/test_plane_drift.py:31-34} {src:tests/scripts/connectors/plane/test_plane_drift.py:93-98}.
- **Hash assertion.** The regex pins the hash width at 12 hex characters {src:tests/scripts/connectors/plane/test_plane_drift.py:53}; changing the width in the code breaks this test, which is the intended guard.
- **Machine and version dependence.** No machine paths; temp folders only {src:tests/scripts/connectors/plane/plane_sync_test_support.py:109-111}. Annotations in this file are plain, so no newer Python feature is needed here; the support module uses `from __future__ import annotations` {src:tests/scripts/connectors/plane/plane_sync_test_support.py:10}.
- **Unchecked inputs.** Ticket ids are fixed strings in the test, and the one with a prefix not in the table is `zz-3` {src:tests/scripts/connectors/plane/test_plane_drift.py:84}. No input reaches a shell command; the only network address is the local stub.
- **Shared file writes.** The tests write state files into the temp tickets folder only {src:tests/scripts/connectors/plane/test_plane_drift.py:81}. The `drift` command itself must not write, and `test_drift_sends_no_write_call` checks the stub side only; it does not check that no vault file or ledger changed {src:tests/scripts/connectors/plane/test_plane_drift.py:87-91}.
