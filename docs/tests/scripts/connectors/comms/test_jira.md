---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/connectors/comms/test_jira.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/connectors/comms/jira_connector.py"]         # source files under test, relative paths from repo root
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

Tests for the tracker connector that pulls recently updated tickets into a cache file. One group proves the shared "off until first use" rules for the connector (the four CON cases). A second group proves what the puller does with a ticket search: page through results, keep only a few fields, stop at a size cap, drop records that contain personal identifiers, replace secrets inside kept records with a labeled marker and count them by label, and never print or log ticket titles.

## Dependencies

**Depends on.**
- `scripts/connectors/comms/jira_connector.py`, the code under test: [[jira_connector]] and [jira_connector](../../../../scripts/connectors/comms/jira_connector.md) {src:tests/scripts/connectors/comms/test_jira.py:18}
- `tests/scripts/connectors/comms/comms_base.py`, which supplies `Base`, `RoutedClient`, `make_con_tests`, `FAKE_ADDRESS`, `ROOT` and the two fake secret builders `fake_slack_token` and `fake_credential` {src:tests/scripts/connectors/comms/test_jira.py:16-17}. [[comms_base]] and [comms_base](comms_base.md)
- The mock client and fake secret store from the harness: [[connector_helpers]] and [connector_helpers](../../../harness/connector_helpers.md), and the throwaway home: [[throwaway_home]] and [throwaway_home](../../../harness/throwaway_home.md), both reached through `comms_base.py` {src:tests/scripts/connectors/comms/comms_base.py:25-26}
- Standard library: `base64`, `json`, `pathlib`, `unittest` {src:tests/scripts/connectors/comms/test_jira.py:11-14}; `pathlib` is also reached inline in one older case {src:tests/scripts/connectors/comms/test_jira.py:121}

**Used by.**
- Product code: none. Searched with `git grep` for `test_jira` and `tests/scripts/connectors` outside `docs/` (2026-11-20); only test files and the two runner scripts below name this area.
- Tests (runners): `tests/scripts/connectors/comms/run.sh` finds it by the pattern `test_*.py` {src:tests/scripts/connectors/comms/run.sh:6}, and `tests/system/run.sh` runs that script for the area `connectors/comms` {src:tests/system/run.sh:22-23}.

## Behavior

**Shared setup.** `JiraBase` binds the test to the connector name `jira` and the imported module {src:tests/scripts/connectors/comms/test_jira.py:46-48}. Its `setUp` makes the mock client answer with one issue on one page {src:tests/scripts/connectors/comms/test_jira.py:54-56}. The `pages()` helper gives one batch per call and sets `nextPageToken` to `tok<n+1>` on every page except the last {src:tests/scripts/connectors/comms/test_jira.py:31-43}. The base class reloads the connector module before every test, swaps in the mock http client and a fake secret store, and runs inside a throwaway home {src:tests/scripts/connectors/comms/comms_base.py:62-72}.

**The four CON cases.** `TestCon` is built by `make_con_tests` with an empty argument list {src:tests/scripts/connectors/comms/test_jira.py:59-60}. The factory defines five tests:
- Not set up: the run exits non-zero, stderr says `jira: not set up` and names `connect.py on jira`, no http call is made and no connectors file is created {src:tests/scripts/connectors/comms/comms_base.py:131-138}.
- Same check through a real subprocess exit code {src:tests/scripts/connectors/comms/comms_base.py:140-145}.
- First use: the fake store was asked to store the key, and the key text appears in no file under the repo root or the throwaway home {src:tests/scripts/connectors/comms/comms_base.py:147-161}.
- After a simulated restart (factories cleared, module reloaded) the connector still runs and reaches the client; here that means exactly one call to `/rest/api/3/search/jql` {src:tests/scripts/connectors/comms/comms_base.py:166-176} {src:tests/scripts/connectors/comms/test_jira.py:50-52}.
- Turning it off removes the stored key and returns to "not set up" {src:tests/scripts/connectors/comms/comms_base.py:178-187}.

