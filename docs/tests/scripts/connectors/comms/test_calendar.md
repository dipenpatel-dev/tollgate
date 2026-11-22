---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/connectors/comms/test_calendar.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/connectors/comms/calendar_connector.py"]         # source files under test, relative paths from repo root
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

This file tests the calendar connector, the script that pulls one day of calendar events into the cache. It checks the four shared connector rules (not set up, first-use secret handling, survives a restart, turn off), the two ways of reading events (a calendar web API and the macOS Calendar app), the same-day copy, that event titles stay out of output and logs, and that a secret inside an event title is replaced in place with a labeled marker and counted by label. Its header says no source test existed before for this connector {src:tests/scripts/connectors/comms/test_calendar.py:8}.

## Dependencies

**Depends on.**
- [[calendar_connector]] ([calendar_connector](../../../../scripts/connectors/comms/calendar_connector.md)): the module under test, imported as `cal` {src:tests/scripts/connectors/comms/test_calendar.py:16}.
- [[comms_base]] ([comms_base](comms_base.md)): the shared test base (`Base`, `make_con_tests`, `FAKE_ADDRESS`, and the two fake secret builders `fake_slack_token` and `fake_credential`) {src:tests/scripts/connectors/comms/test_calendar.py:15}. It supplies the temporary home, a fake secret store and a recording fake web client {src:tests/scripts/connectors/comms/comms_base.py:62-72}.
- [[comms_common]] ([comms_common](../../../../scripts/connectors/comms/comms_common.md)): writes the cache file the tests read back and prints the run line, now with the secret count by label {src:scripts/connectors/comms/comms_common.py:105-114}. Its `redact_records` does the redaction under test {src:scripts/connectors/comms/comms_common.py:81-87}.
- Standard library: `json`, `pathlib`, `subprocess`, `unittest` {src:tests/scripts/connectors/comms/test_calendar.py:10-13}.

**Used by.**
- Product code: none (searched `git grep` for `test_calendar` outside `docs/`, 2026-11-20; the only other hit is a test method name inside this file).
- Tests: found by the comms folder launcher's `test_*.py` discovery {src:tests/scripts/connectors/comms/run.sh:6}, see [[run]] ([run](run.md)). No CI workflow runs it (`.github/workflows/tests.yml` names no connector step).

## Behavior

**Setup.** `CalBase` names the connector `calendar` and gives it the module {src:tests/scripts/connectors/comms/test_calendar.py:29-30}. Its `setUp` makes the fake web client answer every request with one event {src:tests/scripts/connectors/comms/test_calendar.py:32-34}. The `api_event` helper builds that event with a title, a start, an end and two attendees {src:tests/scripts/connectors/comms/test_calendar.py:21-25}. `reached_client` asserts exactly one call whose address starts with the fake base address plus the primary calendar path {src:tests/scripts/connectors/comms/test_calendar.py:36-38}. The fake base address is a reserved invalid host {src:tests/scripts/connectors/comms/comms_base.py:29}.

**Class `TestCon`.** It is built by `make_con_tests` with a fixed day and time zone {src:tests/scripts/connectors/comms/test_calendar.py:41-42}, and gets these five cases from the base {src:tests/scripts/connectors/comms/comms_base.py:131-187}:
- Not set up: with no network allowed, a run exits non-zero, says "calendar: not set up" and how to turn it on, makes no web call and creates no connector state file {src:tests/scripts/connectors/comms/comms_base.py:131-138}. The same through a real child process {src:tests/scripts/connectors/comms/comms_base.py:140-145}.
- First use: turning on stores the secret in the fake store, and a scan of every file under the repo root and the temporary home finds the secret nowhere {src:tests/scripts/connectors/comms/comms_base.py:147-161}.
- Survives restart: after the module is reloaded and the registry emptied, only the saved state file and the store remain, and the next run reaches the client {src:tests/scripts/connectors/comms/comms_base.py:166-176}.
- Off: turning off clears the store and the next run is "not set up" again {src:tests/scripts/connectors/comms/comms_base.py:178-187}.

**Class `TestCalendar`** (every case starts with the connector turned on).

