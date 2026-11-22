---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_connector.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/cli.py, scripts/connectors/connect.py, scripts/connectors/registry.py]         # source files under test, relative paths from repo root
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

Tests for the connector life cycle of the Plane connector: what happens before it is set up, the first time it is turned on, after a restart, and after it is turned off. The header calls these cases CON-01 to CON-04 {src:tests/scripts/connectors/plane/test_plane_connector.py:2}. Every test runs against a throwaway home folder, an in-memory secret store and a recording fake http object, so no real Plane server and no real secret store is touched.

## Dependencies

**Depends on.**
- `cli.main` from [[cli]] ([cli](../../../../scripts/connectors/plane/cli.md)), the Plane command line, called directly with injected folders and an output collector {src:tests/scripts/connectors/plane/test_plane_connector.py:24} {src:tests/scripts/connectors/plane/test_plane_connector.py:54-57}.
- `connect.main` from [[connect]] ([connect](../../../../scripts/connectors/connect.md)), used to turn the connector on, off and ask for its status {src:tests/scripts/connectors/plane/test_plane_connector.py:23} {src:tests/scripts/connectors/plane/test_plane_connector.py:64-65}.
- `registry` from [[registry]] ([registry](../../../../scripts/connectors/registry.md)): the test swaps in a fake secret store and a fake http factory {src:tests/scripts/connectors/plane/test_plane_connector.py:46-47}.
- `FakeSecretStore`, `MockClient`, `assert_no_network` from [[connector_helpers]] ([connector_helpers](../../../harness/connector_helpers.md)) {src:tests/scripts/connectors/plane/test_plane_connector.py:22}.
- `throwaway_home` from [[throwaway_home]] ([throwaway_home](../../../harness/throwaway_home.md)) {src:tests/scripts/connectors/plane/test_plane_connector.py:29}.
- `PlaneStubServer` and `WORKSPACE` from [[plane_stub_server]] ([plane_stub_server](plane_stub_server.md)) {src:tests/scripts/connectors/plane/test_plane_connector.py:25} {src:tests/scripts/connectors/plane/test_plane_connector.py:173}.
- `ROOT`, `SCRIPTS`, `SYNC_TICKET`, `StubHttp`, `SyncTestCase`, `fake_key` from [[plane_sync_test_support]] ([plane_sync_test_support](plane_sync_test_support.md)) {src:tests/scripts/connectors/plane/test_plane_connector.py:26-28}.
- Standard library: `contextlib`, `importlib`, `io`, `os`, `subprocess`, `sys`, `unittest`, `pathlib`, `urllib.parse` {src:tests/scripts/connectors/plane/test_plane_connector.py:11-20}.

**Used by.**
- Product code: none. Tests are not imported by product code (searched with `git grep` for the file name outside `docs/`, 2026-11-20).
- Tests (runner): `tests/scripts/connectors/plane/run.sh` finds it with the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}.

## Behavior

**Fixture.** `ConnectorCase` makes a throwaway home and an environment dict, sets non-interactive mode, installs a fake secret store and a mock http factory, and removes both at cleanup {src:tests/scripts/connectors/plane/test_plane_connector.py:38-50}. `run_plane` runs `cli.main` with output collected into `self.lines` and stderr captured, and returns the exit code and the stderr text {src:tests/scripts/connectors/plane/test_plane_connector.py:52-58}. `turn_on` passes the fake key in a temporary environment variable and removes it afterwards {src:tests/scripts/connectors/plane/test_plane_connector.py:60-67}. `script_drift_replies` queues two canned replies, one empty project list entry and one empty card list {src:tests/scripts/connectors/plane/test_plane_connector.py:76-80}.

**CON-01, not set up.**
- With the connector never turned on, the `drift`, `sync` and `create` commands each return a non-zero code, print "plane: not set up" with the `connect.py on plane` hint on stderr, and make no network call {src:tests/scripts/connectors/plane/test_plane_connector.py:84-91}. The message text comes from `how_to_set_up` {src:scripts/connectors/registry.py:325-327}.
- The same run proves no connectors state file is created {src:tests/scripts/connectors/plane/test_plane_connector.py:92}.
- A second test runs the real script `plane_sync.py` in a subprocess with the throwaway environment and checks a non-zero exit, the message on stderr and an empty stdout {src:tests/scripts/connectors/plane/test_plane_connector.py:94-99}.

