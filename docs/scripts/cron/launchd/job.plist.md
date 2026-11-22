---
doc_type: config
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: config         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/cron/launchd/job.plist.template"    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
format: "plist"         # yaml | toml | json | env
governs: "the shape of the macOS scheduled job file that setup_cron.py writes"        # what component or behavior this config controls
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

This is the template for a macOS launchd job file (an Apple property list in XML). It holds the fixed parts of a scheduled job and five placeholder markers. `setup_cron.py` fills the markers and writes the result as a job file. This page is named `job.plist.md` because the source name has two dots (`job.plist.template`) and the page path drops only the last extension.

## Dependencies

**Depends on.** Nothing at run time. It is plain text with markers.

**Used by.**
- Product code: `scripts/cron/setup_cron.py`, which sets the template path {src:scripts/cron/setup_cron.py:35} and reads it {src:scripts/cron/setup_cron.py:106}: [[setup_cron]], [setup_cron](../setup_cron.md). It is the only file that names the template (searched with `git grep` for `job.plist` and `launchd/` over the repo except `docs/`, 2026-11-20).
- Tests: none name the template directly in that search.

The jobs it schedules call the shared runner in the sibling folder, see [[run_task]], [run_task](../launchers/run_task.md).

## Behavior

The file is a plist with one top-level dictionary {src:scripts/cron/launchd/job.plist.template:4-5}. Each key and the marker that fills it:

- `Label` takes `@LABEL@`, the job name {src:scripts/cron/launchd/job.plist.template:6-7}. `setup_cron.py` replaces it with the XML escaped label {src:scripts/cron/setup_cron.py:107}.
- `ProgramArguments` takes `@PROGRAM_ARGUMENTS@`, inside an array {src:scripts/cron/launchd/job.plist.template:9-12}. It becomes one `string` entry each for `/bin/bash`, the program path and its arguments {src:scripts/cron/setup_cron.py:97-98}.
- `StartCalendarInterval` takes `@SCHEDULE@` {src:scripts/cron/launchd/job.plist.template:14-17}. It becomes `Hour` and `Minute` entries, plus `Weekday` only when a weekday is given, so without one the job runs every day {src:scripts/cron/setup_cron.py:100-103}.
- `EnvironmentVariables` takes `@ENVIRONMENT@` {src:scripts/cron/launchd/job.plist.template:19-22}. It becomes a key and string pair for each variable passed in {src:scripts/cron/setup_cron.py:104-105}.
- `StandardOutPath` and `StandardErrorPath` both take `@LOG_FILE@`, so output and errors go to one file {src:scripts/cron/launchd/job.plist.template:24-27}. `setup_cron.py` fills both with the escaped log path {src:scripts/cron/setup_cron.py:108-109}.
- `RunAtLoad` is the fixed value false {src:scripts/cron/launchd/job.plist.template:29-30}, so loading the job does not run it; it runs at its scheduled time only.

Filling is a plain text replace of each marker, one after another {src:scripts/cron/setup_cron.py:107-110}. A marker left in the template that `setup_cron.py` does not list would stay in the output unchanged; the five in the file all match the five in the code.

## Diagram

None: the file is a flat set of keys with no branches.

## Notes

- The comment says each marker is "written between two at signs" {src:scripts/cron/launchd/job.plist.template:3}. That matches the five markers used, for example {src:scripts/cron/launchd/job.plist.template:7}.
- The template has no `KeepAlive` or `RunAtLoad` true, so a failed run is not restarted until the next scheduled time.
- Escaping: `setup_cron.py` escapes the label, arguments, environment and log path before filling {src:scripts/cron/setup_cron.py:97-98} {src:scripts/cron/setup_cron.py:104-105} {src:scripts/cron/setup_cron.py:107} {src:scripts/cron/setup_cron.py:109}. The schedule numbers are integers formatted into the text {src:scripts/cron/setup_cron.py:100-103}; the range check is in `settings` and is covered on the setup page.
- A marker text appearing inside a filled value (for example in a path) could be replaced by a later pass, since replacement is sequential {src:scripts/cron/setup_cron.py:107-110}. The markers are filled in the order label, arguments, schedule, environment, log file; this is an edge case, not tested here.
- The template is written into the user's launch agents folder by `setup_cron.py`, not by this file; see the setup page for atomicity and overlap.
