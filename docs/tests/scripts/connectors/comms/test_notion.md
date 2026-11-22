---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/connectors/comms/test_notion.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/connectors/comms/notion_connector.py"]         # source files under test, relative paths from repo root
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

Tests for the notes connector that saves one page, or one database, as a markdown note in the vault. One group proves the shared "off until first use" rules (the four CON cases). The other group proves how a page becomes markdown, where the note lands, what happens on a re-run, that a bad id is refused before any network call, that page titles are never printed or logged, that a title or line holding a personal id is not written to the note, that secrets in the title, file name and lines are replaced in place with a labeled marker and counted by label, and that dropped items are counted in the log and the printed line.

## Dependencies

**Depends on.**
- `scripts/connectors/comms/notion_connector.py`, the code under test: [[notion_connector]] and [notion_connector](../../../../scripts/connectors/comms/notion_connector.md) {src:tests/scripts/connectors/comms/test_notion.py:15}
- `tests/scripts/connectors/comms/comms_base.py` for `Base`, `make_con_tests`, `FAKE_ADDRESS` and the two fake secret builders `fake_slack_token` and `fake_credential` {src:tests/scripts/connectors/comms/test_notion.py:14}. [[comms_base]] and [comms_base](comms_base.md)
- The harness mock client, fake secret store and throwaway home, reached through `comms_base.py` {src:tests/scripts/connectors/comms/comms_base.py:25-26}: [[connector_helpers]] and [connector_helpers](../../../harness/connector_helpers.md), [[throwaway_home]] and [throwaway_home](../../../harness/throwaway_home.md)
- Standard library: `json`, `pathlib`, `unittest` {src:tests/scripts/connectors/comms/test_notion.py:10-12}

**Used by.**
- Product code: none. Searched with `git grep` for `test_notion` and `tests/scripts/connectors` outside `docs/` (2026-11-20).
- Tests (runners): `tests/scripts/connectors/comms/run.sh` finds it by the pattern `test_*.py` {src:tests/scripts/connectors/comms/run.sh:6}; `tests/system/run.sh` runs that script for the area `connectors/comms` {src:tests/system/run.sh:22-23}.

## Behavior

**Fake notes service.** `handler_for` builds the canned answers. A URL holding `/pages/` returns the page with a title property. A URL ending in `/query` under `/databases/` returns two rows. A plain `/databases/` URL returns a database title. A `/blocks/<id>/` URL returns the page blocks when the id is the page id, else the children given for that id {src:tests/scripts/connectors/comms/test_notion.py:31-53}. Its default page is a heading, a bullet and a checked to-do {src:tests/scripts/connectors/comms/test_notion.py:32-37}.

**Shared setup.** `NoteBase` names the connector `notion` and installs the handler {src:tests/scripts/connectors/comms/test_notion.py:56-62}. The first call must be a GET of `/pages/<PID>` at the fake address {src:tests/scripts/connectors/comms/test_notion.py:64-66}. The `notes()` helper lists `*.md` under the throwaway vault folder given {src:tests/scripts/connectors/comms/test_notion.py:68-70}; the vault is `<home>/vault` {src:tests/harness/throwaway_home.py:36}.

**The four CON cases.** `TestCon` passes `["page", PID]` as the working command line {src:tests/scripts/connectors/comms/test_notion.py:73-74}. The shared factory then checks: a not-set-up run exits non-zero with a message naming `connect.py on notion`, no call, no connectors file {src:tests/scripts/connectors/comms/comms_base.py:131-138}; the same through a subprocess {src:tests/scripts/connectors/comms/comms_base.py:140-145}; first use stores the key through the store and leaves it in no file {src:tests/scripts/connectors/comms/comms_base.py:147-161}; the connector survives a restart and reaches the client {src:tests/scripts/connectors/comms/comms_base.py:166-176}; turning it off returns to "not set up" {src:tests/scripts/connectors/comms/comms_base.py:178-187}.