**CON-02, first use.**
- Turning the connector on stores the key in the secret store (`asked_to_store`, then the stored value equals the key) {src:tests/scripts/connectors/plane/test_plane_connector.py:101-105}.
- It then walks every file under the repo root (skipping `.git`) and under the throwaway home and fails if the key bytes appear in any file, and checks the connectors state file names `plane` and the address {src:tests/scripts/connectors/plane/test_plane_connector.py:106-118}.
- In a pretend terminal (`interactive` patched to true), a `drift` run asks for the address and key, stores the key, marks the connector on, and the first request goes to the projects URL. The exit code is 2 because the canned reply has no card for the ticket {src:tests/scripts/connectors/plane/test_plane_connector.py:120-130}.

**CON-03, restart.** After turning on, the test empties the registry factories and reloads `cli`, then checks plane is registered again, the next `drift` makes exactly two calls (projects, then work items), the key goes out in the `X-API-Key` header, and the saved state is `{"address": ADDRESS, "on": True}` {src:tests/scripts/connectors/plane/test_plane_connector.py:132-142}. A second test checks the key text is in none of the printed output lines {src:tests/scripts/connectors/plane/test_plane_connector.py:144-148}.

**CON-04, off.** After `connect off plane`, the secret store no longer holds the key, and `drift` is back to the "not set up" message with no network call {src:tests/scripts/connectors/plane/test_plane_connector.py:150-159}.

**Status command.** `status plane` returns 1 and prints "plane: not set up" before turn-on, then 0 and "plane: on" after {src:tests/scripts/connectors/plane/test_plane_connector.py:161-168}.

**Stub is local.** The stub server binds `127.0.0.1` and its base URL starts with `http://127.0.0.1:` {src:tests/scripts/connectors/plane/test_plane_connector.py:171-177}. `StubHttp` raises an assertion error for any other host {src:tests/scripts/connectors/plane/test_plane_connector.py:179-182}.

## Diagram

None: no test setup here has a fixture chain that the Behavior section does not already cover.

## Notes

- **Description versus code.** The header names only CON-01 to CON-04 {src:tests/scripts/connectors/plane/test_plane_connector.py:2}, but the file also holds a status-command test and two stub-is-local tests {src:tests/scripts/connectors/plane/test_plane_connector.py:161} {src:tests/scripts/connectors/plane/test_plane_connector.py:171}. The header Scope line says real HTTP goes to the local stub on `127.0.0.1` {src:tests/scripts/connectors/plane/test_plane_connector.py:5}; the `ConnectorCase` tests use a `MockClient` that makes no HTTP call at all {src:tests/scripts/connectors/plane/test_plane_connector.py:45-47}.
- **Test order dependence.** CON-03 empties every registered connector factory and only the reload of `cli` registers plane again {src:tests/scripts/connectors/plane/test_plane_connector.py:134-135}. Nothing restores other connectors that registered themselves, so a later test in the same process that relies on another connector would fail. Cleanup only resets the store and the http factory {src:tests/scripts/connectors/plane/test_plane_connector.py:48-49}.
- **Weak assertions.** CON-01 and CON-04 accept any exit code other than 0 or None, not a specific one {src:tests/scripts/connectors/plane/test_plane_connector.py:88} {src:tests/scripts/connectors/plane/test_plane_connector.py:157}.
- **Slow and machine dependent.** The key-leak scan reads every file under the repo checkout {src:tests/scripts/connectors/plane/test_plane_connector.py:107-115}, so its time grows with the checkout size. The subprocess test needs `sys.executable` to run `plane_sync.py` with `-B` {src:tests/scripts/connectors/plane/test_plane_connector.py:95}. The function annotations `list[str]` and `tuple[int, str]` are evaluated when the class is defined, because the file has no `from __future__ import annotations`; this needs Python 3.9 or newer {src:tests/scripts/connectors/plane/test_plane_connector.py:52}, which the 3.12 minimum covers.
- **Unchecked inputs.** The test passes the address `https://plane.example.invalid` and a generated key into `connect.main` and never touches a real path outside the throwaway home {src:tests/scripts/connectors/plane/test_plane_connector.py:31} {src:tests/scripts/connectors/plane/test_plane_connector.py:64-65}. No command or network address in the test comes from outside the file. The temporary environment variable `TG_TEST_KEY` is set in the live process environment and removed in a `finally` block, so a crash between set and remove cannot leave it behind {src:tests/scripts/connectors/plane/test_plane_connector.py:61-67}.
- **Shared file writes.** The test does not write to any shared file itself. The code under test writes the connectors state file inside the throwaway home {src:tests/scripts/connectors/plane/test_plane_connector.py:116}; the home is removed on exit {src:tests/harness/throwaway_home.py:58-59}.
- `CREATE_FOR_TEST` is defined at the end of the file, below the class that uses it {src:tests/scripts/connectors/plane/test_plane_connector.py:185-186}. It works because the name is looked up when the test runs, not when the class is built {src:tests/scripts/connectors/plane/test_plane_connector.py:85}.
