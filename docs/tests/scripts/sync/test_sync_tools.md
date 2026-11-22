---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/sync/test_sync_tools.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/sync/sweep, scripts/sync/lint_wikilinks.py, scripts/sync/sync_conversations.py, scripts/sync/sync_meetings.py, scripts/sync/sync_repos.sh]         # source files under test, relative paths from repo root
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

This file holds the main tests for the five sync scripts: `sweep` (staged records into the vault and index), `lint_wikilinks` (turns markdown links into wiki links), `sync_conversations` (Claude session files into vault notes), `sync_meetings` (exported meeting notes into the vault) and `sync_repos` (mirror git repositories). Every run happens in a throwaway home with made-up data. It also holds small helpers that the path safety test file reuses.

## Dependencies

**Depends on.**
- Standard library: `contextlib`, `importlib`, `io`, `json`, `os`, `pathlib`, `subprocess`, `sys`, `unittest` {src:tests/scripts/sync/test_sync_tools.py:13-22}.
- Test helpers: [[throwaway_home]] / [throwaway_home](../../harness/throwaway_home.md), `assert_no_network` from [[connector_helpers]] / [connector_helpers](../../harness/connector_helpers.md), and `RealStateGuard` from [[real_guard]] / [real_guard](../../harness/real_guard.md) {src:tests/scripts/sync/test_sync_tools.py:30-32}.
- Scripts under test: [[sweep]] / [sweep](../../../scripts/sync/sweep.md) (loaded by file path because it has no `.py` ending) {src:tests/scripts/sync/test_sync_tools.py:35-40}; [[lint_wikilinks]] / [lint_wikilinks](../../../scripts/sync/lint_wikilinks.md), [[sync_conversations]] / [sync_conversations](../../../scripts/sync/sync_conversations.md), [[sync_meetings]] / [sync_meetings](../../../scripts/sync/sync_meetings.md) and [[sync_repos]] / [sync_repos](../../../scripts/sync/sync_repos.md), started as child programs {src:tests/scripts/sync/test_sync_tools.py:226} {src:tests/scripts/sync/test_sync_tools.py:252} {src:tests/scripts/sync/test_sync_tools.py:279} {src:tests/scripts/sync/test_sync_tools.py:304}.
- Programs: `git` and `bash` {src:tests/scripts/sync/test_sync_tools.py:297} {src:tests/scripts/sync/test_sync_tools.py:304}. The real index test needs the `chromadb` package, because the real index class imports it {src:scripts/sync/sweep:229}. `tests/scripts/sync/run.sh` does not say so, while the end-to-end runner does {src:tests/scripts/sync/run.sh:2} {src:tests/system/run.sh:7}.

**Used by.** Searched with `git grep` for the file name outside `docs/` (2026-11-20).
- Product code: none.
- Automation: the sync area runner finds it by the pattern `test_*.py` {src:tests/scripts/sync/run.sh:6}; the end-to-end runner runs that area {src:tests/system/run.sh:22-23}.
- Tests: `test_sweep_path_safety.py` imports `load_sweep`, `record`, `FakeIndex` and `tree_files` {src:tests/scripts/sync/test_sweep_path_safety.py:22}.

## Behavior

**Helpers.** `load_sweep` loads the sweep script as a module {src:tests/scripts/sync/test_sync_tools.py:35-40}. `run` starts a child program with `PYTHONDONTWRITEBYTECODE=1` and a 120 second limit {src:tests/scripts/sync/test_sync_tools.py:43-45}. `record` builds a valid staged record, with extra fields to override; its ticket is `T-001` {src:tests/scripts/sync/test_sync_tools.py:52-58}. `FakeIndex` remembers the ids it was asked to sync and fails for chosen ids {src:tests/scripts/sync/test_sync_tools.py:61-69}.

