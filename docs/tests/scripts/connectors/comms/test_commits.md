---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/comms/test_commits.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/comms/commits_connector.py, scripts/connectors/comms/comms_common.py]         # source files under test, relative paths from repo root
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

Tests for the `git-commits` connector, which collects recent commits from local git history into a cache file. The file checks the four connector life-cycle rules shared by all connectors (off until set up, key stored nowhere on disk, on survives a restart, off returns to not set up), then repo discovery, line parsing, how a failed or partly failed run is reported, that commit subjects are not printed or logged, that a secret inside a subject is replaced in place with a labeled marker and counted by label, and the dry run.

## Dependencies

**Depends on.**
- Under test: [[commits_connector]] / [commits_connector](../../../../scripts/connectors/comms/commits_connector.md) imported as `cm` {src:tests/scripts/connectors/comms/test_commits.py:17}; the cache and log helpers in [[comms_common]] / [comms_common](../../../../scripts/connectors/comms/comms_common.md) through that connector {src:scripts/connectors/comms/commits_connector.py:33}.
- Test support: [[comms_base]] / [comms_base](comms_base.md) supplies `Base`, `make_con_tests`, `FAKE_ADDRESS` and the two fake secret builders `fake_slack_token` and `fake_credential` {src:tests/scripts/connectors/comms/test_commits.py:16}. That file in turn uses [[connector_helpers]] / [connector_helpers](../../../harness/connector_helpers.md), [[throwaway_home]] / [throwaway_home](../../../harness/throwaway_home.md), [[registry]] / [registry](../../../../scripts/connectors/registry.md) and [[connect]] / [connect](../../../../scripts/connectors/connect.md) {src:tests/scripts/connectors/comms/comms_base.py:25-27}.
- Standard library: `json`, `os`, `pathlib`, `subprocess`, `unittest` {src:tests/scripts/connectors/comms/test_commits.py:10-14}.

**Used by.** Run by [[run]] / [run](run.md) through the pattern `test_*.py` {src:tests/scripts/connectors/comms/run.sh:6}. `git grep` for `test_commits` outside `docs/` finds no other reference (searched 2026-11-20).

## Behavior

Fixture. `line()` builds one git log line joined with the connector's own separator {src:tests/scripts/connectors/comms/test_commits.py:23-24}. `GitBase.setUp` makes a fake repo folder `work/alpha` with an empty `.git` folder inside the throwaway home {src:tests/scripts/connectors/comms/test_commits.py:33-34}. Its `runner` records each command and returns a fake finished process with the prepared output, so no real git runs {src:tests/scripts/connectors/comms/test_commits.py:38-40}. `reached_client` asserts exactly one git call and no HTTP call {src:tests/scripts/connectors/comms/test_commits.py:42-44}.

Life-cycle cases. `TestCon` is built by `make_con_tests` with `--root <repo>` and the fake runner {src:tests/scripts/connectors/comms/test_commits.py:47-50}. That factory adds five tests: CON-01 not set up (exit non-zero, message names `connect.py on git-commits`, no HTTP, no connectors file) {src:tests/scripts/connectors/comms/comms_base.py:131-138}; CON-01 again as a real subprocess {src:tests/scripts/connectors/comms/comms_base.py:140-145}; CON-02 the secret is nowhere in the repo tree or the home folder {src:tests/scripts/connectors/comms/comms_base.py:147-164}; CON-03 turned on, registry cleared, module reloaded, still reaches the client {src:tests/scripts/connectors/comms/comms_base.py:166-176}; CON-04 turned off, the key is removed from the store and the connector is not set up again {src:tests/scripts/connectors/comms/comms_base.py:178-187}.

