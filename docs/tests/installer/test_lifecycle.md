---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/installer/test_lifecycle.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "source of helpers.sh, then make_repo_copy, then the LIF-01 block"    # function or line that executes when the script runs
requires: ["bash", "python3", "tar", "grep", "ls", "diff", "sed", "readlink", "uname", "wc"]       # external commands or tools this script depends on
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

This script holds the installer lifecycle tests (LIF-01 to LIF-15): what the installer does on a second run, how it handles dropped or renamed files, uninstall, backup pruning, the Claude Code version check, the Python environment step, the nightly job and the local search model. It is not run on its own. The installer test runner sources it and supplies the `check` function and two variables {src:tests/installer/test_lifecycle.sh:2-3}. It produces `PASS` and `FAIL` lines through that runner and changes nothing outside a temporary work folder.

## Dependencies

**Depends on.**
- [[helpers]] ([helpers](helpers.md)): the throwaway-home helpers (`new_world`, `run_install`, `snapshot`, `clone_repo`, `seed_user_settings`, `user_settings_survive`), sourced on the first line of code {src:tests/installer/test_lifecycle.sh:9}.
- [[run]] ([run](run.md)): the runner that defines `check`, `WORK` and `TOLLGATE_DIR` before sourcing this file {src:tests/installer/run.sh:8-23}.
- `install.sh` in the repo root, run from a private copy of the repo {src:tests/installer/helpers.sh:55}. Also [[manifest]] ([manifest](../../installer/manifest.md)) {src:install.sh:488}, [[merge_settings]] ([merge_settings](../../installer/merge_settings.md)) {src:install.sh:486} and [[setup_venv]] ([setup_venv](../../scripts/core/setup_venv.md)) {src:install.sh:1616}.
- Commands: `python3` (also with `-I`) {src:tests/installer/test_lifecycle.sh:44}, `grep`, `ls`, `diff`, `sed` {src:tests/installer/test_lifecycle.sh:157}, `readlink` {src:tests/installer/test_lifecycle.sh:161}, `uname` {src:tests/installer/test_lifecycle.sh:251}, `wc`.
- Environment variables it sets for the code under test: `INSTALL_REPO` {src:tests/installer/test_lifecycle.sh:58}, `RUN_PATH` {src:tests/installer/test_lifecycle.sh:190}, `TOLLGATE_BASE_PYTHON` {src:tests/installer/test_lifecycle.sh:231}, `TOLLGATE_CRON_LAUNCHER` {src:tests/installer/test_lifecycle.sh:257}, `TOLLGATE_DOWNLOAD_MODEL` and `MODEL_FAIL` {src:tests/installer/test_lifecycle.sh:292}.

**Used by.**
- Product code: none (searched `git grep` for `test_lifecycle`, 2026-11-20).
- Tests: sourced by the installer runner {src:tests/installer/run.sh:101}. CI runs that runner {src:.github/workflows/tests.yml:38}.

## Behavior

Every install runs in a throwaway home made by `new_world`, against a copy of the repo made by `make_repo_copy` {src:tests/installer/test_lifecycle.sh:10} {src:tests/installer/helpers.sh:16-21}. The `inst` shortcut adds the fixed answers (name, vault, initials, ticket prefix) and runs non-interactively {src:tests/installer/test_lifecycle.sh:16}. Each block below ends in one or more `check` lines; a check passes only when its command text prints `true`.

