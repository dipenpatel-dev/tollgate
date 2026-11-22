---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/cache/test_cache.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/cache/cache_write.py", "scripts/cache/run_log.py", "scripts/cache/phi_guard.py", "scripts/cache/daily_brief.py"]         # source files under test, relative paths from repo root
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

This file tests the four cache scripts together: the atomic file writer, the run log, the personal-identifier guard and the daily brief assembler. It uses made-up data only, and builds fake identifiers at run time {src:tests/scripts/cache/test_cache.py:3}. Each test class matches one script. The brief assembler is tested both by calling its functions and by running it as a child process.

## Dependencies

**Depends on.**
- [[cache_write]] ([cache_write](../../../scripts/cache/cache_write.md)), [[run_log]] ([run_log](../../../scripts/cache/run_log.md)), [[phi_guard]] ([phi_guard](../../../scripts/cache/phi_guard.md)) and [[daily_brief]] ([daily_brief](../../../scripts/cache/daily_brief.md)), imported as modules {src:tests/scripts/cache/test_cache.py:26-29}.
- [[throwaway_home]] ([throwaway_home](../../harness/throwaway_home.md)): the temporary home factory {src:tests/scripts/cache/test_cache.py:24}.
- [[paths]] ([paths](../../../scripts/core/paths.md)): not imported here, but it decides where the log and cache folders are, from the `HOME` variable the temporary home sets {src:scripts/core/paths.py:94} {src:scripts/core/paths.py:106-107}.
- Standard library: `json`, `os`, `pathlib`, `re`, `subprocess`, `sys`, `unittest`, `datetime` {src:tests/scripts/cache/test_cache.py:10-17}.

**Used by.**
- Product code: none (searched `git grep` for `test_cache` outside `docs/`, 2026-11-20).
- Tests: found by the folder launcher's `test_*.py` discovery {src:tests/scripts/cache/run.sh:6}, see [[run]] ([run](run.md)). No CI workflow runs it (`.github/workflows/tests.yml` names no cache step).

## Behavior

**Setup.** The test puts three folders on the import path: the test harness, `scripts` and `scripts/cache` {src:tests/scripts/cache/test_cache.py:21-23}. The `meta` helper builds a cache file body with a `_meta` block (time pulled, result, reason, reject count) and one data row {src:tests/scripts/cache/test_cache.py:36-39}. The fake identifier is assembled from three number parts {src:tests/scripts/cache/test_cache.py:32-33}.

**Class `CacheWrite`.**
- Writing a dict gives a file with the same JSON and leaves no temp file behind (a glob for the temp name finds nothing) {src:tests/scripts/cache/test_cache.py:44-48}. The writer's temp file is named from the target and the process id {src:scripts/cache/cache_write.py:24}.
- A value whose text conversion raises makes the second write fail, the old file keeps its old content and no temp file is left {src:tests/scripts/cache/test_cache.py:50-61}. The writer removes the temp file and re-raises on any error {src:scripts/cache/cache_write.py:31-33}, and the replace step never runs {src:scripts/cache/cache_write.py:30}.

**Class `RunLog`.**
- Two appended records land as two lines in the logs folder under the throwaway home, and the second line holds the second reason {src:tests/scripts/cache/test_cache.py:71-82}. The log path is the logs folder plus `run_log.jsonl` {src:scripts/cache/run_log.py:61}.
- Seven bad records are refused with `ValueError`, and no file is created: a result outside the allowed words, a free-text reason, `True` as the reject count, a negative count, a script name with a newline, a start time that is not a time, and a record missing the script key {src:tests/scripts/cache/test_cache.py:84-95}. The checks live at: result {src:scripts/cache/run_log.py:72-74}, reason {src:scripts/cache/run_log.py:76-78}, missing keys {src:scripts/cache/run_log.py:80-82}, script name {src:scripts/cache/run_log.py:97}, time {src:scripts/cache/run_log.py:105-107}, count {src:scripts/cache/run_log.py:110}. They all run before the file is opened {src:scripts/cache/run_log.py:88-89}.
- An extra key is dropped from the written line {src:tests/scripts/cache/test_cache.py:97-101} {src:scripts/cache/run_log.py:86}.

**Class `PhiGuard`.**
- Five rows go in; the row with a social-security-style number, the row with a medical-record number nested two levels deep, the row with a titled name and the row with a labelled birth date are all dropped; the lunch row stays; the reject count is 4 {src:tests/scripts/cache/test_cache.py:105-110}. The patterns are at {src:scripts/cache/phi_guard.py:19-38}, and a record is dropped whole {src:scripts/cache/phi_guard.py:79-83}.
- A clean row passes through unchanged with a count of 0 {src:tests/scripts/cache/test_cache.py:112-114}.
- A caller-supplied pattern drops the row it matches and nothing else {src:tests/scripts/cache/test_cache.py:116-119} {src:scripts/cache/phi_guard.py:76}.

**Class `DailyBrief`.** The `status_of` helper writes one cache file (or none) into a temp cache folder, runs `discover_sources` with one required name, then `assemble_sources`, and returns that source's block {src:tests/scripts/cache/test_cache.py:123-130}.

