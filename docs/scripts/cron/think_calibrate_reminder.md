---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/cron/think_calibrate_reminder.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "the if test at line 16, then the osascript call at line 21"    # function or line that executes when the script runs
requires: [bash, osascript]       # external commands or tools this script depends on
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

This script shows a desktop notification that tells the reader to run the thinking calibration command in Claude Code. It exists as the program behind the weekly reminder job. It holds no logic beyond choosing between a real notification and plain text.

## Dependencies

**Depends on.**
- The macOS program `osascript`, which shows the notification {src:scripts/cron/think_calibrate_reminder.sh:21}. The shell built-in `command -v` tests for it {src:scripts/cron/think_calibrate_reminder.sh:16}.
- No repo files, no other environment variables, no folders.

**Used by.**
- Product code: the `weekly-reminder` entry of the job table in [[setup_cron]] [setup_cron](setup_cron.md), which schedules it at 9:00 on weekday 0 {src:scripts/cron/setup_cron.py:48}. Nothing else references it. Searched with `git grep think_calibrate_reminder` over the repo except `docs/` on 2026-11-20.
- Tests: `test_think_calibrate_reminder_dry_run` in `tests/scripts/cron/test_cron_tools.py` {src:tests/scripts/cron/test_cron_tools.py:306-309}, and a setup test that schedules the weekly reminder {src:tests/scripts/cron/test_cron_tools.py:145-147}.

## Behavior

**Text.** The message and the notification title are fixed strings set at the top {src:scripts/cron/think_calibrate_reminder.sh:13-14}.

**Branch.** If the first argument is exactly `--dry-run`, or `osascript` is not on the path, the script prints "title: message" and exits 0 {src:scripts/cron/think_calibrate_reminder.sh:16-19}. Otherwise it calls `osascript` to display the notification with the sound "Ping" {src:scripts/cron/think_calibrate_reminder.sh:21}. The exit code of the script in that case is the exit code of `osascript`, since it is the last command and nothing checks it {src:scripts/cron/think_calibrate_reminder.sh:21}.

## Diagram

<!-- Straight-line script with one branch, no diagram needed: the only decision is dry run or missing osascript versus a real notification (lines 16-21). -->

## Notes

**Code and its own description disagree.** The header says "on any other system it prints the text and exits 0" {src:scripts/cron/think_calibrate_reminder.sh:3-4}. The code does not test the operating system; it tests whether `osascript` exists {src:scripts/cron/think_calibrate_reminder.sh:16}. On any machine that has an `osascript` program the real call is made. The header also says "It touches no files" {src:scripts/cron/think_calibrate_reminder.sh:5}; that is true of the script itself, and nothing in it writes a file.

**Inputs without a check.** No input reaches a file path or network address. The two strings placed in the `osascript` command line are constants set in the script and contain no characters that need escaping {src:scripts/cron/think_calibrate_reminder.sh:13-14} {src:scripts/cron/think_calibrate_reminder.sh:21}. The first argument is only compared with `--dry-run`; anything else is ignored.

**Shared writes.** None.

**Assumptions.** Needs `bash`. Any argument other than `--dry-run` still triggers the real notification. The test only covers the dry run, so the real `osascript` branch is not tested, and the dry-run test would also pass on a machine without `osascript` {src:scripts/cron/think_calibrate_reminder.sh:16}.
