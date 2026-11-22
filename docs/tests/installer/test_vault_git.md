---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/installer/test_vault_git.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-19
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "source helpers.sh, then make_repo_copy"    # function or line that executes when the script runs
requires: ["bash", "git", "sed", "grep", "wc", "tr", "tar", "python3"]       # external commands or tools this script depends on
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

This script holds the installer tests for the vault git setting, named `VGT-01` to `VGT-09` in its header. The setting says how the notes vault is saved: `none` (plain files), `local` (a git repository) or `remote` (a git repository with a printed reminder to add a remote). The script is not run on its own: the installer test runner sources it and supplies the `check` function and the `WORK` and `TOLLGATE_DIR` variables. It runs the installer 17 times in throwaway homes and records 12 pass or fail checks.

## Dependencies

**Depends on.**
- Test runner `tests/installer/run.sh`, which sources this file and defines `check`, `WORK` and `TOLLGATE_DIR` {src:tests/installer/run.sh:105} {src:tests/installer/run.sh:16} {src:tests/installer/run.sh:8} {src:tests/installer/run.sh:10}. Page: [[run]] (no doc yet).
- Helper file `tests/installer/helpers.sh`, sourced on the first line of code {src:tests/installer/test_vault_git.sh:8}: [[helpers]] (no doc yet). It provides `make_repo_copy`, `new_world` and `run_install` {src:tests/installer/helpers.sh:16} {src:tests/installer/helpers.sh:33} {src:tests/installer/helpers.sh:43}.
- Product code under test: the installer `install.sh` [[install]] (no doc yet), the path loader `scripts/core/paths.py` [[paths]] (no doc yet), and the command `scripts/core/tg_vault_git` [[tg_vault_git]] and [tg_vault_git](../../scripts/core/tg_vault_git.md).
- Outside programs: `bash`, `git`, `sed`, `grep`, `wc`, `tr` and `tar` (the helper copies the repo with `tar` {src:tests/installer/helpers.sh:20}), and `python3` for the `tg_vault_git` command {src:scripts/core/tg_vault_git:1}.
- Environment: `TOLLGATE_VAULT_GIT` is set for one install {src:tests/installer/test_vault_git.sh:38}. The helper clears the other `TOLLGATE_*` variables listed in it before each install and sets `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_NOSYSTEM` inside that run {src:tests/installer/helpers.sh:47} {src:tests/installer/helpers.sh:51}.

**Used by.** Only the runner `tests/installer/run.sh` {src:tests/installer/run.sh:105}. The workflow `.github/workflows/tests.yml` runs that runner {src:.github/workflows/tests.yml:38}. Searched 2026-11-19: the whole worktree except `.git`, `docs/`, caches and virtual environments for `test_vault_git`; the other hits were the Python test `tests/scripts/core/test_vault_git.py` (a different file) and the runner line above. Related: the Python test for the same setting, `tests/scripts/core/test_vault_git.py` (no doc yet).

## Behavior

Setup. The file makes one shared copy of the repo for the whole run {src:tests/installer/test_vault_git.sh:9}; the helper skips the copy if it already exists {src:tests/installer/helpers.sh:17}. Three local helpers wrap the install: `vg_inst` runs the installer non-interactively with a fixed name, initials and ticket prefix {src:tests/installer/test_vault_git.sh:13}, `vg_line` prints the saved `vault_git` value from the paths file in the throwaway home {src:tests/installer/test_vault_git.sh:14}, and `vg_has_git` prints `true` when the vault has a `.git` entry {src:tests/installer/test_vault_git.sh:15}. Each case calls `new_world` to get a fresh home folder {src:tests/installer/helpers.sh:33}. The installer's own output goes to `last.out` next to the home {src:tests/installer/helpers.sh:45} {src:tests/installer/helpers.sh:59}.

**Cases**

