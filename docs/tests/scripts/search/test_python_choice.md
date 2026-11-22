---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_python_choice.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/search/rebuild.sh", "scripts/cron/nightly_index.sh"]         # source files under test, relative paths from repo root
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

This file tests which Python program two shell scripts run: the index rebuild script and the nightly maintenance script. Both are meant to take `TOLLGATE_PYTHON` first, then the `venv/bin/python3` program inside the state folder, then plain `python3`, and to say so in a message when they fall back {src:tests/scripts/search/test_python_choice.py:3}. It uses fake Python programs that only print their own name, so the tests show which one was chosen without running the real builder.

## Dependencies

**Depends on.**
- Standard library: `os`, `pathlib`, `stat`, `subprocess`, `unittest` {src:tests/scripts/search/test_python_choice.py:10-14}.
- Test helper `support`: [[support]] and [support](support.md) {src:tests/scripts/search/test_python_choice.py:16}. It provides `throwaway_home` and `write` {src:tests/scripts/search/test_python_choice.py:17}, and the repo and search folder paths `ROOT` and `SEARCH` {src:tests/scripts/search/test_python_choice.py:19} {src:tests/scripts/search/test_python_choice.py:20}. `throwaway_home` itself comes from [[throwaway_home]] and [throwaway_home](../../harness/throwaway_home.md).
- Scripts run as separate processes: [[rebuild]] and [rebuild](../../../scripts/search/rebuild.md) {src:tests/scripts/search/test_python_choice.py:41}, [[nightly_index]] and [nightly_index](../../../scripts/cron/nightly_index.md) {src:tests/scripts/search/test_python_choice.py:44}. Both ask [[tg_path]] and [tg_path](../../../scripts/core/tg_path.md) for folders {src:scripts/search/rebuild.sh:12} {src:scripts/cron/nightly_index.sh:35}.
- System programs: `bash` and `sh` (the fake programs start with `#!/bin/sh`) {src:tests/scripts/search/test_python_choice.py:25}. The test sets `PATH` to `/usr/bin:/bin` {src:tests/scripts/search/test_python_choice.py:35}, so a `python3` must exist there for `tg_path`, whose first line asks `env` for `python3` {src:scripts/core/tg_path:1}. That was not checked on this machine [uncertain].
- Environment names used: `TOLLGATE_STATE_DIR`, read from the throwaway environment {src:tests/scripts/search/test_python_choice.py:34}, which the path loader uses for the state folder {src:scripts/core/paths.py:103-105}; and `TOLLGATE_PYTHON`, set per test {src:tests/scripts/search/test_python_choice.py:52} {src:tests/scripts/search/test_python_choice.py:67}.

**Used by.** No product code. The folder runner `tests/scripts/search/run.sh` finds it with `unittest discover -p 'test_*.py'` {src:tests/scripts/search/run.sh:9}. Searched `git grep` for `test_python_choice` and `PythonChoice` outside `docs/` on 2026-11-20: no match; the file is new and not yet tracked, so a tracked search cannot see it.

## Behavior

One class, `PythonChoice`, with six tests and no skip guard, so it runs on a machine without `chromadb` {src:tests/scripts/search/test_python_choice.py:30}.

**Fixtures.**
- `stub(path, tag)` writes a shell script that prints `STUB-<tag>`, makes it executable and returns the path {src:tests/scripts/search/test_python_choice.py:23-27}.
- `setUp` makes a throwaway home, finds the state folder from the environment and narrows `PATH` to `/usr/bin:/bin` {src:tests/scripts/search/test_python_choice.py:32-35}. The throwaway environment removes every real `TOLLGATE_` name and points the vault, state folder and paths file at the throwaway home {src:tests/harness/throwaway_home.py:31-33} {src:tests/harness/throwaway_home.py:36} {src:tests/harness/throwaway_home.py:38} {src:tests/harness/throwaway_home.py:41}.
- `rebuild()` runs `bash rebuild.sh` with no arguments, 60 second timeout, and returns the process result {src:tests/scripts/search/test_python_choice.py:40-41}.
- `nightly_log()` runs `bash nightly_index.sh --skip-index` with a 120 second timeout, requires that at least one log file exists under `.tollgate/logs/nightly`, and returns the text of the first log file {src:tests/scripts/search/test_python_choice.py:43-48}. The script writes `<logs>/nightly/<date>.log` {src:scripts/cron/nightly_index.sh:47-48}.

