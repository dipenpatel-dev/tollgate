---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/sync/test_sweep_path_safety.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/sync/sweep]         # source files under test, relative paths from repo root
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

This file tests the safety checks in the `sweep` script, which moves staged knowledge records into the vault and the search index. A staged record carries fields that become part of a file path. The tests feed in records with hostile values (`../`, slashes, dots only, spaces, backslashes, a number) and with symlinks that point out of the vault, and check that each such record is refused, counted as skipped, written nowhere, and never echoed in the output.

## Dependencies

**Depends on.**
- Standard library: `contextlib`, `io`, `json`, `os`, `pathlib`, `sys`, `unittest` {src:tests/scripts/sync/test_sweep_path_safety.py:13-19}.
- Helpers from the neighbouring test file: `load_sweep`, `record`, `FakeIndex`, `tree_files` from [[test_sync_tools]] / [test_sync_tools](test_sync_tools.md) {src:tests/scripts/sync/test_sweep_path_safety.py:22}.
- [[throwaway_home]] / [throwaway_home](../../harness/throwaway_home.md) and `assert_no_network` from [[connector_helpers]] / [connector_helpers](../../harness/connector_helpers.md) {src:tests/scripts/sync/test_sweep_path_safety.py:23-24}.
- The script under test, loaded from its file `scripts/sync/sweep` (no `.py` ending): [[sweep]] / [sweep](../../../scripts/sync/sweep.md) {src:tests/scripts/sync/test_sync_tools.py:35-40}.

**Used by.** Searched with `git grep` for the file name outside `docs/` (2026-11-20).
- Product code: none.
- Automation: the sync area runner finds it by the pattern `test_*.py` {src:tests/scripts/sync/run.sh:6}; the end-to-end runner runs that area {src:tests/system/run.sh:22-23}.
- Tests: no other test file imports it.

## Behavior

**Shared setup.** `_run` writes each record as `rec-N.json` into the throwaway vault's `output/knowledge-staging` folder, swaps in the throwaway environment, calls `sweep.main(["--yes"], index_factory=FakeIndex)` in the same process with output captured, then restores the environment {src:tests/scripts/sync/test_sweep_path_safety.py:31-45}. `FakeIndex` replaces the real search index so no index is opened {src:tests/scripts/sync/test_sync_tools.py:61-69}.

**The refusal check.** `_assert_refused` lists every file under the vault's parent folder (the throwaway home) before the run, runs the sweep, and then requires four things: the summary line contains `skipped=1` and `written=0`; the hostile value `EVILVALUE` is in neither stdout nor stderr; and no new file appears anywhere under the home except in the staging folder {src:tests/scripts/sync/test_sweep_path_safety.py:51-61}. The code that makes this hold: the four path fields `id`, `ticket`, `source_repo`, `date` must match letters, digits, dot, underscore and hyphen, and a value of only dots is refused {src:scripts/sync/sweep:104-118}. A refused record adds one to `skipped`, and only the count is printed {src:scripts/sync/sweep:307-310} {src:scripts/sync/sweep:328-330}.

**One test per hostile value.**
- `source_repo` with `../../../../EVILVALUE` on a repo record {src:tests/scripts/sync/test_sweep_path_safety.py:63-64}.
- `ticket` with a slash on an approval record {src:tests/scripts/sync/test_sweep_path_safety.py:66-67}.
- `id` with a slash {src:tests/scripts/sync/test_sweep_path_safety.py:69-70}.
- `ticket` with `../EVILVALUE` on a decision {src:tests/scripts/sync/test_sweep_path_safety.py:72-73}.
- `date` with `../EVILVALUE` on a pattern {src:tests/scripts/sync/test_sweep_path_safety.py:75-76}.
- Dots only: `..` and `.` {src:tests/scripts/sync/test_sweep_path_safety.py:78-80}.
- A space and a backslash {src:tests/scripts/sync/test_sweep_path_safety.py:82-84}.
- A non-string value (the number 5) {src:tests/scripts/sync/test_sweep_path_safety.py:86-87}. The code refuses anything that is not a string {src:scripts/sync/sweep:117}.