1. `VGT-01`: `--vault-git none` must exit 0, save `none` and leave the vault without `.git` {src:tests/installer/test_vault_git.sh:19} {src:tests/installer/test_vault_git.sh:21}. The installer takes the flag as the explicit mode {src:install.sh:116}, saves it {src:install.sh:984}, and runs `git init` only when the mode is not `none` {src:install.sh:987}.
2. `VGT-02`: `--vault-git local` must exit 0, save `local`, make the vault a git repository and add no remote {src:tests/installer/test_vault_git.sh:25} {src:tests/installer/test_vault_git.sh:27}. An explicit flag answers yes to the init question without asking {src:install.sh:988} {src:install.sh:996}, and the installer never adds a remote {src:install.sh:951}.
3. `VGT-03`: `--vault-git=remote` (the equals form {src:install.sh:85}) must save `remote`, make the repository, add no remote, and print the text `remote add origin` {src:tests/installer/test_vault_git.sh:31} {src:tests/installer/test_vault_git.sh:33} {src:tests/installer/test_vault_git.sh:34}. The installer prints that reminder for the `remote` mode {src:install.sh:1005} {src:install.sh:1006}.
4. `VGT-04`: with `TOLLGATE_VAULT_GIT=local` and no flag, the saved value must be `local` and the vault a git repository; with the same variable and `--vault-git none`, the saved value must be `none` and the vault must have no `.git` {src:tests/installer/test_vault_git.sh:38} {src:tests/installer/test_vault_git.sh:41} {src:tests/installer/test_vault_git.sh:43}. The installer reads the flag first and the variable second {src:install.sh:116}. The helper does not clear `TOLLGATE_VAULT_GIT` before an install {src:tests/installer/helpers.sh:47}, which is why the variable reaches the installer. The variable is exported inside a subshell, so it does not leak to later cases {src:tests/installer/test_vault_git.sh:38}.
5. `VGT-05`: four installs with no flag and no variable, followed by two checks {src:tests/installer/test_vault_git.sh:49} {src:tests/installer/test_vault_git.sh:52} {src:tests/installer/test_vault_git.sh:55} {src:tests/installer/test_vault_git.sh:57}. A fresh vault that does not exist yet must save `none` and get no `.git`; a plain existing folder must save `none`; a git vault with no remote must save `local`; a git vault with a remote must save `remote` {src:tests/installer/test_vault_git.sh:58} {src:tests/installer/test_vault_git.sh:59}. The installer detects the mode from the folder {src:install.sh:959} {src:install.sh:961} {src:install.sh:963}, and an unattended run with no mode given turns any mode other than `none` into `none` when there is no `.git` {src:install.sh:979} {src:install.sh:980}. The second check requires the no-remote vault to still have zero remotes and the remote vault to still have exactly `origin` {src:tests/installer/test_vault_git.sh:60} {src:tests/installer/test_vault_git.sh:61}.
6. `VGT-05e`: a saved `local` on a folder without `.git` is edited into the paths file with `sed`, and an unattended re-run must save `none` and not run `git init` {src:tests/installer/test_vault_git.sh:64} {src:tests/installer/test_vault_git.sh:65} {src:tests/installer/test_vault_git.sh:66} {src:tests/installer/test_vault_git.sh:68}. The installer reads the saved value {src:install.sh:956} {src:install.sh:957}, uses it as the default {src:install.sh:966}, then applies the same follow-the-folder rule as case 5 {src:install.sh:979}.
7. `VGT-06`: after saving `none`, an update with no flag must keep `none`, leave exactly one `vault_git:` line and make no `.git` {src:tests/installer/test_vault_git.sh:72} {src:tests/installer/test_vault_git.sh:73} {src:tests/installer/test_vault_git.sh:75}. A later run with `--vault-git local` must change the saved value to `local` {src:tests/installer/test_vault_git.sh:76} {src:tests/installer/test_vault_git.sh:77}. The installer drops old `vault_git` lines before it writes the new one {src:install.sh:984}.
8. `VGT-07`: `--vault-git sometimes` must exit 2 and write no paths file {src:tests/installer/test_vault_git.sh:81} {src:tests/installer/test_vault_git.sh:83}. The installer checks the value right after reading flags and stops with exit 2 {src:install.sh:118} {src:install.sh:120}.
9. `VGT-08`: after installing with `local`, the command `tg_vault_git` run against that paths file and vault must print `local` {src:tests/installer/test_vault_git.sh:87} {src:tests/installer/test_vault_git.sh:88} {src:tests/installer/test_vault_git.sh:89}. The command prints the loader's answer {src:scripts/core/tg_vault_git:23}. The loader returns the saved line when it is one of the three modes {src:scripts/core/paths.py:168} {src:scripts/core/paths.py:169} {src:scripts/core/paths.py:170}, and otherwise detects it from the folder {src:scripts/core/paths.py:171}.
10. `VGT-09`: `--dry-run` with `--vault-git local` must exit 0, write no paths file and make no repository {src:tests/installer/test_vault_git.sh:93} {src:tests/installer/test_vault_git.sh:95}. The installer stops in dry-run mode at a line before the vault git step {src:install.sh:756} {src:install.sh:771} {src:install.sh:949}.

## Diagram

None: the script is a sequence of independent installs, and its only branching is the exit status test inside each check.

## Notes

**Checks that cannot tell the cause.** `VGT-08` installs with `--vault-git local`, which also makes the vault a git repository with no remote. The loader's detection gives `local` for exactly that vault {src:scripts/core/paths.py:150} {src:scripts/core/paths.py:157} {src:scripts/core/paths.py:159}, so the test would still pass if the command ignored the saved line and detected the mode. The name says the command "agrees with what the installer saved" {src:tests/installer/test_vault_git.sh:85}; a saved value that differs from the folder (for example `none` on a git vault) would prove it.

