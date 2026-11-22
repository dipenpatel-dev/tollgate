---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/connectors/comms/test_slack.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/connectors/comms/slack_connector.py"]         # source files under test, relative paths from repo root
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

Tests for the chat connector that turns channel history into one markdown note per channel per month. One group proves the shared "off until first use" rules (the four CON cases). A second group tests the pure text helpers. A third group runs the whole connector against a fake chat service and against a small local SQLite archive, and proves the note layout, the cursor that remembers the newest message, the full re-read flag, direct-message handling, failure of one channel, that message text is never printed or logged, that a message or reply holding a personal id is not written to the note, that secrets in message text are replaced in place with a labeled marker and counted by label, and that dropped messages are counted in the log and the printed line.

## Dependencies

**Depends on.**
- `scripts/connectors/comms/slack_connector.py`, the code under test: [[slack_connector]] and [slack_connector](../../../../scripts/connectors/comms/slack_connector.md) {src:tests/scripts/connectors/comms/test_slack.py:18}
- `tests/scripts/connectors/comms/comms_base.py` for `Base`, `make_con_tests`, `FAKE_ADDRESS` and the two fake secret builders `fake_slack_token` and `fake_credential` {src:tests/scripts/connectors/comms/test_slack.py:17}. [[comms_base]] and [comms_base](comms_base.md)
- The harness mock client, fake secret store and throwaway home through `comms_base.py` {src:tests/scripts/connectors/comms/comms_base.py:25-26}: [[connector_helpers]] and [connector_helpers](../../../harness/connector_helpers.md), [[throwaway_home]] and [throwaway_home](../../../harness/throwaway_home.md)
- Standard library: `json`, `pathlib`, `sqlite3`, `unittest`, `datetime.timezone`, `urllib.parse` {src:tests/scripts/connectors/comms/test_slack.py:10-15}

**Used by.**
- Product code: none. Searched with `git grep` for `test_slack` and `tests/scripts/connectors` outside `docs/` (2026-11-20).
- Tests (runners): `tests/scripts/connectors/comms/run.sh` finds it by the pattern `test_*.py` {src:tests/scripts/connectors/comms/run.sh:6}; `tests/system/run.sh` runs that script for the area `connectors/comms` {src:tests/system/run.sh:22-23}.

## Behavior

**Fake chat service.** `route(history, replies)` returns a handler: `users.list` gives two members (`U1` "Ana Lee", `U2` "bob"), `conversations.history` gives whatever the `history` function returns for the query, `conversations.replies` gives the thread for the `ts` asked, anything else answers `ok: False` {src:tests/scripts/connectors/comms/test_slack.py:27-39}. The default history has a parent message with one reply and a next-day message; if the query holds `oldest`, older messages are dropped {src:tests/scripts/connectors/comms/test_slack.py:42-48}. The time stamps are fixed: 2026-03-02 09:00 UTC, five minutes later, and the next day {src:tests/scripts/connectors/comms/test_slack.py:21-23}.

**The four CON cases.** `TestCon` runs the shared factory with `--channel C1=general --tz UTC` {src:tests/scripts/connectors/comms/test_slack.py:75-79}. It checks the not-set-up message and no http call {src:tests/scripts/connectors/comms/comms_base.py:131-138}, the same through a subprocess {src:tests/scripts/connectors/comms/comms_base.py:140-145}, the key stored and found in no file {src:tests/scripts/connectors/comms/comms_base.py:147-161}, survival of a restart with the first call being `/users.list` at the fake address {src:tests/scripts/connectors/comms/comms_base.py:166-176} {src:tests/scripts/connectors/comms/test_slack.py:67-69}, and a return to "not set up" after turning off {src:tests/scripts/connectors/comms/comms_base.py:178-187}.

**Text helpers (`TestText`, no connector needed).**
- `clean_text` turns `<@U2>` into `@Bob`, `<url|label>` into `label`, a bare `<url>` into the url, `<#C1|dev>` into `#dev`, and an empty string into an empty string {src:tests/scripts/connectors/comms/test_slack.py:83-87} {src:scripts/connectors/comms/slack_connector.py:54-61}.
- `slug` lowercases and turns other characters to dashes (`Ana Lee!` gives `ana-lee`), and gives `unnamed` for `!!` {src:tests/scripts/connectors/comms/test_slack.py:89-91} {src:scripts/connectors/comms/slack_connector.py:68-69}.
- `build_monthly` groups by month, starts a day with `### 2026-03-02`, writes `**[09:00] Ana**: top`, and renders a reply as an indented `  -> **[09:05] Bob**: child` line {src:tests/scripts/connectors/comms/test_slack.py:93-102} {src:scripts/connectors/comms/slack_connector.py:98-114}.