**Rebuild script tests.**
1. `test_rebuild_prefers_tollgate_python`: a fake venv program and a second fake program named by `TOLLGATE_PYTHON` both exist; standard output must be `STUB-env` {src:tests/scripts/search/test_python_choice.py:51-53}. The script uses the variable when it is set and not empty, before it looks at the venv {src:scripts/search/rebuild.sh:14} {src:scripts/search/rebuild.sh:15}.
2. `test_rebuild_uses_the_venv_when_no_variable`: only the fake venv program exists; standard output must be `STUB-venv` and standard error must not contain "no venv" {src:tests/scripts/search/test_python_choice.py:56-59}. The script takes `venv/bin/python3` from the state folder when it is executable {src:scripts/search/rebuild.sh:15}.
3. `test_rebuild_falls_back_to_python3_and_says_so`: with no venv and no variable, standard error must contain "no venv found" {src:tests/scripts/search/test_python_choice.py:63}. The script prints that line, then uses `python3` {src:scripts/search/rebuild.sh:16}. The real `python3` then runs the real builder, and the test ignores how that ends; the comment in the test says only the message matters {src:tests/scripts/search/test_python_choice.py:62}.

**Nightly script tests.**
4. `test_nightly_prefers_tollgate_python`: same two fake programs; the log must contain `STUB-env` and not `STUB-venv` {src:tests/scripts/search/test_python_choice.py:66-70}. The nightly script picks the variable first {src:scripts/cron/nightly_index.sh:44}, and every step it runs through `run_step` writes its output to the log, so the fake name appears there {src:scripts/cron/nightly_index.sh:99-102}.
5. `test_nightly_uses_the_venv_when_no_variable`: only the fake venv program; the log must contain `STUB-venv` and not "no venv found" {src:tests/scripts/search/test_python_choice.py:73-76}. The script uses the state folder venv when the variable is not set {src:scripts/cron/nightly_index.sh:45}.
6. `test_nightly_logs_a_line_when_there_is_no_venv`: no fake programs; the log must contain "no venv found" {src:tests/scripts/search/test_python_choice.py:79}. The script keeps the note and writes it to the log after the header {src:scripts/cron/nightly_index.sh:46} {src:scripts/cron/nightly_index.sh:80}.

## Diagram

None: each test builds its own throwaway home and one or two fake programs; there is no fixture chain or mock chain beyond that.

## Notes

- **Description and code.** The header describes the choice as `TOLLGATE_PYTHON`, then the state folder venv, then `python3` {src:tests/scripts/search/test_python_choice.py:3}, and the scripts do that {src:scripts/search/rebuild.sh:14-16} {src:scripts/cron/nightly_index.sh:44-46}. The module constant named `CRON` holds the path of the nightly script, not the cron folder {src:tests/scripts/search/test_python_choice.py:19}. The header `date:` is empty {src:tests/scripts/search/test_python_choice.py:5}.
- **Gaps.** The tests never check exit codes. They do not cover an empty `TOLLGATE_PYTHON` (which the scripts treat as unset), a venv file that exists but is not executable, or the `tg-search` wrapper, which has its own rule that also needs the variable to be executable {src:scripts/search/tg-search:40}. The two fallback tests depend on a real `python3` being found for the scripts' own `tg_path` calls; the nightly fallback test also lets the real `python3` run the nightly steps {src:tests/scripts/search/test_python_choice.py:79}.
- **Time.** The nightly tests run the real maintenance steps with fake or real Python against the throwaway vault; no step retries, since no repo list or meeting source exists {src:scripts/cron/nightly_index.sh:124} {src:scripts/cron/nightly_index.sh:127}.
- **Machine dependence.** The `PATH` is fixed to `/usr/bin:/bin` {src:tests/scripts/search/test_python_choice.py:35}; the nightly script adds `/opt/homebrew/bin` and `/usr/local/bin` itself {src:scripts/cron/nightly_index.sh:51}, so a `python3` found only there could change the fallback case. No version of Python is checked.
- **Inputs without a check.** The fake programs are written under a temp home, and the only text sent to a script is its own file path {src:tests/scripts/search/test_python_choice.py:41} {src:tests/scripts/search/test_python_choice.py:44}. Nothing reaches a network address.
- **Writes to shared files.** None. The fake programs and the logs live under the throwaway home, which is removed on exit {src:tests/harness/throwaway_home.py:59}. Each test makes its own home, so no two tests share a file.
