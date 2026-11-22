---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_vault_files.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/vault_ticket_files.py, scripts/connectors/plane/plane_sync_ledger.py]         # source files under test, relative paths from repo root
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

This file tests the two plane connector modules that touch files on disk: the one that reads, scans and creates ticket folders in the vault, and the one that keeps a small per-ticket record of what was already sent to Plane. All tests work in temporary folders that are deleted afterwards, so no real vault or output folder is touched.

## Dependencies

**Depends on.**
- Standard library: `json`, `tempfile`, `unittest`, `pathlib` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:11-14}.
- [[plane_sync_test_support]] / [plane_sync_test_support](plane_sync_test_support.md), imported first for its path setup {src:tests/scripts/connectors/plane/test_plane_vault_files.py:10}, and for `read_template`, which reads the ticket state template from the plane package {src:tests/scripts/connectors/plane/test_plane_vault_files.py:23} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:97-98}.
- [[plane_sync_ledger]] / [plane_sync_ledger](../../../../scripts/connectors/plane/plane_sync_ledger.md): `PlaneSyncLedgerError`, `SyncLedger`, `ledger_path`, `load_ledger`, `save_ledger` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:16}.
- [[plane_sync_settings]] / [plane_sync_settings](../../../../scripts/connectors/plane/plane_sync_settings.md): `PrefixRow`, a record of a project key, a ticket-id pattern and a number width {src:tests/scripts/connectors/plane/test_plane_vault_files.py:17} {src:scripts/connectors/plane/plane_sync_settings.py:62-65}.
- [[vault_ticket_files]] / [vault_ticket_files](../../../../scripts/connectors/plane/vault_ticket_files.md): the ten functions and two error classes named in the import {src:tests/scripts/connectors/plane/test_plane_vault_files.py:18-22}.
- Through `vault_ticket_files`, the shared path helpers `ticket_folder` and `iter_ticket_folders` in [[paths]] / [paths](../../../../scripts/core/paths.md) {src:scripts/connectors/plane/vault_ticket_files.py:19}.

**Used by.** Searched with `git grep` for the file name, excluding `docs/` (2026-11-20). No product code names it.
- Found by the pattern `test_*.py` in the plane runner {src:tests/scripts/connectors/plane/run.sh:6}; see [[run]] / [run](run.md).
- Tests: no other test imports it.

## Behavior

The constants: `ROW` is a prefix row for project key `T`, pattern `^T-(\d+)$`, width 1 {src:tests/scripts/connectors/plane/test_plane_vault_files.py:25}; `RENDER` holds priority, scope, repo, work type and date for the template {src:tests/scripts/connectors/plane/test_plane_vault_files.py:26}. Class `TestVaultFiles` makes a fresh temporary folder before each test and deletes it after {src:tests/scripts/connectors/plane/test_plane_vault_files.py:30-33}.

**Scanning and naming ticket folders**
1. Highest local number: folders `T-3`, `T-12`, `T-9`, plus `notes`, `T-x`, `ZZ-99` and a plain file `T-500`; the answer must be 12 {src:tests/scripts/connectors/plane/test_plane_vault_files.py:35-40}. This holds because only folders whose name is a ticket key are yielded {src:scripts/core/paths.py:278-281} and the row pattern must also match {src:scripts/connectors/plane/vault_ticket_files.py:106-108}.
2. Zero when the folder is missing, or exists with nothing matching {src:tests/scripts/connectors/plane/test_plane_vault_files.py:42-45}; the code returns 0 for a missing folder {src:scripts/connectors/plane/vault_ticket_files.py:101-102}.
3. Id formatting: the number is zero-padded to the row width, so width 3 gives `T-007` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:47-49} {src:scripts/connectors/plane/vault_ticket_files.py:80}. The same case checks that an unknown ticket in an empty tickets folder maps to `<root>/T-7` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:50} {src:scripts/connectors/plane/vault_ticket_files.py:97}.
4. Flat and nested: with `T-3`, `T/T-40`, `t/T-41`, `T/notes`, `Z/T-99`, `T/T-x` the answer is 41 {src:tests/scripts/connectors/plane/test_plane_vault_files.py:52-56}. Prefix folders must match the key's letters ignoring case {src:scripts/core/paths.py:289}, so `Z/T-99` is not counted.
5. An existing ticket in a prefix folder is found there {src:tests/scripts/connectors/plane/test_plane_vault_files.py:58-61} {src:scripts/core/paths.py:259-261}.
6. A new ticket goes under its prefix folder when one exists, otherwise flat: `T-8` goes under `T`, `Q-1` stays flat {src:tests/scripts/connectors/plane/test_plane_vault_files.py:63-67} {src:scripts/connectors/plane/vault_ticket_files.py:93-97}.
7. Writing under a prefix folder gives `T/T-9/T-9-state.md` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:69-73} {src:scripts/connectors/plane/vault_ticket_files.py:246-248}.
8. The case at 169-173 repeats the folder rule of case 3 (`<root>/T-7`) and then checks the state file path {src:tests/scripts/connectors/plane/test_plane_vault_files.py:169-173}.