| Case | What it proves |
|---|---|
| fresh | A success file pulled now is `fresh` and its data is passed through {src:tests/scripts/cache/test_cache.py:132-135} {src:scripts/cache/daily_brief.py:121-123}. |
| missing | No file gives `missing` {src:tests/scripts/cache/test_cache.py:137-138} {src:scripts/cache/daily_brief.py:158-159}. |
| stale cases | A pull two days old, a pull three hours in the future, a pull time with no zone, and a file with no `_meta` block are all `stale` {src:tests/scripts/cache/test_cache.py:140-146} {src:scripts/cache/daily_brief.py:112-124}. |
| degraded, failed, unknown | The words `degraded` and `failed` map to their own status; an unknown result word is `stale` {src:tests/scripts/cache/test_cache.py:148-151} {src:scripts/cache/daily_brief.py:116-119}. |
| boolean count | `True` as the reject count is read as 0 {src:tests/scripts/cache/test_cache.py:153-156} {src:scripts/cache/daily_brief.py:135}. |
| unreadable | Broken JSON and a JSON list both give `stale` {src:tests/scripts/cache/test_cache.py:158-165} {src:scripts/cache/daily_brief.py:105-108}. |
| full run | Running the script as a child process with `--source two` writes the brief file with one `fresh` source, one `missing` source, no entry for the brief itself, and exactly one run-log line named `daily_brief` {src:tests/scripts/cache/test_cache.py:167-181}. The brief file is excluded from discovery {src:scripts/cache/daily_brief.py:149}, and one log line is appended every run {src:scripts/cache/daily_brief.py:191-192}. |
| no vault variable | With the vault variable removed, the child process still exits 0 and writes the brief {src:tests/scripts/cache/test_cache.py:183-188}. The cache folder is built from the home folder and not the vault {src:scripts/core/paths.py:106-107}. |

## Diagram

None: no mock chain. The only setup is a temporary home folder and, in two cases, a child process.

## Notes

**Test names that do not match what they check.**
- `test_stale_yesterday_future_and_naive` has no "yesterday" case: it uses a pull two days old {src:tests/scripts/cache/test_cache.py:141}. A pull from yesterday is not tested.
- `test_not_set_up_without_a_vault_is_not_needed_for_cache` reads like a not-set-up check, but it asserts success (exit 0 and a brief file) {src:tests/scripts/cache/test_cache.py:183-188}. The exit-2 "not set up" branch of the script {src:scripts/cache/daily_brief.py:203-205} is not tested here.

**Environment leak (test isolation).** `test_append_goes_to_the_logs_folder` copies the whole temporary environment into the process environment and then, in `finally`, pops every key of that copy {src:tests/scripts/cache/test_cache.py:73-79}. The copy was built from the full current environment {src:tests/harness/throwaway_home.py:30}, so after this test the process has lost `PATH`, `HOME` and every other variable it had, not only the added ones. It does not restore the old values. By test ordering (the unittest loader sorts classes and methods by name {src:docs:https://docs.python.org/3/library/unittest.html}, so `RunLog` is last and this case runs first inside it) only the other `RunLog` cases run after it, and they pass explicit paths or environments, so nothing fails today. A new test added after it would see an emptied environment.

**Tests that depend on the clock or machine.**
- `fresh` builds its timestamp from the current UTC time before the helper reads the local clock {src:tests/scripts/cache/test_cache.py:133} {src:tests/scripts/cache/test_cache.py:129}. The brief calls a source fresh only when the pull is on the same local date as now {src:scripts/cache/daily_brief.py:121-122}, so a run that crosses local midnight between those two lines can fail.
- Child processes use `sys.executable` and a throwaway environment copied from the current one {src:tests/scripts/cache/test_cache.py:172} {src:tests/harness/throwaway_home.py:30}. They have no timeout {src:tests/scripts/cache/test_cache.py:186}.
- Python version: `unlink(missing_ok=True)` in the writer needs 3.8 {src:scripts/cache/cache_write.py:32}. Nothing else version-specific found in this file.

**Tests that cannot fail.** None found. The clean-input case asserts a tuple equal to the input and zero, which a pass-through returns {src:tests/scripts/cache/test_cache.py:114}; it would fail if the guard changed the rows or counted a clean row.

**Not tested here.** Whether the temp file is flushed to disk before the replace {src:scripts/cache/cache_write.py:28-29}; the run log's checks on non-ASCII or empty script names, non-text time fields and the end time {src:scripts/cache/run_log.py:97} {src:scripts/cache/run_log.py:100-107}; the guard's patient-number and slash-date patterns {src:scripts/cache/phi_guard.py:21-22}; the `TOLLGATE_TZ` setting and the `TOLLGATE_BRIEF_SOURCES` list {src:scripts/cache/daily_brief.py:78} {src:scripts/cache/daily_brief.py:200}; the write-failure branch of the brief {src:scripts/cache/daily_brief.py:189-190}.

**Unchecked inputs.** All inputs are constants or built here. The target paths are made by joining the temporary home and fixed file names {src:tests/scripts/cache/test_cache.py:45} {src:tests/scripts/cache/test_cache.py:169}. Nothing reaches a network address, and the child process gets an argument list, not a shell string {src:tests/scripts/cache/test_cache.py:172}.

**Shared-file writes.** All files are written inside a temporary home that is removed afterwards {src:tests/harness/throwaway_home.py:59}. The test does exercise two writers of the code under test: the log append takes an exclusive lock {src:scripts/cache/run_log.py:90} and the brief and cache writes are atomic replaces {src:scripts/cache/cache_write.py:30}. No test starts two writers at once, so those protections are not proved by this file.