| Case | What it proves |
|---|---|
| API mode | `--calendar team` asks for the `team` calendar path, and the cache holds the projected event (id, title, start, end, attendee count of 2) with result `success` {src:tests/scripts/connectors/comms/test_calendar.py:58-67}. The projection keeps the attendee count, not the addresses {src:scripts/connectors/comms/calendar_connector.py:124-127}. |
| two calendars | Two `--calendar` flags make two calls, and the same event id from both is kept once {src:tests/scripts/connectors/comms/test_calendar.py:69-73} {src:scripts/connectors/comms/calendar_connector.py:154-156}. |
| same-day copy | A second run for the same day makes no new call; `--no-day-cache` forces one {src:tests/scripts/connectors/comms/test_calendar.py:75-81} {src:scripts/connectors/comms/calendar_connector.py:217-219}. |
| dry run | `--dry-run` makes no call and does not leave a day copy, so a later normal run still calls {src:tests/scripts/connectors/comms/test_calendar.py:83-88} {src:scripts/connectors/comms/calendar_connector.py:236}. |
| macOS mode | With a fake program runner, no web call is made, the script text holds the calendar name, two identical lines give one event, the start becomes an ISO time in the given zone, and the attendee count is 3 {src:tests/scripts/connectors/comms/test_calendar.py:90-101}. The runner is swapped in from the `runner` argument {src:scripts/connectors/comms/calendar_connector.py:206-207}, and the script is the third item of the command list {src:scripts/connectors/comms/calendar_connector.py:161}. |
| wrong field count | A line with three fields gives no events and the reason `schema_invalid` {src:tests/scripts/connectors/comms/test_calendar.py:103-106} {src:scripts/connectors/comms/calendar_connector.py:99-100}. |
| macOS failure | A non-zero exit from the program means no cache file and the reason `auth_failed` in the log {src:tests/scripts/connectors/comms/test_calendar.py:108-112} {src:scripts/connectors/comms/calendar_connector.py:167-168} {src:scripts/connectors/comms/comms_common.py:105}. |
| quote stripping | A calendar name with a double quote comes out inside the script text with the quote removed {src:tests/scripts/connectors/comms/test_calendar.py:114-115} {src:scripts/connectors/comms/calendar_connector.py:83}. |
| titles | A distinctive title never appears in standard output, standard error or the run log {src:tests/scripts/connectors/comms/test_calendar.py:135-139}. The finish step prints counts only {src:scripts/connectors/comms/comms_common.py:111-113}. |
| secret redaction | Two API events carry a fake chat token and a fake `password=` value in their titles {src:tests/scripts/connectors/comms/test_calendar.py:118-120}. After a run the cache titles read `call [REDACTED:SLACK_TOKEN] now` and `login [REDACTED:CREDENTIAL] ok` {src:tests/scripts/connectors/comms/test_calendar.py:124-127}. The printed line holds `2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)` {src:tests/scripts/connectors/comms/test_calendar.py:128}. Neither secret value appears in the cache file, the same-day copy, the output, the error text or the run log {src:tests/scripts/connectors/comms/test_calendar.py:129-131}. The code under test redacts after the privacy filter and before both writes {src:scripts/connectors/comms/calendar_connector.py:228-229} {src:scripts/connectors/comms/calendar_connector.py:237}. |
| no hard-coded zone | The connector source text does not contain `America/` {src:tests/scripts/connectors/comms/test_calendar.py:141-143}. |

Helper: `fake_osascript` returns a function that records every command it was given and returns a canned result {src:tests/scripts/connectors/comms/test_calendar.py:45-52}.

## Diagram

None: the base class holds the setup (fake store, fake client, throwaway home) and each case is a short call and assertion.

## Notes