**SweepTests.**
- The real index writes the same per-chunk fields as the search build, with the `hash` embedder: keys `file`, `heading`, `source`, `embedding_model`, `truncated`, `origin`, `tags`; `file` equals the source reference, `source` is `knowledge`, `embedding_model` is `hash-v1`, and `source_repo` is `demo` {src:tests/scripts/sync/test_sync_tools.py:95-112}. The code sets these at {src:scripts/sync/sweep:248-251}, with the collection name at {src:scripts/sync/sweep:48} and the embedder name at {src:scripts/search/embedder.py:43}.
- Preview (no `--yes`) exits 0, never calls the index factory, writes nothing, prints `plan:` and `preview only` and a summary of `processed=2` with zero written, and leaves both staging files {src:tests/scripts/sync/test_sync_tools.py:114-127} {src:scripts/sync/sweep:352-359}.
- With `--yes`, four records (decision, approval, pattern, repo) give `processed=4 written=4 synced=4`, and an empty staging folder {src:tests/scripts/sync/test_sync_tools.py:129-145}. The notes land at four expected paths {src:tests/scripts/sync/test_sync_tools.py:139-144} {src:scripts/sync/sweep:147-161}. The approval path is the changed assertion: the ticket `T-001` has no folder in that vault, so the test expects the approval at `02-tickets/T/T-001/approval-b.md` and no flat `02-tickets/T-001` folder {src:tests/scripts/sync/test_sync_tools.py:140-142}. The code does this through `_ticket_dir`, which builds `<tickets>/PREFIX/KEY` when no folder exists {src:scripts/sync/sweep:141-143} {src:scripts/sync/sweep:156}. The tickets folder is named `02-tickets` by default {src:scripts/core/paths.py:35}.
- New test `test_approval_goes_to_the_ticket_folder_that_already_exists`: for each of two cases, a flat folder `02-tickets/T-001` and a prefix folder `02-tickets/T/T-001`, it creates that folder in a fresh throwaway vault, stages one approval record, runs with `--yes`, requires exit 0, and requires `approval-b.md` inside the folder that already existed {src:tests/scripts/sync/test_sync_tools.py:149-157}. The code uses an existing folder as found {src:scripts/sync/sweep:138-140}, with the flat folder tried first and then the prefix folder {src:scripts/core/paths.py:248-261}.
- If the index fails for a record, the vault note is still written once and the staging file is kept with `vault_written`; a second run indexes it, writes nothing new, and the note holds the id marker once {src:tests/scripts/sync/test_sync_tools.py:159-171} {src:scripts/sync/sweep:311-326}.
- A missing index library (an `ImportError` from the factory) is counted as `partial` and the run exits 0 {src:tests/scripts/sync/test_sync_tools.py:173-181} {src:scripts/sync/sweep:314-326}.
- Two staged files with the same id: one is written, one is skipped {src:tests/scripts/sync/test_sync_tools.py:183-188} {src:scripts/sync/sweep:300-303}.
- A file that is not JSON and a file missing required fields are skipped; the test only checks `processed=1` {src:tests/scripts/sync/test_sync_tools.py:190-196} {src:scripts/sync/sweep:91-101}.
- Nothing staged prints `nothing staged` and exits 0; run as a program with the loader variables removed it exits 2 and says `not set up` {src:tests/scripts/sync/test_sync_tools.py:198-207} {src:scripts/sync/sweep:344-351}.
- A command line preview leaves the throwaway vault unchanged, leaves the guarded files unchanged, and creates no `.tollgate/index` {src:tests/scripts/sync/test_sync_tools.py:209-217}.

**LintAndConversations.**
- `lint_wikilinks.py --dry-run` changes nothing; a real run turns `[the note](b.md)` into `[[b|the note]]` and `[b](b.md#sec)` into `[[b#sec]]`, leaves the web link, writes its state file in the state folder, and no `.json` file ends up inside the vault {src:tests/scripts/sync/test_sync_tools.py:221-237} {src:scripts/sync/lint_wikilinks.py:16} {src:scripts/sync/lint_wikilinks.py:41}.
- `sync_conversations.py` converts one made-up session into one note named with `auto-abcd1234`, prints `Converted : 1`, leaves the sessions folder unchanged, writes its state file, and on a second run prints `Skipped   : 1` {src:tests/scripts/sync/test_sync_tools.py:239-262} {src:scripts/sync/sync_conversations.py:252} {src:scripts/sync/sync_conversations.py:341-342}.
- Without the loader variables it exits 2 {src:tests/scripts/sync/test_sync_tools.py:264-268} {src:scripts/sync/sync_conversations.py:276-280}.

