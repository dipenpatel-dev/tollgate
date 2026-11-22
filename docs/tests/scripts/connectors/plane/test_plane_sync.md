---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_sync.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/plane_ticket_syncer.py, scripts/connectors/plane/plane_comment_builder.py, scripts/connectors/plane/plane_sync_ledger.py, scripts/connectors/plane/cli.py]         # source files under test, relative paths from repo root
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

Tests for the Plane `sync` command, which copies one ticket's state file, status word and new session-log text onto its Plane card. The file is grouped by what is sent: the card description, the board status, session-log comments, the optional "extras" comments (spec or validation text), and the edges (unmapped prefix, missing card, bad ledger, failed post). A last group runs the same command through the command line wrapper. Every test runs the real sync code against a local fake Plane server, never a real one.

## Dependencies

**Depends on.**
- `run_sync` from [[plane_ticket_syncer]] ([plane_ticket_syncer](../../../../scripts/connectors/plane/plane_ticket_syncer.md)) is the code under test {src:tests/scripts/connectors/plane/test_plane_sync.py:19}.
- `comment_key` from [[plane_comment_builder]] ([plane_comment_builder](../../../../scripts/connectors/plane/plane_comment_builder.md)) is used to compute the expected hash {src:tests/scripts/connectors/plane/test_plane_sync.py:17} {src:tests/scripts/connectors/plane/test_plane_sync.py:29-30}.
- `ledger_path`, `load_ledger`, `save_ledger` and `PlaneSyncLedgerError` from [[plane_sync_ledger]] ([plane_sync_ledger](../../../../scripts/connectors/plane/plane_sync_ledger.md)) are used to read and rewrite the ledger file directly {src:tests/scripts/connectors/plane/test_plane_sync.py:18}.
- `PlaneApiError` from [[plane_work_item_client]] ([plane_work_item_client](../../../../scripts/connectors/plane/plane_work_item_client.md)) {src:tests/scripts/connectors/plane/test_plane_sync.py:20}.
- `FailRule` from [[plane_stub_server]] ([plane_stub_server](plane_stub_server.md)), the fake Plane server {src:tests/scripts/connectors/plane/test_plane_sync.py:21}.
- Base classes and helpers (`SyncTestCase`, `CliCase`, `state_text`, `FAKE_TOKEN`, `STATE_BODY`, `SYNC_TICKET`) from [[plane_sync_test_support]] ([plane_sync_test_support](plane_sync_test_support.md)) {src:tests/scripts/connectors/plane/test_plane_sync.py:22}.
- The shipped example settings file `scripts/connectors/plane/plane_sync_settings.example.json`, loaded by the support module {src:tests/scripts/connectors/plane/plane_sync_test_support.py:42} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:82}.
- Standard library: `contextlib`, `dataclasses`, `io`, `json`, `unittest`.

**Used by.** No product code (a test file). Run by `unittest discover -p 'test_*.py'` from `tests/scripts/connectors/plane/run.sh` {src:tests/scripts/connectors/plane/run.sh:6}, which `tests/system/run.sh` calls for the `connectors/plane` area {src:tests/system/run.sh:22-23}. Searched `git grep` for the file name outside `docs/` on 2026-11-20: only the file's own header line matches.
Tests: none import it.

## Behavior

Setup shared by every case (from the support module): a fake Plane server on 127.0.0.1 with five cards `T-1` to `T-5`, a temp tickets folder with five folders, a temp state folder, and a `T-5` state file with title "Sync ticket" and the spec-stage status word {src:tests/scripts/connectors/plane/plane_sync_test_support.py:106-118} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:128-133} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:139-142}. `self.sync()` calls `run_sync` and collects the printed lines {src:tests/scripts/connectors/plane/plane_sync_test_support.py:157-163}.

