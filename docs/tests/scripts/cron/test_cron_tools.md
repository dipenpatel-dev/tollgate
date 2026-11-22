---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/cron/test_cron_tools.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/cron/setup_cron.py, scripts/cron/nightly_index.sh, scripts/cron/write_nightly_health.py, scripts/cron/vault_staleness.py, scripts/cron/backup_vault.sh, scripts/cron/think_calibrate_reminder.sh, scripts/cron/launchers/run_task.sh, scripts/cron/launchd/job.plist.template]         # source files under test, relative paths from repo root
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

This file tests the scheduled-job scripts in `scripts/cron`: the script that writes a macOS launchd job file, the nightly maintenance script, the health file writer, the vault staleness report, the encrypted vault backup, the weekly reminder and the manual task launcher. The header states the aim: prove the setup script writes only into the home it is given and never loads a job without `--yes-install-job`, and that the nightly scripts write only inside folders the path loader returns {src:tests/scripts/cron/test_cron_tools.py:7-9}.

## Dependencies

**Depends on.**
- Standard library imports, as written: `json`, `os`, `pathlib`, `plistlib`, `re`, `subprocess`, `sys`, `unittest`, `uuid` {src:tests/scripts/cron/test_cron_tools.py:13-21}.
- `throwaway_home` {src:tests/scripts/cron/test_cron_tools.py:29}: [[throwaway_home]] and [throwaway_home](../../harness/throwaway_home.md).
- `core.paths` {src:tests/scripts/cron/test_cron_tools.py:30}: [[paths]] and [paths](../../../scripts/core/paths.md).
- `RealStateGuard` {src:tests/scripts/cron/test_cron_tools.py:31}: [[real_guard]] and [real_guard](../../harness/real_guard.md).
- Scripts run as separate processes: [[setup_cron]] [setup_cron](../../../scripts/cron/setup_cron.md), [[nightly_index]] [nightly_index](../../../scripts/cron/nightly_index.md), [[write_nightly_health]] [write_nightly_health](../../../scripts/cron/write_nightly_health.md), [[vault_staleness]] [vault_staleness](../../../scripts/cron/vault_staleness.md), [[backup_vault]] [backup_vault](../../../scripts/cron/backup_vault.md), [[think_calibrate_reminder]] [think_calibrate_reminder](../../../scripts/cron/think_calibrate_reminder.md), [[run_task]] [run_task](../../../scripts/cron/launchers/run_task.md), and [[tg_path]] [tg_path](../../../scripts/core/tg_path.md) {src:tests/scripts/cron/test_cron_tools.py:49}.
- `vault_staleness` is also imported inside two tests {src:tests/scripts/cron/test_cron_tools.py:191} {src:tests/scripts/cron/test_cron_tools.py:200}.
- System programs: `bash`, `openssl` and `tar` (the decrypt check {src:tests/scripts/cron/test_cron_tools.py:340}), and `launchctl` only as a name that must never be reached {src:tests/scripts/cron/test_cron_tools.py:117}.

**Used by.**
- Product code: none. Searched with `git grep` for `test_cron_tools` outside `docs/` on 2026-11-20; no file under `scripts/`, `hooks/`, `installer/` or `tools/` names it.
- Found at run time by `unittest discover` in [[run]] [run](run.md) {src:tests/scripts/cron/run.sh:6}, which the end-to-end runner calls {src:tests/system/run.sh:23}.
- Tests: this file is itself a test.

## Behavior

**Helpers.**
- `ROOT` is two folders above the test folder, the repo root; `CRON` is `scripts/cron` {src:tests/scripts/cron/test_cron_tools.py:23-25}.
- `run` starts a process with `PYTHONDONTWRITEBYTECODE=1` added, captures text output, and has a 180 second timeout by default {src:tests/scripts/cron/test_cron_tools.py:37-39}.
- `files_under` lists every file below a folder {src:tests/scripts/cron/test_cron_tools.py:42-43}. `loader_folders` asks `tg_path` for 11 names and returns the ones that resolve {src:tests/scripts/cron/test_cron_tools.py:33-34} {src:tests/scripts/cron/test_cron_tools.py:46-52}.
- `make_stub_launcher` writes a fake launcher script that appends its arguments to a log and exits 0 {src:tests/scripts/cron/test_cron_tools.py:55-61}.

