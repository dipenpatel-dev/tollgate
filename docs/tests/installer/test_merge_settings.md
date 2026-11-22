---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/installer/test_merge_settings.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [installer/merge_settings.py, settings.json]         # source files under test, relative paths from repo root
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

Twenty-one unit tests for the script that merges Tollgate's settings template into the user's own Claude settings file without destroying the user's keys. They cover the merge rules (whose hook is whose, which side wins), the command line (backup, restore, file mode, symlinks, argument count) and the permission rules for the search wrapper, including the literal-dollar escape. The header scope names the same areas: merge rules, backup, restore {src:tests/installer/test_merge_settings.py:5}.

## Dependencies

**Depends on.**
- Standard library: `json`, `os`, `sys`, `tempfile`, `unittest` {src:tests/installer/test_merge_settings.py:15} {src:tests/installer/test_merge_settings.py:16} {src:tests/installer/test_merge_settings.py:17} {src:tests/installer/test_merge_settings.py:18} {src:tests/installer/test_merge_settings.py:19}.
- `merge_settings` ([[merge_settings]] and [merge_settings](../../installer/merge_settings.md)), found by putting `installer/` on `sys.path` {src:tests/installer/test_merge_settings.py:23} {src:tests/installer/test_merge_settings.py:24}.
- The repo's own `settings.json` template, read from the repo root by `SearchWrapperRules`, so those tests depend on the real file's contents {src:tests/installer/test_merge_settings.py:171}. That file lists the two search wrapper rules the tests look for {src:settings.json:274} {src:settings.json:275}.

**Used by.** No product code imports this file. It is run by the installer test runner through `unittest discover` over `tests/installer` {src:tests/installer/run.sh:110}, a step of the CI workflow {src:.github/workflows/tests.yml:38}. Searched `git grep` for `test_merge_settings` outside `docs/` (2026-11-20): nothing else names it. Sibling: [[test_manifest]] and [test_manifest](test_manifest.md).

## Behavior

Helpers: `cmd(path, interpreter)` builds one command hook, quoting the path {src:tests/installer/test_merge_settings.py:27-28}; `TEMPLATE` has one `PreToolUse` hook on `$CLAUDE_DOTFILES/hooks/guard.py` and one allow rule {src:tests/installer/test_merge_settings.py:31-34}. The merge functions are called directly, so the placeholder in `TEMPLATE` is not replaced in the first class.

**Class `MergeRules`** (calls `merge`, `combine_templates`).

| Test | What it proves |
|---|---|
| `test_user_interpreter_hook_is_not_mistaken_for_ours` | A user hook that runs a script through `python3` is kept next to the Tollgate hook, because hook identity is the script name and the interpreter is skipped {src:tests/installer/test_merge_settings.py:38-43} {src:installer/merge_settings.py:108}. |
| `test_stale_tollgate_path_replaced_and_mixed_group_keeps_user_hook` | A hook group holding an old-path Tollgate hook and a user hook ends with the user hook plus the new Tollgate hook {src:tests/installer/test_merge_settings.py:45-49}. The code keeps the group with only the non-owned hooks {src:installer/merge_settings.py:143-144} and appends the template group {src:installer/merge_settings.py:147-148}. |
| `test_user_keys_win_and_template_adds_missing` | The user's `model`, `statusLine` and `enabledPlugins` are untouched, a new template key is added {src:tests/installer/test_merge_settings.py:51-57}. The code uses `setdefault` for keys other than hooks, permissions and env {src:installer/merge_settings.py:212-214}. |
| `test_combine_templates_adds_new_hook_entries_once` | Folding the same extra fragment in twice gives two `PreToolUse` groups and one `Stop` group, a union of allow rules in order, and the extra env {src:tests/installer/test_merge_settings.py:59-68}. The code skips groups already present {src:installer/merge_settings.py:164}, unions list permissions {src:installer/merge_settings.py:169} and merges env {src:installer/merge_settings.py:173}. |
| `test_non_command_hook_identity_is_its_whole_json` | A prompt-type hook is identified by its whole JSON, so the user's other prompt hook stays, and merging again changes nothing {src:tests/installer/test_merge_settings.py:70-76}. The code builds a `json:` identity for non-command hooks {src:installer/merge_settings.py:120}. |

**Class `CommandLine`** (calls `main` with a temp settings file; `run_main` passes six positional values: template, target and four folders {src:tests/installer/test_merge_settings.py:87-90}).

