---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/installer/run.sh    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "top-level script body: sets WORK and the trap, runs cases t1 to t4, then sources the three test files"    # function or line that executes when the script runs
requires:          # external commands or tools this script depends on
  - bash
  - mktemp
  - awk
  - find
  - sort
  - xargs
  - cksum
  - python3
  - grep
  - ls
  - cp
  - rm
  - chmod
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

The runner for the installer safety tests. It makes a temporary work folder, runs four first-party cases that check backup, clean, dry-run and secret handling in `install.sh`, then sources the three larger test files and the Python unit tests, and prints a pass and fail count. It exits 0 only when nothing failed.

## Dependencies

**Depends on.**
- `install.sh` at the repo root {src:tests/installer/run.sh:9}. Vault copy: [[install]]. Repo copy: [install](../../install.md).
- Sourced test files: [[test_ins]] ([test_ins](test_ins.md)) {src:tests/installer/run.sh:97}, [[test_lifecycle]] ([test_lifecycle](test_lifecycle.md)) {src:tests/installer/run.sh:101}, [[test_vault_git]] ([test_vault_git](test_vault_git.md)) {src:tests/installer/run.sh:105}. These in turn source [[helpers]] ([helpers](helpers.md)).
- Python unit tests found by `unittest discover` in the same folder: `test_manifest.py` and `test_merge_settings.py` {src:tests/installer/run.sh:110}.
- Programs listed in `requires`. `python3 -I` is used for the unit tests {src:tests/installer/run.sh:110}.

**Used by.** Searched with `git grep` outside `docs/` on 2026-11-20.
- The CI workflow runs `bash tests/installer/run.sh` on Ubuntu and macOS {src:.github/workflows/tests.yml:38} {src:.github/workflows/tests.yml:17}.
- No product code calls it (searched the worktree outside `docs/`).

## Behavior

**Setup.** `set -uo pipefail` without `-e`, so a failing command does not stop the run; failures are counted by `check` {src:tests/installer/run.sh:6}. `TOLLGATE_DIR` is two folders above this file {src:tests/installer/run.sh:8}. `WORK` is a `mktemp -d` folder {src:tests/installer/run.sh:10}, deleted on exit after a `chmod -R u+rwx` so read-only test folders can go {src:tests/installer/run.sh:11}. `check DESC COND` prints PASS or FAIL and bumps a counter; the condition must be the text `true` {src:tests/installer/run.sh:16-23}. `new_home NAME` makes a fake `~/.claude` with a `CLAUDE.md`, a command file and a stub `security` program that logs its arguments {src:tests/installer/run.sh:25-33}.

**Case t1, failed backup in clean mode.** `cp` is replaced by a function that fails {src:tests/installer/run.sh:46}. The functions `backup_claude_dir` and `clean_claude_dir` are pulled out of `install.sh` with `awk` and evaluated {src:tests/installer/run.sh:45}. The case expects a non-zero result and the fake `~/.claude` untouched {src:tests/installer/run.sh:51-52}. This follows `install.sh`: a failed copy blanks the backup folder and returns 1 {src:install.sh:383-385}, and the clean function refuses to run without a verified backup {src:install.sh:403-406}.

**Case t2, good backup then clean.** Runs both functions in order {src:tests/installer/run.sh:56-58}; expects exit 0, a backup folder holding the original files, and an empty `~/.claude` {src:tests/installer/run.sh:60-63}. `install.sh` compares file counts in source and copy {src:install.sh:387-393} and then deletes and recreates the folder {src:install.sh:407-408}.

**Case t2b.** Greps `install.sh` for the sentence "Clean mode needs a backup" {src:tests/installer/run.sh:67-68}; that sentence is at {src:install.sh:644}, followed by `exit 1` {src:install.sh:645}.

**Case t3, dry run.** Pipes three answers into the whole installer with `--dry-run` {src:tests/installer/run.sh:73}, compares a checksum of every file before and after {src:tests/installer/run.sh:72} {src:tests/installer/run.sh:74}, and checks exit 0, no change, no backup folder, the stub keychain never called, and that the output holds the "would delete" and "would copy" lines {src:tests/installer/run.sh:75-79}. `install.sh` prints those lines in dry-run mode {src:install.sh:380} {src:install.sh:400}.

