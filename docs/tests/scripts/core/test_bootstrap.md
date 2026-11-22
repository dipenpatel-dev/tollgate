---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/core/test_bootstrap.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/core/bootstrap/_worker_common.sh, scripts/core/bootstrap/bootstrap-dispatch.sh, scripts/core/bootstrap/bootstrap-arch-1.sh, scripts/core/bootstrap/bootstrap-arch-2.sh, scripts/core/bootstrap/bootstrap-dev-1.sh, scripts/core/bootstrap/bootstrap-dev-2.sh, scripts/core/bootstrap/bootstrap-qa-1.sh, scripts/core/bootstrap/bootstrap-qa-2.sh, scripts/core/bootstrap/bootstrap-spec-1.sh, scripts/core/bootstrap/bootstrap-spec-2.sh, scripts/core/run.sh, scripts/core/hooks/precompact_hook.sh, scripts/core/hooks/session_state_hook.sh, scripts/core/session_cost.py, scripts/core/memory/_enums.py]         # source files under test, relative paths from repo root
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

This file holds the tests for the small launch-and-helper scripts in `scripts/core`: the nine worker launcher scripts, the manual job runner `run.sh`, the two hook helper scripts, the session cost tracker, and the memory enum constants. Its own header says it covers "the bootstrap scripts, run.sh, hook helpers, session_cost and memory enums" {src:tests/scripts/core/test_bootstrap.py:3}, and the six test classes match that list. Every test that runs a script does so in a throwaway home, so nothing in the real home is changed.

## Dependencies

**Depends on.**
- Standard library imports, as written: `json`, `os`, `pathlib`, `stat`, `subprocess`, `sys`, `unittest` {src:tests/scripts/core/test_bootstrap.py:10-16}.
- `throwaway_home` from the harness folder, put on the import path at {src:tests/scripts/core/test_bootstrap.py:19} and imported at {src:tests/scripts/core/test_bootstrap.py:22}: [[throwaway_home]] and [throwaway_home](../../harness/throwaway_home.md).
- `core.memory._enums`, imported inside the one memory test {src:tests/scripts/core/test_bootstrap.py:208}: [[_enums]] and [_enums](../../../scripts/core/memory/_enums.md).
- The nine launcher wrappers, found by name in the `bootstrap` folder {src:tests/scripts/core/test_bootstrap.py:25-26}:
  [[bootstrap-dispatch]] [bootstrap-dispatch](../../../scripts/core/bootstrap/bootstrap-dispatch.md), [[bootstrap-arch-1]] [bootstrap-arch-1](../../../scripts/core/bootstrap/bootstrap-arch-1.md), [[bootstrap-arch-2]] [bootstrap-arch-2](../../../scripts/core/bootstrap/bootstrap-arch-2.md), [[bootstrap-dev-1]] [bootstrap-dev-1](../../../scripts/core/bootstrap/bootstrap-dev-1.md), [[bootstrap-dev-2]] [bootstrap-dev-2](../../../scripts/core/bootstrap/bootstrap-dev-2.md), [[bootstrap-qa-1]] [bootstrap-qa-1](../../../scripts/core/bootstrap/bootstrap-qa-1.md), [[bootstrap-qa-2]] [bootstrap-qa-2](../../../scripts/core/bootstrap/bootstrap-qa-2.md), [[bootstrap-spec-1]] [bootstrap-spec-1](../../../scripts/core/bootstrap/bootstrap-spec-1.md), [[bootstrap-spec-2]] [bootstrap-spec-2](../../../scripts/core/bootstrap/bootstrap-spec-2.md).