**Class `SetupCron`** (every call is `setup_cron.py --home <home> --job nightly-index` plus extras {src:tests/scripts/cron/test_cron_tools.py:66}).
- `test_dry_run_prints_and_writes_nothing`: with `--dry-run --yes-install-job` and the stub, exit 0, stdout holds "would write:" and `nightly_index.sh`, no file is created in the home, and the stub log never appears {src:tests/scripts/cron/test_cron_tools.py:72-77}. The script returns after printing, before writing or loading {src:scripts/cron/setup_cron.py:158-163}.
- `test_write_without_the_flag_never_calls_the_launcher`: exit 0, "not loaded" in stdout, no stub log, and exactly one new file, `Library/LaunchAgents/tg-job-nightly-index.plist` {src:tests/scripts/cron/test_cron_tools.py:83-89}. The script prints "not loaded" and returns when the flag is absent {src:scripts/cron/setup_cron.py:170-172}. The plist is then parsed: label, program `/bin/bash`, a script ending in `nightly_index.sh`, schedule `{"Hour": 2, "Minute": 0}`, `RunAtLoad` false, and no `@` left in the text {src:tests/scripts/cron/test_cron_tools.py:90-96}. These match the template and the job table {src:scripts/cron/launchd/job.plist.template:7} {src:scripts/cron/launchd/job.plist.template:29-30} {src:scripts/cron/setup_cron.py:47} {src:scripts/cron/setup_cron.py:98}.
- `test_flag_loads_through_the_stub_only`: with the flag, "loaded" is printed and the stub log has exactly one call that contains `bootstrap` and the plist name {src:tests/scripts/cron/test_cron_tools.py:101-107} {src:scripts/cron/setup_cron.py:176-178}.
- `test_real_launcher_is_refused_for_a_foreign_home`: a `launchctl` stub that touches a marker is placed first on `PATH`; `--home` is a sub-folder that is not the real home; with `--yes-install-job` the script exits 1 with "refused" on stderr and the marker is absent {src:tests/scripts/cron/test_cron_tools.py:111-124}. The script refuses when the launcher is the default `launchctl` and the home differs from `HOME` {src:scripts/cron/setup_cron.py:173-175}.
- `test_bad_input_is_refused`: four calls each exit 2: no job and no program, a label `../evil`, hour 25, and a home folder that does not exist {src:tests/scripts/cron/test_cron_tools.py:129-132}. The script rejects these through the label pattern, the time check and the folder check {src:scripts/cron/setup_cron.py:37} {src:scripts/cron/setup_cron.py:88-91} {src:scripts/cron/setup_cron.py:130-132} {src:scripts/cron/setup_cron.py:73-74}. Only the exit codes are checked, not the messages.
- `test_remove_deletes_only_the_job_file`: after a write, `--remove` exits 0, the plist is gone, and the stub log still does not exist {src:tests/scripts/cron/test_cron_tools.py:137-143}. Unloading happens only with the flag {src:scripts/cron/setup_cron.py:143-147}. The assertions do not test that nothing else was deleted, which the test name claims.
- `test_weekly_reminder_has_a_weekday`: the `weekly-reminder` job gets `{"Weekday": 0, "Hour": 9, "Minute": 0}` {src:tests/scripts/cron/test_cron_tools.py:149} {src:scripts/cron/setup_cron.py:48}.
- `test_a_custom_program_and_the_carried_variables`: `--program backup_vault.sh --arg=--dry-run --hour 3` writes one plist; its third program argument is `--dry-run`, `TOLLGATE_KNOWLEDGE` is carried into the job environment, and the word "secret" appears nowhere in the plist {src:tests/scripts/cron/test_cron_tools.py:153-161}. Carried names are a fixed list {src:scripts/cron/setup_cron.py:42-43} {src:scripts/cron/setup_cron.py:155}. The hour 3 is passed but never asserted.

