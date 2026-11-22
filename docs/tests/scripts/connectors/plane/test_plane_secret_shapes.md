---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_secret_shapes.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/plane_sync_settings.py, scripts/connectors/plane/plane_comment_builder.py]         # source files under test, relative paths from repo root
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

Tests for two of the built-in secret patterns of the Plane connector: the shape of a Plane API key and a JSON member that holds a credential. The connector refuses to send text that matches a pattern, so these tests prove each pattern catches the real shape and leaves short or placeholder values alone. All sample keys are obviously fake and are built from pieces at run time so the file itself does not hold a key-shaped string.

## Dependencies

**Depends on.**
- `find_secret_pattern` from [[plane_comment_builder]] ([plane_comment_builder](../../../../scripts/connectors/plane/plane_comment_builder.md)) {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:14} {src:scripts/connectors/plane/plane_comment_builder.py:31}.
- `DEFAULT_SECRET_PATTERNS` from [[plane_sync_settings]] ([plane_sync_settings](../../../../scripts/connectors/plane/plane_sync_settings.md)) {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:15} {src:scripts/connectors/plane/plane_sync_settings.py:24}.
- `plane_sync_test_support` from [[plane_sync_test_support]] ([plane_sync_test_support](plane_sync_test_support.md)), imported only to put the scripts folder on the module path {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:10} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:29-31}.
- Standard library: `re`, `unittest` {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:11-12}.

**Used by.**
- Product code: none. Tests are not imported by product code (searched with `git grep` for the file name outside `docs/`, 2026-11-20).
- Tests (runner): `tests/scripts/connectors/plane/run.sh` finds it with the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}.

## Behavior

**Sample builders.** `fake_plane_key` joins three pieces into `plane_api_` followed by 25 fake characters {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:18-19}. `fake_member` builds a JSON object with one member, by default with the value `FAKE` repeated six times (24 characters) {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:22-23}.

**Test cases.**
- **Plane key shape.** The `plane_api_key` pattern matches text that contains the fake key after a header-like prefix. It does not match the prefix alone and does not match `plane_api_short` {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:27-31}. The pattern asks for `plane_api_` plus at least 20 letters or digits {src:scripts/connectors/plane/plane_sync_settings.py:35}.
- **JSON quoted members.** The `json_quoted_secret` pattern matches a member named `api_key`, `apikey`, `token`, `secret`, `access_token`, `client_secret` or `API_KEY` with the 24-character value {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:33-36}. The pattern is case insensitive and asks for a value of 20 or more allowed characters {src:scripts/connectors/plane/plane_sync_settings.py:36-39}.
- **No match.** A 5-character value, a value in angle brackets (`<your token here>`), and a member with the harmless name `name` and a long value are all left alone {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:38-42}.
- **Whole function.** `find_secret_pattern` with the default set returns a hit for a note holding the fake Plane key and for a JSON member `api_key` {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:44-46}.

## Diagram

None: these are plain unit tests with no fixtures or mocks.

## Notes

- **Description versus code.** The header says the default patterns "match the Plane key shape and a JSON quoted credential member, and leave short or placeholder values alone" {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:2}. That matches the tests. The header Scope line says keys are built at run time from parts {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:5}; this is true for the Plane key {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:19} and the JSON value is a repeated word {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:22}.
- **Name list gap.** The pattern also allows `api_token` as a member name {src:scripts/connectors/plane/plane_sync_settings.py:37}, but the test does not try that name {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:35}.
- **Weak check.** `test_find_secret_pattern_blocks_both_shapes` only checks the result is not `None`, so it does not prove which pattern fired. Another pattern (for example the named assignment pattern) could be the one that matched {src:tests/scripts/connectors/plane/test_plane_secret_shapes.py:44-46}.
- **Machine and version dependence.** None found: no paths, no clock and no newer syntax. The test does depend on the pattern text in the settings module, so a deliberate change to a pattern breaks it by design.
- **Unchecked inputs.** All strings are fixed in the file. No input reaches a file path, shell command or network address.
- **Shared file writes.** None; the file writes nothing.
