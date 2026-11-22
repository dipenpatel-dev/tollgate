---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/core/test_vault_git.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-19
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/core/paths.py, scripts/core/tg_vault_git]         # source files under test, relative paths from repo root
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

This file tests how Tollgate decides whether the vault is saved with git: the function `vault_git_mode` in `scripts/core/paths.py` and the command `scripts/core/tg_vault_git` that prints its answer. The first test class checks the function directly {src:tests/scripts/core/test_vault_git.py:40}. The second class runs the command as a separate process and checks what it prints and its exit codes {src:tests/scripts/core/test_vault_git.py:84}.

## Dependencies

Imports (as written): `os`, `pathlib`, `subprocess`, `sys`, `unittest` from the standard library {src:tests/scripts/core/test_vault_git.py:10-14}; `throwaway_home` from the test harness folder {src:tests/scripts/core/test_vault_git.py:20}, whose source is `tests/harness/throwaway_home.py` (no doc yet; `docs/tests/harness.md` is a different page); and `core` for its `paths` module {src:tests/scripts/core/test_vault_git.py:21}.

What it exercises:
- `scripts/core/paths.py` (no doc yet), through `paths.vault_git_mode` and `paths.NotSetUp`.
- [[tg_vault_git]] and [tg_vault_git](../../../scripts/core/tg_vault_git.md), run through the current Python with `-B` {src:tests/scripts/core/test_vault_git.py:37}. The command path is built from the repo root {src:tests/scripts/core/test_vault_git.py:23}.
- The `git` program, called to make a vault repo and to add a remote {src:tests/scripts/core/test_vault_git.py:29}.

## Behavior

**Fixtures.**
- `REPO` is three folders above the test file, and both `tests/harness` and `scripts` are put on the import path {src:tests/scripts/core/test_vault_git.py:16-18}.
- Each test runs inside `throwaway_home()`, which gives a temp home and an environment dict {src:tests/scripts/core/test_vault_git.py:42}. The harness removes every real `TOLLGATE_*` variable, then points `TOLLGATE_KNOWLEDGE` at a `vault` folder in the temp home and `TOLLGATE_PATHS` at a paths file there {src:tests/harness/throwaway_home.py:31-33} {src:tests/harness/throwaway_home.py:36} {src:tests/harness/throwaway_home.py:41}. The temp home is created with an empty `vault` folder {src:tests/harness/throwaway_home.py:53-55}.
- `git(env, ...)` runs git with the user and system git config switched off, so a developer's own settings cannot change the result {src:tests/scripts/core/test_vault_git.py:27-29}.
- `write_paths(env, text)` writes the paths file {src:tests/scripts/core/test_vault_git.py:33}. `cli(env)` runs the command and captures output {src:tests/scripts/core/test_vault_git.py:37}.

**Function tests (`VaultGitMode`).**
- A saved `none`, `local` or `remote` is returned as written {src:tests/scripts/core/test_vault_git.py:43-45}.
- A saved value beats detection: the vault is a git repo, the file says `none`, the answer is `none` {src:tests/scripts/core/test_vault_git.py:49-51}.
- No `vault_git` line and no `.git` in the vault gives `none` {src:tests/scripts/core/test_vault_git.py:55-56}.
- No line, a repo with no remote gives `local` {src:tests/scripts/core/test_vault_git.py:60-61}.
- No line, a repo with a remote added gives `remote` {src:tests/scripts/core/test_vault_git.py:67-68}.
- A bad value (`sometimes`) is ignored and the vault is detected: `none` before `git init`, `local` after {src:tests/scripts/core/test_vault_git.py:73-76}.
- With only a missing paths file and no `TOLLGATE_KNOWLEDGE`, the function raises `NotSetUp` {src:tests/scripts/core/test_vault_git.py:79-81}.

**Command tests (`VaultGitCli`).**
- For each saved mode the command exits 0 and prints that mode {src:tests/scripts/core/test_vault_git.py:88-90}.
- With no paths file it prints `none`, and `local` after `git init` of the vault {src:tests/scripts/core/test_vault_git.py:94-96}.
- A bad saved value (`nope`) prints `none` for a vault with no git {src:tests/scripts/core/test_vault_git.py:100-101}.
- With `TOLLGATE_KNOWLEDGE` removed, the command exits 1 and stderr contains "not set up" {src:tests/scripts/core/test_vault_git.py:105-108}.
- One extra argument makes it exit 2 {src:tests/scripts/core/test_vault_git.py:112-113}.

The tests run under `unittest` and the file can be run on its own {src:tests/scripts/core/test_vault_git.py:116-117}.

## Diagram

None: the setup is one throwaway home per test, with no mock chains.

## Notes

- **Not covered.** The timeout, missing git program and failing git fall back to `local` in `detect_vault_git` are never triggered, and neither is a mixed-case saved value such as `Local`, which the code lower-cases {src:scripts/core/paths.py:155-156} {src:scripts/core/paths.py:168}. A `vault` line in the paths file is also not tested.
- **Weak checks.** The extra-argument test checks only the exit code {src:tests/scripts/core/test_vault_git.py:113}, not the usage line. The `none` and not-set-up command tests check stdout or a substring of stderr, not the full text.
- **Test name overlap.** Both classes have a `test_bad_value_is_detected` method {src:tests/scripts/core/test_vault_git.py:70} {src:tests/scripts/core/test_vault_git.py:98}. They sit in different classes, so neither hides the other.
- **Header.** The `date:` field of the file header is empty {src:tests/scripts/core/test_vault_git.py:5}.
- **Shared writes.** Each test writes only inside its own temp home; the home is deleted when the test ends {src:tests/harness/throwaway_home.py:58-59}.