**Puller cases (`TestJira`).**
1. Cache format: the run writes `.tollgate/cache/jira.json` whose `_meta` has exactly `pulled_at`, `result`, `reason`, `reject_count`; the first record has only the six projected fields; the text `emailAddress` appears nowhere in the file {src:tests/scripts/connectors/comms/test_jira.py:64-74}. This matches the projection, which keeps the display name only {src:scripts/connectors/comms/jira_connector.py:62-66}.
2. Paging: with three pages the connector makes three calls and the second request body carries `nextPageToken` equal to `tok1` {src:tests/scripts/connectors/comms/test_jira.py:76-83}. The code that does this is the loop in `fetch` {src:scripts/connectors/comms/jira_connector.py:98-114}.
3. Query flag: `--jql` is sent as the `jql` field of the request body, unchanged {src:tests/scripts/connectors/comms/test_jira.py:85-88} {src:scripts/connectors/comms/jira_connector.py:79}.
4. Auth header: a key with a colon goes out as `Basic` plus base64 of the whole key; after the store entry is replaced by a plain token it goes out as `Bearer` {src:tests/scripts/connectors/comms/test_jira.py:90-101} {src:scripts/connectors/comms/jira_connector.py:73-76}.
5. Size cap: the test lowers `MAX_TOTAL` to 2, serves three issues, and expects result `degraded` with 2 records; it restores the old value in a `finally` block {src:tests/scripts/connectors/comms/test_jira.py:103-114} {src:scripts/connectors/comms/jira_connector.py:107-108}.
6. Bad shape: `issues` set to a string gives exit code 0, no cache file, and `schema_invalid` in the run log {src:tests/scripts/connectors/comms/test_jira.py:116-122}. The code returns a failed result with that reason {src:scripts/connectors/comms/jira_connector.py:90-92}, and the writer skips the cache on failure while still returning 0 on purpose {src:scripts/connectors/comms/comms_common.py:105-107} {src:scripts/connectors/comms/comms_common.py:114}.
7. Wrong nested type: `project_issue` returns `None` when `status` is a string or when `fields` is missing {src:tests/scripts/connectors/comms/test_jira.py:124-128} {src:scripts/connectors/comms/jira_connector.py:53-60}.
8. Identifier drop: a record whose summary holds a number in social-security format is removed; the cache then shows `reject_count` 1, result `degraded`, one record left {src:tests/scripts/connectors/comms/test_jira.py:130-138}. The pattern is `SSN_PATTERN` {src:scripts/cache/phi_guard.py:19} and `classify` maps a rejection to a degraded result {src:scripts/connectors/comms/jira_connector.py:127-128}.
9. Secret redaction: two issues carry a fake chat token and a fake `password=` value in their summaries {src:tests/scripts/connectors/comms/test_jira.py:142-143}. After a run the cached summaries read `see [REDACTED:SLACK_TOKEN] now` and `login [REDACTED:CREDENTIAL] ok` {src:tests/scripts/connectors/comms/test_jira.py:149-150}, the printed line holds `2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)` {src:tests/scripts/connectors/comms/test_jira.py:151}, and neither secret value is in the cache file, the output, the error text or the run log {src:tests/scripts/connectors/comms/test_jira.py:152-153}. The code under test redacts the kept records after `classify` and passes the tally to the finish step {src:scripts/connectors/comms/jira_connector.py:148-150}.
10. Privacy: a unique marker in a title is absent from stdout, stderr and the run log, and stdout contains `1 records` {src:tests/scripts/connectors/comms/test_jira.py:155-160}. The only printed line is built from counts and the secret count by label {src:scripts/connectors/comms/comms_common.py:111-113}.
11. Dry run: after turning the connector on, `--dry-run` makes no http call and writes the two fixture records {src:tests/scripts/connectors/comms/test_jira.py:162-167}. The connector still calls `ensure` before the dry-run branch, so a dry run needs the connector on {src:scripts/connectors/comms/jira_connector.py:137-142}.
12. Error status: a 503 reply whose body holds the marker gives `api_5xx` in the log and no marker in any output {src:tests/scripts/connectors/comms/test_jira.py:169-180} {src:scripts/connectors/comms/comms_common.py:117-122}.

## Diagram

None: the fixtures are one mock client with a handler function and a fake secret store, which the Behavior section already describes in full.

## Notes

- Description versus coverage: the header says the file covers "caps" in the plural {src:tests/scripts/connectors/comms/test_jira.py:3}. Only the total-record cap is tested. The page cap `MAX_PAGES` {src:scripts/connectors/comms/jira_connector.py:36} and the "token missing on a non-last page" failure {src:scripts/connectors/comms/jira_connector.py:112-113} have no test (searched this file, 2026-11-20).
- Unused import: `ROOT` is imported {src:tests/scripts/connectors/comms/test_jira.py:16} and not used anywhere else in the file (read all 184 lines, 2026-11-20).
- Weak assertion: the dry-run case counts records only (`len == 2`) and does not check their content, so a changed fixture text would not fail it {src:tests/scripts/connectors/comms/test_jira.py:167}.
- Machine and version dependence: the cache and log paths are rebuilt from `self.home` as `.tollgate/cache/jira.json` and `.tollgate/logs/run_log.jsonl` {src:tests/scripts/connectors/comms/test_jira.py:68} {src:tests/scripts/connectors/comms/comms_base.py:113}. They match the product only because the test sets `HOME` and the path loader expands `~` {src:scripts/core/paths.py:93-94}. The run log uses `fcntl`, so the suite runs on POSIX systems only {src:scripts/cache/run_log.py:13}. No Python-version check in this file.
- Shared global state: the size-cap test patches a module constant {src:tests/scripts/connectors/comms/test_jira.py:104-111}; the module is reloaded in `setUp`, which resets it {src:tests/scripts/connectors/comms/comms_base.py:63-64}. The error-status test replaces the registry http factory in the middle of the test {src:tests/scripts/connectors/comms/test_jira.py:175-176}; `tearDown` clears it {src:tests/scripts/connectors/comms/comms_base.py:74-77}.
- Inputs without a check: the `--jql` text goes into the request body unchecked {src:scripts/connectors/comms/jira_connector.py:79}, and this test sends a plain string to prove it passes through {src:tests/scripts/connectors/comms/test_jira.py:87-88}. The test address is the fixed placeholder `https://api.example.invalid` {src:tests/scripts/connectors/comms/comms_base.py:29}. Only the CON tests block the network with `assert_no_network` {src:tests/scripts/connectors/comms/comms_base.py:132}; the puller cases rely on the mock client being swapped in {src:tests/scripts/connectors/comms/comms_base.py:71}.
- Shared-file writes: the tests write only inside the throwaway home. The cache write is atomic through a temp file and `os.replace` {src:scripts/cache/cache_write.py:24-30}. The log append takes an exclusive lock {src:scripts/cache/run_log.py:90}. Nothing stops two cache writers racing on the same name except the process id in the temp file name {src:scripts/cache/cache_write.py:24}.
- The first CON-02 test walks the whole repo tree (skipping `.git` only) and reads every file, so it is slow in a checkout that holds a virtual environment {src:tests/scripts/connectors/comms/comms_base.py:153-161}.
