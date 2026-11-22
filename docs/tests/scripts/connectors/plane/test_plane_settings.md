---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_settings.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/plane_sync_settings.py, scripts/connectors/plane/plane_sync_settings.example.json]         # source files under test, relative paths from repo root
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

Tests for the settings file of the Plane connector. They check that the example file shipped with the repo loads and gives the expected values, that a bad or missing key raises an error that names only the key, that the built-in secret patterns are the default, that the example holds no address and no key, and where the settings file is looked for.

## Dependencies

**Depends on.**
- `PlaneSyncConfigError`, `default_settings_path`, `load_settings` from [[plane_sync_settings]] ([plane_sync_settings](../../../../scripts/connectors/plane/plane_sync_settings.md)) {src:tests/scripts/connectors/plane/test_plane_settings.py:16-20}.
- `EXAMPLE_SETTINGS` (the path of `scripts/connectors/plane/plane_sync_settings.example.json`) from [[plane_sync_test_support]] ([plane_sync_test_support](plane_sync_test_support.md)) {src:tests/scripts/connectors/plane/test_plane_settings.py:21} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:42}.
- `plane_sync_test_support` is also imported for its side effect of putting the scripts folder on the module path {src:tests/scripts/connectors/plane/test_plane_settings.py:10}.
- Standard library: `json`, `tempfile`, `unittest`, `pathlib` {src:tests/scripts/connectors/plane/test_plane_settings.py:11-14}.

**Used by.**
- Product code: none. Tests are not imported by product code (searched with `git grep` for the file name outside `docs/`, 2026-11-20).
- Tests (runner): `tests/scripts/connectors/plane/run.sh` finds it with the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}.

## Behavior

**Helper.** `_variant` loads the example JSON, lets the test change it, writes the result to `variant.json` in a temp folder and returns that path; the folder is removed at cleanup {src:tests/scripts/connectors/plane/test_plane_settings.py:25-32}.

**Test cases.**
- **Example loads.** Loading the example with an empty environment gives source name `tollgate`, pause between calls 1.2 seconds, page size 100, comment limit 15000, board status `Backlog`, a `T` prefix row with project key `T`, number width 3 and pattern `^T-(\d+)$`, a map entry from the blocked word to `Waiting`, and one blocked word {src:tests/scripts/connectors/plane/test_plane_settings.py:34-45}. The example file holds those values {src:scripts/connectors/plane/plane_sync_settings.example.json:4} {src:scripts/connectors/plane/plane_sync_settings.example.json:6} {src:scripts/connectors/plane/plane_sync_settings.example.json:16} {src:scripts/connectors/plane/plane_sync_settings.example.json:25-29}. The pattern `^T-(\d+)$` is not in the file, so it is a code default {src:scripts/connectors/plane/plane_sync_settings.py:118-127}.
- **Default secret patterns.** With no `secret_patterns` key in the file, the loaded settings carry exactly ten named patterns, listed sorted in the test {src:tests/scripts/connectors/plane/test_plane_settings.py:47-53}. The code falls back to the built-in dictionary when the key is absent {src:scripts/connectors/plane/plane_sync_settings.py:184}.
- **No address or key in the example.** The lower-cased example text must not contain `http:`, `https:`, `token`, `api_key`, `secret` or `password` {src:tests/scripts/connectors/plane/test_plane_settings.py:55-58}.
- **Settings path.** With `TOLLGATE_PATHS` set to `/somewhere/cfg/paths.yaml` the settings file is `/somewhere/cfg/plane-sync.json`; with the variable missing, a config error is raised {src:tests/scripts/connectors/plane/test_plane_settings.py:60-64}. The code takes the parent folder of the paths file and adds the file name {src:scripts/connectors/plane/plane_sync_settings.py:87-90}.
- **Prefix from the environment.** With `prefix_table` removed, a `TOLLGATE_TICKET_PREFIX` of `QQ` gives a one-row table for `QQ`; with no variable, the error text is exactly `prefix_table` {src:tests/scripts/connectors/plane/test_plane_settings.py:66-73}. The code reads the variable only when the table is missing {src:scripts/connectors/plane/plane_sync_settings.py:132-137}.
- **Missing required key.** Removing `workspace_slug`, `new_ticket_board_status` or `status_map` raises an error whose text equals the key name {src:tests/scripts/connectors/plane/test_plane_settings.py:75-80}.
- **Wrong type.** `page_size` set to text raises an error naming `page_size` {src:tests/scripts/connectors/plane/test_plane_settings.py:82-86}. A boolean for `min_seconds_between_calls` is refused {src:tests/scripts/connectors/plane/test_plane_settings.py:88-91}; the code excludes booleans from numbers {src:scripts/connectors/plane/plane_sync_settings.py:97-98}.
- **Bad status map entry.** A status entry whose value is the number 5 raises an error naming `status_map` {src:tests/scripts/connectors/plane/test_plane_settings.py:93-97}.
- **Missing or broken file.** A path that does not exist, and a file holding `{not json`, both raise a config error {src:tests/scripts/connectors/plane/test_plane_settings.py:99-107}.

## Diagram

None: these tests use one small helper and no mock chain.

## Notes

- **Description versus code.** The header says "no address or key lives in it" {src:tests/scripts/connectors/plane/test_plane_settings.py:2}. The test only looks for six words in the lower-cased example file {src:tests/scripts/connectors/plane/test_plane_settings.py:57}; it does not look for an address in any other form. The header Scope line says real HTTP goes to the local stub on `127.0.0.1` {src:tests/scripts/connectors/plane/test_plane_settings.py:5}; this file makes no HTTP call and starts no stub.
- **Side effect on the example file.** Adding a `secret_patterns` key to the example would put the word `token` into the file and fail the no-key test, even though it holds no key {src:tests/scripts/connectors/plane/test_plane_settings.py:57} {src:scripts/connectors/plane/plane_sync_settings.py:27}.
- **Weak assertion.** `test_bool_is_not_a_number` and the missing-file test check only that the error type is raised, not its text {src:tests/scripts/connectors/plane/test_plane_settings.py:90-91} {src:tests/scripts/connectors/plane/test_plane_settings.py:100-107}. The missing-file case relies on `/nonexistent/plane-sync.json` not existing on the machine {src:tests/scripts/connectors/plane/test_plane_settings.py:101}.
- **Machine and version dependence.** The path test compares against a POSIX path `/somewhere/cfg/plane-sync.json`, which would differ on Windows {src:tests/scripts/connectors/plane/test_plane_settings.py:62}. The `mutate` argument has no annotation, so no newer syntax is needed {src:tests/scripts/connectors/plane/test_plane_settings.py:25}.
- **Unchecked inputs.** All values are fixed in the file. The settings file path comes from the example constant or a temp folder {src:tests/scripts/connectors/plane/test_plane_settings.py:30}; no input reaches a shell command or network address.
- **Shared file writes.** The tests write `variant.json` and `plane-sync.json` only in temp folders removed at cleanup {src:tests/scripts/connectors/plane/test_plane_settings.py:28-31} {src:tests/scripts/connectors/plane/test_plane_settings.py:102-105}. The shipped example file is only read {src:tests/scripts/connectors/plane/test_plane_settings.py:26}.
- **Not covered.** No test sets a custom `secret_patterns` key, `template_path` or `external_source_name`, and none checks `http_timeout_seconds`; the example sets the last at 30 {src:scripts/connectors/plane/plane_sync_settings.example.json:27} and the code reads all of them {src:scripts/connectors/plane/plane_sync_settings.py:184-193}.
