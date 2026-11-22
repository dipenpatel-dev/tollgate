---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/test_connectors.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/registry.py, scripts/connectors/connect.py, scripts/connectors/secret_store.py]         # source files under test, relative paths from repo root
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

This is the main test file for the connector framework. It proves the rule that a connector does nothing until a person turns it on, that turning it on stores the key only in the secret store and never in a file, that the on state survives a restart, and that turning it off puts the connector back to "not set up". A second class checks how each secret store passes the key to its command-line tool.

## Dependencies

**Depends on.**
- Standard library: `contextlib`, `io`, `os`, `pathlib`, `subprocess`, `sys`, `unittest`, `uuid` {src:tests/scripts/connectors/test_connectors.py:10-17}, and `importlib`, imported inside one test {src:tests/scripts/connectors/test_connectors.py:140}.
- [[connector_helpers]] / [connector_helpers](../../harness/connector_helpers.md): `MockClient`, `FakeSecretStore`, `assert_no_network` {src:tests/scripts/connectors/test_connectors.py:25}.
- [[throwaway_home]] / [throwaway_home](../../harness/throwaway_home.md): a temporary home and environment {src:tests/scripts/connectors/test_connectors.py:26}.
- `fake_connector`, a test-only connector in the same folder, imported by name {src:tests/scripts/connectors/test_connectors.py:27} (no doc yet).
- [[registry]] / [registry](../../../scripts/connectors/registry.md), [[connect]] / [connect](../../../scripts/connectors/connect.md), [[secret_store]] / [secret_store](../../../scripts/connectors/secret_store.md) {src:tests/scripts/connectors/test_connectors.py:28}.
- The folder paths for imports are built from the file location: its own folder, `tests/harness` and `scripts` at the repo root {src:tests/scripts/connectors/test_connectors.py:19-23}.

**Used by.** Searched with `git grep` for the file name, excluding `docs/` (2026-11-20). No product code names it.
- Found by the pattern `test_*.py` in the connectors runner {src:tests/scripts/connectors/run.sh:6}, which the end-to-end runner calls for the area `connectors` {src:tests/system/run.sh:22-23}. See [[run]] / [run](run.md).
- Tests: no other test imports it.

## Behavior

**Setup.** `Base.setUp` makes a throwaway home, forces the non-interactive flag on, installs a fake secret store and a mock web client into the registry, and makes a random fake key {src:tests/scripts/connectors/test_connectors.py:40-48}. `tearDown` clears both hooks and removes the home {src:tests/scripts/connectors/test_connectors.py:50-53}. The fake key is a fixed prefix plus a random hex string {src:tests/scripts/connectors/test_connectors.py:31-32}. `turn_on` runs `connect on fakeconn` with the key passed through an environment variable and removes the variable afterwards {src:tests/scripts/connectors/test_connectors.py:55-63}.

**Class `TestCon`**
1. `test_con01_not_set_up`: with no network allowed, running the fake connector's main fails with a non-zero code, prints `fakeconn: not set up` and the `connect.py on fakeconn` hint to stderr, makes no web call, and does not even create the connectors file {src:tests/scripts/connectors/test_connectors.py:83-90}. The message comes from `how_to_set_up` {src:scripts/connectors/registry.py:325-327}, and `run_cli` turns the error into exit code 2 {src:scripts/connectors/registry.py:434-436}. The file is only read, never created, when state is empty {src:scripts/connectors/registry.py:271-275}.
2. `test_con01_subprocess_exit_code`: the same check in a separate Python process: non-zero exit, same message {src:tests/scripts/connectors/test_connectors.py:92-96}.
3. `test_con02_first_use_stores_secret_nowhere_on_disk`: turning on returns 0 and the store was asked to save under the name `fakeconn` {src:tests/scripts/connectors/test_connectors.py:98-101}. Then the test reads every file under the repo root and under the throwaway home (skipping `.git` folders and unreadable files) and fails if the key bytes appear in any {src:tests/scripts/connectors/test_connectors.py:103-115}. The connectors file must name `fakeconn` and the address {src:tests/scripts/connectors/test_connectors.py:116-119}. The code sends the key to the store first and writes state without it {src:scripts/connectors/registry.py:372-380}.
4. `test_con02_key_from_stdin`: the key can arrive on standard input and reaches the store {src:tests/scripts/connectors/test_connectors.py:121-126} {src:scripts/connectors/connect.py:61-62}.
5. `test_con02_noninteractive_without_key_refuses`: no key and no terminal gives a non-zero code and nothing is stored {src:tests/scripts/connectors/test_connectors.py:128-134} {src:scripts/connectors/connect.py:86-89}.
6. `test_con03_on_survives_restart_and_reaches_client`: after turning on, the registry's table of connector builders is cleared and `fake_connector` is reloaded to simulate a restart {src:tests/scripts/connectors/test_connectors.py:136-141}. `require` then returns a client; its one `ping` produces exactly one mock call to `https://fake.invalid/ping`, and the saved state is the address with `on` true {src:tests/scripts/connectors/test_connectors.py:143-152}. Reloading re-registers the builder {src:tests/scripts/connectors/fake_connector.py:27}.
7. `test_con04_off_returns_to_not_set_up`: after `off`, the secret is gone from the store and the fake connector again fails with the not-set-up message and makes no call {src:tests/scripts/connectors/test_connectors.py:154-162}. `turn_off` marks the entry off and deletes the key {src:scripts/connectors/registry.py:383-390}.
8. `test_status`: status for a named, unset connector returns 1 and prints `not set up`; after turning on it returns 0 and prints `fakeconn: on` {src:tests/scripts/connectors/test_connectors.py:164-171} {src:scripts/connectors/connect.py:131}.
9. `test_ensure_first_use_in_terminal`: with the registry's terminal check replaced to answer yes, `ensure` asks (through supplied answers) for address and key, turns the connector on, and the client then pings the entered address {src:tests/scripts/connectors/test_connectors.py:173-185} {src:scripts/connectors/registry.py:418-427}. The original check is restored in a `finally` block {src:tests/scripts/connectors/test_connectors.py:182-183}.