- [[_worker_common]] [_worker_common](../../../scripts/core/bootstrap/_worker_common.md), which every wrapper hands off to {src:scripts/core/bootstrap/bootstrap-arch-1.sh:11}. The test never names it directly.
- [[run]] for `scripts/core/run.sh`: the page for that script is `docs/scripts/core/run.md` [run](../../../scripts/core/run.md). The test builds its path at {src:tests/scripts/core/test_bootstrap.py:24}.
- [[precompact_hook]] [precompact_hook](../../../scripts/core/hooks/precompact_hook.md), [[session_state_hook]] [session_state_hook](../../../scripts/core/hooks/session_state_hook.md), [[session_cost]] [session_cost](../../../scripts/core/session_cost.md).
- System programs: `bash`, `sh` (the fake `claude` uses `#!/bin/sh` {src:tests/scripts/core/test_bootstrap.py:35}), `sed` and `date` (called by the launcher {src:scripts/core/bootstrap/_worker_common.sh:43} {src:scripts/core/bootstrap/_worker_common.sh:57}), and `python3` on `PATH` for the hook writer test {src:scripts/core/hooks/session_state_hook.sh:24}.

**Used by.**
- Product code: none. Searched with `git grep` for `test_bootstrap` outside `docs/` on 2026-11-20; the only hit is this file's own header {src:tests/scripts/core/test_bootstrap.py:2}.
- Found at run time by the folder runner, which calls `unittest discover` with the pattern `test_*.py` {src:tests/scripts/core/run.sh:6}. The area runner is documented at {src:scripts/README.md:31} and called by the end-to-end runner {src:tests/system/run.sh:23}.
- Tests: this file is itself a test.

## Behavior

**Setup helpers.**
- `REPO` is three folders above the test file {src:tests/scripts/core/test_bootstrap.py:18}. `ROLES` is `dispatch` plus `arch`, `dev`, `qa` and `spec`, each numbered 1 and 2, nine names in all {src:tests/scripts/core/test_bootstrap.py:26}.
- `make_env` points `TOLLGATE_HOME` at the repo {src:tests/scripts/core/test_bootstrap.py:31}, writes a fake `claude` program that prints each of its arguments on its own line and then the value of `TOLLGATE_WORKER_ID` into a file named by `TG_FAKE_OUT` {src:tests/scripts/core/test_bootstrap.py:35-36}, and puts that program first on `PATH` {src:tests/scripts/core/test_bootstrap.py:38}.
- It also writes five identity templates (`dispatch`, `arch`, `dev`, `qa`, `spec`) whose text is `I am {{WORKER_NAME}} of type <type>` {src:tests/scripts/core/test_bootstrap.py:42-43}, and sets `TOLLGATE_WORKER_TEMPLATES` to that folder {src:tests/scripts/core/test_bootstrap.py:44}. The launcher honours that variable {src:scripts/core/bootstrap/_worker_common.sh:27}.

**Class `Bootstrap`.**
- `test_all_scripts_present_and_executable`: each of the nine wrapper files exists and is executable {src:tests/scripts/core/test_bootstrap.py:54-57}. It does not check `_worker_common.sh`.
- `test_each_role_launches_with_identity`: for every role it runs the wrapper and expects exit 0 {src:tests/scripts/core/test_bootstrap.py:63-64}. It then proves three things.
  1. The identity file `workers/<role>-identity.md` in the state folder holds the text `I am <role> of type` {src:tests/scripts/core/test_bootstrap.py:65-67}. The launcher fills the template with `sed` {src:scripts/core/bootstrap/_worker_common.sh:43}.
  2. The fake `claude` received `--append-system-prompt-file`, the identity file path, and the role as the worker id, in that order {src:tests/scripts/core/test_bootstrap.py:68-71}. The launcher exports the id and then starts `claude` with that flag {src:scripts/core/bootstrap/_worker_common.sh:66-67}.
  3. `dispatch` leaves no registry file {src:tests/scripts/core/test_bootstrap.py:73-74}, while every other role gets a JSON record with `worker_name`, `type` (the part of the role before the hyphen) and `status` equal to `available`, and no `.json.tmp` file left behind {src:tests/scripts/core/test_bootstrap.py:76-80}. The launcher skips the registry for type `dispatch` and writes the others through a temp file and a rename {src:scripts/core/bootstrap/_worker_common.sh:46-49} {src:scripts/core/bootstrap/_worker_common.sh:62}.