| Test | What it proves |
|---|---|
| `test_set_writes_env_and_fills_placeholders` | `--set` values land in `env`, an extra template via `--template` is merged, and `$TOLLGATE_HOME` and `$CLAUDE_DOTFILES` are replaced in hook commands {src:tests/installer/test_merge_settings.py:99-109}. The code builds the placeholder table from the folder arguments plus `--set` {src:installer/merge_settings.py:413-415} and the env from `--set` {src:installer/merge_settings.py:418-419}. |
| `test_backup_only_when_the_file_changes` | The first run with `--backup` makes one backup, the second run makes none and leaves the file equal {src:tests/installer/test_merge_settings.py:111-119}. The code skips the write and the backup when the merge changes nothing {src:installer/merge_settings.py:424-426}. |
| `test_no_backup_when_file_is_new` | No backup is made when the target did not exist {src:tests/installer/test_merge_settings.py:121-123}; the code only backs up an existing target {src:installer/merge_settings.py:427}. |
| `test_restore_newest_backup_and_keep_replaced_file` | After a merge, `--restore` puts back the original content and saves the replaced file as `settings.json.before-restore.*` {src:tests/installer/test_merge_settings.py:125-132}. The code picks the newest backup by modified time {src:installer/merge_settings.py:318} and saves the current file first {src:installer/merge_settings.py:324-326}. |
| `test_restore_without_backup_fails` | `--restore` with no backup returns 1 {src:tests/installer/test_merge_settings.py:134-135}; the code prints a message and returns 1 {src:installer/merge_settings.py:315-317}. |
| `test_file_mode_is_kept` | A file with mode 644 still has mode 644 after a merge {src:tests/installer/test_merge_settings.py:137-142}. The code copies the old mode onto the temp file before replacing {src:installer/merge_settings.py:275-276}. |
| `test_symlinked_settings_are_written_through` | After a merge with `--backup`, the target is still a symlink, the real file still has `model` equal to `mine`, and one backup exists {src:tests/installer/test_merge_settings.py:144-153}. The code writes to the real path behind the link {src:installer/merge_settings.py:269}. |
| `test_wrong_argument_count_returns_2` | One positional value returns 2, and the old seventh argument (a skill prefix) returns 2 {src:tests/installer/test_merge_settings.py:155-157}. The code requires exactly six {src:installer/merge_settings.py:404-406}. |

