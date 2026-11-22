---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "run_test calls from line 62 to the final exit on line 209"    # function or line that executes when the script runs
requires: ["bash", "python3", "grep", "env"]       # external commands or tools this script depends on
tags: [hooks, test-runner]
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
---

## Purpose

This script is the test runner for the hooks. It feeds saved JSON fixtures to six hooks, checks each exit code and output, then runs the hook inventory check and the whole Python unit test folder, and prints one pass and fail count {src:tests/hooks/run.sh:2-4} {src:tests/hooks/run.sh:206}. It needs no live Claude Code session {src:tests/hooks/run.sh:4}. Before it starts it checks the Python version and warns when `python3` is older than 3.12 {src:tests/hooks/run.sh:14-15}.

## Dependencies

**Depends on.**
- `bash`, `python3`, `grep` and `env`. The runner finds the repo root from its own location, then reads hooks from `hooks/` and fixtures from `tests/hooks/fixtures` {src:tests/hooks/run.sh:8} {src:tests/hooks/run.sh:16-17}. `python3` is called for the version check and for two steps {src:tests/hooks/run.sh:14} {src:tests/hooks/run.sh:190} {src:tests/hooks/run.sh:198}. The Python hooks start with `#!/usr/bin/env python3`, so they find `python3` through the same `PATH` {src:hooks/post-tool-bash-scan-secrets.py:1}.
- Environment: `TOLLGATE_PYTHON`, optional {src:tests/hooks/run.sh:11}.
- Hooks under test, each run only when its file is executable: [[pre-submit-vault-inject]] and [pre-submit-vault-inject](../../hooks/pre-submit-vault-inject.md), [[post-tool-bash-scan-secrets]] and [post-tool-bash-scan-secrets](../../hooks/post-tool-bash-scan-secrets.md), [[pre-tool-write-scan-phi]] and [pre-tool-write-scan-phi](../../hooks/pre-tool-write-scan-phi.md), [[pre-tool-write-guard-path]] and [pre-tool-write-guard-path](../../hooks/pre-tool-write-guard-path.md), [[post-tool-result-scan-phi]] and [post-tool-result-scan-phi](../../hooks/post-tool-result-scan-phi.md), [[pre-compact-checkpoint-warn]] and [pre-compact-checkpoint-warn](../../hooks/pre-compact-checkpoint-warn.md) {src:tests/hooks/run.sh:64} {src:tests/hooks/run.sh:83} {src:tests/hooks/run.sh:106} {src:tests/hooks/run.sh:129} {src:tests/hooks/run.sh:148} {src:tests/hooks/run.sh:179}.
- The inventory check [[check_hook_inventory]] and [check_hook_inventory](check_hook_inventory.md) {src:tests/hooks/run.sh:190}, and the unit test files in the same folder, among them [test_gate_rules](test_gate_rules.md) and [test_state_file_io](test_state_file_io.md) {src:tests/hooks/run.sh:198}.

**Used by.** Run by hand with `bash tests/hooks/run.sh` {src:tests/hooks/run.sh:3}. The CI workflow runs it as the step named "Hook shell tests" on Ubuntu and macOS {src:.github/workflows/tests.yml:28-29} {src:.github/workflows/tests.yml:17}. The same workflow then runs the inventory check and the unit test discovery again as their own steps {src:.github/workflows/tests.yml:32} {src:.github/workflows/tests.yml:35}, so both run twice in CI. Searched 2026-11-21 across the worktree except `.git`, `docs/` and caches for `hooks/run.sh`; the other hit is the checklist `tests/hooks/e2e-wiring-checklist.md`, which names the command as its first tier.

## Behavior

**Python selection.** When `TOLLGATE_PYTHON` is set and not empty, the script puts the folder that holds it first on `PATH` and exports `PATH`, so the `python3` found in that folder (or later on `PATH`) is the one used by the script and by the hooks it starts {src:tests/hooks/run.sh:11-13}. Then it runs `python3 -c` with a version test for 3.12 or newer, with output hidden {src:tests/hooks/run.sh:14}. If the test fails or `python3` is missing, it prints one `WARNING` line with the version found and the advice to set `TOLLGATE_PYTHON` or put 3.12 first on `PATH` {src:tests/hooks/run.sh:15}. The warning does not stop the run and does not change the counts {src:tests/hooks/run.sh:6}.

**The helper.** `run_test` takes a description, a hook path, a fixture path, an expected exit code (default 0), a pattern that must appear in the output, a pattern that must not appear, and optional env overrides {src:tests/hooks/run.sh:22-29}. It runs the hook under `env` with the overrides, the fixture on stdin, and stderr merged into the output {src:tests/hooks/run.sh:34}. A test fails on a wrong exit code, a missing required pattern, or a rejected pattern that is present {src:tests/hooks/run.sh:38-51}. A failing test prints the first three output lines {src:tests/hooks/run.sh:57}.