**Case t4, secret never on the command line.** Three checks. First, no `security add-generic-password` line in `install.sh` has `-w` followed by a value {src:tests/installer/run.sh:82-83}. Second, some such line ends with `-w` {src:tests/installer/run.sh:84-85}; the `security add-generic-password` line in `cred_store` does {src:install.sh:257}. Third, the `cred_store` function is extracted and run with the stub `security` on the path, and the log must not contain the secret text {src:tests/installer/run.sh:87-93}. `install.sh` explains that a value after `-w` would sit in the process list {src:install.sh:254-255}.

**Then.** The three test files are sourced {src:tests/installer/run.sh:97} {src:tests/installer/run.sh:101} {src:tests/installer/run.sh:105}, the unit tests run with output discarded and error text printed on failure {src:tests/installer/run.sh:110-114}, and the script exits 0 only if `FAIL` is 0 {src:tests/installer/run.sh:118-119}.

## Diagram

Skipped: a straight-line script; the only branching is the unit-test pass or fail.

## Notes

- **Dead code.** `load_functions` is defined {src:tests/installer/run.sh:36-38} and never called anywhere under `tests/` (searched with `git grep` 2026-11-20); t1, t2 and t4 each repeat the `awk` extraction inline {src:tests/installer/run.sh:45} {src:tests/installer/run.sh:57} {src:tests/installer/run.sh:88}.
- **Code versus description.** The comment above the `source` line for the first test file says it covers INS-00 to INS-11 {src:tests/installer/run.sh:95}, which matches the file it sources: the newest block is INS-11 (installed commands, a repo path with a space, escaped workspace paths, profile quoting and the meetings folder) {src:tests/installer/test_ins.sh:303}, and that file's header also says INS-00 to INS-11 {src:tests/installer/test_ins.sh:2}. The comment says only the two backup functions are loaded {src:tests/installer/run.sh:35}; the `awk` also prints the file-count helper line {src:tests/installer/run.sh:37}. The header says every case runs in a temp `HOME` {src:tests/installer/run.sh:4}. Case t3 sets `HOME` and `PATH` but does not clear `TOLLGATE_` variables, `CLAUDE_DOTFILES` or git config as `run_install` does {src:tests/installer/run.sh:73} {src:tests/installer/helpers.sh:47-51}; a developer's own values reach the dry run. In dry-run mode `install.sh` writes nothing, which is what t3 asserts.
- **Tests that can pass without proving much.** t2b only checks a sentence exists in the source {src:tests/installer/run.sh:67-68}. The first t4 check passes if `install.sh` had no `add-generic-password` line at all {src:tests/installer/run.sh:82-83}. The last t4 check passes when `security.log` does not exist {src:tests/installer/run.sh:92-93}, for example if the extracted function failed before calling the stub. t4 forces `OS=Darwin` {src:tests/installer/run.sh:87}, so it tests the macOS branch on every host.
- **Inputs reaching a path, command, network address or outbound text without a check.** The `eval` calls run text cut from `install.sh` by `awk` {src:tests/installer/run.sh:37} {src:tests/installer/run.sh:45}; the source is the repo under test. `rm -rf "$WORK"` runs on exit with a value from `mktemp` and no emptiness check {src:tests/installer/run.sh:11}; an empty value would delete nothing. `xargs cksum` splits on spaces, so a work folder path with spaces would break the before and after compare {src:tests/installer/run.sh:72}.
- **Writes to shared files.** Output files `t3.out` and `unit.err` are written under `$WORK` with plain redirection, no lock {src:tests/installer/run.sh:73} {src:tests/installer/run.sh:110}. The stub keychain log is appended inside each fake home {src:tests/installer/run.sh:30}. Nothing is written outside `$WORK`.
- **OS assumptions.** `find`, `xargs` and `cksum` differ slightly between BSD and GNU; CI runs both {src:.github/workflows/tests.yml:17}.
