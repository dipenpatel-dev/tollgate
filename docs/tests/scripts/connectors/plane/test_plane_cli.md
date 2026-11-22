---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_cli.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/cli.py, scripts/connectors/plane/vault_ticket_creator.py, scripts/connectors/plane/plane_sync_settings.py, scripts/core/paths.py]         # source files under test, relative paths from repo root
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

Tests for the plane command line: that `create` asks before it changes anything, that each kind of failure maps to its own exit code, that the key never leaks into output or files, and that settings and ticket folders are found through the shared path loader when no flags are given. All HTTP goes to the local stub on `127.0.0.1` {src:tests/scripts/connectors/plane/test_plane_cli.py:5}.

## Dependencies

**Depends on.**
- Under test: [[cli]] / [cli](../../../../scripts/connectors/plane/cli.md) {src:tests/scripts/connectors/plane/test_plane_cli.py:20}; [[plane_sync_ledger]] / [plane_sync_ledger](../../../../scripts/connectors/plane/plane_sync_ledger.md) for the error type {src:tests/scripts/connectors/plane/test_plane_cli.py:21}; [[paths]] / [paths](../../../../scripts/core/paths.md) for `get_path` {src:tests/scripts/connectors/plane/test_plane_cli.py:22}; [[registry]] / [registry](../../../../scripts/connectors/registry.md) {src:tests/scripts/connectors/plane/test_plane_cli.py:19}.
- Test support: [[plane_sync_test_support]] / [plane_sync_test_support](plane_sync_test_support.md) {src:tests/scripts/connectors/plane/test_plane_cli.py:24}; [[plane_stub_server]] / [plane_stub_server](plane_stub_server.md) {src:tests/scripts/connectors/plane/test_plane_cli.py:23}.
- Standard library: `contextlib`, `io`, `json`, `os`, `unittest`, `pathlib`, `unittest.mock` {src:tests/scripts/connectors/plane/test_plane_cli.py:11-17}.

**Used by.** Run by [[run]] / [run](run.md) through the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}. `git grep` for `test_plane_cli` outside `docs/` finds no other reference (searched 2026-11-20).

## Behavior

All classes inherit `CliCase`: a stub with five cards and five ticket folders, a throwaway home, a fake secret store and the connector switched on {src:tests/scripts/connectors/plane/plane_sync_test_support.py:176-190}. `run_cli` clears `lines` on each call {src:tests/scripts/connectors/plane/plane_sync_test_support.py:209-210}. `CREATE_ARGV` is a full create command without `--yes` {src:tests/scripts/connectors/plane/test_plane_cli.py:26-27}.

**`TestCreateConfirmation`** {src:tests/scripts/connectors/plane/test_plane_cli.py:30}
- `test_create_with_no_flag_and_no_terminal_refuses_and_calls_nothing` proves exit 2, one output line containing `pass --yes`, zero stub calls and no new ticket folder {src:tests/scripts/connectors/plane/test_plane_cli.py:31-36}. The code path is `_confirmed` returning false when there is no terminal {src:scripts/connectors/plane/cli.py:118-122}. The throwaway env sets `TOLLGATE_NONINTERACTIVE`, which makes `interactive` false {src:tests/scripts/connectors/plane/plane_sync_test_support.py:184} {src:scripts/connectors/registry.py:408-411}.
- `test_create_with_yes_runs_with_no_terminal` proves `--yes` gives exit 0, the exact line `created | T-6 | card 6`, a `T-6` folder, and no key in the output {src:tests/scripts/connectors/plane/test_plane_cli.py:38-42}. The line comes from `_finish_create` {src:scripts/connectors/plane/vault_ticket_creator.py:145}.
- `test_a_terminal_answer_of_yes_runs_it_and_the_question_comes_before_any_call` replaces `registry.interactive` with a function returning true, passes its own `confirm`, and records how many stub calls existed when the question was asked {src:tests/scripts/connectors/plane/test_plane_cli.py:44-52}. It proves one question, containing the title, asked at zero calls, then a successful create {src:tests/scripts/connectors/plane/test_plane_cli.py:53-56}. The question text is built in `_confirmed` {src:scripts/connectors/plane/cli.py:124-126}.
- `test_a_terminal_answer_of_no_or_blank_stops_with_no_call` loops over `n`, blank and `maybe`; each gives exit 2 and the line `stopped | create was not confirmed`; afterwards the stub saw no call at all {src:tests/scripts/connectors/plane/test_plane_cli.py:58-63}. Only `y` and `yes` count as a yes {src:scripts/connectors/plane/cli.py:48} {src:scripts/connectors/plane/cli.py:126-129}.
- `test_sync_and_drift_never_ask` runs `drift` with a `confirm` that records any question and checks none was recorded {src:tests/scripts/connectors/plane/test_plane_cli.py:65-69}.

