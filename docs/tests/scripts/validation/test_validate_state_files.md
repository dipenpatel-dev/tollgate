---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/validation/test_validate_state_files.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/validation/validate_state_files.py", "tests/fixtures/tickets/build_vault_100.py"]         # source files under test, relative paths from repo root
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

This file tests the ticket state file checker, `validate_state_files`, and checks that the sample ticket files under `tests/fixtures/tickets` are labelled correctly: every sample passes except one that is built to fail. It exists so a change to the checker, or a stray edit to a sample, shows up as a red test.

## Dependencies

**Depends on.**
- Standard library: `os`, `pathlib`, `subprocess`, `sys`, `tempfile`, `unittest` {src:tests/scripts/validation/test_validate_state_files.py:11-15}.
- The checker under test, imported as `vsf` after the folder `scripts/validation` is put at the front of `sys.path` {src:tests/scripts/validation/test_validate_state_files.py:20-21}. Page: [[validate_state_files]] / [validate_state_files](../../../scripts/validation/validate_state_files.md).
- The sample folder `tests/fixtures/tickets` {src:tests/scripts/validation/test_validate_state_files.py:19}, including the generator script `build_vault_100.py` that one test reads as text {src:tests/scripts/validation/test_validate_state_files.py:62}. Page: [[build_vault_100]] / [build_vault_100](../../fixtures/tickets/build_vault_100.md).
- The repo root is found from this file's own location, three folders up {src:tests/scripts/validation/test_validate_state_files.py:17}.

**Used by.** No product code runs this file. Searched `git grep` for `validate_state_files` and `test_validate` outside `docs/` on 2026-11-20.
- Tests and test runners: the folder's `run.sh` finds it with the pattern `test_*.py` {src:tests/scripts/validation/run.sh:6}; the end to end runner calls that `run.sh` as the `validation` suite {src:tests/system/run.sh:22} {src:tests/system/run.sh:23}.

## Behavior

**`TestCheckText.test_valid`** proves two good front matter blocks give an empty reason list: one with `ticket` and an empty `terminal_status` line, one with `ticket_id` {src:tests/scripts/validation/test_validate_state_files.py:26} {src:tests/scripts/validation/test_validate_state_files.py:27}. The checker accepts either key name {src:scripts/validation/validate_state_files.py:24} and skips nothing else for these inputs {src:scripts/validation/validate_state_files.py:45-48}.

**`TestCheckText.test_problems`** proves five failure codes, each from a small inline string:
- Text with no opening `---` gives `no_front_matter` {src:tests/scripts/validation/test_validate_state_files.py:30}, matching {src:scripts/validation/validate_state_files.py:31-32}.
- An opening `---` with no closing one gives `front_matter_not_closed` {src:tests/scripts/validation/test_validate_state_files.py:31}, matching {src:scripts/validation/validate_state_files.py:34-35}.
- A line `status OPEN` (no colon) gives `malformed_line` {src:tests/scripts/validation/test_validate_state_files.py:32}, matching {src:scripts/validation/validate_state_files.py:40-42}. It uses `assertIn`, so extra codes would not fail it.
- No ticket key gives `no_ticket_key` {src:tests/scripts/validation/test_validate_state_files.py:33}; an empty `status:` gives `no_status` {src:tests/scripts/validation/test_validate_state_files.py:34}, matching {src:scripts/validation/validate_state_files.py:45-48}.

**`TestFixtures.test_fixture_folder_present`** proves the sample folder exists {src:tests/scripts/validation/test_validate_state_files.py:39}. It fails if the folder is moved or renamed.