**Symlinks.** A symlink named `linked.md` in the repos folder that points to a file outside the vault is refused and the target is not created {src:tests/scripts/sync/test_sweep_path_safety.py:89-99}. A symlinked patterns folder pointing outside the vault is refused and the outside folder stays empty {src:tests/scripts/sync/test_sweep_path_safety.py:101-110}. The code resolves the real path and requires it to stay under the base folder {src:scripts/sync/sweep:121-129} {src:scripts/sync/sweep:162-163}.

**Preview and direct call.** In preview mode (no `--yes`) the plan line says `refused` {src:tests/scripts/sync/test_sweep_path_safety.py:112-115} {src:scripts/sync/sweep:271-273}. `write_vault_doc` called directly with a bad record raises `ValueError`, so it does not depend on the router having checked first {src:tests/scripts/sync/test_sweep_path_safety.py:117-121} {src:scripts/sync/sweep:192-193}.

**Normal names still work.** A record with id `r.1_a-b` and repo `my.repo-1` is written as `my.repo-1.md` in the repos folder and the summary says `written=1` {src:tests/scripts/sync/test_sweep_path_safety.py:123-128}.

## Diagram

None: every test follows the same three steps (stage a record, run the sweep, check nothing escaped), and there are no mock chains beyond one fake index.

## Notes

- **Code and description.**
  - The header says the sweep "must never write outside the vault" {src:tests/scripts/sync/test_sweep_path_safety.py:3}. For approval records the code limits writes to the tickets folder, not the vault folder {src:scripts/sync/sweep:155-157}. In `main` that folder comes from the path loader unless `--vault` is given {src:scripts/sync/sweep:341-342}. No test here sends an approval record through a symlink; the symlink tests use a repo record and a pattern record {src:tests/scripts/sync/test_sweep_path_safety.py:97} {src:tests/scripts/sync/test_sweep_path_safety.py:108}.
  - The header says a refused record is "logged by count only" {src:tests/scripts/sync/test_sweep_path_safety.py:6-7}; the code prints the count to stderr, and the preview plan line prints the staging file name {src:scripts/sync/sweep:329} {src:scripts/sync/sweep:272}. A staging file named from the hostile value would show up there; the tests name their files `rec-N.json`, so they cannot catch it {src:tests/scripts/sync/test_sweep_path_safety.py:35}.
  - The `Date:` header line is empty {src:tests/scripts/sync/test_sweep_path_safety.py:8}.
- **Coverage gaps.** An empty string value is refused by the code (the pattern needs one or more characters) but has no test {src:scripts/sync/sweep:105}. The `already written` branch and a hostile `source_ref` are out of scope for these tests; `source_ref` is not a path field {src:scripts/sync/sweep:104}.
- **Import order.** The file imports `throwaway_home` and `connector_helpers` right after `test_sync_tools`, which is what adds `tests/harness` to the import path {src:tests/scripts/sync/test_sweep_path_safety.py:22-24} {src:tests/scripts/sync/test_sync_tools.py:27}. Importing this file alone with a different path setup would fail.
- **Network guard.** `assert_no_network` blocks sockets in this process only. These tests call the sweep in the same process, so the guard applies here {src:tests/scripts/sync/test_sweep_path_safety.py:52} {src:tests/scripts/sync/test_sweep_path_safety.py:41}.
- **Machine dependence.** Creating symlinks needs a system that allows them {src:tests/scripts/sync/test_sweep_path_safety.py:96} {src:tests/scripts/sync/test_sweep_path_safety.py:107}. Nothing depends on the Python version beyond what the other files in the folder need.
- **Inputs without a check.** All hostile values are written on purpose by the test and go into files inside the throwaway home; the point of the file is that the sweep checks them. No input reaches a network address or a shell command.
- **Shared file writes.** The tests write the staging files and, in the one passing test, a note, all inside the throwaway home {src:tests/scripts/sync/test_sweep_path_safety.py:33-35} {src:tests/scripts/sync/test_sweep_path_safety.py:123-128}. The process environment is replaced and restored in a `finally` block, which is neither atomic nor locked; tests run one at a time {src:tests/scripts/sync/test_sweep_path_safety.py:36-44}.
