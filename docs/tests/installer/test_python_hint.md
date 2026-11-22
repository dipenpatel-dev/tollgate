---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/installer/test_python_hint.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [install.sh, tests/hooks/run.sh, tests/e2e/run.sh]         # source files under test, relative paths from repo root
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

Two test classes for the Python 3.12 requirement. One checks that the message `install.sh` prints when `python3` is too old is useful on any operating system. The other checks that the two test runner scripts honour `TOLLGATE_PYTHON`, putting a chosen Python first on `PATH` and warning when `python3` is still older than 3.12. The header gives the scope {src:tests/installer/test_python_hint.py:5}.

## Dependencies

**Depends on.**
- Standard library: `os`, `re`, `subprocess`, `tempfile`, `unittest` {src:tests/installer/test_python_hint.py:13} {src:tests/installer/test_python_hint.py:14} {src:tests/installer/test_python_hint.py:15} {src:tests/installer/test_python_hint.py:16} {src:tests/installer/test_python_hint.py:17}.
- `install.sh` {src:tests/installer/test_python_hint.py:49}, `tests/hooks/run.sh` and `tests/e2e/run.sh` {src:tests/installer/test_python_hint.py:77}, all read from the repo root two folders above the test {src:tests/installer/test_python_hint.py:20}. [[install]] / [install](../../install.md); [[run (hooks)]] / [run (hooks)](../hooks/run.md); [[run (e2e)]] / [run (e2e)](../e2e/run.md).
- `bash` at `/bin/bash` {src:tests/installer/test_python_hint.py:49} {src:tests/installer/test_python_hint.py:73}.

**Used by.** Run by the installer test runner through `unittest discover` over `tests/installer` {src:tests/installer/run.sh:110}, a step of the CI workflow {src:.github/workflows/tests.yml:38}. Searched `git grep test_python_hint` outside `docs/` (2026-11-21): nothing else names it. Siblings: [[test_mcp_pins]] and [test_mcp_pins](test_mcp_pins.md), [[test_requirements]] and [test_requirements](test_requirements.md).

## Behavior

Helper `old_python_dir` makes a folder with a fake `python3` shell script that answers as Python 3.11 by default. For `--version` it prints `Python 3.11.0`; for `-c` it exits 1 when the code text holds `sys.exit(0 if` (the version test) and otherwise prints `3.11` {src:tests/installer/test_python_hint.py:23} {src:tests/installer/test_python_hint.py:31} {src:tests/installer/test_python_hint.py:32} {src:tests/installer/test_python_hint.py:34} {src:tests/installer/test_python_hint.py:35}.

**Class `InstallerPythonMessage`**, test `test_message_is_os_neutral_and_actionable`. It runs `install.sh --non-interactive` with the fake `python3` first on `PATH` and an empty temp `HOME` {src:tests/installer/test_python_hint.py:48} {src:tests/installer/test_python_hint.py:49}. It asserts exit code 1 {src:tests/installer/test_python_hint.py:52}, then that the output holds `Tollgate needs Python 3.12 or newer, found 3.11`, the text `python3 --version`, a phrase matching `first on (your )?PATH`, `brew install python@3.12` and a `Linux:` line {src:tests/installer/test_python_hint.py:53} {src:tests/installer/test_python_hint.py:54} {src:tests/installer/test_python_hint.py:55} {src:tests/installer/test_python_hint.py:56} {src:tests/installer/test_python_hint.py:57}. The installer prints each of those at its Python check {src:install.sh:150} {src:install.sh:151} {src:install.sh:152} {src:install.sh:153} {src:install.sh:154} and exits 1 {src:install.sh:155}.

**Class `TestRunnersHonorTollgatePython`**, test `test_both_runners_prepend_the_folder_and_warn_when_old`. For `tests/hooks/run.sh` and `tests/e2e/run.sh` it cuts the block that starts at the comment `# Python 3.12 is the minimum.` up to the next variable assignment or blank line {src:tests/installer/test_python_hint.py:64}. It runs that block alone with `TOLLGATE_PYTHON` set to the fake `python3` and a `PATH` of `/usr/bin:/bin`, then prints `command -v python3` {src:tests/installer/test_python_hint.py:71} {src:tests/installer/test_python_hint.py:72} {src:tests/installer/test_python_hint.py:73}. It asserts that the first `python3` is the fake one and that the output says `older than 3.12` {src:tests/installer/test_python_hint.py:80} {src:tests/installer/test_python_hint.py:81}. The cut blocks are the `PATH` change and the version warning in each runner {src:tests/hooks/run.sh:12} {src:tests/hooks/run.sh:15} {src:tests/e2e/run.sh:28} {src:tests/e2e/run.sh:31}.

## Diagram

None needed: each test builds one fake `python3` in a temp folder and runs one shell command against it.

## Notes

- The first test passes only with a 3.11 fake; it never checks the real Python on the machine. The rest of `PATH` holds `/usr/bin:/bin` after the fake {src:tests/installer/test_python_hint.py:48}, which does not matter because the fake is found first.
- The runner test runs only the cut header block, not the rest of each runner. It does not prove the install step of `tests/e2e/run.sh` receives the folder: that is a separate `PATH` set on a later line {src:tests/e2e/run.sh:40}, not covered here (searched the test for `env -i`, 2026-11-21).
- The cut is a regular expression tied to the comment text and to the next line that starts with a word and `=` {src:tests/installer/test_python_hint.py:64}. If the comment is reworded the test fails on its `assertIsNotNone` {src:tests/installer/test_python_hint.py:65}.
- `TOLLGATE_PYTHON` is taken as given with no check that the file exists in either runner {src:tests/e2e/run.sh:28}.
- The header Date is empty {src:tests/installer/test_python_hint.py:4}. Inputs reaching a path, command, network address or outbound text: only paths built in a temp folder; no network call. Writes to shared files: none outside the temp folder, removed after each test {src:tests/installer/test_python_hint.py:45} {src:tests/installer/test_python_hint.py:69}.
- One run of the installer happens inside the first test; it stops at the Python check, before any write to the temp `HOME` {src:install.sh:155}.