Connector cases (ten tests in `TestCommits`):
1. `test_writes_cache_and_uses_local_word_as_key` turns on with the key `local`, runs, and reads `commits.json`: repo name `alpha`, result `success`, no HTTP call {src:tests/scripts/connectors/comms/test_commits.py:61-67}. This proves the cache envelope that `finish` writes {src:scripts/connectors/comms/comms_common.py:44-48}.
2. `test_root_without_git_walks_children_once` shows a folder with no `.git` yields its child repos in sorted order and skips plain folders, a repo folder yields itself, and a missing folder yields an empty list {src:tests/scripts/connectors/comms/test_commits.py:69-75}, matching `resolve_repos` {src:scripts/connectors/comms/commits_connector.py:50-57}.
3. `test_address_gives_roots_and_flag_overrides` turns on with the repo as the address, runs with no flags, and expects one git call. It then checks that an address of two folders joined by the path separator gives two roots and that a `--root` flag replaces the address {src:tests/scripts/connectors/comms/test_commits.py:77-83}, matching `roots` {src:scripts/connectors/comms/commits_connector.py:72-77}.
4. `test_local_address_uses_repos_path` sets `TOLLGATE_CODE_DIR` to `/somewhere` and expects the address `local` to give that folder; it restores the old value in a `finally` {src:tests/scripts/connectors/comms/test_commits.py:85-95}. The lookup is `get_path("repos")` {src:scripts/connectors/comms/commits_connector.py:77}.
5. `test_parse_line_shape` expects `None` for a line with two fields and a record with the author for a good line {src:tests/scripts/connectors/comms/test_commits.py:97-99}, matching `parse_line` {src:scripts/connectors/comms/commits_connector.py:60-65}.
6. `test_all_repos_failing_is_failed_and_no_cache` makes git exit 128, then expects no `commits.json` and the text `api_4xx` in the run log {src:tests/scripts/connectors/comms/test_commits.py:101-108}. The code maps a non-zero git exit to that reason {src:scripts/connectors/comms/commits_connector.py:88-89} and skips the cache write on a failed run {src:scripts/connectors/comms/comms_common.py:105-107}.
7. `test_one_bad_repo_is_degraded` makes the `beta` repo fail and `alpha` succeed, then expects result `degraded` and one record {src:tests/scripts/connectors/comms/test_commits.py:110-120}. The fake picks the repo from `argv[2]`, which is the folder after `-C` {src:tests/scripts/connectors/comms/test_commits.py:115} {src:scripts/connectors/comms/commits_connector.py:81}.
8. `test_secrets_are_redacted_in_place_and_counted_by_label` feeds two commits whose subjects hold a fake chat token and a fake `password=` value, runs, and reads `commits.json`. The subjects must read `fix [REDACTED:SLACK_TOKEN] now` and `login [REDACTED:CREDENTIAL] ok` {src:tests/scripts/connectors/comms/test_commits.py:124-130}. The printed line must hold `2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)` {src:tests/scripts/connectors/comms/test_commits.py:131}, and neither secret value may appear in the cache file, the output, the error text or the run log {src:tests/scripts/connectors/comms/test_commits.py:132-133}. The code under test redacts after the privacy filter and before the write, and passes the tally to the finish step {src:scripts/connectors/comms/commits_connector.py:142-143} {src:scripts/connectors/comms/commits_connector.py:152}.
9. `test_subjects_never_printed_or_logged` puts a marker in the subject and expects it absent from standard output, standard error and the run log {src:tests/scripts/connectors/comms/test_commits.py:135-139}.
10. `test_dry_run_runs_no_git` expects zero git calls and two cached records {src:tests/scripts/connectors/comms/test_commits.py:141-145}, matching the two fixture records in the connector {src:scripts/connectors/comms/commits_connector.py:42-47}.

## Diagram

<!-- Skipped: the fixtures are one fake runner and one base class; there is no mock chain that needs a picture. -->

## Notes

- **Code and description.** The header says "CON-01 to CON-04, repo discovery, parsing, privacy" {src:tests/scripts/connectors/comms/test_commits.py:3}. All of these are covered. The `date:` field in the header is empty {src:tests/scripts/connectors/comms/test_commits.py:5}.
- **Test that depends on the machine.** `test_local_address_uses_repos_path` changes only `os.environ`, not the paths file. `get_path` reads the file named by `TOLLGATE_PATHS` first and returns its `repos` line before it looks at `TOLLGATE_CODE_DIR` {src:scripts/core/paths.py:125-127}. A developer shell that sets `TOLLGATE_PATHS` with a `repos:` line would make this test fail {src:scripts/core/paths.py:72}. No Python version dependence found.
- **Test that is weak.** `test_subjects_never_printed_or_logged` never checks that the commit was read. If the run stopped early the marker would also be absent. It also does not look in the cache file, which does hold the subject {src:scripts/connectors/comms/commits_connector.py:65} {src:scripts/connectors/comms/comms_common.py:107}, so the privacy rule holds for print and log only. Secrets in that subject are replaced before the write, which the redaction test checks for one token of each kind {src:tests/scripts/connectors/comms/test_commits.py:129-130}. Two tokens of one kind in one subject count once {src:scripts/connectors/comms/comms_common.py:74-75}, and no test covers that.
- **Slow test.** The CON-02 case walks every file under the repo root and the home folder {src:tests/scripts/connectors/comms/comms_base.py:153-161}.
- **Unchecked inputs (product code the tests drive).** The `--root` values and the address go to `git -C <path>` and to directory checks with no check on their value {src:scripts/connectors/comms/commits_connector.py:52-57} {src:scripts/connectors/comms/commits_connector.py:81}. `--since` is sent as one argument `--since=<text>` {src:scripts/connectors/comms/commits_connector.py:81}. The command is a list, not a shell string, so the text cannot start a second command. No test sends odd values for either.
- **Writes to shared files.** The tests write only inside the throwaway home. The product writes the cache through `atomic_replace` {src:scripts/connectors/comms/comms_common.py:55}, which writes a temp file named for the process id and swaps it in with `os.replace` {src:scripts/cache/cache_write.py:24} {src:scripts/cache/cache_write.py:30}. That is atomic, but there is no lock: two runs at once each swap in a whole file and the later one wins. No test here runs two writers.