- `test_missing_template_fails_clearly`: with the templates folder pointed at a folder that does not exist, the wrapper exits non-zero and says "template not found" {src:tests/scripts/core/test_bootstrap.py:85-88}. The launcher's message is `identity template not found for worker type` {src:scripts/core/bootstrap/_worker_common.sh:33-35}.
- `test_unset_home_says_not_set_up`: with `TOLLGATE_HOME` removed, `bootstrap-dev-1.sh` exits 1 and says "not set up" {src:tests/scripts/core/test_bootstrap.py:93-96}, matching the launcher check {src:scripts/core/bootstrap/_worker_common.sh:19-22}.

**Class `RunScript`** (the job runner `scripts/core/run.sh`, not the test runner of the same name).
- A bad option exits 2 with "Usage" on stderr {src:tests/scripts/core/test_bootstrap.py:103-105}, matching {src:scripts/core/run.sh:55-58}.
- With `TOLLGATE_HOME` pointed at a home that has no `scripts` folder, `all` exits 0 and prints "skipped" {src:tests/scripts/core/test_bootstrap.py:109-112}. The runner prints "skipped" when a job script is missing {src:scripts/core/run.sh:30} {src:scripts/core/run.sh:35} {src:scripts/core/run.sh:42}.
- A fake `sweep` script that exits 3 makes the runner exit 1 and print "failed" {src:tests/scripts/core/test_bootstrap.py:116-124}. Any failing job sets one flag, so the code 3 is reduced to 1 {src:scripts/core/run.sh:29} {src:scripts/core/run.sh:61}.
- With no `TOLLGATE_HOME` it exits 1 with "not set up" {src:tests/scripts/core/test_bootstrap.py:127-131}, matching {src:scripts/core/run.sh:18-21}.

**Class `Hooks`.**
- `test_precompact_prints_warning` runs the script with a copy of the real environment {src:tests/scripts/core/test_bootstrap.py:136} and expects exit 0 and the text `<precompact_warning>` {src:tests/scripts/core/test_bootstrap.py:137-138}. The script prints that block and exits 0 {src:scripts/core/hooks/precompact_hook.sh:11} {src:scripts/core/hooks/precompact_hook.sh:24}.
- `test_session_state_logs_when_unconfigured`: with no writer set, the hook exits 0 and its log file under the throwaway home contains "not configured" {src:tests/scripts/core/test_bootstrap.py:142-146}. The hook writes that line when the writer variable is empty or the file is missing {src:scripts/core/hooks/session_state_hook.sh:19-20}.
- `test_session_state_runs_writer`: a one-line Python writer is named in `TOLLGATE_SESSION_STATE_WRITER`; the hook exits 0 and its log contains "writer ran" {src:tests/scripts/core/test_bootstrap.py:151-157}. The hook runs the writer and appends its output to the log {src:scripts/core/hooks/session_state_hook.sh:24}.

**Class `SessionCost`.**
- `_session` builds a two-line session log with one million input and one million output tokens {src:tests/scripts/core/test_bootstrap.py:165-171}.
- `test_close_writes_ledger_in_output`: `--mode close` exits 0, writes `output/session-costs.jsonl` under the vault, and the last entry has status `closed`, input tokens of 1,000,000 and a cost of 18.0 {src:tests/scripts/core/test_bootstrap.py:181-185}. The 18.0 is 3.00 plus 15.00 from the price constants {src:scripts/core/session_cost.py:26-27}; the entry is built with status `closed` {src:scripts/core/session_cost.py:243}. The printed summary includes the task text "demo" {src:tests/scripts/core/test_bootstrap.py:186} {src:scripts/core/session_cost.py:192}.
- `test_not_set_up_without_vault`: with `TOLLGATE_KNOWLEDGE` removed, the command exits non-zero with "not set up" on stderr {src:tests/scripts/core/test_bootstrap.py:191-195}. The ledger path lookup exits with the loader's message {src:scripts/core/session_cost.py:46-50}.
- `test_needs_sessions_dir_when_no_override`: with `CLAUDE_CONFIG_DIR` removed and no session file, `--mode start` exits non-zero with "not set up" {src:tests/scripts/core/test_bootstrap.py:199-203}, matching {src:scripts/core/session_cost.py:40-42}.

