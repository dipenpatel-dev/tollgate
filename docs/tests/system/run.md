---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/system/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "top-level commands from line 9 (no function); the first test run is line 16"    # function or line that executes when the script runs
requires: [bash, python3, dirname, cd, pwd, tail, grep, tr, printf]         # external commands or tools this script depends on
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

This script is the one command that runs the whole Tollgate end to end check. It runs the stranger install scenario first, then, unless told to skip, the hook tests and every script test suite, and prints one final pass or fail line. It changes no files itself; the tests it starts create and remove their own temporary folders.

## Dependencies

**Depends on.**
- `bash`; the script uses `BASH_SOURCE` {src:tests/system/run.sh:10}.
- A Python, taken from `TOLLGATE_TEST_PYTHON` or else `python3` {src:tests/system/run.sh:16} {src:tests/system/run.sh:20}.
- Environment variable `TOLLGATE_REAL_VAULT`: named in the usage line {src:tests/system/run.sh:7}. The script never reads it; it passes through the environment to the test file, which reads it {src:tests/system/test_e2e.py:65}.
- The end to end test file in the same folder {src:tests/system/run.sh:16}. Page: [[test_e2e]] / [test_e2e](test_e2e.md).
- The hook test folder `tests/hooks` {src:tests/system/run.sh:20}.
- One `run.sh` in each script suite folder under `tests/scripts` {src:tests/system/run.sh:23}. The folders it names are `core`, `search`, `cache`, `state`, `sync`, `cron`, `chart`, `qa`, `validation`, `connectors`, `connectors/plane`, `connectors/comms` and `connectors/data` {src:tests/system/run.sh:22}.
- Programs `tail`, `grep`, `tr` and `printf` for the summary lines {src:tests/system/run.sh:20} {src:tests/system/run.sh:24}.

**Used by.** No product code or other file calls this script. Searched `git grep` for `system/run`, `tests/system` and `test_e2e` outside `docs/` on 2026-11-20: the only hits are in this folder, where the usage line names the script {src:tests/system/test_e2e.py:12} and the script runs the test file {src:tests/system/run.sh:16}.
- Tests: none call it. It is started by hand.

## Behavior

1. The script sets `set -u -o pipefail`: an unset variable is an error, and a pipeline fails when any command in it fails, not only the last one. There is no `-e`, so a failing step does not stop the script; the steps set the failure flag instead {src:tests/system/run.sh:9}.
2. It works out its own folder and the repo root (two levels up) {src:tests/system/run.sh:10} {src:tests/system/run.sh:11}, turns off Python bytecode files for everything it starts {src:tests/system/run.sh:12}, and sets a failure flag to 0 {src:tests/system/run.sh:13}.
3. E2E-01 and E2E-02: runs the test file `test_e2e.py` through `unittest discover` with `-B`. A non-zero result sets the failure flag {src:tests/system/run.sh:16}.
4. If the first argument is not `--quick`, it continues {src:tests/system/run.sh:18}. With `--quick` the two steps below are skipped. Only the first argument is looked at.
5. E2E-03 hook tests: runs every `test_*.py` in `tests/hooks`, shows only the last 4 lines of output, and sets the failure flag when the pipeline fails. Because of `pipefail`, a failing hook test run fails the pipeline even though `tail` succeeds {src:tests/system/run.sh:20}.
6. E2E-03 script suites: for each of the 13 folders it runs that folder's `run.sh`, keeps all its output in a variable, prints one line with the folder name and the lines that start with `Ran `, `OK` or `FAILED`, and sets the failure flag when the exit code is not 0 {src:tests/system/run.sh:22-26}.
7. It prints `E2E: all passed` or `E2E: FAILED`, then exits with the flag value, 0 or 1 {src:tests/system/run.sh:28} {src:tests/system/run.sh:29}.

Exit codes: 0 when the flag stayed 0, 1 when any counted step failed {src:tests/system/run.sh:28-29}.

## Diagram

None: the flow is a short list of steps with one skip switch, described in numbered steps above.

## Notes

**Code and description disagree.**
- The header says E2E-03 is "the hook tests and every script suite together in one run" {src:tests/system/run.sh:3-4}. Earlier this was not true for the hook tests: line 20 ends with `| tail -4 || fail=1`, a pipeline returns the status of its last command, which is `tail`, and `pipefail` was not set, so a failing hook test could still end with `E2E: all passed`. That gap is closed: `pipefail` is now set {src:tests/system/run.sh:9}, so the pipeline takes the status of the failing test run and `|| fail=1` runs {src:tests/system/run.sh:20}. Checked on 2026-11-20 with a one line test in macOS system bash: `false 2>&1 | tail -4 || fail=1` leaves `fail=1` with `pipefail` and `fail=0` without it. The full script was not run for this page.
- The header and usage line do not mention the `--quick` switch {src:tests/system/run.sh:3-7} {src:tests/system/run.sh:18}.
- The script suite list is typed by hand {src:tests/system/run.sh:22}. A new folder under `tests/scripts` is not run until someone adds it. At the time of this page, the 13 names match the folders with a `run.sh` that were found by `ls` (10 top level folders, 3 under `connectors`); the sibling test folders `commands`, `installer`, `leak` and `harness` each hold their own `run.sh` and are not started by this script (listing of `tests/` on 2026-11-20), so "every script suite" means only the 13 folders under `tests/scripts`.
- The folder's own `run.sh` files use `TOLLGATE_TEST_PYTHON` themselves {src:tests/scripts/validation/run.sh:6}. Line 23 calls them with `bash`, so the variable reaches them only through the environment.

**Inputs that reach a command without a check.** `TOLLGATE_TEST_PYTHON` is run as a program with no check on its value {src:tests/system/run.sh:16} {src:tests/system/run.sh:20}. It is quoted, so spaces in the path are safe, but a wrong value is simply executed. The first argument is only compared with `--quick` {src:tests/system/run.sh:18}. No input reaches a network address or outbound text.

**Python 3.12 note.** The comment says 3.12 is the minimum and tells the user to point `TOLLGATE_TEST_PYTHON` at a 3.12 or newer venv with `pyyaml` and `scripts/requirements.txt` {src:tests/system/run.sh:8}. The script does not check the Python version itself: it runs whatever `TOLLGATE_TEST_PYTHON` names, or `python3` {src:tests/system/run.sh:16}. The comment used to name 3.9 as the minimum.

**Shared file writes.** The script writes no file. Test output is held in a variable {src:tests/system/run.sh:23} or printed. The tests it starts are expected to use their own temporary folders; the check that the real settings file is unchanged is in the test file {src:tests/system/test_e2e.py:198-203}. Two runs at once do not conflict in this script, since nothing shared is written.

**Idempotency.** Safe to run again. It has no state of its own.
