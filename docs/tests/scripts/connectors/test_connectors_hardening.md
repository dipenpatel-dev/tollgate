---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/test_connectors_hardening.py    # relative path from repo root, e.g., tests/test_assembler.py
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

This file holds three hardening checks for the connector framework. The first proves that a web address with a user name or password inside it is refused and that the password is never printed. The second proves that a hand-edited connectors file with wrong types in it never crashes the commands, and that a wrongly typed entry reads as "off". The third proves that a connector name with a space, quote, semicolon, dollar sign, slash, a leading dash, capital letters or no characters is refused before it reaches the secret store.

## Dependencies

**Depends on.**
- Standard library: `contextlib`, `io`, `pathlib`, `sys`, `unittest` {src:tests/scripts/connectors/test_connectors_hardening.py:12-16}, and `os`, imported inside a test {src:tests/scripts/connectors/test_connectors_hardening.py:51}.
- [[connector_helpers]] / [connector_helpers](../../harness/connector_helpers.md): `MockClient`, `FakeSecretStore` {src:tests/scripts/connectors/test_connectors_hardening.py:24}.
- [[throwaway_home]] / [throwaway_home](../../harness/throwaway_home.md) {src:tests/scripts/connectors/test_connectors_hardening.py:25}.
- [[registry]] / [registry](../../../scripts/connectors/registry.md) and [[connect]] / [connect](../../../scripts/connectors/connect.md) {src:tests/scripts/connectors/test_connectors_hardening.py:26}.
- [[secret_store]] / [secret_store](../../../scripts/connectors/secret_store.md): `MacKeychainStore`, `SecretStoreError` and `check_name`, imported inside two tests {src:tests/scripts/connectors/test_connectors_hardening.py:162} {src:tests/scripts/connectors/test_connectors_hardening.py:184}.
- Import folders built from the file location: its own folder, `tests/harness`, `scripts` {src:tests/scripts/connectors/test_connectors_hardening.py:18-22}.

**Used by.** Searched with `git grep` for the file name, excluding `docs/` (2026-11-20). No product code names it.
- Found by the pattern `test_*.py` in the connectors runner {src:tests/scripts/connectors/run.sh:6}, called by the end-to-end runner for the area `connectors` {src:tests/system/run.sh:22-23}. See [[run]] / [run](run.md).
- Tests: no other test imports it.

## Behavior

The three classes make a throwaway home with the non-interactive flag on, a fake secret store and a mock client factory, and undo that afterwards {src:tests/scripts/connectors/test_connectors_hardening.py:32-43} {src:tests/scripts/connectors/test_connectors_hardening.py:97-108} {src:tests/scripts/connectors/test_connectors_hardening.py:145-155}. The name class sets no mock client.

**Class `Q06Credentials`** (the fake password is `hunter2-fakepw` {src:tests/scripts/connectors/test_connectors_hardening.py:28})
1. `test_q06_url_with_login_is_refused_and_not_echoed`: three addresses are tried: user and password, a lone user name, and an empty user with a password {src:tests/scripts/connectors/test_connectors_hardening.py:46-48}. For each, `connect on` returns 1, stderr says "user name or password", does not contain the password, the connector is not on, and nothing was saved to the store {src:tests/scripts/connectors/test_connectors_hardening.py:58-62}. The code refuses before any key or state is written {src:scripts/connectors/registry.py:367-372}; the error text never repeats the address {src:scripts/connectors/registry.py:86-88}; `main` prints it and returns 1 {src:scripts/connectors/connect.py:157-159}.
2. `test_q06_normal_address_still_accepted`: an address with `@` only in the query string passes the login check, and an https address with a port passes the address check {src:tests/scripts/connectors/test_connectors_hardening.py:64-66}. The login test looks at the parsed user name, password and the host part only {src:scripts/connectors/registry.py:82}.
3. `test_q06_check_address_refuses_login_without_echo`: `check_address` raises `ValueError` and the text does not contain the password {src:tests/scripts/connectors/test_connectors_hardening.py:68-71} {src:scripts/connectors/registry.py:94}.
4. `test_q06_status_hides_a_saved_login`: the connectors file is written by hand with a login in the address; `status` output must not contain the password {src:tests/scripts/connectors/test_connectors_hardening.py:73-80}. The code swaps such an address for a fixed text {src:scripts/connectors/connect.py:120-123}.