**Note cases (`TestNotion`).**
1. Page to markdown: the default folder is `references`; the file is named `weekly-notes-abcd1234.md`; the text has `# Weekly notes`, `# Agenda`, `- item one` and `- [x] ship` {src:tests/scripts/connectors/comms/test_notion.py:77-88}. The name is the slug of the title plus the first eight characters of the id without dashes {src:scripts/connectors/comms/notion_connector.py:181}; `references` is the default for `--into` {src:scripts/connectors/comms/notion_connector.py:192}; the checkbox form comes from the `to_do` branch {src:scripts/connectors/comms/notion_connector.py:73-74}.
2. Into meetings: `--into meetings` puts one note in `meetings` and none in `references` {src:tests/scripts/connectors/comms/test_notion.py:90-94}.
3. Re-run: two runs for the same page leave one file {src:tests/scripts/connectors/comms/test_notion.py:96-100}. The writer overwrites the same path {src:scripts/connectors/comms/notion_connector.py:184}.
4. Nested blocks: a bullet marked as having children, with id `kid1`, makes the connector fetch the children and indent them by two spaces (`  - nested`) {src:tests/scripts/connectors/comms/test_notion.py:102-108}. The recursion and indent come from `blocks` and `block_to_md` {src:scripts/connectors/comms/notion_connector.py:121-125} {src:scripts/connectors/comms/notion_connector.py:70}.
5. Database: the note lists `- row a` and `- row b`, and the calls are exactly one GET then one POST {src:tests/scripts/connectors/comms/test_notion.py:110-116}. The code makes one GET for the database object and one POST to `/query` {src:scripts/connectors/comms/notion_connector.py:135-143}.
6. Headers: the first call carries `Bearer <key>` and the `Notion-Version` equal to the module constant `API_VERSION` {src:tests/scripts/connectors/comms/test_notion.py:118-123} {src:scripts/connectors/comms/notion_connector.py:94-96}. The test reads the constant from the module, so it cannot catch a wrong version string.
7. Bad id: `../x?y` makes the command exit non-zero and no http call happens {src:tests/scripts/connectors/comms/test_notion.py:125-129}. The id check runs before the connector is fetched {src:scripts/connectors/comms/notion_connector.py:194-196}.
8. Failure: a reply that is a list, not a map, writes no note and logs `schema_invalid` {src:tests/scripts/connectors/comms/test_notion.py:131-136}. The code turns a non-map body into that reason {src:scripts/connectors/comms/notion_connector.py:100-101}, and the run still returns 0 {src:scripts/connectors/comms/notion_connector.py:220}.
9. Privacy: a marker used as the page title is absent from stdout, stderr and the run log, while one note is still written {src:tests/scripts/connectors/comms/test_notion.py:178-183}. The printed line holds a result word, counts and secret labels only {src:scripts/connectors/comms/notion_connector.py:218-219}.
10. Personal ids: a page whose title holds `MRN 12345678` and whose blocks hold one line with `SSN 123-45-6789` and one `safe line` gives a note that has `safe line`, no `123-45-6789`, no `12345678`, and a file name without `12345678` {src:tests/scripts/connectors/comms/test_notion.py:138-148}. The code runs the title and then each body line through the privacy filter and drops what matches {src:scripts/connectors/comms/notion_connector.py:170} {src:scripts/connectors/comms/notion_connector.py:175}. A dropped title leaves an empty title, so the name uses `untitled` {src:scripts/connectors/comms/notion_connector.py:85} {src:scripts/connectors/comms/notion_connector.py:181}.

11. Secret redaction: a page whose title holds a fake chat token, with one line holding a fake `password=` value and one `safe line`, gives a note whose first heading is `# Notes [REDACTED:SLACK_TOKEN]`, which holds `- use [REDACTED:CREDENTIAL] here` and `safe line` {src:tests/scripts/connectors/comms/test_notion.py:152-162}. The printed line holds `2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)` {src:tests/scripts/connectors/comms/test_notion.py:163}. Neither secret value is in the note text, the note's file name, the output, the error text or the run log {src:tests/scripts/connectors/comms/test_notion.py:164-165}. The code redacts the title and each kept line after the privacy filter and before the file name is built {src:scripts/connectors/comms/notion_connector.py:179-181}.
12. Dropped items are counted: with the same personal-id page as case 10, the printed line holds `2 phi dropped` and the last run log record has a `reject_count` of 2, one for the title and one for the line {src:tests/scripts/connectors/comms/test_notion.py:168-176}. The code counts a dropped title and each dropped line and passes the total to the log and the print {src:scripts/connectors/comms/notion_connector.py:170-178} {src:scripts/connectors/comms/notion_connector.py:217-219}.