**Status words and reading state files**
9. `normalize_status_word`: leading and trailing space is cut, text from the first space followed by `(` or `-` is dropped, the rest is upper-cased with spaces and hyphens turned into underscores {src:scripts/connectors/plane/vault_ticket_files.py:203-204}. The test feeds an already normal word, a spaced mixed-case word with a date in brackets, a hyphenated word followed by " - by someone", and a lower-case word {src:tests/scripts/connectors/plane/test_plane_vault_files.py:75-79}.
10. `parse_state_text` reads title, status and ticket id from the frontmatter, and the body is everything after the second fence line {src:tests/scripts/connectors/plane/test_plane_vault_files.py:81-86} {src:scripts/connectors/plane/vault_ticket_files.py:117}. A quoted title is decoded as JSON {src:scripts/connectors/plane/vault_ticket_files.py:129-130}.
11. Errors name their source: no frontmatter gives an error with the file name {src:tests/scripts/connectors/plane/test_plane_vault_files.py:89-91} {src:scripts/connectors/plane/vault_ticket_files.py:116}; a missing title names the file and the key `title` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:92-95} {src:scripts/connectors/plane/vault_ticket_files.py:170}; a title written as the number 5 is read as not text and also fails {src:tests/scripts/connectors/plane/test_plane_vault_files.py:96-97} {src:scripts/connectors/plane/vault_ticket_files.py:133}.
12. A line `Status:` at column one in the body is used when the frontmatter has no status {src:tests/scripts/connectors/plane/test_plane_vault_files.py:151-153} {src:scripts/connectors/plane/vault_ticket_files.py:171}. The same line inside a code fence is ignored and parsing fails for lack of a status {src:tests/scripts/connectors/plane/test_plane_vault_files.py:155-158} {src:scripts/connectors/plane/vault_ticket_files.py:156-160}. A frontmatter status wins over a body line {src:tests/scripts/connectors/plane/test_plane_vault_files.py:160-162}.
13. A frontmatter line that is not `key: value` is an error that names the file {src:tests/scripts/connectors/plane/test_plane_vault_files.py:164-167} {src:scripts/connectors/plane/vault_ticket_files.py:142-144}.
14. `read_state_file` reads `<folder>/<id>-state.md`; a missing file gives an error naming `T-5-state.md` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:134-140} {src:scripts/connectors/plane/vault_ticket_files.py:186-190}.
15. `session_log_files` returns only `<id>-session-*.md` files sorted by name, and an empty list for a folder that does not exist {src:tests/scripts/connectors/plane/test_plane_vault_files.py:142-149} {src:scripts/connectors/plane/vault_ticket_files.py:263-265}.

**Rendering and creating the state file**
16. A title with a quote, colon, hash and backslash comes back unchanged after render and parse {src:tests/scripts/connectors/plane/test_plane_vault_files.py:99-102}. Render stores the title as a JSON string {src:scripts/connectors/plane/vault_ticket_files.py:223} and parse decodes it {src:scripts/connectors/plane/vault_ticket_files.py:129-130}.
17. The rendered file parses to id `T-9` and status word `BACKLOG`, and contains nine listed frontmatter lines and six listed headings {src:tests/scripts/connectors/plane/test_plane_vault_files.py:104-114}. The template carries those lines {src:scripts/connectors/plane/plane_ticket_state_template.md:2-22} and headings {src:scripts/connectors/plane/plane_ticket_state_template.md:29-41}.
18. An unknown placeholder `{surprise}` raises {src:tests/scripts/connectors/plane/test_plane_vault_files.py:116-118} {src:scripts/connectors/plane/vault_ticket_files.py:233-234}; a priority holding a newline raises {src:tests/scripts/connectors/plane/test_plane_vault_files.py:119-120} {src:scripts/connectors/plane/vault_ticket_files.py:219-220}.
19. Braces inside a title are not treated as placeholders, because all placeholders are replaced in one pass over the template text, so inserted values are not scanned again {src:tests/scripts/connectors/plane/test_plane_vault_files.py:122-124} {src:scripts/connectors/plane/vault_ticket_files.py:237}.
20. Create-only: a second write to the same folder raises the folder-exists error and the first file content stays `first` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:126-132} {src:scripts/connectors/plane/vault_ticket_files.py:248-250}.

