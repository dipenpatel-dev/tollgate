---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/installer/test_manifest.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [installer/manifest.py, installer/merge_settings.py]         # source files under test, relative paths from repo root
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

Eleven unit tests for the list of things Tollgate has installed into the user's Claude folder (the "manifest") and for the settings merge rules that depend on it. They check that an entry Tollgate dropped upstream is removed on the next update, that anything the user added is never removed, that command files are moved to a backup folder rather than deleted, and that old backups are pruned. The file header gives the same scope: stale entries removed, user entries kept, uninstall, backup pruning {src:tests/installer/test_manifest.py:5-6}.

## Dependencies

**Depends on.**
- Standard library: `glob`, `json`, `os`, `sys`, `tempfile`, `unittest` {src:tests/installer/test_manifest.py:14} {src:tests/installer/test_manifest.py:15} {src:tests/installer/test_manifest.py:16} {src:tests/installer/test_manifest.py:17} {src:tests/installer/test_manifest.py:18} {src:tests/installer/test_manifest.py:19}.
- Repo modules, found by putting the `installer/` folder on `sys.path` {src:tests/installer/test_manifest.py:23}: `manifest` ([[manifest]] and [manifest](../../installer/manifest.md)) {src:tests/installer/test_manifest.py:24} and `merge_settings` ([[merge_settings]] and [merge_settings](../../installer/merge_settings.md)) {src:tests/installer/test_manifest.py:25}.

**Used by.** No product code imports this file. It is run by the installer test runner, which calls `unittest discover` over `tests/installer` with the pattern `test_*.py` {src:tests/installer/run.sh:110}, and that runner is a step of the CI workflow {src:.github/workflows/tests.yml:38}. The result shows up as one line, "MRG settings merge unit tests" {src:tests/installer/run.sh:111}. Searched `git grep` for `test_manifest` outside `docs/` (2026-11-20): nothing else names it. Sibling test file: [[test_merge_settings]] and [test_merge_settings](test_merge_settings.md).

## Behavior

Shared helpers: `hook(path)` builds one command hook {src:tests/installer/test_manifest.py:28-29}; `template(*scripts, allow=())` builds a settings template with one `PreToolUse` group and an allow list {src:tests/installer/test_manifest.py:32-34}; `USER` is a settings object with one user hook and one user permission {src:tests/installer/test_manifest.py:37-38}; `commands(settings)` lists the hook command strings {src:tests/installer/test_manifest.py:41-42}.

**Class `ManifestRules`** (settings merge). `two_runs` merges a template into `USER`, then merges a second template on top, passing the first run's "owned" result back in as the manifest {src:tests/installer/test_manifest.py:46-49}. That mirrors how `merge_full` takes a manifest {src:installer/merge_settings.py:208}.

| Test | What it proves |
|---|---|
| `test_hook_removed_upstream_is_removed_and_user_hook_kept` | After run 1 the hook `b.py` is present; after run 2, whose template no longer lists it, `b.py` is gone, `a.py` stays and the user's `mine.py` stays {src:tests/installer/test_manifest.py:51-56}. The code removes both the template's hooks and the manifest's earlier hooks before re-adding the template {src:installer/merge_settings.py:134-135}, and keeps hooks that are not owned {src:installer/merge_settings.py:140-144}. |
| `test_hook_renamed_upstream_is_old_removed_new_added` | A renamed hook leaves only the new name, and the owned list is exactly `["cmd:tg-new.py"]` {src:tests/installer/test_manifest.py:58-63}. The owned hook list comes from the template's hook identities {src:installer/merge_settings.py:220}. |
| `test_permission_removed_upstream_is_removed_and_user_rule_kept` | A rule dropped from the template disappears, a kept rule stays, the user's rule stays, and the owned allow list shrinks to the kept rule {src:tests/installer/test_manifest.py:65-72}. The code computes stale rules from the manifest minus the template {src:installer/merge_settings.py:194-198}. |
| `test_rule_the_user_already_had_is_never_removed` | A rule the user already had is not counted as owned, so a later update that drops it from the template does not remove it, while the rule Tollgate added does go {src:tests/installer/test_manifest.py:74-80}. The code only marks a rule as owned if it was owned before or the user did not have it {src:installer/merge_settings.py:199}. |
| `test_second_merge_with_same_template_changes_nothing` | Two merges with the same template give equal results {src:tests/installer/test_manifest.py:82-84}. It compares merged data, not file writes. |
| `test_strip_owned_keeps_user_entries` | Stripping the owned entries leaves only the user's hook and rule, and drops the `env` key entirely once it is empty {src:tests/installer/test_manifest.py:86-91}. The code deletes empty `hooks`, `permissions` and `env` {src:installer/merge_settings.py:234-253}. |