**TestDescription**
- First sync sends exactly one `description_html` update that ends with `<p>state-sha: <hash></p>` and carries the title as the card name; the summary line says `description=updated` and `first_sync=yes` {src:tests/scripts/connectors/plane/test_plane_sync.py:34-42}. The code builds that HTML at {src:scripts/connectors/plane/plane_ticket_syncer.py:109} and sends the name from the state title at {src:scripts/connectors/plane/plane_ticket_syncer.py:110-112}.
- A second sync with an unchanged file makes no non-GET call and reports `description=same` {src:tests/scripts/connectors/plane/test_plane_sync.py:44-50}; the code skips when the stored hash equals the new one {src:scripts/connectors/plane/plane_ticket_syncer.py:103-104}.
- Changing the file sends a second update containing the new text {src:tests/scripts/connectors/plane/test_plane_sync.py:52-57}.
- A `<script>` tag in the body is not present in the stored description {src:tests/scripts/connectors/plane/test_plane_sync.py:59-62}; the markdown converter escapes text {src:scripts/connectors/plane/plane_markdown.py:26} {src:scripts/connectors/plane/plane_markdown.py:47}.
- A token-shaped string in the body stops the run: exit 2, one line naming the pattern `long_mixed_token`, no PATCH, no comment, and the token never appears in the output {src:tests/scripts/connectors/plane/test_plane_sync.py:64-70}. The code scans title plus body before sending {src:scripts/connectors/plane/plane_ticket_syncer.py:106-108}.

**TestStatus**
- First sync moves the card to the board column mapped from the status word and posts no status comment {src:tests/scripts/connectors/plane/test_plane_sync.py:74-78}; with no earlier word in the ledger the code only moves the card {src:scripts/connectors/plane/plane_ticket_syncer.py:139-143}.
- A card already in the right column gets no state update on first sync {src:tests/scripts/connectors/plane/test_plane_sync.py:80-83} {src:scripts/connectors/plane/plane_ticket_syncer.py:141-142}.
- An unchanged word makes no second state update and no comment {src:tests/scripts/connectors/plane/test_plane_sync.py:85-90}.
- A changed word moves the card to Done and posts exactly one comment with the text `Status: <old> to <new> (board: Done) (generated)`, and a third sync does not post it again {src:tests/scripts/connectors/plane/test_plane_sync.py:92-100} {src:scripts/connectors/plane/plane_ticket_syncer.py:120}.
- A word with a trailing note such as `(pushed)` is cut at the note before mapping {src:tests/scripts/connectors/plane/test_plane_sync.py:102-105} {src:scripts/connectors/plane/vault_ticket_files.py:25} {src:scripts/connectors/plane/vault_ticket_files.py:203-204}.
- An unmapped word is named in the summary (`status=unknown:...`), the other steps (description, comment) still run, no state update is sent, the card stays in Backlog, and the exit code is 2 {src:tests/scripts/connectors/plane/test_plane_sync.py:107-118} {src:scripts/connectors/plane/plane_ticket_syncer.py:159-163} {src:scripts/connectors/plane/plane_ticket_syncer.py:290}.
- The blocked word moves the card to Waiting and its comment carries the "Current state" section of the body; a non-blocked word does not {src:tests/scripts/connectors/plane/test_plane_sync.py:120-134} {src:scripts/connectors/plane/plane_ticket_syncer.py:121-123}.
- A secret in the would-be status comment stops the run before any write: only GET calls reach the server, the ledger keeps its old status word, and the card stays in place. The test pre-sets the ledger description hash so the description step is skipped and the status step is reached {src:tests/scripts/connectors/plane/test_plane_sync.py:136-149} {src:scripts/connectors/plane/plane_ticket_syncer.py:146-148}.
- A word mapped to a board column that Plane does not have stops with `board status Nowhere not found in Plane` {src:tests/scripts/connectors/plane/test_plane_sync.py:151-155} {src:scripts/connectors/plane/plane_ticket_syncer.py:164-166}.