**Class `MemoryEnums`.** One test reads constants and compares them with literals: `all` is in the scope values and not in the restricted set, the standards default for a missing status is the drop sentinel, `general` is a data domain, and the quarantine folder keys are `draft`, `deprecated`, `superseded` {src:tests/scripts/core/test_bootstrap.py:209-214}. The matching definitions are at {src:scripts/core/memory/_enums.py:13-21} {src:scripts/core/memory/_enums.py:60-64} {src:scripts/core/memory/_enums.py:101-102}.

## Diagram

None: each test builds one throwaway home and runs one script, with no mock chain beyond the fake `claude` program.

## Notes

- **Code and description.** No disagreement found between the file header {src:tests/scripts/core/test_bootstrap.py:3} and what the classes test. The README line that says tests "never touch your real files" {src:scripts/README.md:31} is only partly true for this file: `test_precompact_prints_warning` runs with the real environment {src:tests/scripts/core/test_bootstrap.py:136}. That script only prints text {src:scripts/core/hooks/precompact_hook.sh:10}, so nothing is touched in practice.
- **Weak or unfailable checks.**
  - `MemoryEnums` restates constants as literals {src:tests/scripts/core/test_bootstrap.py:209-214}. It fails if a constant is edited, but it does not show that any code uses the constants.
  - `test_all_scripts_present_and_executable` does not check `_worker_common.sh`, so a missing helper is caught only by the launch test.
  - The cost test hard-codes 18.0 {src:tests/scripts/core/test_bootstrap.py:185}, so it fails whenever the price constants change {src:scripts/core/session_cost.py:26-27}. That is a maintenance cost, not a bug.
- **Machine and version dependence.** The fake `claude` needs `/bin/sh` {src:tests/scripts/core/test_bootstrap.py:35}. The hook writer test needs `python3` on `PATH`. `core.memory._enums` annotates module-level names with `frozenset[str]`, which is evaluated at import and needs Python 3.9 or later {src:scripts/core/memory/_enums.py:13}; the 3.12 minimum covers that. The throwaway home copies the real environment except `TOLLGATE_*` variables {src:tests/harness/throwaway_home.py:30-33}, so a real `CLAUDE_CONFIG_DIR` stays set unless a test removes it, as the last cost test does {src:tests/scripts/core/test_bootstrap.py:199}.
- **Inputs that reach paths or commands without a check.** In the scripts under test: `TOLLGATE_HOME` builds the script paths that `run.sh` executes, with only an empty-value check {src:scripts/core/run.sh:18} {src:scripts/core/run.sh:41}; `TOLLGATE_SESSION_STATE_WRITER` is run as a Python file after only a file-exists check {src:scripts/core/hooks/session_state_hook.sh:19} {src:scripts/core/hooks/session_state_hook.sh:24}; the worker name is placed in a `sed` expression and in file names with no check {src:scripts/core/bootstrap/_worker_common.sh:43} {src:scripts/core/bootstrap/_worker_common.sh:31}, though the wrappers fix it to a constant {src:scripts/core/bootstrap/bootstrap-arch-1.sh:11}. In this test file every such value is a constant or a temp path.
- **Writes to shared files.** The tests write only inside the throwaway home, which is deleted when each test ends {src:tests/harness/throwaway_home.py:58-59}. The registry record under test is written to a temp file and renamed {src:scripts/core/bootstrap/_worker_common.sh:62}, so it is atomic on one file system, but nothing stops two launchers for the same worker from writing at once.
- **Header.** The `date:` field of the header is empty {src:tests/scripts/core/test_bootstrap.py:5}.
