---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/cron/launchers/run-conversations.command"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "line 6, the call to run_task.sh with the task name conv"    # function or line that executes when the script runs
requires: [bash]       # external commands or tools this script depends on
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

A double click launcher for macOS. Opening `run-conversations.command` runs the `conv` task of the shared runner in a terminal window and keeps the window open until a key is pressed, so the output can be read. The task converts Claude session files into the conversations folder.

## Dependencies

**Depends on.**
- `scripts/cron/launchers/run_task.sh`, called by path from the folder the launcher sits in {src:scripts/cron/launchers/run-conversations.command:5-6}: [[run_task]], [run_task](run_task.md).
- bash, named in the shebang line {src:scripts/cron/launchers/run-conversations.command:1}.

**Used by.** No product code or test references this file by name (searched with `git grep` for the file name over the repo except `docs/`, 2026-11-20). It is meant to be opened by hand from Finder.

## Behavior

The launcher works out its own folder, then runs `run_task.sh conv` from there {src:scripts/cron/launchers/run-conversations.command:5-6}. Nothing else is passed, so it never does a dry run and always runs the real job {src:scripts/cron/launchers/run-conversations.command:6}. After the task ends, it prints a blank line and "Press any key to close...", then waits for one key press {src:scripts/cron/launchers/run-conversations.command:7-9}.

The task's exit status is not saved or checked, so the launcher's own status comes from the key read, not from the job {src:scripts/cron/launchers/run-conversations.command:6} {src:scripts/cron/launchers/run-conversations.command:9}.

## Diagram

None: the script is straight-line (run, prompt, wait).

## Notes

- Shell: bash, required for `read -n 1` {src:scripts/cron/launchers/run-conversations.command:9}.
- The header has an empty `Date:` field {src:scripts/cron/launchers/run-conversations.command:4}; this is a blank, not a disagreement with the code.
- Inputs reaching paths or commands: the only path built is the script's own folder, taken from `$0` and quoted {src:scripts/cron/launchers/run-conversations.command:5}; no outside input is used. No file is written by the launcher itself, and what the task writes is covered on the runner page.
- Idempotency and overlap: nothing stops a manual run from overlapping the nightly job; see [[run_task]].