**Tests whose name or claim does not match the check.**
- `test_calendar_choice_is_not_hard_coded` says calendar choice, but it checks only that the text `America/` is absent from the connector source {src:tests/scripts/connectors/comms/test_calendar.py:141-143}. That guards one time-zone string, not the calendar name choice, and would not notice another zone name.
- The header says the tests cover "privacy" {src:tests/scripts/connectors/comms/test_calendar.py:3}. The privacy case checks only output, errors and the log. The cache file itself holds the title, as the API-mode case shows {src:tests/scripts/connectors/comms/test_calendar.py:63-64}, with only secrets inside it replaced, as the redaction case shows {src:tests/scripts/connectors/comms/test_calendar.py:126-127}.
- The shared helper module's header calls its rule "counts only, never message text or titles" {src:scripts/connectors/comms/comms_common.py:6-7}, while the calendar cache and the same-day copy store titles, with secrets in them redacted {src:scripts/connectors/comms/calendar_connector.py:237} {src:scripts/connectors/comms/comms_common.py:107}. The connector's own header is narrower and holds: titles are never printed or logged {src:scripts/connectors/comms/calendar_connector.py:24}.

**Coverage gaps.** The redaction case covers API mode only and one token of each kind per title; it does not cover macOS mode, a reused same-day copy (which is not redacted again {src:scripts/connectors/comms/calendar_connector.py:218-219}), or two tokens of one kind in one title (counted once {src:scripts/connectors/comms/comms_common.py:74-75}). The redaction case sets its argument list in a class attribute defined after the test method, which repeats `ARGV` {src:tests/scripts/connectors/comms/test_calendar.py:133} {src:tests/scripts/connectors/comms/test_calendar.py:56}. Only the double quote case is tried for calendar names, though the code also strips a backslash {src:scripts/connectors/comms/calendar_connector.py:83}. Not tested: the time-out and operating-system-error branches of the macOS read {src:scripts/connectors/comms/calendar_connector.py:163-166}, an API body of the wrong shape {src:scripts/connectors/comms/calendar_connector.py:148-153}, a web error status {src:scripts/connectors/comms/comms_common.py:137-138}, and the privacy-guard branches that mark a run degraded {src:scripts/connectors/comms/calendar_connector.py:230-233}.

**Tests that depend on the machine.**
- The macOS and API cases build a time zone from the name `UTC` with `ZoneInfo` {src:scripts/connectors/comms/calendar_connector.py:77}; that needs Python 3.9 or later (the 3.12 minimum covers that) and a time-zone database on the machine (not checked here).
- The base finds the repo root by going up a fixed number of folders from its own file {src:tests/scripts/connectors/comms/comms_base.py:21}.
- The first-use case reads every file under the repo root and the home folder {src:tests/scripts/connectors/comms/comms_base.py:153-161}, so it gets slower as the repo grows.
- The case dates are fixed (2026-03-02), so no case depends on today's date {src:tests/scripts/connectors/comms/test_calendar.py:56}.

**Tests that cannot fail.** None found. The `pass` body of `TestCon` is by design; the cases come from the base {src:tests/scripts/connectors/comms/test_calendar.py:41-42}.

**Unchecked inputs.** Test inputs are constants. For the code under test, a calendar name given on the command line reaches the AppleScript text with only `"` and `\` removed and no other check {src:scripts/connectors/comms/calendar_connector.py:83}. It runs as an argument list, not through a shell {src:scripts/connectors/comms/calendar_connector.py:161}. In API mode the name is URL-quoted into the path {src:scripts/connectors/comms/calendar_connector.py:142}. The address comes from saved connector state and goes into the web call with no check on its value in this file; in the tests it is an invalid host and the client is a fake that makes no network call {src:tests/scripts/connectors/comms/comms_base.py:53-55}.

**Shared-file writes.** The tests write only under the throwaway home, which is removed in `tearDown` {src:tests/scripts/connectors/comms/comms_base.py:74-77}. They exercise two writes of the code under test: the cache file by an atomic replace {src:scripts/connectors/comms/comms_common.py:55}, and the same-day copy by a plain write that ignores errors with no lock {src:scripts/connectors/comms/calendar_connector.py:187-193}. No test starts two writers at once. The tests also change shared process state: they reload the connector module {src:tests/scripts/connectors/comms/comms_base.py:64}, set and unset global registry hooks {src:tests/scripts/connectors/comms/comms_base.py:70-71} {src:tests/scripts/connectors/comms/comms_base.py:75-76}, and copy then restore the whole environment around each run {src:tests/scripts/connectors/comms/comms_base.py:90-102}. Unlike the cache tests, this base restores the environment correctly.
