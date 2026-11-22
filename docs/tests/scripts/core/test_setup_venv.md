---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/core/test_setup_venv.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/core/setup_venv.sh]         # source files under test, relative paths from repo root
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

This file tests the Python version check in the venv setup script: a base Python older than 3.12 must be refused, and the refusal must happen before the script deletes or creates anything. It runs the real script against a fake Python that reports a chosen minor version, so no real Python of any version is needed.

## Dependencies

**Depends on.**
- Standard library imports, as written: `os`, `pathlib`, `stat`, `subprocess`, `tempfile`, `unittest` {src:tests/scripts/core/test_setup_venv.py:10-15}.
- `scripts/core/setup_venv.sh`, run as a separate `bash` process {src:tests/scripts/core/test_setup_venv.py:18} {src:tests/scripts/core/test_setup_venv.py:48-49}: [[setup_venv]] and [setup_venv](../../../scripts/core/setup_venv.md).
- The environment variable `TOLLGATE_BASE_PYTHON`, set to the fake Python {src:tests/scripts/core/test_setup_venv.py:47}. The script reads it at {src:scripts/core/setup_venv.sh:17}.
- `/bin/sh`, which runs the fake Python {src:tests/scripts/core/test_setup_venv.py:25}.

**Used by.**
- Product code: none. Searched `git grep` for `test_setup_venv` outside `docs/` on 2026-11-20; the only hit is this file's own header.
- Found at run time by `unittest discover` in the folder runner {src:tests/scripts/core/run.sh:6}, which the end-to-end runner calls for the `core` area {src:tests/system/run.sh:22-23}.
- Tests: this file is itself a test.

## Behavior

**Fake Python.** `fake_python(folder, minor)` writes a small shell script called `fakepy` that pretends to be Python 3.`minor` {src:tests/scripts/core/test_setup_venv.py:21-35}. When called with `-c` and a command that contains the word `print`, it prints `3.<minor>` and exits 0 {src:tests/scripts/core/test_setup_venv.py:26-28}. That matches the script's second call, which prints the version {src:scripts/core/setup_venv.sh:41}. For any other `-c` command, which matches the script's yes or no version test {src:scripts/core/setup_venv.sh:40}, it exits 0 when `minor` is 12 or more and 1 otherwise {src:tests/scripts/core/test_setup_venv.py:29}. For any call that is not `-c`, such as `-m venv`, it appends the arguments to a `fakepy.calls` file and exits 7 {src:tests/scripts/core/test_setup_venv.py:32-33}. The file is made executable {src:tests/scripts/core/test_setup_venv.py:34}.

**Runner.** `run_script(minor, extra, premade)` works in a temp folder, picks `venv` inside it as the target {src:tests/scripts/core/test_setup_venv.py:40-41}, and with `premade` creates that folder with a `marker.txt` in it {src:tests/scripts/core/test_setup_venv.py:43-45}. It runs `bash setup_venv.sh --venv <folder>` plus any extra flags, with `TOLLGATE_BASE_PYTHON` set to the fake {src:tests/scripts/core/test_setup_venv.py:47-49}. It returns the process result, whether the venv folder exists, whether the marker exists, and the text of the calls file or an empty string {src:tests/scripts/core/test_setup_venv.py:50-52}.

**`test_old_python_is_refused_before_anything_is_made`.** With a fake 3.11 the script exits 1 {src:tests/scripts/core/test_setup_venv.py:56}, stderr holds `Tollgate needs Python 3.12 or newer, found 3.11` {src:tests/scripts/core/test_setup_venv.py:57}, the venv folder does not exist {src:tests/scripts/core/test_setup_venv.py:58}, and the fake was never asked to do anything except answer `-c` checks, since the calls file is empty {src:tests/scripts/core/test_setup_venv.py:59}. The script's refusal branch matches: it prints that message and exits 1 {src:scripts/core/setup_venv.sh:42-43}.

**`test_python_312_reaches_venv_creation`.** With a fake 3.12 the refusal message is absent {src:tests/scripts/core/test_setup_venv.py:63}, stdout says `creating venv` {src:tests/scripts/core/test_setup_venv.py:64}, and the calls file holds `-m venv`, so the script did ask the fake to build the venv {src:tests/scripts/core/test_setup_venv.py:65}. The fake then exits 7, so the script exits non-zero {src:tests/scripts/core/test_setup_venv.py:66}. That follows from `set -e` and the venv call {src:scripts/core/setup_venv.sh:13} {src:scripts/core/setup_venv.sh:52}.

**`test_force_with_old_python_deletes_nothing`.** The same 3.11 case with `--force` and a pre-made folder: exit 1, the refusal message, the folder still there, the marker file still there, and an empty calls file {src:tests/scripts/core/test_setup_venv.py:69-74}. The test comment says the check runs before `rm -rf` {src:tests/scripts/core/test_setup_venv.py:73}, and the script agrees: the version check is at lines 40-44 and the delete at 46-48 {src:scripts/core/setup_venv.sh:40-44} {src:scripts/core/setup_venv.sh:47}.

## Diagram

None: each test builds one temp folder and one fake script, with no mock chain.

## Notes

- **Code and description.** The header says the file tests the version check "(minimum 3.12)" {src:tests/scripts/core/test_setup_venv.py:3}, and the script's own header agrees {src:scripts/core/setup_venv.sh:9}. The `date:` field of this file's header is empty {src:tests/scripts/core/test_setup_venv.py:5}.
- **What the fake hides.** The fake decides on the word `print` in the `-c` text {src:tests/scripts/core/test_setup_venv.py:27}. If the script's version command is rewritten without that word, the fake would answer with the yes or no branch instead and the `found 3.11` assertion would fail. That ties the test to the script's wording of those two commands.
- **Coverage gaps.** Searched this file on 2026-11-20. Not tested: the `no working python` wording when the version cannot be read {src:scripts/core/setup_venv.sh:41-42}, the `python not found` branch {src:scripts/core/setup_venv.sh:35-38}, a Python newer than 3.12 such as 3.13 (the fake only branches on `>= 12` {src:tests/scripts/core/test_setup_venv.py:29}), the real `pip` steps, and the reuse of an existing venv built by an older Python.
- **Machine and version dependence.** Needs `bash` and `/bin/sh` and a file system where the temp folder can hold an executable script {src:tests/scripts/core/test_setup_venv.py:34}. The test itself runs on whatever Python starts `unittest`; it does not need 3.12. It passes `PYTHONDONTWRITEBYTECODE` to the child {src:tests/scripts/core/test_setup_venv.py:47}.
- **Inputs that reach paths or commands.** The values passed to the script are the temp folder and the fake path, both made in the test {src:tests/scripts/core/test_setup_venv.py:40-47}. `subprocess.run` gets an argument list, not a shell string {src:tests/scripts/core/test_setup_venv.py:48-49}. The fake script text is built with `%d` from the integer `minor` only {src:tests/scripts/core/test_setup_venv.py:28-29}.
- **Writes to shared files.** Everything is written inside a temp folder that is removed on exit {src:tests/scripts/core/test_setup_venv.py:40}. The fake script and calls file are plain writes, not atomic, and each test has its own folder, so no two writers meet.
