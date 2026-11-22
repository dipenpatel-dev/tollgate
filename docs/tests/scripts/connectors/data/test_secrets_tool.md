---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/data/test_secrets_tool.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/data/secrets_tool.py, scripts/connectors/secret_store.py, scripts/connectors/registry.py]         # source files under test, relative paths from repo root
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

Tests for the secrets tool, a small command that lists, sets, deletes and cleans up named secrets in the user's own secret store. The point of the file is to prove that a secret value never shows up in output, in any file, or in a command argument list; that an empty value, a bad name, or a connector's own key name is refused; that cleanup does nothing without a confirm flag; and that with no secret store every command refuses and nothing is written.

## Dependencies

**Depends on.**
- Under test: [[secrets_tool]] / [secrets_tool](../../../../scripts/connectors/data/secrets_tool.md) imported as `st` {src:tests/scripts/connectors/data/test_secrets_tool.py:28}; [[registry]] / [registry](../../../../scripts/connectors/registry.md) and [[secret_store]] / [secret_store](../../../../scripts/connectors/secret_store.md) {src:tests/scripts/connectors/data/test_secrets_tool.py:27}.
- Test helpers: [[connector_helpers]] / [connector_helpers](../../../harness/connector_helpers.md) for `FakeSecretStore` {src:tests/scripts/connectors/data/test_secrets_tool.py:25}; [[throwaway_home]] / [throwaway_home](../../../harness/throwaway_home.md) {src:tests/scripts/connectors/data/test_secrets_tool.py:26}.
- Standard library: `contextlib`, `io`, `os`, `pathlib`, `subprocess`, `sys`, `unittest`, `uuid` {src:tests/scripts/connectors/data/test_secrets_tool.py:11-18}.

**Used by.** Run by [[run]] / [run](run.md) through the pattern `test_*.py` {src:tests/scripts/connectors/data/run.sh:6}. `git grep` for `test_secrets_tool` outside `docs/` finds no reference (searched 2026-11-20).

## Behavior

Fixtures. `Base.setUp` makes a throwaway home, copies the environment, and installs a fake secret store {src:tests/scripts/connectors/data/test_secrets_tool.py:34-41}. `run_tool` calls the tool's `main` in process with the given arguments, text for standard input and the throwaway environment, catches `SystemExit`, and returns the exit code with the captured output and error text {src:tests/scripts/connectors/data/test_secrets_tool.py:49-56}. `set_it` runs `set <name> --stdin` with a fake value {src:tests/scripts/connectors/data/test_secrets_tool.py:58-59}. The value is `tgfake-` plus a random hex string, new for each test {src:tests/scripts/connectors/data/test_secrets_tool.py:41}.

`TestTool` (twelve tests):
1. `test_set_stores_value_and_prints_no_value`: exit 0, the store holds the value, the value is not in output or error text, and the output says `alpha: saved` {src:tests/scripts/connectors/data/test_secrets_tool.py:63-68}. The tool prints only the name {src:scripts/connectors/data/secrets_tool.py:121}.
2. `test_list_names_only`: after two sets, `list` prints the two names in order and no value {src:tests/scripts/connectors/data/test_secrets_tool.py:70-76}; the names come from an index file, sorted {src:scripts/connectors/data/secrets_tool.py:65}.
3. `test_no_value_in_any_file`: after a set, no readable file under the repo root or the home folder contains the value, and the names-only index file exists and holds `alpha` {src:tests/scripts/connectors/data/test_secrets_tool.py:78-92}. It calls the private helper `_index_path` {src:tests/scripts/connectors/data/test_secrets_tool.py:90}.
4. `test_value_cannot_be_an_argument`: `set alpha <value>` exits 2, prints no value, and stores nothing {src:tests/scripts/connectors/data/test_secrets_tool.py:94-98}. The tool exits 2 on any extra word and does not echo it {src:scripts/connectors/data/secrets_tool.py:164-169}.
5. `test_value_reaches_store_not_argv`: with the Linux style store and a fake runner, the value is in the `input` of the call and not in the argument list {src:tests/scripts/connectors/data/test_secrets_tool.py:100-110}. The store passes the value as `input` {src:scripts/connectors/secret_store.py:105-107}.
6. `test_empty_value_refused`: a blank line on standard input exits 1 with `empty` in the error and nothing stored {src:tests/scripts/connectors/data/test_secrets_tool.py:112-116}; see {src:scripts/connectors/data/secrets_tool.py:116-117}.
7. `test_no_terminal_without_stdin_flag_refuses`: `set alpha` with no flag exits 1 and the error names `--stdin` {src:tests/scripts/connectors/data/test_secrets_tool.py:118-121}. The throwaway environment sets the non-interactive switch {src:tests/harness/throwaway_home.py:44}, which makes `interactive` return false {src:scripts/connectors/registry.py:410-411}, so the tool takes the no-terminal branch {src:scripts/connectors/data/secrets_tool.py:115}.
8. `test_bad_name_refused`: names with a space, a slash, and 65 characters exit 1 {src:tests/scripts/connectors/data/test_secrets_tool.py:123-126}; the pattern allows letters, digits, dot, dash and underscore, 1 to 64 long {src:scripts/connectors/data/secrets_tool.py:34}.
9. `test_delete`: delete removes the value from the store and the name from `list` {src:tests/scripts/connectors/data/test_secrets_tool.py:128-133}.
10. `test_cleanup_needs_confirm`: cleanup without `--confirm` exits 1, deletes nothing and prints `would delete`; with `--confirm` it deletes only the named secret {src:tests/scripts/connectors/data/test_secrets_tool.py:135-144}; see {src:scripts/connectors/data/secrets_tool.py:141-144}.
11. `test_cleanup_deletes_only_named`: one of two secrets stays, in the store and in `list` {src:tests/scripts/connectors/data/test_secrets_tool.py:146-151}.
12. `test_connector_key_names_are_protected`: with a connector entry saved as on, `delete` and `cleanup` of that name exit 1, the error mentions `connect.py`, and the stored value is unchanged {src:tests/scripts/connectors/data/test_secrets_tool.py:153-160}; see {src:scripts/connectors/data/secrets_tool.py:91-93}.