| Block | Scenario and what it proves |
|---|---|
| LIF-01 | A second run with a user's own command file present exits 0, still merges settings, leaves the file alone, copies nothing into the repo and keeps the file out of the manifest {src:tests/installer/test_lifecycle.sh:19-31}. |
| LIF-02 | A second run changes no file (a before and after checksum list is compared), the installed-version file equals the `VERSION` file, the manifest names the commands, hooks and version, and no full `.claude` backup is made on an update {src:tests/installer/test_lifecycle.sh:33-51}. |
| LIF-03 | A command dropped upstream is removed from the home and saved under a `removed` folder; a rename counts as one removal plus one add; a user's own command is never removed {src:tests/installer/test_lifecycle.sh:53-70}. |
| LIF-04 | A hook dropped from the settings template leaves the installed settings on the next run, while the user's own hook and keys survive {src:tests/installer/test_lifecycle.sh:72-101}. |
| LIF-05 | `--uninstall` removes only manifest entries: user settings survive, no Tollgate hook is left, commands are gone but saved, the notes folder and saved answers stay, a settings backup exists, a second uninstall with no manifest exits 0, and `--dry-run` changes nothing {src:tests/installer/test_lifecycle.sh:103-124}. The installer's no-manifest branch prints a note and exits 0 {src:install.sh:476-478}. |
| LIF-06 | Five fake full backups and five per-file `.bak` copies are pruned to the newest three; folders with other names are never deleted {src:tests/installer/test_lifecycle.sh:126-140}. The installer keeps 3 {src:install.sh:12}, deletes only names ending in 14 digits {src:install.sh:356} {src:install.sh:366}. |
| LIF-07 | An edited cursor rule is backed up as `.bak`, then replaced {src:tests/installer/test_lifecycle.sh:142-149}. |
| LIF-08 | A private memory note in another project folder is not copied into the repo, the memory link uses a slug where every non-letter and non-digit becomes `-`, and `.gitignore` ignores memory notes except the index {src:tests/installer/test_lifecycle.sh:151-163}. The ignore lines exist {src:.gitignore:8-9}. |
| LIF-09 | A line added to the paths file changes the folder the installer creates, and `install.sh` no longer holds its own folder list {src:tests/installer/test_lifecycle.sh:165-171}. The paths file format is `name: value` {src:scripts/core/paths.py:85-89}. |
| LIF-10 | The Claude Code version check: a newer version gives no warning; older (including an older major version) warns that hooks will not fail closed and still installs; missing Claude Code warns; `--strict` stops with exit 1 before anything is written for older or missing, and passes at exactly the minimum {src:tests/installer/test_lifecycle.sh:173-203}. The installer holds the minimum {src:install.sh:8}, compares numerically with "less than" {src:install.sh:449}, prints the warning {src:install.sh:456-457} and stops under `--strict` {src:install.sh:465-467}. |
| LIF-11 | `--help` exits 0, names nine flags and writes nothing; an unknown flag exits 2 and writes nothing {src:tests/installer/test_lifecycle.sh:205-214}. The installer exits 0 after help {src:install.sh:83} and 2 on an unknown flag {src:install.sh:99}. |
| LIF-12 | With stub Python and pip, `--with-venv` builds the venv, installs `scripts/requirements.txt`, adds no model package, runs the index build with the venv Python, and sets `TOLLGATE_PYTHON` in settings; `--skip-venv` never builds; no flag in non-interactive mode builds nothing {src:tests/installer/test_lifecycle.sh:216-248}. In the simple install mode the installer asks and the default answer is no {src:install.sh:1647-1648}; whether the test run takes that mode was not traced. |
| LIF-13 | On macOS only: no flag means no job file and no launcher call; `--with-cron` writes the job file and calls the stub launcher with `bootstrap`; the manifest records the job; `--uninstall` removes the file and calls `bootout` {src:tests/installer/test_lifecycle.sh:250-264}. The installer hands the launcher name to the cron script {src:install.sh:1674-1675}. |
| LIF-14 | The local embedding model step: skipped without a yes; `TOLLGATE_DOWNLOAD_MODEL=1` installs it and runs the download script with `--yes-download`; a failing install prints one line and the install still finishes and builds the index; `=0` skips {src:tests/installer/test_lifecycle.sh:266-298}. The installer's logic and its one-line failure message are in `offer_local_model` {src:install.sh:1582-1604}. |
| LIF-15 | An install that used a skill prefix is upgraded to the fixed `tg-` names: old listed command files are removed and backed up, look-alike user files survive, one profile block with no prefix replaces the old one, and a later uninstall leaves the user's commands {src:tests/installer/test_lifecycle.sh:300-326}. The new marker has no prefix {src:install.sh:1524}. |

Stubs used: a `security` stub, a stub launcher, a stub base Python that builds a fake venv with logging `pip` and `python3`, and fake `claude` scripts {src:tests/installer/helpers.sh:33-39} {src:tests/installer/test_lifecycle.sh:253} {src:tests/installer/test_lifecycle.sh:218-229} {src:tests/installer/test_lifecycle.sh:174}. So the venv, model and cron checks prove the call shape, not that a real `pip` or `launchctl` works.

## Diagram

None: the file is a list of independent scenarios run top to bottom, with no branching beyond one macOS-only block and one skip path.

## Notes

**Where the file and its own description disagree.**
- The header says the tests are LIF-01 to LIF-13 {src:tests/installer/test_lifecycle.sh:2}, but the file also holds LIF-14 {src:tests/installer/test_lifecycle.sh:266} and LIF-15 {src:tests/installer/test_lifecycle.sh:300}.
- The banner printed at the start names update path, manifest, backups, uninstall, version, venv and cron {src:tests/installer/test_lifecycle.sh:12}; it leaves out the model step and the prefix upgrade.

**Dead or odd lines.** The helper `_flags` {src:tests/installer/test_lifecycle.sh:14} is never called (searched `tests/installer` for `_flags`, 2026-11-20). The line `echo "mine" > /dev/null` {src:tests/installer/test_lifecycle.sh:57} has no effect.

**Checks that cannot fail or depend on the machine.**
- LIF-10 prints a `PASS` named "skipped" when a real `claude` is on the minimal test path {src:tests/installer/test_lifecycle.sh:187-189}. That line always passes.
- LIF-13 is skipped on anything but macOS {src:tests/installer/test_lifecycle.sh:251}.
- LIF-10 uses the machine's `python3` location to build a minimal PATH {src:tests/installer/test_lifecycle.sh:185-186}.
- LIF-04 picks the first hook in the settings template with a `/hooks/` command {src:tests/installer/test_lifecycle.sh:77-85}; if the template changes shape the "before" count check can fail for a reason unrelated to the installer.
- LIF-02 and LIF-08 read the real repo's `VERSION` and `.gitignore`, not the copy {src:tests/installer/test_lifecycle.sh:42} {src:tests/installer/test_lifecycle.sh:163}.

**Unchecked inputs.** The only inputs are constants and paths built under `$WORK`. Nothing from outside reaches a command or network address; the `claude` and `python3` names come from the test's own PATH. The tests never call the network, since the base Python and the launcher are stubs {src:tests/installer/test_lifecycle.sh:253} {src:tests/installer/test_lifecycle.sh:231}.

**Shared-file writes.** All writes go to the temporary `$WORK` folder, which the runner removes on exit {src:tests/installer/run.sh:10-11}. Each scenario has its own home, so no two writers meet. One exception to "nothing outside": the clone and copy helpers read the real repo and write only into `$WORK` {src:tests/installer/helpers.sh:24-29}.