**Gaps and checks that prove less than their text.**
- The second `VGT-05` check is named "never added a remote or pushed" {src:tests/installer/test_vault_git.sh:60}, but it counts remotes only {src:tests/installer/test_vault_git.sh:61}. No assertion looks for a push. The remote address in that case is a made-up one {src:tests/installer/test_vault_git.sh:53}, so a push would fail by itself.
- In `VGT-05`, the exit code variable is read once, after the first install {src:tests/installer/test_vault_git.sh:49} {src:tests/installer/test_vault_git.sh:58}. The other three installs are judged by the saved value alone.
- In `VGT-04`, the exit codes of both installs are not read {src:tests/installer/test_vault_git.sh:38} {src:tests/installer/test_vault_git.sh:41}.
- The second `VGT-06` check does not look at `.git` after the `local` run {src:tests/installer/test_vault_git.sh:77}, although the installer runs `git init` for an explicit mode {src:install.sh:996}.
- Branches without a case: the interactive question {src:install.sh:971}, an answer of `n` to the init question {src:install.sh:991} {src:install.sh:1002}, and a failed `git init` {src:install.sh:1000}.

**Description versus code.**
- The header says "no remote is ever added" {src:tests/installer/test_vault_git.sh:4}, but `VGT-05` adds `origin` to its own fixture vault with `git remote add` {src:tests/installer/test_vault_git.sh:53}. The statement holds for the installer, not for the test script.
- The header names `VGT-01` to `VGT-09` {src:tests/installer/test_vault_git.sh:2}; the file records 12 `check` results, because `VGT-05`, `VGT-05e` and `VGT-06` have more than one each {src:tests/installer/test_vault_git.sh:57} {src:tests/installer/test_vault_git.sh:60} {src:tests/installer/test_vault_git.sh:67} {src:tests/installer/test_vault_git.sh:74} {src:tests/installer/test_vault_git.sh:77}.

**Machine path and tool dependence.**
- The tests read the paths file at `$H/.claude/tollgate/paths.yaml` {src:tests/installer/test_vault_git.sh:14}. That matches the installer default only while `TOLLGATE_PATHS` is unset, which the helper guarantees {src:tests/installer/helpers.sh:47} {src:install.sh:926} {src:install.sh:7}.
- The test's own `git init` and `git remote add` calls run in the caller's shell, outside the isolation that `run_install` sets {src:tests/installer/test_vault_git.sh:51} {src:tests/installer/test_vault_git.sh:53} {src:tests/installer/helpers.sh:51}. A user's global git settings apply to those fixture repositories.
- `VGT-08` starts `tg_vault_git` through its `python3` shebang {src:scripts/core/tg_vault_git:1} with the `python3` on the caller's `PATH`, not the `PATH` that `run_install` builds {src:tests/installer/test_vault_git.sh:88} {src:tests/installer/helpers.sh:52}. The loader needs Python 3.7 or newer because of its future annotations import {src:scripts/core/paths.py:12}.
- `sed -i.bak` {src:tests/installer/test_vault_git.sh:65} is accepted by both the macOS and GNU versions of `sed`, and leaves `paths.yaml.bak` in the throwaway home.

**Running it alone.** The file sets no `WORK` and defines no `check`. Run directly with `WORK` unset, the first code line after sourcing the helper calls `make_repo_copy` {src:tests/installer/test_vault_git.sh:9}, whose target is `$WORK/repo` {src:tests/installer/helpers.sh:17}, which becomes `/repo`, and it then calls `mkdir -p` on it {src:tests/installer/helpers.sh:19}. Run only through `tests/installer/run.sh`.

**Inputs without a check.** All inputs are literals in the file. The `--vault-git` values come from the file itself, and the bad value in `VGT-07` is a fixed word {src:tests/installer/test_vault_git.sh:81}. Paths are built under `$WORK`, a folder made by the runner with `mktemp -d` {src:tests/installer/run.sh:10}.

**Writes to shared files.** None outside `$WORK`. The runner removes `$WORK` on exit and first restores write permission {src:tests/installer/run.sh:11}. The paths file is replaced by writing a temporary file and then moving it over the original {src:install.sh:983} {src:install.sh:984} {src:install.sh:985}, which is atomic on one file system; nothing stops two installers from writing the same paths file at once, and the script runs them one at a time. The 17 installs use separate homes, except `VGT-05e` and `VGT-06`, which run several installs against one home in sequence {src:tests/installer/test_vault_git.sh:64} {src:tests/installer/test_vault_git.sh:66} {src:tests/installer/test_vault_git.sh:72} {src:tests/installer/test_vault_git.sh:73} {src:tests/installer/test_vault_git.sh:76}.

This script was not run while writing the page: it runs only inside the whole installer runner, so the pass or fail state of the 12 checks is not confirmed here {unverified}.