**Connector cases (`TestSlack`).**
1. API mode: the note `channels/general/2026-03-general.md` under the vault folder `05-conversations/slack` has the heading `# #general - 2026 March`, `Channel ID: C1`, the mention and link cleaned, the reply inline, and no copy of the parent text from the replies call {src:tests/scripts/connectors/comms/test_slack.py:144-153} {src:tests/scripts/connectors/comms/test_slack.py:71-72}. The heading is built at {src:scripts/connectors/comms/slack_connector.py:134} and the parent copy is skipped when its `ts` equals the thread parent {src:scripts/connectors/comms/slack_connector.py:196}.
2. Cursor: after a run, `state/slack/cursor.json` holds `{"C1": <newest ts>}`; a second run sends `oldest=1772528400.300000`-style text (six decimals) and leaves the note unchanged {src:tests/scripts/connectors/comms/test_slack.py:155-165}. The cursor is the largest `ts` fetched {src:scripts/connectors/comms/slack_connector.py:342}; the query value is formatted with `%.6f` {src:scripts/connectors/comms/slack_connector.py:180}.
3. Full: `--full` sends no `oldest` {src:tests/scripts/connectors/comms/test_slack.py:167-173}. The cursor is ignored by starting from an empty state {src:scripts/connectors/comms/slack_connector.py:319}.
4. Direct message: `--dm D1=Ana Lee` writes `dms/ana-lee/2026-03-ana-lee.md` {src:tests/scripts/connectors/comms/test_slack.py:175-178} {src:scripts/connectors/comms/slack_connector.py:329-330}.
5. Channels only from flags: a run with no flags exits non-zero, makes no call, and the exit message names `--channel`; the test also searches the connector source for the text `C0` {src:tests/scripts/connectors/comms/test_slack.py:180-186} {src:scripts/connectors/comms/slack_connector.py:309-310}.
6. One channel fails: history for `CBAD` answers `ok: False`; the good channel still gets its note, and the log says `degraded` {src:tests/scripts/connectors/comms/test_slack.py:188-199}. The loop records the first failure reason and continues {src:scripts/connectors/comms/slack_connector.py:333-335}, then logs a degraded result {src:scripts/connectors/comms/slack_connector.py:347-348}.
7. Archive mode: a SQLite file with three tables is built in the throwaway home; the run makes no http call, the thread reply appears under its parent with the name from the archive, and the direct-message channel `D9` is found and written even though it was not named on the command line {src:tests/scripts/connectors/comms/test_slack.py:201-222}. The archive path reads with `mode=ro` {src:scripts/connectors/comms/slack_connector.py:210} and finds direct messages through `is_im` or `is_mpim` {src:scripts/connectors/comms/slack_connector.py:239-243}.
8. Privacy: a marker in a message is absent from stdout, stderr and the log, present in the note, and stdout contains `messages=1` {src:tests/scripts/connectors/comms/test_slack.py:224-230}. The printed line is made only from counts and the secret count by label {src:scripts/connectors/comms/slack_connector.py:349-350}.
9. Personal ids: a thread whose parent says `ok keep` has one reply that holds `MRN 12345678`, and a second top level message holds `SSN 123-45-6789`. The note keeps `ok keep` and holds neither number {src:tests/scripts/connectors/comms/test_slack.py:106-115}. The code drops a top level message that the privacy filter matches {src:scripts/connectors/comms/slack_connector.py:88-90} {src:scripts/connectors/comms/slack_connector.py:101-103} and drops a matching reply on its own {src:scripts/connectors/comms/slack_connector.py:110-111}. The reply set used is `REPLIES_PHI` {src:tests/scripts/connectors/comms/test_slack.py:55-56}.
10. Secret redaction: two top level messages carry a fake chat token and a fake `password=` value {src:tests/scripts/connectors/comms/test_slack.py:119-121}. The note must hold `deploy with [REDACTED:SLACK_TOKEN] now` and `login [REDACTED:CREDENTIAL] ok` {src:tests/scripts/connectors/comms/test_slack.py:126-127}, the printed line must hold `2 secrets redacted (CREDENTIAL 1, SLACK_TOKEN 1)` {src:tests/scripts/connectors/comms/test_slack.py:128}, and neither secret value may appear in the note, the output, the error text or the run log {src:tests/scripts/connectors/comms/test_slack.py:129-130}. The code redacts each kept message after the privacy filter and before the write {src:scripts/connectors/comms/slack_connector.py:88-91}.
11. Dropped messages are counted: with the personal-id thread of case 9, the printed line holds `phi_dropped=2` and `0 secrets redacted`, and the last run log record has a `reject_count` of 2, one for the reply and one for the top level message {src:tests/scripts/connectors/comms/test_slack.py:133-142}. The code counts each dropped message and passes the total to the log and the print {src:scripts/connectors/comms/slack_connector.py:89} {src:scripts/connectors/comms/slack_connector.py:347-350}.