**`TestFixtures.test_only_the_bad_fixture_fails`** runs the checker over the whole sample folder and expects exactly one failing file name, `BAD-001-state.md` {src:tests/scripts/validation/test_validate_state_files.py:42} {src:tests/scripts/validation/test_validate_state_files.py:43}. The checker looks at every `.md` file under the folder whose name contains `state` {src:scripts/validation/validate_state_files.py:55}. It compares only file names, not reason codes. Running the checker by hand on 2026-11-20 printed `BAD-001-state.md: malformed_line, no_status`, and line 3 of that sample is `status OPEN` with no colon {src:tests/fixtures/tickets/vault_mixed/02-tickets/BAD-001/BAD-001-state.md:3}.

**`TestFixtures.test_cli_exit_codes`** runs the checker as a program three times with bytecode writing off {src:tests/scripts/validation/test_validate_state_files.py:46}:
- On the single good file `state_complete.md`, exit code 0 {src:tests/scripts/validation/test_validate_state_files.py:49}.
- On the whole sample folder, exit code 1 and the bad file's name in the output {src:tests/scripts/validation/test_validate_state_files.py:50-52}, matching {src:scripts/validation/validate_state_files.py:79-81}.
- On a path that does not exist, exit code 2 {src:tests/scripts/validation/test_validate_state_files.py:53-54}, matching {src:scripts/validation/validate_state_files.py:75-77}.

**`TestFixtures.test_state_files_in_temp_copy`** writes one valid state file into a throwaway folder and expects the checker to return an empty result {src:tests/scripts/validation/test_validate_state_files.py:57-59}. It passes a plain string folder name, so it also proves the checker accepts a string path {src:scripts/validation/validate_state_files.py:61}.

**`TestFixtures.test_build_vault_fixture_script_writes_only_where_asked`** reads `build_vault_100.py` as text and checks it contains the author line and does not contain `PROJ-174` {src:tests/scripts/validation/test_validate_state_files.py:62-64}.

## Diagram

None: a simple unit test file, no fixture chains or mocks. The only shared set up is a sample folder and one temporary folder.

## Notes

**Code and description disagree.**
- The module docstring says the file proves "no file text is printed" {src:tests/scripts/validation/test_validate_state_files.py:6}. The CLI test only checks that the bad file's name appears in the output {src:tests/scripts/validation/test_validate_state_files.py:52}. It never asserts that file text is absent from the output.
- The last test is named "writes only where asked" {src:tests/scripts/validation/test_validate_state_files.py:61}. It does not run the generator or look at what it writes. It only checks two text facts about the script's source {src:tests/scripts/validation/test_validate_state_files.py:62-64}. The generator itself writes to a `vault_100` folder next to it {src:tests/fixtures/tickets/build_vault_100.py:11} {src:tests/fixtures/tickets/build_vault_100.py:23-29}, and nothing tests that.
- The `Date:` header line is empty {src:tests/scripts/validation/test_validate_state_files.py:5}.

**Tests that are weak or machine dependent.**
- The last test can fail only if someone changes the author line or adds `PROJ-174` to the generator. It does not test behavior.
- No test covers the `unreadable` reason {src:scripts/validation/validate_state_files.py:64-65}, or the skipping of comment, list and indented lines {src:scripts/validation/validate_state_files.py:38}.
- No machine path is hard coded: the root comes from the file location {src:tests/scripts/validation/test_validate_state_files.py:17} and the child process uses `sys.executable` {src:tests/scripts/validation/test_validate_state_files.py:49}. Nothing depends on a Python version beyond what the checker needs. The checker uses `from __future__ import annotations` {src:scripts/validation/validate_state_files.py:17}.
- Importing the checker in the test process can leave a bytecode folder next to it unless `PYTHONDONTWRITEBYTECODE` is set, which `run.sh` does {src:tests/scripts/validation/run.sh:5}. Running the file directly does not set it.

**Unchecked inputs.** Every path and command is fixed inside the test or built from the file location or a temporary folder. No outside input reaches a path, shell command or network address.

**Shared file writes.** The only write is one file inside a private temporary folder {src:tests/scripts/validation/test_validate_state_files.py:57-58}. It is removed with the folder. No shared file is written, so atomicity and two writers do not apply.