**Class `TestSecretStores`.** A `Recorder` stands in for the command runner: it records each call and returns a fixed result {src:tests/scripts/connectors/test_connectors.py:189-195}.
10. Keychain: the key is not in the command arguments but is in the text sent on standard input {src:tests/scripts/connectors/test_connectors.py:197-203} {src:scripts/connectors/secret_store.py:77-79}. A key holding a double quote raises the store error {src:tests/scripts/connectors/test_connectors.py:205-207} {src:scripts/connectors/secret_store.py:72-75}.
11. secret-tool: the key is sent as standard input, exactly, and is not in the arguments {src:tests/scripts/connectors/test_connectors.py:209-215} {src:scripts/connectors/secret_store.py:105-107}.
12. `get`: output `abc` plus a newline reads back as `abc`; a non-zero result gives `None` {src:tests/scripts/connectors/test_connectors.py:217-221} {src:scripts/connectors/secret_store.py:88-90}.
13. No tool found: on Linux without `secret-tool`, saving raises an error whose text says "plain file"; on Windows the default store is the refusing store {src:tests/scripts/connectors/test_connectors.py:223-230} {src:scripts/connectors/secret_store.py:142-144} {src:scripts/connectors/secret_store.py:158-162}.
14. Default choice: macOS gives the Keychain store, Linux gives the secret-tool store when the tool is found {src:tests/scripts/connectors/test_connectors.py:232-238} {src:scripts/connectors/secret_store.py:158-161}.
15. Memory store: set, get and delete round trip {src:tests/scripts/connectors/test_connectors.py:240-245} {src:scripts/connectors/secret_store.py:129-136}.

## Diagram

None: each case sets up the same small fixture (throwaway home, fake store, mock client) {src:tests/scripts/connectors/test_connectors.py:40-48} and runs one flow. The chain is short enough to read in the setup above.

## Notes

- **Code and description.** The docstring says it covers "CON-01 to CON-04, plus secret store checks" and proves a connector "is off until first use, and never leaks a key" {src:tests/scripts/connectors/test_connectors.py:1-6}. The file does carry those cases. "Never leaks a key" is shown only for the repo tree and the throwaway home (case 3), not for standard output, standard error, or the system temp folder.
- **Process environment is wiped by case 6.** After the restart simulation, `for k in self.env: os.environ.pop(k, None)` removes every key of `self.env` from the live process environment {src:tests/scripts/connectors/test_connectors.py:147-148}. That dictionary was built from a copy of the whole environment, not just `TOLLGATE_` names {src:tests/harness/throwaway_home.py:30-34}, so `HOME`, `USER`, `PATH` and the rest are removed from the test process [uncertain: not run; the effect on tests that run after it was not observed]. `run_fake_main` restores whatever it found on entry, so it would restore the wiped state {src:tests/scripts/connectors/test_connectors.py:66-79}.
- **Case 3 is slow and layout bound.** It reads every file below the repo root, not a short list {src:tests/scripts/connectors/test_connectors.py:104-115}. A large virtual environment or data folder in the repo would make it slow. It skips only `.git` {src:tests/scripts/connectors/test_connectors.py:107}.
- **Weak checks.** `self.addCleanup(lambda: None)` registers a cleanup that does nothing {src:tests/scripts/connectors/test_connectors.py:56}. In the secret store cases, the "not found" result is an arbitrary exit code 44 {src:tests/scripts/connectors/test_connectors.py:221}; any non-zero would pass {src:scripts/connectors/secret_store.py:88-89}. `SecretToolStore.get` and both `delete` methods are not tested {src:scripts/connectors/secret_store.py:111-120}.
- **Untested input to a command.** In the code under test, the connector `name` and the account name are placed inside the Keychain command text with no check, and only the key is checked {src:scripts/connectors/secret_store.py:72} {src:scripts/connectors/secret_store.py:77-78}. No test here passes a name with a quote.
- **Other unchecked inputs.** The connectors file path comes from the environment variable `TOLLGATE_CONNECTORS` with no check {src:scripts/connectors/registry.py:264-268}; the tests point it into the throwaway home {src:tests/harness/throwaway_home.py:42}.
- **Writes to a shared file.** The code under test writes the connectors file with a plain `write_text`, not through a temp file, and nothing stops two writers at once {src:scripts/connectors/registry.py:318}. The tests write only inside the throwaway home.
- **Python version.** `subprocess.run(..., capture_output=True, text=True)` needs Python 3.7 or newer {src:tests/scripts/connectors/test_connectors.py:93-94}. No machine path is written in the file.