**Class `SetupCronCarriesPathsAndNightlyChecks`.**
- The job file carries `TOLLGATE_HOME` and `TOLLGATE_PATHS`, stdout says "not loaded", and stdout holds the `vault:` note {src:tests/scripts/cron/test_cron_tools.py:170-175} {src:scripts/cron/setup_cron.py:168-169}.
- `test_nightly_index_stops_with_a_clear_message_when_the_vault_is_gone`: with `TOLLGATE_KNOWLEDGE` pointing at a folder that does not exist, `nightly_index.sh --skip-index` exits 1, prints "the vault folder does not exist" on stderr, writes one log under `logs/nightly` that holds `ABORT: the vault folder does not exist`, and does not create the vault {src:tests/scripts/cron/test_cron_tools.py:179-187}. The script checks the vault folder before any step {src:scripts/cron/nightly_index.sh:84-89}.
- `test_vault_staleness_skips_memory_by_whole_folder_name`: five calls to `under_folder`: `memory/a.md` and `memory` are inside `memory`; `memory-notes.md` under another folder, `memory2/a.md` and `a/memory/b.md` are not {src:tests/scripts/cron/test_cron_tools.py:192-196} {src:scripts/cron/vault_staleness.py:85-89}. It tests the helper, not the skipping in the scans {src:scripts/cron/vault_staleness.py:178} {src:scripts/cron/vault_staleness.py:203}.
- `test_vault_staleness_rules_come_from_the_layout`: the rules include `01-system-map/platform-learning` and `01-system-map/clients`, and none of the rule names holds `products` or `databricks` {src:tests/scripts/cron/test_cron_tools.py:201-204} {src:scripts/cron/vault_staleness.py:64-68}. The second check is a negative check that passes as long as those words are absent.

**Class `NightlyAndHelpers`.**
- `_sessions_dir` creates the Claude project folder for the vault: the vault path with every non letter or digit turned into a dash {src:tests/scripts/cron/test_cron_tools.py:210} {src:scripts/sync/sync_conversations.py:47-48}.
- `test_dry_run_runs_and_writes_nothing`: `nightly_index.sh --dry-run` exits 0, names `sync_conversations` and `build_index`, and creates no file {src:tests/scripts/cron/test_cron_tools.py:217-221} {src:scripts/cron/nightly_index.sh:67-71}.
- `test_run_writes_only_inside_loader_folders_and_records_health`: builds a vault with `a.md` holding `[b](b.md)` and an empty `b.md`, a fake `osascript` that touches a marker, and a `settings.json` with `{}` {src:tests/scripts/cron/test_cron_tools.py:227-237}. Inside `RealStateGuard(vault_path=None)` it runs `nightly_index.sh --skip-index` {src:tests/scripts/cron/test_cron_tools.py:240-241}. It then asserts:
  1. exit 0, and `a.md` now holds `[[b]]` {src:tests/scripts/cron/test_cron_tools.py:242-243};
  2. every new file lies under a folder the loader returns, and the fake settings file is unchanged {src:tests/scripts/cron/test_cron_tools.py:244-249};
  3. the health file lists exactly `sync_conversations`, `lint_wikilinks`, `vault_staleness`, with overall `PASS` {src:tests/scripts/cron/test_cron_tools.py:250-253}, because there is no repo list, no meetings source and the index steps are skipped {src:scripts/cron/nightly_index.sh:124-131} {src:scripts/cron/nightly_index.sh:133} {src:scripts/cron/nightly_index.sh:146};
  4. the fake `osascript` was not called, so no notification without `--notify` {src:tests/scripts/cron/test_cron_tools.py:254} {src:scripts/cron/nightly_index.sh:149};
  5. exactly one log file exists {src:tests/scripts/cron/test_cron_tools.py:255-256}.
- `test_a_failed_step_is_recorded_and_the_rest_still_run`: with no sessions folder, the script still exits 0, `sync_conversations` is `FAIL`, `lint_wikilinks` is `PASS`, and the overall result is `FAIL` {src:tests/scripts/cron/test_cron_tools.py:261-267}. The failing step exits non-zero when the sessions folder is missing {src:scripts/sync/sync_conversations.py:282-284}, the step runner records it and goes on {src:scripts/cron/nightly_index.sh:99-104}, and the script ends with `exit 0` {src:scripts/cron/nightly_index.sh:157}.
- `test_not_set_up`: with `TOLLGATE_KNOWLEDGE` and `TOLLGATE_PATHS` removed, exit 2 and "not set up" {src:tests/scripts/cron/test_cron_tools.py:271-274} {src:scripts/cron/nightly_index.sh:36}.
- `test_health_notifies_only_with_the_flag`: a fake `osascript` is first on `PATH`; `write_nightly_health.py a:FAIL:1` leaves the marker absent, and with `--notify` the marker exists {src:tests/scripts/cron/test_cron_tools.py:280-289} {src:scripts/cron/write_nightly_health.py:95-96} {src:scripts/cron/write_nightly_health.py:71}. The exit codes are not checked.
- `test_vault_staleness_writes_one_report_into_output`: a system-map note with an open checkbox and a link to `[[missing-note]]` {src:tests/scripts/cron/test_cron_tools.py:296}. Exit is 2 (issues found), the report `output/vault-health-report.md` exists, it is the only new file in the vault, and it names `missing-note` {src:tests/scripts/cron/test_cron_tools.py:299-303}. With `--report-only` the exit is 0 {src:tests/scripts/cron/test_cron_tools.py:304} {src:scripts/cron/vault_staleness.py:314}.
- `test_think_calibrate_reminder_dry_run`: with `--dry-run` and the real environment, exit 0 and the text holds `think-calibrate` {src:tests/scripts/cron/test_cron_tools.py:307-309} {src:scripts/cron/think_calibrate_reminder.sh:13} {src:scripts/cron/think_calibrate_reminder.sh:16-18}.
- `test_launchers_dry_run`: `run_task.sh all --dry-run` exits 0, names `sync_conversations`, and creates no file; an unknown task exits 2 {src:tests/scripts/cron/test_cron_tools.py:314-318} {src:scripts/cron/launchers/run_task.sh:26} {src:scripts/cron/launchers/run_task.sh:28} {src:scripts/cron/launchers/run_task.sh:50}.

