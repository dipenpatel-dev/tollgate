---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_fixes.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/vault_ticket_creator.py, scripts/connectors/plane/plane_ticket_syncer.py, scripts/connectors/plane/plane_drift_checker.py, scripts/connectors/plane/plane_comment_builder.py, scripts/connectors/plane/plane_sync_ledger.py, scripts/connectors/plane/vault_ticket_files.py, scripts/connectors/plane/plane_work_item_client.py, scripts/connectors/plane/cli.py]         # source files under test, relative paths from repo root
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

Regression tests for a round of fixes to the Plane connector, grouped by the fix label in each test name (f01 to f15, d02 to d04). They cover the order of work in `create`, the comment size limit, ticket id parsing, the built-in secret patterns, the https requirement, the file mode of the ledger, and how card names are printed. Each group runs the real code against the local fake Plane server or a temp folder.

## Dependencies

**Depends on.**
- `find_secret_pattern`, `markdown_to_html` from [[plane_comment_builder]] ([plane_comment_builder](../../../../scripts/connectors/plane/plane_comment_builder.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:24}.
- `run_drift` from [[plane_drift_checker]] ([plane_drift_checker](../../../../scripts/connectors/plane/plane_drift_checker.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:25}.
- `PlaneSyncLedgerError`, `SyncLedger`, `ledger_path`, `load_ledger`, `save_ledger` from [[plane_sync_ledger]] ([plane_sync_ledger](../../../../scripts/connectors/plane/plane_sync_ledger.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:26}.
- `run_sync` from [[plane_ticket_syncer]] ([plane_ticket_syncer](../../../../scripts/connectors/plane/plane_ticket_syncer.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:27}.
- `PlaneApiError` from [[plane_work_item_client]] ([plane_work_item_client](../../../../scripts/connectors/plane/plane_work_item_client.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:28}.
- `run_create` from [[vault_ticket_creator]] ([vault_ticket_creator](../../../../scripts/connectors/plane/vault_ticket_creator.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:29}.
- `VaultTicketError`, `parse_ticket_id`, `read_state_file`, `render_initial_state_file`, `safe_text` from [[vault_ticket_files]] ([vault_ticket_files](../../../../scripts/connectors/plane/vault_ticket_files.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:30-32}.
- Test helpers `SYNC_TICKET`, `CliCase`, `StubTestCase`, `SyncTestCase`, `make_settings`, `read_template` from [[plane_sync_test_support]] ([plane_sync_test_support](plane_sync_test_support.md)) {src:tests/scripts/connectors/plane/test_plane_fixes.py:33-35}.
- Standard library: `contextlib`, `dataclasses`, `inspect`, `io`, `os`, `stat`, `tempfile`, `unittest`, `pathlib`, `unittest.mock` {src:tests/scripts/connectors/plane/test_plane_fixes.py:13-22}.

**Used by.**
- Product code: none. Tests are not imported by product code (searched with `git grep` for the file name outside `docs/`, 2026-11-20).
- Tests (runner): `tests/scripts/connectors/plane/run.sh` finds it with the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}.

## Behavior

**create order (f01, f06, f07).**
- If the ledger cannot be written (a file sits where the ledger folder should be), `create` stops with `stopped | plane_sync_ledger.json cannot be written; card 6 kept`, writes no ticket folder, and after the blocker is removed the re-run adopts the card with only one POST in total {src:tests/scripts/connectors/plane/test_plane_fixes.py:54-65}. The code writes the ledger before the folder {src:scripts/connectors/plane/vault_ticket_creator.py:139-140}.
- A spy on `save_ledger` records whether the `T-6` folder exists when the ledger is saved; the answer must be false {src:tests/scripts/connectors/plane/test_plane_fixes.py:67-77}.
- A title that contains a password-like text makes no Plane call and no folder {src:tests/scripts/connectors/plane/test_plane_fixes.py:79-83}. The code checks the title first {src:scripts/connectors/plane/vault_ticket_creator.py:153-155}.
- A priority ending in a newline is refused both by `render_initial_state_file` (raises `VaultTicketError`) and by `create` (exit 2, no Plane call) {src:tests/scripts/connectors/plane/test_plane_fixes.py:85-90}.

**sync comment size and keys (f02, f03, f13, f15).**
- With an "extras" request but no extras files, three syncs post one comment in total and the last line says `comment=none` {src:tests/scripts/connectors/plane/test_plane_fixes.py:99-103}.
- Session text full of characters that grow when escaped (`<`, `&`, `>`) ends within `comment_max_chars` as HTML, the output says `cut=yes`, and the comment ends with a pointer to the vault files {src:tests/scripts/connectors/plane/test_plane_fixes.py:105-112}.
- When the spec extras alone are over the limit, the new session words are still visible in the comment and the comment stays within the limit {src:tests/scripts/connectors/plane/test_plane_fixes.py:114-122}.
- When extras alone fit (850 lines), they may use more than half the limit and the output says `cut=no` {src:tests/scripts/connectors/plane/test_plane_fixes.py:124-129}.
- With a limit of 80, a comment is still posted within 80 characters and says `cut=yes` {src:tests/scripts/connectors/plane/test_plane_fixes.py:131-137}.
- After the state file moves to the shipped status, the ledger is saved right after the status comment is posted: a snapshot of the ledger at each save holds the earlier status word with one posted key, and the last snapshot holds the new word with one key {src:tests/scripts/connectors/plane/test_plane_fixes.py:139-152}.
- A ledger whose session offsets were wiped still blocks a second post of the same session text, and the offsets are advanced again to the text length {src:tests/scripts/connectors/plane/test_plane_fixes.py:154-165}.
- A ledger whose status word was set back still blocks a second status comment, and the word is corrected {src:tests/scripts/connectors/plane/test_plane_fixes.py:167-177}.
- A session file with only blank lines posts nothing but the offsets are still saved {src:tests/scripts/connectors/plane/test_plane_fixes.py:179-185}.

**ticket id handling (f04, f05, d03, d04).**
- `parse_ticket_id` returns `("T", 339)` and `("zz", 1)` for good ids, and `None` for six bad ones, including a trailing newline, Arabic-Indic digits, a path trick, a bare prefix, empty text and a trailing space {src:tests/scripts/connectors/plane/test_plane_fixes.py:189-195}. The code uses a full match on ASCII digits {src:scripts/connectors/plane/vault_ticket_files.py:27} {src:scripts/connectors/plane/vault_ticket_files.py:54}.
- `run_sync` with each bad id exits 2, prints one line starting `stopped | not a ticket id: ` with no newline in it, and makes no Plane call {src:tests/scripts/connectors/plane/test_plane_fixes.py:197-206}.
- A well formed id with an unmapped prefix is a skip with exit 0 {src:tests/scripts/connectors/plane/test_plane_fixes.py:208-212}. `run_drift` with a bad id exits 2 and prints the id without the newline {src:tests/scripts/connectors/plane/test_plane_fixes.py:214-217}.
- `safe_text` removes control characters and cuts to 80 characters {src:tests/scripts/connectors/plane/test_plane_fixes.py:219-221}. The code uses a control-character pattern and a limit of 80 {src:scripts/connectors/plane/vault_ticket_files.py:28-29} {src:scripts/connectors/plane/vault_ticket_files.py:62}.
- Through the command line: an unmapped prefix is a skip (exit 0) for `sync` and `drift` with no card call, `create` with it exits 2, a bad id exits 2 {src:tests/scripts/connectors/plane/test_plane_fixes.py:225-241}. With the connector off, every other check loses: exit 2 and the "plane: not set up" message {src:tests/scripts/connectors/plane/test_plane_fixes.py:243-249}.
- The command line refuses an `http` address when insecure addresses are not allowed (exit 1, message `the connector address must start with https://`) {src:tests/scripts/connectors/plane/test_plane_fixes.py:251-254}.
- `--help` exits 0 and no arguments exit 2 {src:tests/scripts/connectors/plane/test_plane_fixes.py:256-260}. `run_sync` has no `today` parameter {src:tests/scripts/connectors/plane/test_plane_fixes.py:262-263}.

**card name printing (f10).** A card name with a newline and escape codes is printed with the controls removed, and a 200-character name is cut to 80 {src:tests/scripts/connectors/plane/test_plane_fixes.py:272-280}.

**secret patterns and markdown (f08, f09).**
- Ten sample strings (named assignments, JSON password, URL credentials, bearer header, an AWS-style key, GitHub and Slack tokens and others) must each be caught by `find_secret_pattern` {src:tests/scripts/connectors/plane/test_plane_fixes.py:284-300}. The default pattern set comes from the settings module {src:scripts/connectors/plane/plane_sync_settings.py:24-44}.
- Four plain sentences and URLs are not caught {src:tests/scripts/connectors/plane/test_plane_fixes.py:302-305}.
- A 40000-character run of `a-` is scanned with the named assignment pattern and must return nothing {src:tests/scripts/connectors/plane/test_plane_fixes.py:307-308}.
- A markdown image makes no `img` tag and a normal link stays {src:tests/scripts/connectors/plane/test_plane_fixes.py:310-313}.

**error shape (d02).** `PlaneApiError` has no `reason` attribute and its text is `GET projects/ failed: status 500 (unexpected status)` {src:tests/scripts/connectors/plane/test_plane_fixes.py:317-320}.

**ledger file (f12).**
- A saved ledger has file mode 0600 {src:tests/scripts/connectors/plane/test_plane_fixes.py:330-332}. The code sets that mode when it opens the temp file {src:scripts/connectors/plane/plane_sync_ledger.py:22} {src:scripts/connectors/plane/plane_sync_ledger.py:80}.
- If the replace step fails, the temp file is removed and `PlaneSyncLedgerError` is raised {src:tests/scripts/connectors/plane/test_plane_fixes.py:334-338}. The code removes it in the error branch {src:scripts/connectors/plane/plane_sync_ledger.py:92-95}.
- Two saves use two different temp names, and neither is the old fixed `.tmp` name {src:tests/scripts/connectors/plane/test_plane_fixes.py:340-352}.

**stub cap (f14).** After the stub's request cap (set to 2), the third call gets a 500 and the stub counts three calls {src:tests/scripts/connectors/plane/test_plane_fixes.py:355-363}.

## Diagram

None: no test setup here has a fixture chain that the Behavior section does not already cover.

## Notes

- **Description versus code.** The header lists "create order, comment limit, id parsing, secret patterns, https, ledger file mode" {src:tests/scripts/connectors/plane/test_plane_fixes.py:2}. The file also tests card name printing {src:tests/scripts/connectors/plane/test_plane_fixes.py:266-280}, markdown images {src:tests/scripts/connectors/plane/test_plane_fixes.py:310-313}, the error text {src:tests/scripts/connectors/plane/test_plane_fixes.py:316-320}, status and session key handling {src:tests/scripts/connectors/plane/test_plane_fixes.py:139-185} and the stub cap {src:tests/scripts/connectors/plane/test_plane_fixes.py:355-363}, which the header does not name. The Scope line says real HTTP goes to the local stub {src:tests/scripts/connectors/plane/test_plane_fixes.py:5}; several classes here use no HTTP at all (`TestPatterns`, `TestErrorShape`, `TestLedgerFile`) {src:tests/scripts/connectors/plane/test_plane_fixes.py:283} {src:tests/scripts/connectors/plane/test_plane_fixes.py:316} {src:tests/scripts/connectors/plane/test_plane_fixes.py:323}.
- **Tests that may not fail when they should.** `test_f08_a_long_run_of_word_characters_scans_fast` has no time limit, so a slow pattern makes the run hang instead of fail {src:tests/scripts/connectors/plane/test_plane_fixes.py:307-308}. `test_f09_markdown_images...` repeats a check in `test_plane_markdown` through another import path; both names point to the same function {src:tests/scripts/connectors/plane/test_plane_fixes.py:310-313} {src:scripts/connectors/plane/plane_comment_builder.py:17}.
- **Coverage gaps.** The sample list in `TestPatterns` has no case for the private key block pattern or the long mixed token pattern {src:tests/scripts/connectors/plane/test_plane_fixes.py:284-295}; other test files cover them (searched `tests/` with `git grep`, 2026-11-20).
- **Machine and version dependence.** The file mode test checks `0o600` through `os.stat`, which assumes a file system that keeps Unix modes {src:tests/scripts/connectors/plane/test_plane_fixes.py:332}. `from __future__ import annotations` lets the file use `str | None` annotations on older Python {src:tests/scripts/connectors/plane/test_plane_fixes.py:10} {src:tests/scripts/connectors/plane/test_plane_fixes.py:142}; it was kept from when the minimum was 3.9 and is not needed on 3.12. The test that patches `os.open` and `os.replace` uses module paths in strings {src:tests/scripts/connectors/plane/test_plane_fixes.py:335} {src:tests/scripts/connectors/plane/test_plane_fixes.py:348}.
- **Unchecked inputs.** The tests send fixed strings only. Bad ids such as `T-1/../x` are passed to prove the code blocks them {src:tests/scripts/connectors/plane/test_plane_fixes.py:189} {src:tests/scripts/connectors/plane/test_plane_fixes.py:240}. The test strings that look like secrets are built from parts so the file itself holds no real key {src:tests/scripts/connectors/plane/test_plane_fixes.py:292} {src:tests/scripts/connectors/plane/test_plane_fixes.py:293}.
- **Shared file writes.** The tests write only in temp folders or a stub, and the ledger tests use a fresh temp folder per test {src:tests/scripts/connectors/plane/test_plane_fixes.py:324-327}. The ledger test confirms an atomic replace with a private temp name, but no test here covers two writers at once {src:tests/scripts/connectors/plane/test_plane_fixes.py:340-352}.
