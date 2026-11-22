---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/installer/helpers.sh    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "none: a sourced file; it sets FAKE_USER and defines nine functions"    # function or line that executes when the script runs
requires:          # external commands or tools this script depends on
  - bash
  - tar
  - find
  - sort
  - cksum
  - python3
  - mkdir
  - chmod
  - cat
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

Shared helper functions for the installer tests. They build a private copy of the repo, a throwaway home folder with a stub keychain command, and a wrapper that runs `install.sh` inside that home. The aim is that no installer test can touch the real `~/.claude`, shell profile, keychain or repo. This file has no `check` calls of its own and is not run directly.

## Dependencies

**Depends on.**
- Caller-provided variables `WORK` (a `mktemp -d` folder) and `TOLLGATE_DIR` (repo root) {src:tests/installer/helpers.sh:10}. Optional `INSTALL_REPO`, `RUN_PATH` and `INSTALL_STDIN` {src:tests/installer/helpers.sh:9} {src:tests/installer/helpers.sh:54}.
- `install.sh` in the repo copy, which the wrapper runs {src:tests/installer/helpers.sh:55}. Vault copy: [[install]]. Repo copy: [install](../../install.md).
- Programs: `tar` {src:tests/installer/helpers.sh:20}, `find`, `sort` and `cksum` {src:tests/installer/helpers.sh:67-70}, `python3 -I` {src:tests/installer/helpers.sh:76} {src:tests/installer/helpers.sh:85} {src:tests/installer/helpers.sh:111}.

**Used by.** Searched with `git grep` over `tests/` and the rest of the repo outside `docs/` on 2026-11-20.
- Sourced by the three installer test files; each calls `make_repo_copy` right after: `test_ins.sh` {src:tests/installer/test_ins.sh:6}, `test_lifecycle.sh` {src:tests/installer/test_lifecycle.sh:9}, `test_vault_git.sh` {src:tests/installer/test_vault_git.sh:8}.
- Tests: all three are tests; `run.sh` sources them {src:tests/installer/run.sh:97} {src:tests/installer/run.sh:101} {src:tests/installer/run.sh:105}. Related pages: [[run]] ([run](run.md)), [[test_ins]] ([test_ins](test_ins.md)), [[test_lifecycle]] ([test_lifecycle](test_lifecycle.md)), [[test_vault_git]] ([test_vault_git](test_vault_git.md)).

## Behavior

**`FAKE_USER`** is `tg_tester_` plus the shell process id, so it never equals the real user name {src:tests/installer/helpers.sh:12}.

**`make_repo_copy`** copies the repo into `$WORK/repo` with `tar`, leaving out `.git` and `__pycache__`. If that folder already exists it returns at once, so every test file in one run shares one copy {src:tests/installer/helpers.sh:16-21}. `clone_repo NAME` does the same into `$WORK/NAME` and prints the path, for tests that change the repo {src:tests/installer/helpers.sh:24-29}.

**`new_world NAME`** makes `$WORK/NAME/home/bin`, writes a stub `security` program there that appends its arguments to `security.log`, marks it executable and prints the home path {src:tests/installer/helpers.sh:33-38}.

**`run_install HOME [args]`** runs `install.sh` in a subshell {src:tests/installer/helpers.sh:46}:
- it unsets the `TOLLGATE_` settings that would point at real folders, and `CLAUDE_DOTFILES` {src:tests/installer/helpers.sh:47-49};
- it sets `HOME`, `USER`, `LOGNAME` and `SHELL` {src:tests/installer/helpers.sh:50}, turns off global and system git config and Python bytecode files {src:tests/installer/helpers.sh:51}, and puts the home `bin` folder first on `PATH` unless `RUN_PATH` replaces the whole path {src:tests/installer/helpers.sh:52};
- it changes into the throwaway home, or exits 99 if that fails {src:tests/installer/helpers.sh:53};
- stdin comes from the file named by `INSTALL_STDIN`, or from `/dev/null` when it is not set {src:tests/installer/helpers.sh:54-58};
- stdout and stderr go to `last.out` beside the home folder {src:tests/installer/helpers.sh:45} {src:tests/installer/helpers.sh:59}. The function returns the installer exit code, because the subshell is its last command {src:tests/installer/helpers.sh:59}.

**`snapshot HOME`** prints a sorted `path checksum` line for each file, leaving out full backups, `.bak.` copies, `security.log` and the stub `bin` folder {src:tests/installer/helpers.sh:65-72}. **`json_equal A B`** prints `true` when two JSON files hold equal data {src:tests/installer/helpers.sh:75-81}. **`normalise HOME FILE`** prints a file with the home path replaced by `<HOME>` {src:tests/installer/helpers.sh:84-89}. **`seed_user_settings HOME`** writes a settings file with a model, an env var, a plugin, a status line, allow and deny rules and two user hooks {src:tests/installer/helpers.sh:92-107}. **`user_settings_survive FILE`** prints `true` only when every one of those seeded values is still present {src:tests/installer/helpers.sh:110-126}.

## Diagram

Skipped: straight-line functions with no branching beyond one early return.

## Notes

- **Code versus description.** The header says the file is sourced by `test_ins.sh` {src:tests/installer/helpers.sh:2}; it is sourced by two other files as well {src:tests/installer/test_lifecycle.sh:9} {src:tests/installer/test_vault_git.sh:8}. The header says the real home is "never touched" {src:tests/installer/helpers.sh:7}; that holds only for code that follows `HOME`, and the stub `security` only protects the keychain while `$h/bin` stays on `PATH`. A caller using `RUN_PATH` must include it itself {src:tests/installer/helpers.sh:52}; the lifecycle tests do {src:tests/installer/test_lifecycle.sh:186}.
- **Inputs reaching a path, command, network address or outbound text without a check.** `NAME` is joined into paths with no check for `/` or `..` {src:tests/installer/helpers.sh:25} {src:tests/installer/helpers.sh:34}. `INSTALL_REPO` is run as `bash <value>/install.sh` with no check {src:tests/installer/helpers.sh:55}. The home path is placed inside the text of the stub script written by `printf`, so a path holding a double quote or a dollar sign would change that script {src:tests/installer/helpers.sh:36}. All callers pass fixed names.
- **Whole-repo copy.** `tar` copies everything under the repo root except `.git` and `__pycache__`, including untracked and ignored files {src:tests/installer/helpers.sh:20}. A large untracked folder would be copied into every copy.
- **Reuse is not enforced.** The comment says the installer writes into the repo it runs from, so tests must not use the real one {src:tests/installer/helpers.sh:14-15}. Tests that edit the repo must call `clone_repo` themselves; nothing stops a test from editing the shared copy.
- **Writes to shared files.** `security.log` is appended to by the stub with `>>`, not atomically, and nothing locks it {src:tests/installer/helpers.sh:36}. Tests run one after another, so no second writer exists in practice. Everything else is written under `$WORK`.
- **Silent failure mode.** If `user_settings_survive` hits a missing key, Python raises and prints nothing, and the caller's `check` then reports a failure, not a pass {src:tests/installer/helpers.sh:114-115} {src:tests/installer/run.sh:18-22}.
- **Environment assumptions.** Uses `cksum`, `tar -C` and `find` options common to macOS and GNU; no fixed machine path.