**Class `BackupVault`.**
- `test_backup_encrypts_rotates_and_never_prints_the_key`: a fake key (random hex) is printed by a small script given as `--key-cmd`; the vault holds `note.md` {src:tests/scripts/cron/test_cron_tools.py:324-329}. The test expects exit 0, the key absent from stdout and stderr, one `vault-*.enc` file in `output/backups` and one in the copy folder, the text `hello backup` absent from the archive bytes, a successful decrypt that lists `note.md`, and no leftover temp file {src:tests/scripts/cron/test_cron_tools.py:333-343}. The script names the archive `vault-<date>.enc`, writes it through a temp file and a rename, and copies it to the second folder {src:scripts/cron/backup_vault.sh:43-44} {src:scripts/cron/backup_vault.sh:100} {src:scripts/cron/backup_vault.sh:151}. The decrypt step in the test uses 600000 iterations, which must equal the script's value {src:tests/scripts/cron/test_cron_tools.py:340} {src:scripts/cron/backup_vault.sh:41}. No rotation is tested, despite the name (see Notes).
- `test_missing_key_and_missing_copy_folder_are_refused`: no `--key-cmd` exits 1; a key command that prints nothing exits 1; a missing copy folder exits 1 and is not created, and the backups folder is not created either {src:tests/scripts/cron/test_cron_tools.py:351-357} {src:scripts/cron/backup_vault.sh:55-58} {src:scripts/cron/backup_vault.sh:63-68} {src:scripts/cron/backup_vault.sh:79-82} {src:scripts/cron/backup_vault.sh:84}.
- `test_dry_run_writes_nothing`: exit 0, "would write" in stdout, no files {src:tests/scripts/cron/test_cron_tools.py:363-365} {src:scripts/cron/backup_vault.sh:50}.
- `test_option_without_a_value_fails_instead_of_looping`: for each of `--key-cmd` and `--copy-to` given alone as the only argument, the script is run with a 20 second timeout, must exit 2, and must print "missing value" on stderr {src:tests/scripts/cron/test_cron_tools.py:369-372}. The script tests that a second word is left before it reads the value and exits 2 with that message {src:scripts/cron/backup_vault.sh:30} {src:scripts/cron/backup_vault.sh:31}. The short timeout is passed through `run` {src:tests/scripts/cron/test_cron_tools.py:370} {src:tests/scripts/cron/test_cron_tools.py:37-39}, so a return of the old endless loop would end as a timeout error from `subprocess.run` {src:docs:https://docs.python.org/3/library/subprocess.html#subprocess.run}. The test passes no vault, so it also relies on the option loop running before any folder lookup {src:scripts/cron/backup_vault.sh:28-35} {src:scripts/cron/backup_vault.sh:37}.

## Diagram

None: each test builds its own throwaway home, and the only mock is a fake launcher or fake `osascript` script written into that home.

## Notes

- **Code and description disagree.**
  - The test name says the backup "rotates" {src:tests/scripts/cron/test_cron_tools.py:322}. The test makes one archive and asserts nothing about removing old ones, so the rotation code {src:scripts/cron/backup_vault.sh:103-145} is not exercised with anything to remove.
  - The remove test says "deletes only the job file" {src:tests/scripts/cron/test_cron_tools.py:134}; it asserts that the file is gone and the launcher is untouched, not that nothing else was deleted.
  - The header says the nightly scripts "write only inside folders the path loader returns" {src:tests/scripts/cron/test_cron_tools.py:8-9}. Only one test asserts that, for `nightly_index.sh --skip-index` {src:tests/scripts/cron/test_cron_tools.py:244-248}. Because the vault is itself a loader folder, any write under the vault passes that check.
  - The nightly script's header says every step runs even when an earlier one fails {src:scripts/cron/nightly_index.sh:5-6}, yet it stops before any step when the vault folder is missing {src:scripts/cron/nightly_index.sh:84-89} or `python3` is missing {src:scripts/cron/nightly_index.sh:91-94}. The vault case is pinned by a test here {src:tests/scripts/cron/test_cron_tools.py:182-186}.
  - The README line that says tests "never touch your real files" {src:scripts/README.md:31} is true for writes. Several tests here read the real environment: two import `vault_staleness` in the test process, which reads the real paths file at import {src:scripts/cron/vault_staleness.py:32-38}, and two run scripts with a copy of the real environment {src:tests/scripts/cron/test_cron_tools.py:307} {src:tests/scripts/cron/test_cron_tools.py:238-239}.
- **Weak checks.** The missing-value test checks the text "missing value" but not which option name is in the message {src:tests/scripts/cron/test_cron_tools.py:372}, and does not cover an option followed by another option word, which the script accepts as the value {src:scripts/cron/backup_vault.sh:30}. The `loaded` check accepts any text that contains the word, such as "not loaded"; the stub log is the strong proof {src:tests/scripts/cron/test_cron_tools.py:103} {src:tests/scripts/cron/test_cron_tools.py:104-107}. The "no `@` left" check would also fail if a carried path held an `@` {src:tests/scripts/cron/test_cron_tools.py:96}. The `secret` check cannot detect a secret with another name {src:tests/scripts/cron/test_cron_tools.py:161}. The notification test ignores exit codes {src:tests/scripts/cron/test_cron_tools.py:286-288}. The staleness layout test mixes a positive and a negative check {src:tests/scripts/cron/test_cron_tools.py:202-204}.
- **Real environment and machine paths.** `test_vault_staleness_rules_come_from_the_layout` and the report test assume the default folder name `01-system-map` or ask the test process for it {src:tests/scripts/cron/test_cron_tools.py:202} {src:tests/scripts/cron/test_cron_tools.py:294}. The child process uses the throwaway environment but the test process uses the real one, so a real paths file that renames `system_map` could make them disagree. The nightly run test wraps the script in a guard that checksums the real `~/.claude/settings.json` before and after, so it reads the real home even though the script runs in the throwaway one {src:tests/harness/real_guard.py:46-47} {src:tests/scripts/cron/test_cron_tools.py:240}. The backup test needs `openssl` with `-pbkdf2` and `tar` on `PATH` {src:tests/scripts/cron/test_cron_tools.py:340}.
- **Python version.** `Path.is_relative_to` needs Python 3.9 or later {src:tests/scripts/cron/test_cron_tools.py:248}; the 3.12 minimum covers that.
- **Time.** A retry step in the nightly script sleeps 30 seconds {src:scripts/cron/nightly_index.sh:114-115}. It applies only to the repo and meeting steps, which the tests never switch on, so the tests do not wait.
- **Inputs that reach paths, commands or text without a check.**
  - The decrypt command is a string run with `shell=True`, with the archive path inside single quotes and no escaping {src:tests/scripts/cron/test_cron_tools.py:339-341}. The path comes from a temp folder, so it is safe here.
  - `backup_vault.sh` runs its `--key-cmd` text with `bash -c` twice, with no check on it {src:scripts/cron/backup_vault.sh:79} {src:scripts/cron/backup_vault.sh:87}. That is by design: the caller supplies the command.
  - `setup_cron.py` accepts any `--program` path without checking that it exists {src:scripts/cron/setup_cron.py:83}. Values in the plist are XML-escaped {src:scripts/cron/setup_cron.py:97-98}.
  - `nightly_index.sh` reads one line from a `meetings-source` file and passes it to another script as `--source` with no check {src:scripts/cron/nightly_index.sh:58} {src:scripts/cron/nightly_index.sh:128}.
- **Writes to shared files.** All writes are inside throwaway homes. The scripts under test write health, log and report files with plain writes, not temp-and-rename {src:scripts/cron/write_nightly_health.py:65} {src:scripts/cron/vault_staleness.py:309} {src:scripts/cron/setup_cron.py:166}; nothing prevents two nightly runs from writing the same health file at once. The backup is written through a temp file and a rename {src:scripts/cron/backup_vault.sh:100}.
- **Header.** The `Date:` field of the header is empty {src:tests/scripts/cron/test_cron_tools.py:6}.
