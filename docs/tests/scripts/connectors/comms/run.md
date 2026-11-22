---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/comms/run.sh    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "the exec of unittest discover on line 6"    # function or line that executes when the script runs
requires: [bash, dirname, pwd, python3]       # external commands or tools this script depends on
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

This is the one-command runner for the comms connector tests (chat, tracker, notes, calendar and git history). It finds its own folder, turns off Python bytecode files, and starts Python's unittest discovery on that folder. It writes nothing itself.

## Dependencies

Depends on:
- `bash`, run through the `#!/usr/bin/env bash` line {src:tests/scripts/connectors/comms/run.sh:1}.
- `dirname` and `pwd`, used to find the script's own folder {src:tests/scripts/connectors/comms/run.sh:4}.
- The environment variable `TOLLGATE_TEST_PYTHON`, which names the Python program; when unset the script uses `python3` {src:tests/scripts/connectors/comms/run.sh:6}.
- The Python standard library `unittest` module {src:tests/scripts/connectors/comms/run.sh:6}.
- The five test files it finds in the folder: [[test_calendar]] ([test_calendar](test_calendar.md)), [[test_commits]] ([test_commits](test_commits.md)), [[test_jira]] ([test_jira](test_jira.md)), [[test_notion]] ([test_notion](test_notion.md)) and [[test_slack]] ([test_slack](test_slack.md)). The shared base [[comms_base]] ([comms_base](comms_base.md)) is imported by all five.

Used by:
- Product code: none. The system runner loops over area names and `connectors/comms` is one of them {src:tests/system/run.sh:22}, run as `bash "$REPO/tests/scripts/$area/run.sh"` {src:tests/system/run.sh:23}.
- Documentation: `scripts/README.md` says each area has `tests/scripts/<area>/run.sh` {src:scripts/README.md:31}.
- Tests: none (searched `git grep -n "run\.sh"` outside `docs/` on 2026-11-20).

## Behavior

1. `set -u` makes any use of an unset variable an error {src:tests/scripts/connectors/comms/run.sh:3}. There is no `set -e`.
2. `DIR` is the absolute folder of the script, from `BASH_SOURCE[0]` {src:tests/scripts/connectors/comms/run.sh:4}. The `cd` is inside a command substitution, so the caller's folder does not change.
3. `PYTHONDONTWRITEBYTECODE=1` is exported {src:tests/scripts/connectors/comms/run.sh:5}, and Python is also called with `-B` {src:tests/scripts/connectors/comms/run.sh:6}.
4. `exec` replaces the shell with `python -B -m unittest discover -s "$DIR" -p 'test_*.py' -v`, so the exit code is unittest's {src:tests/scripts/connectors/comms/run.sh:6}.
5. Because `-s` is given without a top-level folder, unittest puts the start folder on the import path {src:docs:https://docs.python.org/3/library/unittest.html#unittest-test-discovery}. This is what lets the test files write `from comms_base import ...` with no package {src:tests/scripts/connectors/comms/test_calendar.py:15}.
6. The pattern `test_*.py` leaves out `comms_base.py`, so the base module is imported by the tests but never collected on its own {src:tests/scripts/connectors/comms/run.sh:6}.

## Diagram

None: the script is straight-line with no branches.

## Notes

- Code and description disagree: nowhere found. The comment lists "slack, jira, calendar, git-commits, notion" {src:tests/scripts/connectors/comms/run.sh:2}. The folder holds exactly five `test_*.py` files with those five connectors (searched with `ls` on 2026-11-20), so the list is right today, but it is a hand-kept list and nothing ties it to the folder.
- Unchecked inputs: `TOLLGATE_TEST_PYTHON` is run as a command with no check {src:tests/scripts/connectors/comms/run.sh:6}. It comes from the caller's environment. No other input reaches a path, shell command, network address or outbound text; extra arguments to the script are ignored.
- Shared-file writes: the script writes no file; bytecode is off {src:tests/scripts/connectors/comms/run.sh:5}. The tests write inside a temporary home folder only (see [[comms_base]]).
- Needs bash because it uses `BASH_SOURCE` {src:tests/scripts/connectors/comms/run.sh:4}.