**TestComments**
- New session-log text posts one comment naming the log file; a rerun posts none (`comment=none`) {src:tests/scripts/connectors/plane/test_plane_sync.py:159-169}.
- Only text after the stored offset is posted next time {src:tests/scripts/connectors/plane/test_plane_sync.py:171-179} {src:scripts/connectors/plane/plane_comment_builder.py:56}.
- The comment carries `external_source` `tollgate` and a 12-hex-character `external_id` that is also saved in the ledger's `posted_keys` {src:tests/scripts/connectors/plane/test_plane_sync.py:181-189} {src:scripts/connectors/plane/plane_comment_builder.py:127}.
- Raw HTML in session text is escaped {src:tests/scripts/connectors/plane/test_plane_sync.py:191-195}.
- A first sync with no ledger posts no old text (offsets are set to each file's current length) {src:tests/scripts/connectors/plane/test_plane_sync.py:197-202} {src:scripts/connectors/plane/plane_ticket_syncer.py:95-97}. Deleting the ledger later does not repost history either {src:tests/scripts/connectors/plane/test_plane_sync.py:204-211}.
- `from_start=True` posts existing text once, and is refused (exit 2, message names `--from-start`) when a ledger already exists {src:tests/scripts/connectors/plane/test_plane_sync.py:213-224} {src:scripts/connectors/plane/plane_ticket_syncer.py:314-316}.
- With the limit set to 300 characters, a long log is cut with the pointer `(cut; full text in the T-5 files in the vault)`, the summary says `cut=yes`, the stored offset is the full text length, and a rerun posts nothing {src:tests/scripts/connectors/plane/test_plane_sync.py:226-237} {src:scripts/connectors/plane/plane_ticket_syncer.py:213} {src:scripts/connectors/plane/plane_ticket_syncer.py:220}.
- A secret in session text stops the run with one line, posts nothing, leaves offsets unchanged, and the token is not printed {src:tests/scripts/connectors/plane/test_plane_sync.py:239-247} {src:scripts/connectors/plane/plane_ticket_syncer.py:251-253}. After the text is edited clean, the next sync posts {src:tests/scripts/connectors/plane/test_plane_sync.py:249-255}.
- A `password: ...` line and a private key block are also stopped, with pattern names `named_secret_assignment` and `private_key_block` {src:tests/scripts/connectors/plane/test_plane_sync.py:257-264}. The pattern names come from the settings, not from this file; the test only proves the names appear in the output.

**TestExtras** (setUp writes a spec file and a design file and does one sync) {src:tests/scripts/connectors/plane/test_plane_sync.py:268-272}
- `extras="spec"` posts one comment with the requirements, the acceptance criteria, the diagram (escaped arrow `--&gt;`) and the session text, but not the Budget section {src:tests/scripts/connectors/plane/test_plane_sync.py:274-281} {src:scripts/connectors/plane/plane_comment_builder.py:26} {src:scripts/connectors/plane/plane_comment_builder.py:101-112}.
- The same extras twice with no new session text post once {src:tests/scripts/connectors/plane/test_plane_sync.py:283-288} {src:scripts/connectors/plane/plane_ticket_syncer.py:242-243}.
- Extras are not repeated when later session text arrives {src:tests/scripts/connectors/plane/test_plane_sync.py:290-295}; a changed spec posts them again {src:tests/scripts/connectors/plane/test_plane_sync.py:297-301} {src:scripts/connectors/plane/plane_ticket_syncer.py:196-197}.
- A 2000-line session log is cut while the extras stay whole {src:tests/scripts/connectors/plane/test_plane_sync.py:303-312} {src:scripts/connectors/plane/plane_ticket_syncer.py:202}.
- `extras="dev"` posts the validation file without its frontmatter, and once only {src:tests/scripts/connectors/plane/test_plane_sync.py:314-321} {src:scripts/connectors/plane/plane_comment_builder.py:115-122}.
- A missing validation file is named in the comment and the note is posted once, giving one entry in `posted_keys` {src:tests/scripts/connectors/plane/test_plane_sync.py:323-327} {src:scripts/connectors/plane/plane_ticket_syncer.py:187} {src:scripts/connectors/plane/plane_ticket_syncer.py:194-195}.
- A secret in the spec posts nothing and exits 2 {src:tests/scripts/connectors/plane/test_plane_sync.py:329-332}.

**TestSyncEdges**
- Prefix `zz` is skipped: exit 0, one `skip | ...` line, no server call at all {src:tests/scripts/connectors/plane/test_plane_sync.py:336-341} {src:scripts/connectors/plane/vault_ticket_files.py:66} {src:scripts/connectors/plane/plane_ticket_syncer.py:305-308}.
- No card for the ticket: exit 2 and `stopped | no card for T-5` {src:tests/scripts/connectors/plane/test_plane_sync.py:343-346} {src:scripts/connectors/plane/plane_ticket_syncer.py:320-322}.
- A ledger that is not valid JSON makes `run_sync` raise `PlaneSyncLedgerError`, the file is left byte for byte as it was, and no server call is made {src:tests/scripts/connectors/plane/test_plane_sync.py:348-355} {src:scripts/connectors/plane/plane_sync_ledger.py:71-74}.
- A server 500 on the comment POST raises `PlaneApiError`, offsets in the ledger do not move, and exactly one POST was attempted (no retry) {src:tests/scripts/connectors/plane/test_plane_sync.py:357-365}.

**TestSyncCli** (uses `CliCase`: a throwaway home, a fake secret store, the connector turned on with the fake token and the stub's host and port recorded with `--allow-host`) {src:tests/scripts/connectors/plane/plane_sync_test_support.py:190} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:198-200}
- `sync T-5 --from-start` exits 0 and posts one comment; a later `sync T-5 --extras spec` exits 0 and never prints the token {src:tests/scripts/connectors/plane/test_plane_sync.py:369-374}.
- With the connector turned off the command exits 2, prints `plane: not set up` on stderr and makes no call {src:tests/scripts/connectors/plane/test_plane_sync.py:376-383} {src:scripts/connectors/plane/cli.py:162-163} {src:scripts/connectors/plane/cli.py:195-197}.
- `--extras other` is a usage error with exit 2 {src:tests/scripts/connectors/plane/test_plane_sync.py:385-388} {src:scripts/connectors/plane/cli.py:90} {src:scripts/connectors/plane/cli.py:191-192}.
- A server 500 on the project list gives exit 3 {src:tests/scripts/connectors/plane/test_plane_sync.py:390-392} {src:scripts/connectors/plane/cli.py:198-200}.

## Diagram

None: every test class follows the same chain (state file on disk, `run_sync`, fake server, assertions), and the fixture chain is described in the Behavior section.

## Notes

- Disagreements between the file's own description and its code: none found. The header lists "first sync and the cli" {src:tests/scripts/connectors/plane/test_plane_sync.py:2}; the edge group (`TestSyncEdges`) is not named there but is present {src:tests/scripts/connectors/plane/test_plane_sync.py:335}.
- Weak assertion: `test_long_session_log_is_cut_and_the_extras_stay_whole` only requires the comment HTML to be shorter than twice the limit {src:tests/scripts/connectors/plane/test_plane_sync.py:312}, while the code aims for at most the limit itself {src:scripts/connectors/plane/plane_ticket_syncer.py:219}. A regression that let the HTML reach 1.9 times the limit would still pass.
- `test_sync_through_the_cli` checks the exit code and the absence of the token but not how many comments the second (`--extras spec`) call posted; no spec file exists in that test, so the code would post a "not found" note {src:tests/scripts/connectors/plane/test_plane_sync.py:373-374} {src:scripts/connectors/plane/plane_ticket_syncer.py:187}.
- Tests depend on the shipped example settings file: the status-to-column map, the blocked word list and `comment_max_chars` 15000 {src:scripts/connectors/plane/plane_sync_settings.example.json:8-25} {src:scripts/connectors/plane/plane_sync_settings.example.json:29}. Editing that file can break these tests; the board names asserted in them are Ready, Done, Waiting and Backlog.
- `test_secret_in_the_status_comment_sends_nothing_and_keeps_the_ledger` computes the description hash itself with `comment_key` of the state text {src:tests/scripts/connectors/plane/test_plane_sync.py:142}; this ties the test to the code's choice to hash the whole raw file {src:scripts/connectors/plane/plane_ticket_syncer.py:323}.
- Gaps not covered here: a secret in the ticket title only (the code scans title plus body {src:scripts/connectors/plane/plane_ticket_syncer.py:106}); a malformed ticket id (`stopped | not a ticket id`) {src:scripts/connectors/plane/vault_ticket_files.py:73}; a ledger error through the command line exit code 2 {src:scripts/connectors/plane/cli.py:201-203}. Other test files may cover them; this page did not check.
- Reachable inputs: file paths are all under temp folders {src:tests/scripts/connectors/plane/plane_sync_test_support.py:109-112}; the only network address is the fake server, and the test http object raises if the host is not 127.0.0.1 {src:tests/scripts/connectors/plane/plane_sync_test_support.py:68-69}; no shell command is run. The fake token is built at import time from a random uuid {src:tests/scripts/connectors/plane/plane_sync_test_support.py:47-52}.
- Shared-file writes: the tests write only temp files. Line 143 rewrites a ledger through `save_ledger`, which writes a temp file then `os.replace` (atomic) and has no lock against a second writer {src:scripts/connectors/plane/plane_sync_ledger.py:90-91}. Other writes are plain `write_text` calls on temp files {src:tests/scripts/connectors/plane/plane_sync_test_support.py:145} {src:tests/scripts/connectors/plane/test_plane_sync.py:253}.
- Machine and version dependence: no machine path is hard coded; the repo root comes from the file location {src:tests/scripts/connectors/plane/plane_sync_test_support.py:26-28}. The stub binds an operating-system-chosen port on 127.0.0.1 {src:tests/scripts/connectors/plane/plane_stub_server.py:177}. No Python-version-specific syntax in this file; the support module uses `from __future__ import annotations` {src:tests/scripts/connectors/plane/plane_sync_test_support.py:10}.