**MeetingsAndRepos.**
- `sync_meetings.py` strips the CSS header and decodes `&#39;`, giving `# Weekly Sync\nIt's fine`; after the note is edited by hand, a `--full` run leaves it as `curated` {src:tests/scripts/sync/test_sync_tools.py:272-285} {src:scripts/sync/sync_meetings.py:112-130} {src:scripts/sync/sync_meetings.py:199-203}.
- With no `--source` it exits 1 and says `not set up` {src:tests/scripts/sync/test_sync_tools.py:287-291} {src:scripts/sync/sync_meetings.py:141-143}.
- `sync_repos.sh` with a one-line list `mirror <local path>` clones the repo into a folder named `mirror` under the code folder, and after a second commit prints `Pulled 1 new commit` and updates the file {src:tests/scripts/sync/test_sync_tools.py:293-312} {src:scripts/sync/sync_repos.sh:39-46} {src:scripts/sync/sync_repos.sh:76}.
- With no list file it exits 0 and says `nothing to sync` {src:tests/scripts/sync/test_sync_tools.py:314-318} {src:scripts/sync/sync_repos.sh:25-27}.

## Diagram

None: each test is a short straight run of setup, one call and checks; the only mock is `FakeIndex`.

## Notes

- **Code and description.**
  - The test named for leaving "the real state" alone passes the throwaway vault, not a real vault, to the guard; the only real file it watches is `~/.claude/settings.json` {src:tests/scripts/sync/test_sync_tools.py:209} {src:tests/scripts/sync/test_sync_tools.py:213} {src:tests/harness/real_guard.py:46-47}. The docstring's claim that every run happens in a throwaway home holds for the child programs; the guard reads the real settings file from the test process {src:tests/scripts/sync/test_sync_tools.py:3}.
  - The `Date:` header line is empty {src:tests/scripts/sync/test_sync_tools.py:6}. The change log lists no entry for the ticket folder assertion or the new approval test {src:tests/scripts/sync/test_sync_tools.py:9-11}.
- **Assertions that cannot fail or prove little.**
  - The `assertTrue(all(not f.startswith("..") ...))` line for "everything written is inside the vault" cannot fail: `tree_files(vault)` lists paths relative to the vault, so none can start with `..` {src:tests/scripts/sync/test_sync_tools.py:146-147} {src:tests/scripts/sync/test_sync_tools.py:48-49}. The `exists` checks just above it are the real check {src:tests/scripts/sync/test_sync_tools.py:139-144}.
  - The corrupt-file test checks only `processed=1` {src:tests/scripts/sync/test_sync_tools.py:196}.
  - `assert_no_network` blocks sockets in the test process only. The `sync_repos` test runs `git clone` and `git fetch` in child programs, so the guard does not cover them; the test stays offline only because the list names a local folder {src:tests/harness/connector_helpers.py:60-89} {src:tests/scripts/sync/test_sync_tools.py:294-304}.
- **Coverage gaps (approval folder).** Not tested (searched `tests/` for `_ticket_dir` and for approval records, 2026-11-20): a ticket key that is not letters, a hyphen and digits, which keeps the flat path {src:scripts/sync/sweep:144}; a prefix folder written in another letter case {src:scripts/core/paths.py:257-261}; a ticket folder that is a symlink leaving the tickets folder {src:scripts/core/paths.py:249}; and the preview line for an approval whose folder already exists. The new test checks the written file only, not the plan line, and does not check that no second folder was created for the existing-folder cases {src:tests/scripts/sync/test_sync_tools.py:157}.
- **Machine dependence.** The index field test fails with an import error when `chromadb` is not installed; it is not skipped {src:tests/scripts/sync/test_sync_tools.py:95-101} {src:scripts/sync/sweep:229}. `git init -b main` needs a git that knows `-b` {src:tests/scripts/sync/test_sync_tools.py:297}. The preview-guard test reads the real `~/.claude/settings.json` through `RealStateGuard` {src:tests/harness/real_guard.py:46-47}.
- **Inputs without a check.** The test passes its own throwaway paths and made-up names to child programs from lists, never through a shell {src:tests/scripts/sync/test_sync_tools.py:43-45}. Not checked by the tests: `sync_repos.sh` runs `git clone` on whatever address the list holds, with `set -- $LINE` unquoted {src:scripts/sync/sync_repos.sh:39} {src:scripts/sync/sync_repos.sh:46}; the test supplies a local folder.
- **Shared file writes.** All writes go to the throwaway home. The tests swap `os.environ` and restore it in `finally` blocks {src:tests/scripts/sync/test_sync_tools.py:84-92} {src:tests/scripts/sync/test_sync_tools.py:98-106}. Not atomic, not locked; unittest runs tests one at a time. The sweep under test deletes the duplicate staging file without comparing it to the first one {src:scripts/sync/sweep:300-302}; the duplicate test checks the counts, not the deleted file {src:tests/scripts/sync/test_sync_tools.py:183-188}.