**Class `Q07MalformedFile`**
5. `BAD_FILES` lists sixteen contents: JSON of the wrong shape (a list, null, a string, a number), broken or empty text, and entries of the wrong type for the entry itself, `on`, `address` or `settings` {src:tests/scripts/connectors/test_connectors_hardening.py:83-93}.
6. `test_q07_no_traceback_for_any_malformed_file`: for each one (as a sub-test), the file is written and then these run: `is_on`, `get_settings`, `set_settings`, then `status`, `status fakeconn`, `off fakeconn`, and finally `on fakeconn` with a key on stdin, rewriting the bad content between steps {src:tests/scripts/connectors/test_connectors_hardening.py:115-131}. The last call must return 0 {src:tests/scripts/connectors/test_connectors_hardening.py:132}. An uncaught error in any step fails the sub-test, which is how "no traceback" is proven. The code reads the file defensively: bad JSON or a non-map gives an empty state {src:scripts/connectors/registry.py:274-278}, a non-map entry is dropped {src:scripts/connectors/registry.py:292-293}, and `on` is true only for the JSON value true {src:scripts/connectors/registry.py:295}.
7. `test_q07_wrong_typed_entry_reads_as_off`: entries `"str"`, `{"on": "yes"}` and `{"on": 1}` all read as off {src:tests/scripts/connectors/test_connectors_hardening.py:134-138} {src:scripts/connectors/registry.py:295}.

**Class `S5ConnectorName`** (nine bad names in `BAD_NAMES`: `my conn`, `-bad`, `a;b`, `a"b`, `a$(x)`, `../x`, an empty string, `UP` and `slack` followed by a newline {src:tests/scripts/connectors/test_connectors_hardening.py:141})
8. `test_s5_keychain_store_refuses_bad_name_before_security`: a Keychain store is built with a run function that fails the test if it is ever called. For every bad name, `set`, `get` and `delete` each raise `SecretStoreError`, and the run function is never called {src:tests/scripts/connectors/test_connectors_hardening.py:157-169}. The code checks the name when it builds the service name, before any program is started {src:scripts/connectors/secret_store.py:56} {src:scripts/connectors/secret_store.py:78} {src:scripts/connectors/secret_store.py:86} {src:scripts/connectors/secret_store.py:94}.
9. `test_s5_connect_on_and_off_refuse_bad_name_and_write_nothing`: for `my conn`, `a;b` and `a"b`, `connect on` (key on stdin) and `connect off` both return 1, stderr holds `connector name`, and the connectors file reads as empty afterwards {src:tests/scripts/connectors/test_connectors_hardening.py:171-181}. The code checks the name in `turn_on` and `turn_off` {src:scripts/connectors/registry.py:366} {src:scripts/connectors/registry.py:384}, the error is caught in `main` and printed {src:scripts/connectors/connect.py:157-159}, and its text starts with `a connector name` {src:scripts/connectors/secret_store.py:50}.
10. `test_s5_plain_names_still_accepted`: `fakeconn`, `databricks` and `my-conn_2` pass `check_name` {src:tests/scripts/connectors/test_connectors_hardening.py:183-186}.

## Diagram

None: both classes use the same short fixture and call one command at a time.

## Notes

- **Name check gaps.** `BAD_NAMES` now holds a name with a trailing newline, which the pattern (anchored with `\A` and `\Z`) refuses {src:scripts/connectors/secret_store.py:44}. It has no name over 64 characters, and no value that is not a string (searched this file, 2026-11-20). The name tests do not run `SecretToolStore`, whose service name also goes through `check_name` {src:scripts/connectors/secret_store.py:102}. The first-use path in `connect.first_use` is not run with a bad name {src:scripts/connectors/connect.py:38}. In test 9 the only assertion on the message is that it holds the words `connector name` {src:tests/scripts/connectors/test_connectors_hardening.py:180}.
- **Code and description.** The docstring says a web address with a login "is refused without echoing the password" and a bad file "never causes a traceback" {src:tests/scripts/connectors/test_connectors_hardening.py:2-8}. Both are what the cases check. The docstring names only these two checks, so the connector name class is not described in it {src:tests/scripts/connectors/test_connectors_hardening.py:2-3}. The change log has one dated line, `2026-11-18`, where the sibling test files say only "First version" {src:tests/scripts/connectors/test_connectors_hardening.py:10}.
- **Weak check.** Case 4 asserts only that the password is absent from the output {src:tests/scripts/connectors/test_connectors_hardening.py:80}. It would also pass if `status` printed nothing at all; it does not check for the replacement text {src:scripts/connectors/connect.py:123}.
- **Gaps.** Case 6 tests only the file `fakeconn` in several broken shapes. It does not check what is left in the file afterwards beyond the final return code. A login in the address given to the first-use prompt path is not tested here (the code checks it {src:scripts/connectors/connect.py:48-50}).
- **Environment handling.** The test sets and removes the one variable `TG_Q06_KEY` itself, inside a `try` and `finally` {src:tests/scripts/connectors/test_connectors_hardening.py:52-57}. It does not wipe the whole environment as the sibling file does.
- **Unchecked inputs.** The tests pass fixed strings. In the code under test, the connectors file path comes from `TOLLGATE_CONNECTORS` with no check {src:scripts/connectors/registry.py:264-268}.
- **Writes to a shared file.** The code under test writes the connectors file with a plain `write_text`, no temp file, no lock {src:scripts/connectors/registry.py:318}. The tests write the file by hand with `write_text` {src:tests/scripts/connectors/test_connectors_hardening.py:113} inside the throwaway home only.
- **Machine and version dependence.** None found: no machine path, and only standard library calls.