**Class `TestLedger`** (fresh temporary state folder and a ledger for ticket `T-4` before each test {src:tests/scripts/connectors/plane/test_plane_vault_files.py:176-182})
21. Path is `<state>/T-4/plane_sync_ledger.json` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:184-185} {src:scripts/connectors/plane/plane_sync_ledger.py:46-47}.
22. An absent file loads as `None` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:187-188} {src:scripts/connectors/plane/plane_sync_ledger.py:69-70}.
23. Save then load returns an equal ledger; saving again with a changed `description_sha` overwrites, and the folder then holds only the ledger file, so no temporary file is left {src:tests/scripts/connectors/plane/test_plane_vault_files.py:190-196} {src:scripts/connectors/plane/plane_sync_ledger.py:90-91}.
24. Text that is not JSON raises the ledger error and the file content is unchanged {src:tests/scripts/connectors/plane/test_plane_vault_files.py:198-203} {src:scripts/connectors/plane/plane_sync_ledger.py:73-74}.
25. A missing key `posted_keys` raises and the message names the key {src:tests/scripts/connectors/plane/test_plane_vault_files.py:205-213} {src:scripts/connectors/plane/plane_sync_ledger.py:55}; a number given as text raises {src:tests/scripts/connectors/plane/test_plane_vault_files.py:214-216} {src:scripts/connectors/plane/plane_sync_ledger.py:62-64}.

## Diagram

None: each case builds its own temporary folder and calls one function; there is no shared fixture chain.

## Notes

- **Code and description.** The header scope line says "real HTTP goes to the local stub on 127.0.0.1" {src:tests/scripts/connectors/plane/test_plane_vault_files.py:5}. This file makes no HTTP call and uses no stub; the support module it imports builds the stub types but none is used here {src:tests/scripts/connectors/plane/test_plane_vault_files.py:10-23}. The case name `test_rendered_state_file_has_every_template_key` {src:tests/scripts/connectors/plane/test_plane_vault_files.py:104} claims every template key, but it asserts nine frontmatter lines {src:tests/scripts/connectors/plane/test_plane_vault_files.py:108-111}. The template has more keys, for example `parent`, `release`, `blocks`, `scope` and `repo` {src:scripts/connectors/plane/plane_ticket_state_template.md:5-6} {src:scripts/connectors/plane/plane_ticket_state_template.md:9} {src:scripts/connectors/plane/plane_ticket_state_template.md:16} {src:scripts/connectors/plane/plane_ticket_state_template.md:21-22}.
- **Cases that cannot fail in practice.** In case 24 the check that the file is unchanged cannot fail while `load_ledger` only reads {src:scripts/connectors/plane/plane_sync_ledger.py:68-75}. Case 8 duplicates part of case 3.
- **Machine and version dependence.** Case 4 makes both `T` and `t` folders {src:tests/scripts/connectors/plane/test_plane_vault_files.py:54}. On a case-insensitive disk (the macOS default) they are the same folder, so the lower-case rule is not tested there; on a case-sensitive disk it is [uncertain: not run on both]. Nothing depends on a machine path or on the Python version beyond what the modules need.
- **Not covered.** `save_ledger` failure (the write error path and temp-file cleanup {src:scripts/connectors/plane/plane_sync_ledger.py:92-95}); the file mode 0600 {src:scripts/connectors/plane/plane_sync_ledger.py:80}; two writers at once; a ledger number of `True` (the code rejects booleans {src:scripts/connectors/plane/plane_sync_ledger.py:62}). `parse_ticket_id` and `safe_text` are tested in another file {src:tests/scripts/connectors/plane/test_plane_fixes.py:191-193} {src:tests/scripts/connectors/plane/test_plane_fixes.py:219-221}; `ticket_id_gate` and `skip_line` have no direct test in this file.
- **Unchecked inputs in the code under test.** `render_initial_state_file` checks `priority` and `work_type` {src:scripts/connectors/plane/vault_ticket_files.py:218-220} but puts `ticket_id` and `today` into the file text with no check {src:scripts/connectors/plane/vault_ticket_files.py:222} {src:scripts/connectors/plane/vault_ticket_files.py:228}. `write_new_ticket_folder` builds a file path from `folder` and `ticket_id` with no check {src:scripts/connectors/plane/vault_ticket_files.py:246-248}; the id gate that guards this lives in another function {src:scripts/connectors/plane/vault_ticket_files.py:69-76}. The tests pass only safe values.
- **Writes to shared files.** `write_new_ticket_folder` makes the folder with `exist_ok=False`, so the operating system lets only one of two writers succeed {src:scripts/connectors/plane/vault_ticket_files.py:248-250}; the state file is then opened in exclusive-create mode and written directly, not through a temp file, so a crash can leave a partial file {src:scripts/connectors/plane/vault_ticket_files.py:254-255}. Only an error during the write removes it {src:scripts/connectors/plane/vault_ticket_files.py:256-258}. `save_ledger` writes a uniquely named temp file then `os.replace`, which is atomic on one disk, with no lock between two writers; the last one wins {src:scripts/connectors/plane/plane_sync_ledger.py:86-91}. These tests write only inside temporary folders.