## Diagram

None: the only fixture is one handler function over a mock client, described in Behavior.

## Notes

- Code versus its description, id message: the refusal text says the id "must be letters, digits and dashes only" {src:scripts/connectors/comms/notion_connector.py:195}, but the pattern accepts only hex digits and dashes, 8 to 64 characters {src:scripts/connectors/comms/notion_connector.py:37}. A letter such as `z` is refused. No test covers a letter outside a to f.
- Code versus its description, re-run: the connector header says rerunning the same id overwrites the same file {src:scripts/connectors/comms/notion_connector.py:19-20}. The file name includes a slug of the page title {src:scripts/connectors/comms/notion_connector.py:181}, so a renamed page writes a second file. The re-run test keeps the title fixed {src:tests/scripts/connectors/comms/test_notion.py:96-100}, so this case is not tested.
- The bad-id test checks the exit value with `assertNotEqual(code, 0)`; the value is a text message from `SystemExit`, so any text passes that line {src:tests/scripts/connectors/comms/test_notion.py:128} {src:scripts/connectors/comms/notion_connector.py:195}. The test can still fail: with the check removed the connector would make a call and exit 0, and the call-list assertion on the next line would fail.
- Privacy gaps: only the page path is tested. A database row title with a personal id is not tested, though rows go through the same filter {src:scripts/connectors/comms/notion_connector.py:175} {src:scripts/connectors/comms/notion_connector.py:211}. The two ids used match the social security style pattern {src:scripts/cache/phi_guard.py:19} and the `MRN` pattern {src:scripts/cache/phi_guard.py:20}; the other four patterns (patient id, two date of birth forms, titled name) are not exercised here {src:scripts/cache/phi_guard.py:32-37} (searched this file, 2026-11-20). The reject count in the run log is now checked, but only for one title and one line {src:tests/scripts/connectors/comms/test_notion.py:175-176}. Redaction of database row titles is also not tested, though rows are redacted with the other lines {src:scripts/connectors/comms/notion_connector.py:180}, and neither is two tokens of one kind in one line, which count once {src:scripts/connectors/comms/comms_common.py:74-75}.
- Gaps: depth cap `MAX_DEPTH` {src:scripts/connectors/comms/notion_connector.py:36}, paging by `has_more` and `next_cursor` {src:scripts/connectors/comms/notion_connector.py:126-130}, and the `--into` values other than the two tested were not found in any test (searched this file, 2026-11-20). The nested test covers one level only.
- Inputs without a check (product code behind these tests): ids of child blocks come from the server reply and go into the request path with no format check, since the check in `main` covers only the top-level id {src:scripts/connectors/comms/notion_connector.py:194} {src:scripts/connectors/comms/notion_connector.py:111} {src:scripts/connectors/comms/notion_connector.py:121-122}. The paging cursor is appended to the path unencoded {src:scripts/connectors/comms/notion_connector.py:113}. The page title is turned into a file name by `slug`, which keeps only lowercase letters, digits and dashes {src:scripts/connectors/comms/notion_connector.py:85}. Neither the server-supplied ids nor the cursor is exercised by a hostile value in this test file.
- Shared-file write: the note is written with a plain `write_text`, not atomically, and no lock stops two runs writing the same note at once {src:scripts/connectors/comms/notion_connector.py:184}. The test runs one process at a time.
- Machine dependence: the vault path comes from `TOLLGATE_KNOWLEDGE`, which the throwaway home sets {src:tests/harness/throwaway_home.py:36}. No Python-version dependence found in this file.
- The first CON-02 test reads every file under the repo root, so it is slow in a checkout with a virtual environment {src:tests/scripts/connectors/comms/comms_base.py:153-161}.