**Fixture sections.** Each runs only if the hook file is executable, and otherwise prints `SKIP` and counts nothing {src:tests/hooks/run.sh:65} {src:tests/hooks/run.sh:77-79}.
- Vault inject hook: a short prompt and a skill invocation must exit 0 and not print `vault_context`; a third fixture with no knowledge folder must exit 0 {src:tests/hooks/run.sh:67-76}. All three cases set `TOLLGATE_KNOWLEDGE` to an empty value through the env override {src:tests/hooks/run.sh:68} {src:tests/hooks/run.sh:72} {src:tests/hooks/run.sh:76}.
- Secret scan after Bash: clean output must not print `additionalContext`; an Anthropic style key must print the label `ANTHROPIC_KEY`; a Write tool result must not print `additionalContext`; a file that is not JSON must exit 2, print `fails closed` and no `additionalContext` {src:tests/hooks/run.sh:86-99}.
- PHI scan before Write: clean content must not print `permissionDecision`; a record number, a social security number and an Edit tool case must each print one {src:tests/hooks/run.sh:109-122}.
- Write path guard: with `TOLLGATE_CODE_DIR` set empty it must exit 0 and not print `permissionDecision`; a path under a fake code folder must print one; a path outside must not {src:tests/hooks/run.sh:132-141}.
- PHI scan on tool results: a clean Bash result must not print `decision`; PHI in a Bash result, in an MCP result and in a Read result must each print `additionalContext`; the Write tool and a clean MCP result must not {src:tests/hooks/run.sh:151-172}.
- Pre compact warning: any input must print `precompact_warning` {src:tests/hooks/run.sh:182-183}.
- The clean cases check only that a pattern is absent, not that the output is empty {src:tests/hooks/run.sh:87} {src:tests/hooks/run.sh:110}.

**Two single step blocks.** The hook inventory check runs next {src:tests/hooks/run.sh:190-194}. Then `python3 -m unittest discover` runs over the folder of this script with the pattern `test_*.py`, so every unit test file there is picked up {src:tests/hooks/run.sh:198-202}. Each block counts as one pass or one fail in the totals, not one per test {src:tests/hooks/run.sh:190-202}.

**Exit code.** The script prints the totals and a pointer to the live run `tests/e2e/run.sh` {src:tests/hooks/run.sh:206-207}. It exits 0 when no test failed and 1 otherwise {src:tests/hooks/run.sh:209}. It sets `-uo pipefail` but not `-e`, so one failure does not stop the run {src:tests/hooks/run.sh:6}.

## Diagram

None: the script is straight-line, with one section after another and no branching worth drawing.

## Notes

**Description against code.**
- The comment on the Python selection says `TOLLGATE_PYTHON` is "a path to a python3" that is put first on `PATH` {src:tests/hooks/run.sh:10}. The code puts the folder that holds it on `PATH` {src:tests/hooks/run.sh:12}, so a file named for example `python3.12` is used only if a `python3` in the same folder points at the right version.
- The comment above the write guard case says an unset `TOLLGATE_CODE_DIR` gives "exit 0, no output" {src:tests/hooks/run.sh:131}. The hook prints a `systemMessage` warning in that case and still exits 0 {src:hooks/pre-tool-write-guard-path.sh:86-91}; the case passes because it rejects only `permissionDecision` {src:tests/hooks/run.sh:133}.

**Coverage.** The fixture sections cover six hooks only. No section exists for the other hooks in `hooks/`, among them the Bash code folder guard, the gate override Bash guard, the scrubber, the git guards, the gate check hook, the Databricks hook and the read-before-write hooks (searched `tests/hooks/run.sh` for each hook file name, 2026-11-21; only the six names above appear {src:tests/hooks/run.sh:64} {src:tests/hooks/run.sh:83} {src:tests/hooks/run.sh:106} {src:tests/hooks/run.sh:129} {src:tests/hooks/run.sh:148} {src:tests/hooks/run.sh:179}). The unit test block is the only place the rest are run, and this page does not list which unit tests cover which hook. The v1 unit test files `test_git_readonly_no_index`, `test_secret_shapes` and `test_self_protection` are picked up by the same discovery pattern {src:tests/hooks/run.sh:198}: [test_git_readonly_no_index](test_git_readonly_no_index.md), [test_secret_shapes](test_secret_shapes.md), [test_self_protection](test_self_protection.md).

**Version and machine dependence.** The Python version check is a warning only, so a run on an older `python3` goes on and may fail later in the unit tests {src:tests/hooks/run.sh:14-15}. The hooks start through their own shebang line and find `python3` through `PATH`, so `TOLLGATE_PYTHON` also changes the interpreter the hooks use {src:tests/hooks/run.sh:12}. Some failure messages hold an em dash, which is existing output text {src:tests/hooks/run.sh:39}.

**Inputs without a check, and shared writes.** `TOLLGATE_PYTHON` goes into `PATH` through `dirname` with no check that the file exists or is a Python {src:tests/hooks/run.sh:12}. The env override words are passed unquoted to `env`, so they are split on spaces {src:tests/hooks/run.sh:34}; all values are constants in the script. The script writes no file itself. Python may write `__pycache__` folders when the inventory check and the unit tests import code; nothing stops two runs at once from writing them, and the write is not atomic.