**Class `SearchWrapperRules`** (runs `main` with `--manifest` and `--set TOLLGATE_HOME=/th` against the repo's real `settings.json` {src:tests/installer/test_merge_settings.py:173-175}).

| Test | What it proves |
|---|---|
| `test_double_dollar_stays_a_single_literal_dollar` | `substitute` turns `$$TOLLGATE_HOME/x` into the literal `$TOLLGATE_HOME/x`, replaces the single-dollar form, turns `$$5` into `$5`, and `$$$TOLLGATE_HOME` into `$/th` {src:tests/installer/test_merge_settings.py:181-184}. The code hides `$$`, replaces placeholders, then restores one `$` {src:installer/merge_settings.py:89-92}. |
| `test_both_rules_are_installed_and_owned` | Both the absolute and the literal `tg-search` rule are in the allow list and in the manifest's owned list {src:tests/installer/test_merge_settings.py:186-194}. The code saves the owned entries when a manifest path is given {src:installer/merge_settings.py:422-423}. |
| `test_no_interpreter_search_rules_remain` | No installed allow rule mentions `query_index.py` or `TOLLGATE_PYTHON` {src:tests/installer/test_merge_settings.py:196-200}. This is a check on the content of the repo's `settings.json`, not on merge code. |
| `test_uninstall_removes_both_and_keeps_user_rules` | After an install and `--uninstall`, only the user's rule is left {src:tests/installer/test_merge_settings.py:202-208}. The code removes the rules the manifest lists {src:installer/merge_settings.py:239-243}. |
| `test_update_drops_old_search_rules_and_old_prefix_env` | Two old search rules (listed in a prior manifest) are removed, the user's rule and `MY_VAR` stay, the new literal rule is added, and `TOLLGATE_SKILL_PREFIX` is gone {src:tests/installer/test_merge_settings.py:210-225}. The code drops owned rules the template no longer has {src:installer/merge_settings.py:194-198}. |
| `test_update_drops_retired_rules_without_manifest_and_keeps_user_rules` | With no manifest file written before the run, the three retired allow rules (the plain `git config` rule, the `query_index.py` rule with the repo path, and the same rule with the literal `$CLAUDE_DOTFILES`) are removed, while three user rules stay, including `Bash(git config --get user.name)` and `Bash(git config:* extra)`, which only look like the retired one {src:tests/installer/test_merge_settings.py:227-238}. The code lists the retired rules {src:installer/merge_settings.py:77}, builds the repo-dir form {src:installer/merge_settings.py:196} and drops exact matches {src:installer/merge_settings.py:197}. |
| `test_second_run_writes_nothing` | A second run leaves the file's modified time (in nanoseconds) unchanged {src:tests/installer/test_merge_settings.py:240-244}. |
| `test_same_form_twice_is_listed_once` | A template holding `Bash($TOLLGATE_HOME/x:*)` and `Bash($$TOLLGATE_HOME/x:*)` installs as the absolute rule and the literal rule, one each {src:tests/installer/test_merge_settings.py:246-251}. |

## Diagram

None needed: each test builds its own data, and the only shared fixture is the real `settings.json`, described above.

## Notes

- **Test name and assertion disagree.** `test_same_form_twice_is_listed_once` says a repeated rule is listed once {src:tests/installer/test_merge_settings.py:246}. After substitution the two input rules differ (`/th/x` and `$TOLLGATE_HOME/x`) {src:tests/installer/test_merge_settings.py:249}, and the test expects both {src:tests/installer/test_merge_settings.py:251}. The duplicate removal in the code, `dict.fromkeys` {src:installer/merge_settings.py:191}, is therefore never exercised, and the test would still pass if that line were deleted.
- **Weak symlink assertion.** `test_symlinked_settings_are_written_through` checks that the real file still says `model` is `mine` {src:tests/installer/test_merge_settings.py:151-152}. That is also true if the merge never wrote to it. The write is proven only indirectly, by the backup count of one {src:tests/installer/test_merge_settings.py:153}.
- **Old env cleanup is not tied to the manifest.** The update test puts `TOLLGATE_SKILL_PREFIX` into the manifest's env list {src:tests/installer/test_merge_settings.py:217}, but the code removes that name unconditionally on every merge {src:installer/merge_settings.py:219}. The test cannot tell which path did the removal.
- **Depends on a real repo file.** The `SearchWrapperRules` tests read the repo's `settings.json` {src:tests/installer/test_merge_settings.py:171}, so editing the allow list there can fail them without any change to the merge code.
- **Retired rules, scope of the test.** The retired rule test writes no manifest file before `main` runs, so it proves the no-manifest path only {src:tests/installer/test_merge_settings.py:231-233}. The repo folder given to `main` is `/repo`, which is why the second retired rule uses that path {src:tests/installer/test_merge_settings.py:228} {src:tests/installer/test_merge_settings.py:175}; the literal `$CLAUDE_DOTFILES` form is the third rule {src:tests/installer/test_merge_settings.py:229}. It does not test that a retired rule the current template still lists is kept {src:installer/merge_settings.py:197}.
- **Timestamp check.** `test_second_run_writes_nothing` compares `st_mtime_ns` {src:tests/installer/test_merge_settings.py:242-244}. On a file system with coarse timestamps an unwanted rewrite inside the same tick would go unnoticed.
- **Not tested.** Searched this file (2026-11-20) for `--uninstall` with `--backup`, an explicit backup file after `--restore`, and a target that is not valid JSON; none appear. The code paths are {src:installer/merge_settings.py:372-373}, {src:installer/merge_settings.py:396-397} and {src:installer/merge_settings.py:264}.
- **Inputs that reach a path, command or network address.** All targets are temp-folder paths {src:tests/installer/test_merge_settings.py:82-87}. The strings `/repo`, `/vault`, `/scripts`, `/code` and `/th` are only text substituted into settings, never opened. No shell command and no network call. No outbound text.
- **Writes to shared files.** The only read of a shared file is `settings.json`, which is not written {src:tests/installer/test_merge_settings.py:171}. The code under test writes with a temp file and `os.replace` {src:installer/merge_settings.py:272-277}, and nothing stops two writers at once.
- **Python version.** The helper annotation `list[str]` {src:tests/installer/test_merge_settings.py:96} worked on 3.9 only because annotations are deferred {src:tests/installer/test_merge_settings.py:13}. The future import was kept from when the minimum was 3.9; it is not needed on 3.12.
