---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/sync/test_sync_vault_scan.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/sync/vault_write_scan.py, scripts/sync/sync_conversations.py, scripts/sync/sync_meetings.py]         # source files under test, relative paths from repo root
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

This file tests the safety layer that sits in front of the two sync scripts that copy text into the vault: the one that converts Claude session transcripts and the one that copies meeting notes. Before a note is written, secrets are replaced by a marker and the text is scanned for health information (PHI). The tests prove that a note with PHI is not written and only a short record goes to a quarantine log, that secrets are redacted, that a damaged state file is reported and replaced, that the state file is written through a temporary file, that the Claude project folder name is worked out correctly, and that two meetings with the same date and title both reach the vault. Fake PHI and a fake key are built at run time from parts, so no real-looking value sits in the source.

## Dependencies

**Depends on.**
- Standard library: `json`, `os`, `pathlib`, `subprocess`, `sys`, `unittest` {src:tests/scripts/sync/test_sync_vault_scan.py:15-20}.
- [[throwaway_home]] / [throwaway_home](../../harness/throwaway_home.md) {src:tests/scripts/sync/test_sync_vault_scan.py:29}.
- The fake PHI builders: [[fake_phi]] / [fake_phi](../../hooks/fake_phi.md) {src:tests/scripts/sync/test_sync_vault_scan.py:30}.
- The scan module under test, imported directly: [[vault_write_scan]] / [vault_write_scan](../../../scripts/sync/vault_write_scan.md) {src:tests/scripts/sync/test_sync_vault_scan.py:31}. It loads the hook modules `phi_patterns` and `scrub_secrets` from the repo `hooks` folder {src:scripts/sync/vault_write_scan.py:47-61}.
- The two scripts run as child programs: [[sync_conversations]] / [sync_conversations](../../../scripts/sync/sync_conversations.md) and [[sync_meetings]] / [sync_meetings](../../../scripts/sync/sync_meetings.md) {src:tests/scripts/sync/test_sync_vault_scan.py:98} {src:tests/scripts/sync/test_sync_vault_scan.py:207}. `sync_conversations` is also imported as a module for the folder name tests {src:tests/scripts/sync/test_sync_vault_scan.py:165}.

**Used by.** Searched with `git grep` for the file name outside `docs/` (2026-11-20).
- Product code: none.
- Automation: the sync area runner finds it by the pattern `test_*.py` {src:tests/scripts/sync/run.sh:6}; the end-to-end runner runs that area {src:tests/system/run.sh:22-23}.
- Tests: no other test file imports it.

## Behavior

**ScanModule (direct calls).**
- Clean text passes with no quarantine, no redaction and unchanged text {src:tests/scripts/sync/test_sync_vault_scan.py:58-61}.
- A fake Anthropic key is replaced by `[REDACTED:ANTHROPIC_KEY]`, the label is reported and the key text is gone {src:tests/scripts/sync/test_sync_vault_scan.py:63-67} {src:scripts/sync/vault_write_scan.py:66-67}. The pattern and label are defined in the hook {src:hooks/scrub_secrets.py:51}.
- A fake SSN and record number set `quarantine`, and the reason does not contain the SSN {src:tests/scripts/sync/test_sync_vault_scan.py:69-72} {src:scripts/sync/vault_write_scan.py:68-71}. Quarantine happens for levels `deny` and `ask` {src:scripts/sync/vault_write_scan.py:27}.
- A damaged state file (not JSON, or JSON that is a list) gives `{}` and one warning each; a missing file gives `{}` and no warning {src:tests/scripts/sync/test_sync_vault_scan.py:74-85} {src:scripts/sync/vault_write_scan.py:83-95}.
- Two writes of the state file leave the second content and only `state.json` in the folder, so no temporary file stays behind {src:tests/scripts/sync/test_sync_vault_scan.py:87-93} {src:scripts/sync/vault_write_scan.py:98-111}.

**Conversations (child program).**
- Two sessions, one with a fake SSN and record number and one plain: the exit code is 0, the output says `Converted : 1` and `Quarantined : 1`, only the plain session reaches `05-conversations`, the quarantine log names the PHI file and holds `PHI scan` but not the SSN, the SSN is not in stdout, and a second run says `Skipped   : 2` {src:tests/scripts/sync/test_sync_vault_scan.py:100-123} {src:scripts/sync/sync_conversations.py:322-326} {src:scripts/sync/sync_conversations.py:341-345}. The log line holds time, file name and reason only {src:scripts/sync/vault_write_scan.py:74-80}.
- A fake key in a message is redacted in the written note {src:tests/scripts/sync/test_sync_vault_scan.py:125-137}.
- A state file holding `{broken` is reported as `unreadable` on stderr, the session is still converted, and the state file is replaced by one holding the session name {src:tests/scripts/sync/test_sync_vault_scan.py:139-152} {src:scripts/sync/vault_write_scan.py:88-91}.
- The script text carries `from __future__ import annotations` before `import json` {src:tests/scripts/sync/test_sync_vault_scan.py:154-157} {src:scripts/sync/sync_conversations.py:20-22}.

**SessionsFolderName.**
- `project_slug` turns every character that is not a letter or digit into a dash: `/Users/a.b/My_Vault v2/x` becomes `-Users-a-b-My-Vault-v2-x` {src:tests/scripts/sync/test_sync_vault_scan.py:168-170} {src:scripts/sync/sync_conversations.py:46-48}.
- The default sessions folder is `CLAUDE_CONFIG_DIR/projects/<slug of the vault path>` and the final name has no `_` or `.` {src:tests/scripts/sync/test_sync_vault_scan.py:172-187} {src:scripts/sync/sync_conversations.py:60-63}.
- A `sessions:` line in the paths file wins over the default {src:tests/scripts/sync/test_sync_vault_scan.py:189-202} {src:scripts/sync/sync_conversations.py:57-59}.

