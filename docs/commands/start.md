# /tg-start

**It opens a work session: it checks the date, the vault and the open blockers, then shows a short agenda.** Use it at the start of a session. It changes nothing except the saved agenda {src:commands/tg-start.md:5} {src:commands/tg-start.md:156-159}.

The command name is fixed. Modes: `/tg-start` (full load), `/tg-start learn`, `/tg-start ticket {KEY}`. If the mode is unclear it asks one question and does not go on until the mode is confirmed {src:commands/tg-start.md:16-18} {src:commands/tg-start.md:21}.

## What it does

1. Runs `date` and states the mode and what it will load. It waits for your confirmation {src:commands/tg-start.md:28} {src:commands/tg-start.md:31} {src:commands/tg-start.md:33}.
2. Runs the vault health check `$TOLLGATE_HOME/scripts/search/tg-search health --top 5`. Over 10 dead links it flags `SEARCH DEGRADED`. Exit 1 is reported without stopping; exit 2 or `not set up` is logged as a skip {src:commands/tg-start.md:40} {src:commands/tg-start.md:43}.
3. Finds state files with an open time-sensitive fact (stale after 7 days) or a BLOCKED state, and runs `python3 $TOLLGATE_HOME/scripts/state/ticket_state_check.py {KEY}` on each {src:commands/tg-start.md:52} {src:commands/tg-start.md:55} {src:commands/tg-start.md:60}.
4. For medium or high stakes sessions, searches your own reference store with `tg-search reference --situation session_start`. If it prints `not set up` or `no match`, it says so in one line and goes on {src:commands/tg-start.md:77-87}.
5. Shows yesterday's work from the session cost log, then the agenda, then saves it {src:commands/tg-start.md:134} {src:commands/tg-start.md:138-154}.

A script that is unavailable is skipped with a logged reason; `/tg-start` never fails because of one {src:commands/tg-start.md:185}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{landing}`, `{tickets}` and `{education}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-start.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-start.md:3}.

- Reads: the vault; `{ticket}/{KEY}-state.md` and the spec, design and latest session file in that folder (ticket mode); `{education}/learning-state.md` (learn mode); the session cost log `session-costs.jsonl` in the output folder {src:commands/tg-start.md:95} {src:commands/tg-start.md:113} {src:commands/tg-start.md:134}.
- Writes: an archive copy `{date}.md` in the `_start` folder of the output folder, and a landing note at `{landing}/YYYY/MM/YYYY-MM-DD-start.md`. It also records session cost with `python3 $TOLLGATE_HOME/scripts/core/session_cost.py --mode start` {src:commands/tg-start.md:158-159} {src:commands/tg-start.md:174}.
- Vault git: it does not commit and runs no vault git line {src:commands/tg-start.md:187}.

## Hooks and gate lines

The landing note passes the vault frontmatter hook: `type: session_start`, upper case `status`, a real `date`, no empty string values {src:commands/tg-start.md:163-166}. No gate line is written.

## Example

```
/tg-start ticket T-001
```

It loads the T-001 state, spec and design, shows blockers, and asks what you are working on {src:commands/tg-start.md:113} {src:commands/tg-start.md:121}.