`TestNoStore` (two tests):
1. `test_every_command_refuses_in_process`: with the refusing store, `list`, `set`, `delete` and `cleanup` each exit 1, print `plain file` in the error and no value, and no index file is created {src:tests/scripts/connectors/data/test_secrets_tool.py:164-172}. The refusing message holds those words {src:scripts/connectors/secret_store.py:142-144}, and each command asks for the store before it changes anything {src:scripts/connectors/data/secrets_tool.py:97} {src:scripts/connectors/data/secrets_tool.py:108} {src:scripts/connectors/data/secrets_tool.py:127} {src:scripts/connectors/data/secrets_tool.py:138}.
2. `test_subprocess_with_no_tools_refuses_and_writes_nothing`: the tool script runs as a real process with an empty `PATH`; it exits 1, says `no secret store`, prints no value, and writes no index {src:tests/scripts/connectors/data/test_secrets_tool.py:174-181}. The default store looks for `security` or `secret-tool` on the path and falls back to the refusing store {src:scripts/connectors/secret_store.py:156-162}.

## Diagram

<!-- Skipped: two setups only (fake store in process, no tools in a subprocess); a picture adds nothing. -->

## Notes

- **Code and description.** The header says the file proves "list shows names only, set never echoes, a missing secret store refuses with no plain-file fallback, and cleanup needs --confirm" {src:tests/scripts/connectors/data/test_secrets_tool.py:6-7}. Each part has a test. The `Date:` field is empty {src:tests/scripts/connectors/data/test_secrets_tool.py:5}. The tool's own header says that with no secret store "every command refuses" {src:scripts/connectors/data/secrets_tool.py:17}. For `set` the name is checked before the store {src:scripts/connectors/data/secrets_tool.py:107-108}, so a bad name is reported first; the test uses a good name, so this order is not tested.
- **Test that cannot fail.** In `test_bad_name_refused` the empty name is never run: the line is `... if bad else (1, "", "")`, which gives the expected result 1 by itself for an empty string {src:tests/scripts/connectors/data/test_secrets_tool.py:125}. Only three of the four listed names reach the tool.
- **Tests that depend on the machine or the Python version.**
  - `test_subprocess_with_no_tools_refuses_and_writes_nothing` needs `shutil.which` to find nothing when `PATH` is the empty string; on Python 3.12 here it returns `None` (checked 2026-11-20), but the test does not guard against another version or system {src:tests/scripts/connectors/data/test_secrets_tool.py:175}. It also runs the real interpreter {src:tests/scripts/connectors/data/test_secrets_tool.py:176}.
  - `test_no_value_in_any_file` walks every file under the repo root and the home folder and skips any it cannot open {src:tests/scripts/connectors/data/test_secrets_tool.py:81-89}.
  - The test calls the private helper `_index_path`, so renaming it breaks the test {src:tests/scripts/connectors/data/test_secrets_tool.py:90} {src:tests/scripts/connectors/data/test_secrets_tool.py:172}.
- **Not tested (product code the tests drive).**
  - The index folder comes from `TOLLGATE_STATE_DIR` and is used as a file path with no check on its value {src:scripts/connectors/data/secrets_tool.py:51-53}.
  - The macOS store refuses a value with a quote, backslash or line break, but no test sends one {src:scripts/connectors/secret_store.py:72-75}.
  - A secret name is checked against the name pattern before it is used {src:scripts/connectors/data/secrets_tool.py:78-81}; the value is not checked beyond being non-empty {src:scripts/connectors/data/secrets_tool.py:116}.
- **Writes to shared files.** The tests write only in the throwaway home. The product's index file is written with `write_text` and then `chmod 600`, so it is not atomic and briefly has the default permissions {src:scripts/connectors/data/secrets_tool.py:71-73}. The index is read, changed in memory and written back with no lock {src:scripts/connectors/data/secrets_tool.py:120}, so two `set` commands at once could lose a name. No test covers two writers.