**`TestExitCodes`** {src:tests/scripts/connectors/plane/test_plane_cli.py:72}
- `test_plane_failure_is_exit_3_with_one_line`: a stub 500 on `GET /projects/` gives exit 3 and the single line `stopped | GET projects/ failed: status 500 (unexpected status)` {src:tests/scripts/connectors/plane/test_plane_cli.py:73-76}. Code: `PlaneApiError` maps to `EXIT_PLANE` {src:scripts/connectors/plane/cli.py:40} {src:scripts/connectors/plane/cli.py:198-200}; the message text is built by the client {src:scripts/connectors/plane/plane_work_item_client.py:57} {src:scripts/connectors/plane/plane_work_item_client.py:165}.
- `test_guard_stop_is_exit_2`: a local folder `T-9` against a Plane highest of 5 stops with exit 2 and the line `stopped | Plane highest 5, local highest 9` {src:tests/scripts/connectors/plane/test_plane_cli.py:78-81}. Code: the number guard in the creator {src:scripts/connectors/plane/vault_ticket_creator.py:87-89}.
- `test_corrupt_ledger_error_is_exit_2` patches `run_create` to raise the ledger error and expects exit 2 and `stopped | x is not valid JSON` {src:tests/scripts/connectors/plane/test_plane_cli.py:83-86}. Code: {src:scripts/connectors/plane/cli.py:201-203}. This test never reads a real ledger; it proves only the mapping.
- `test_a_settings_problem_is_exit_1_naming_the_key` passes `settings=None`, so the command loads the default settings file, which does not exist in the throwaway home; expects exit 1 and a first line starting `stopped | settings problem: ` {src:tests/scripts/connectors/plane/test_plane_cli.py:88-90}. Code: {src:scripts/connectors/plane/cli.py:164-166} {src:scripts/connectors/plane/cli.py:207-209}.
- `test_unknown_command_is_exit_2` expects exit 2 from `nope` with stderr hidden {src:tests/scripts/connectors/plane/test_plane_cli.py:92-94}. The code returns the argument parser's own exit code {src:scripts/connectors/plane/cli.py:191-192}.
- `test_the_key_never_appears_in_output_or_files` runs a create that fails (POST 500), clears the rule, runs it again, then checks the output lines and every file under the tickets folder, the state folder and the throwaway home for the key bytes {src:tests/scripts/connectors/plane/test_plane_cli.py:96-105}.

**`TestPathLoaderUse`** {src:tests/scripts/connectors/plane/test_plane_cli.py:108}
- `test_settings_and_folders_are_found_without_flags` writes `plane-sync.json` next to the paths file {src:tests/scripts/connectors/plane/test_plane_cli.py:112-116}, sets the process environment to the throwaway one {src:tests/scripts/connectors/plane/test_plane_cli.py:117}, creates ticket `T-3` in the folder that `get_path("tickets")` returns {src:tests/scripts/connectors/plane/test_plane_cli.py:118-121}, and runs `sync T-3` with no roots or settings given {src:tests/scripts/connectors/plane/test_plane_cli.py:123}. It proves exit 0, a last line starting `synced`, a ledger file in the state folder, and a card description ending with `</p>` {src:tests/scripts/connectors/plane/test_plane_cli.py:124-127}. The file name matches the default {src:scripts/connectors/plane/plane_sync_settings.py:19} {src:scripts/connectors/plane/plane_sync_settings.py:90}; the folders come from `get_path` {src:scripts/connectors/plane/cli.py:133-135} {src:scripts/core/paths.py:119-132}; the description ends with a paragraph holding the state hash {src:scripts/connectors/plane/plane_ticket_syncer.py:109}.
- `test_the_settings_flag_wins_over_the_default_file` writes settings to a different file, passes `--settings`, and runs `drift zz-1` {src:tests/scripts/connectors/plane/test_plane_cli.py:129-136}. It proves exit 0 and the single line `skip | prefix zz has no Plane project in the settings` {src:tests/scripts/connectors/plane/test_plane_cli.py:137-138}. Code: the flag is read first {src:scripts/connectors/plane/cli.py:165} and an unmapped prefix gives a skip line with exit 0 {src:scripts/connectors/plane/vault_ticket_files.py:74-75}.

## Diagram

<!-- Skipped: the fixtures are a single inheritance chain (stub, ticket folders, throwaway home) described in plane_sync_test_support; no extra mock chain here. -->

## Notes

- **Name and code disagree:** `test_sync_and_drift_never_ask` runs only `drift` {src:tests/scripts/connectors/plane/test_plane_cli.py:68}. `sync` is never run, so the claim that sync never asks is untested. It also ignores the exit code.
- **Name and code disagree:** `test_a_settings_problem_is_exit_1_naming_the_key` asserts only the prefix of the line {src:tests/scripts/connectors/plane/test_plane_cli.py:90}. The loader names the settings file (`plane-sync.json`), not a key, when the file is missing {src:scripts/connectors/plane/plane_sync_settings.py:161-162}. The test depends on that default file being absent from the throwaway home.
- **Weak proof:** `test_the_settings_flag_wins_over_the_default_file` creates no default file, so it shows the flag is used, not that it beats an existing default {src:tests/scripts/connectors/plane/test_plane_cli.py:129-136}. The extra stub card added on line 134 is never reached, because the run stops at the skip line.
- **Weak proof:** `test_corrupt_ledger_error_is_exit_2` mocks `run_create`, so a real corrupt ledger is not exercised {src:tests/scripts/connectors/plane/test_plane_cli.py:84}. The key-leak test scans only the temp folders, not the repo or process memory {src:tests/scripts/connectors/plane/test_plane_cli.py:102}.
- **Machine and version dependence:** none on a machine path. The path-loader test changes the whole process environment for its duration with `mock.patch.dict` {src:tests/scripts/connectors/plane/test_plane_cli.py:117}, which is safe only while tests run one at a time. No Python-version-specific syntax found except `from __future__` in the support module.
- **Cannot fail:** no test is without an assertion. The weakest is the never-ask test, which fails only if a question is recorded.
- **Coverage gaps:** no test for `sync --extras`, `--from-start` or a multi-id `drift` at the command line level; those flags exist {src:scripts/connectors/plane/cli.py:90-93}. Other test files in the folder may cover them; this file does not.