**Meetings (child program).**
- Three exports with the same date and title, two at 13:29 (one a ` (1)` copy) and one at 09:00, give exactly two folders, `2026-04-07_weekly-sync` (morning) and `2026-04-07_weekly-sync_1329` (afternoon); a `--full` run adds none and prints `Synced: 0` {src:tests/scripts/sync/test_sync_vault_scan.py:217-234} {src:scripts/sync/sync_meetings.py:89-109} {src:scripts/sync/sync_meetings.py:250}.
- Two exports with the same title and the same time, the second named ` (2)`, give one folder `2026-04-07_review` {src:tests/scripts/sync/test_sync_vault_scan.py:236-246}.
- A title that reduces to nothing (`!!!`) gets the folder name `2026-04-07_untitled-meeting` {src:tests/scripts/sync/test_sync_vault_scan.py:248-256} {src:scripts/sync/sync_meetings.py:62} {src:scripts/sync/sync_meetings.py:72}.
- A damaged `.sync-state.json` is reported as `unreadable`, replaced by a file that names the export, and no `.tmp` file stays behind {src:tests/scripts/sync/test_sync_vault_scan.py:258-271} {src:scripts/sync/sync_meetings.py:154} {src:scripts/sync/sync_meetings.py:247}.
- A note with a fake record number and SSN is not written; the output says `Quarantined (PHI): 1`, the plain note is written, the `.quarantine.log` names the file and not the SSN {src:tests/scripts/sync/test_sync_vault_scan.py:273-290} {src:scripts/sync/sync_meetings.py:230-235} {src:scripts/sync/sync_meetings.py:250}.
- A fake key in a note is redacted {src:tests/scripts/sync/test_sync_vault_scan.py:292-302}.
- A hand-made folder with its own `notes.md` is never overwritten and no second folder appears {src:tests/scripts/sync/test_sync_vault_scan.py:304-315} {src:scripts/sync/sync_meetings.py:199-203}.

## Diagram

None: the tests are short and independent; the one repeated pattern is write a made-up input, run a script, check the vault and the quarantine log.

## Notes

- **Code and description.**
  - The test named "same time and title gets a number" asserts the opposite: one folder with no number {src:tests/scripts/sync/test_sync_vault_scan.py:236-246}. The two files are the same export and a ` (2)` copy, and the script treats the copy as the same meeting {src:scripts/sync/sync_meetings.py:182} {src:scripts/sync/sync_meetings.py:194-196}. The numbered folder name branch exists in the code {src:scripts/sync/sync_meetings.py:99-100} and no test reaches it.
  - The copy marker ` (2)` sorts before the dot of the plain name, so the copy is processed first and its text is the one written to `notes.md`; the plain file is then skipped as already present {src:scripts/sync/sync_meetings.py:163} {src:scripts/sync/sync_meetings.py:199-203}. I confirmed the sort order with a one-line check on 2026-11-20; the effect on `notes.md` is read from the code, not run. The test does not check the content of that note {src:tests/scripts/sync/test_sync_vault_scan.py:246}.
  - The header says a "short record with no content" goes to the quarantine log {src:tests/scripts/sync/test_sync_vault_scan.py:9-10}; the record holds the time, the source file name and the reason {src:scripts/sync/vault_write_scan.py:80}. The file name is part of the log, and the code cuts it to 200 characters and removes newlines only {src:scripts/sync/vault_write_scan.py:78}.
  - The `Date:` header line is empty {src:tests/scripts/sync/test_sync_vault_scan.py:7}.
- **Weak or indirect checks.**
  - The atomic write test checks the result (new content, one file left) and cannot prove that a crash mid-write keeps the old file {src:tests/scripts/sync/test_sync_vault_scan.py:87-93}.
  - The future-annotations test is a text search; it does not run the script on any Python; the test name still says 39, from when 3.9 was the minimum {src:tests/scripts/sync/test_sync_vault_scan.py:154-157}.
  - Fake PHI is detected only if the hook patterns in `hooks/` still match the builders in `fake_phi`; a change in one without the other would fail these tests, which is intended {src:tests/scripts/sync/test_sync_vault_scan.py:104} {src:scripts/sync/vault_write_scan.py:64-71}.
- **Machine and version dependence.** No machine paths. The tests import `scripts/sync` and `tests/hooks` through `sys.path` edits at the top {src:tests/scripts/sync/test_sync_vault_scan.py:25-27}. The folder name tests change `os.environ` of the test process and put it back in `finally` blocks {src:tests/scripts/sync/test_sync_vault_scan.py:175-186} {src:tests/scripts/sync/test_sync_vault_scan.py:193-201}.
- **Inputs without a check.** The test passes its own paths and made-up file contents to child programs from lists, never through a shell {src:tests/scripts/sync/test_sync_vault_scan.py:34-36}. Not covered by any test in this file: a meeting export whose title yields a long or odd folder name; the folder name is made from the title with only letters, digits, spaces and hyphens kept, cut at 60 characters {src:scripts/sync/sync_meetings.py:67-72}.
- **Shared file writes.** All files go to the throwaway home. The scripts write the state files atomically {src:scripts/sync/sync_meetings.py:247} {src:scripts/sync/sync_conversations.py:263}. They append to the quarantine log with a plain `open(..., "a")` and nothing stops two runs from appending at once {src:scripts/sync/vault_write_scan.py:79-80}. The notes themselves are written with `write_text`, which is not atomic {src:scripts/sync/sync_meetings.py:238} {src:scripts/sync/sync_conversations.py:331}.