**Class `SettingsBackups`.** `test_settings_backups_are_pruned_to_three` writes six old backup files named like `settings.json.bak.20200101000001`, calls `make_backup`, and expects three files left and the oldest one gone {src:tests/installer/test_manifest.py:95-106}. `make_backup` copies the file, then prunes {src:installer/merge_settings.py:294-299}; the prune sorts by name and removes all but the newest three {src:installer/merge_settings.py:304-305}. The new backup name starts with the current year, so it sorts after the 2020 names {src:installer/merge_settings.py:285}.

**Class `ManifestFile`** (command files). `setUp` makes a temp folder, a `commands` folder, a manifest path and a backup path {src:tests/installer/test_manifest.py:110-116}; `touch` creates a command file and `sync` calls `manifest.sync_commands` with version `0.2.0` {src:tests/installer/test_manifest.py:118-123}.

| Test | What it proves |
|---|---|
| `test_rename_is_remove_old_plus_add_new` | After a rename the old file is moved to the backup folder, the new file exists, a file that was never in the manifest is untouched, and the manifest lists only the new name {src:tests/installer/test_manifest.py:125-135}. The code removes names that were in the manifest and are not in the new list {src:installer/manifest.py:102-105}. |
| `test_names_with_a_folder_part_are_never_removed` | A manifest naming `../keep.md`, `/etc/hosts` and `.hidden.md` does not delete the file outside the commands folder {src:tests/installer/test_manifest.py:137-143}. The guard is `safe_name`, which rejects names with a folder part, names not ending in `.md` and names starting with a dot {src:installer/manifest.py:70}, and `remove_files` skips unsafe names {src:installer/manifest.py:87-88}. |
| `test_save_writes_only_on_change` | The first `save` returns true, the same data again returns false {src:tests/installer/test_manifest.py:145-147}. The code returns false when the file text is already equal {src:installer/manifest.py:55-57}. |
| `test_removed_backup_folders_are_pruned_to_three` | With five old backup folders plus the one a move creates, only three folders remain {src:tests/installer/test_manifest.py:149-156}. `remove_files` creates the backup folder and prunes after a move {src:installer/manifest.py:92-96}; the prune keeps the last three names in sorted order {src:installer/manifest.py:78-80}. |

## Diagram

None needed: the tests are independent and each builds its own data in a temp folder or in memory.

## Notes

- **Description and code disagree (scope line).** The header scope lists "uninstall" {src:tests/installer/test_manifest.py:5-6}. The only uninstall-like test is `test_strip_owned_keeps_user_entries`, which covers the settings side (`strip_owned`) {src:tests/installer/test_manifest.py:86-91}. The command-file side, `uninstall_commands` {src:installer/manifest.py:114}, and the command line entry `main` {src:installer/manifest.py:123}, are not called anywhere in this file (searched the file for `uninstall_commands` and `main`, 2026-11-20).
- **`test_names_with_a_folder_part_are_never_removed` is weaker than its name.** It asserts only that the outside file `keep.md` still exists {src:tests/installer/test_manifest.py:143}. Nothing checks `/etc/hosts` or the hidden name. It also depends on a real machine path: if `safe_name` stopped rejecting `/etc/hosts`, `os.path.join` would ignore the commands folder for an absolute name, and `remove_files` would try to move the real system file into the backup folder {src:installer/manifest.py:89-93}. On a normal user account the move would be refused, which is the only thing protecting the file.
- **Name sort in pruning.** The prune sorts folder names as text {src:installer/manifest.py:78}. The test uses single-digit names (`removed.1` to `removed.9`) {src:tests/installer/test_manifest.py:151-155}, so it would not notice that `removed.10` sorts before `removed.2`.
- **Unused import.** `json` is imported {src:tests/installer/test_manifest.py:15} and never used: the only other `json` text in the file is part of a file name (searched `json\.` in the file, 2026-11-20).
- **Inputs that reach a path, command or network address.** All paths are built from a temp folder {src:tests/installer/test_manifest.py:111-116}; the `/etc/hosts` string above is the one exception, and it is test data, not a file the test opens. No shell command is run and there is no network call. No value reaches outbound text.
- **Writes to shared files.** None outside temp folders, which are removed at the end {src:tests/installer/test_manifest.py:112}. The code under test writes the manifest with a temp file and `os.replace`, which is atomic, and nothing stops two writers at once {src:installer/manifest.py:61-64}.
- **Python version.** Nothing here needs a newer Python than the 3.12 minimum. Annotations are deferred {src:tests/installer/test_manifest.py:12}, a line kept from when the minimum was 3.9; it is not needed on 3.12.