## Diagram

None: the fixtures are a routing function over a mock client and, for one case, a temporary SQLite file. Both are described in Behavior.

## Notes

- Cannot-fail part: the `build_monthly` test is named "skips empty", but its empty message falls in the same month as the others, so the month key list is the same with or without the skip. No assertion looks for a line from the empty message {src:tests/scripts/connectors/comms/test_slack.py:93-102}. The skip, which also covers a message the privacy filter drops, is at {src:scripts/connectors/comms/slack_connector.py:86-90}.
- Weak check: the last assertion of the flags test strips `C0-9` from the connector source and requires that `C0` is absent {src:tests/scripts/connectors/comms/test_slack.py:186}. It depends on the exact text of the source (a comment holding `C0` would fail it) and would not catch a hard-coded id that does not start with `C0`.
- Privacy gaps: the dropped message count is now tested, but the printed `messages` count still includes the dropped messages, since it counts the messages read {src:scripts/connectors/comms/slack_connector.py:343}; no test pins that. The redaction case uses top level messages only, so a secret in a reply is not tested, though replies pass through the same helper {src:scripts/connectors/comms/slack_connector.py:110}, nor are two tokens of one kind in one message, which count once {src:scripts/connectors/comms/comms_common.py:74-75}. No test drops a parent that has kept replies, so the case where the replies are hidden with their parent is not tested {src:scripts/connectors/comms/slack_connector.py:109}. Archive mode is not tested with a personal id, though it uses the same `build_monthly` {src:scripts/connectors/comms/slack_connector.py:338}. Only the social security and `MRN` patterns are used {src:scripts/cache/phi_guard.py:19} {src:scripts/cache/phi_guard.py:20}.
- Gap: the note writer skips a month whose new text is already in the file, and otherwise appends {src:scripts/connectors/comms/slack_connector.py:128-132}. The `--full` test re-reads everything but does not check that the note is unchanged afterwards {src:tests/scripts/connectors/comms/test_slack.py:167-173}, so the skip is not tested. The cursor test passes without reaching it, since the second run has no new messages {src:tests/scripts/connectors/comms/test_slack.py:155-165}.
- Gaps: paging through `next_cursor` for users or history {src:scripts/connectors/comms/slack_connector.py:170-172}, `--archive` combined with `--full`, a bad `ID=name` pair {src:scripts/connectors/comms/slack_connector.py:289-294}, and a failed `users.list` call {src:scripts/connectors/comms/slack_connector.py:321-322} have no test (searched this file, 2026-11-20).
- Machine dependence: `--tz UTC` goes to `ZoneInfo`, which needs time zone data on the machine (system data or the `tzdata` package) {src:scripts/connectors/comms/slack_connector.py:312-313} {src:docs:python-zoneinfo}. The `zoneinfo` module needs Python 3.9 or later, which the 3.12 minimum covers. The vault folder comes from the throwaway home variable `TOLLGATE_KNOWLEDGE` {src:tests/harness/throwaway_home.py:36}.
- Inputs without a check in the product code behind these tests: `--archive` goes to the SQLite open call after URL quoting and no check that it is a file the user meant {src:scripts/connectors/comms/slack_connector.py:210}; `--tz` goes to `ZoneInfo` and a bad name raises an uncaught error {src:scripts/connectors/comms/slack_connector.py:313}; the channel name becomes the note folder and file name through `slug`, which turns every character that is not a word character or dash into a dash, so `..` cannot appear {src:scripts/connectors/comms/slack_connector.py:68-69} {src:scripts/connectors/comms/slack_connector.py:339-341}; the channel id is URL-encoded into the API call {src:scripts/connectors/comms/slack_connector.py:152} and bound as a parameter in the archive query {src:scripts/connectors/comms/slack_connector.py:228}. The channel name is written into the note heading unchanged {src:scripts/connectors/comms/slack_connector.py:340}.
- Shared-file writes: a note is changed by reading it and writing the whole text back, not atomically, with no lock {src:scripts/connectors/comms/slack_connector.py:129-132}. The cursor file is a plain `write_text` with the same lack of atomicity and lock {src:scripts/connectors/comms/slack_connector.py:286}. Two runs at once could lose an update. The tests use one process.
- The first CON-02 test reads every file under the repo root, so it is slow in a checkout with a virtual environment {src:tests/scripts/connectors/comms/comms_base.py:153-161}.
