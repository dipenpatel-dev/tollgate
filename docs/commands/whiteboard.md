# /tg-whiteboard

**It tests a new idea and gives a verdict: BUILD, PARK or DROP.** Use it before an idea enters your backlog. It is not for client tickets; those go to `/tg-ticket` {src:commands/tg-whiteboard.md:5} {src:commands/tg-whiteboard.md:113}.

The command name is fixed: `/tg-whiteboard {idea}` or `/tg-whiteboard quick {idea}` {src:commands/tg-whiteboard.md:20-21}.

## What it does

1. Reads two optional prior-reasoning notes if they exist; if missing it says so in one line {src:commands/tg-whiteboard.md:31-36}.
2. Asks for the problem in one concrete sentence. No sharp problem, no whiteboard {src:commands/tg-whiteboard.md:42-49}.
3. Analyses the idea on eight points: viability, goal fit, who it serves, dependencies, steelman and killshot, a six-month stress test, edge cases and timing {src:commands/tg-whiteboard.md:55}.
4. Asks you exactly three questions, one at a time {src:commands/tg-whiteboard.md:95-97}.
5. Adds cost, a measurement signal and what the idea unlocks {src:commands/tg-whiteboard.md:101-107}.
6. Gives the verdict. BUILD also gives a backlog entry, a priority and a first spec scope. BUILD needs a measurement signal {src:commands/tg-whiteboard.md:113-118} {src:commands/tg-whiteboard.md:234}.
7. Writes a note with a context diagram and runs the chart check on it {src:commands/tg-whiteboard.md:132} {src:commands/tg-whiteboard.md:136-141}. The note is written even on DROP {src:commands/tg-whiteboard.md:132}.

`/tg-whiteboard quick` runs only dimensions 1, 2, 5, 9 and 10, and escalates to full for command redesigns {src:commands/tg-whiteboard.md:21} {src:commands/tg-whiteboard.md:23}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{knowledge}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-whiteboard.md:3}.

- Reads: the notes `{knowledge}/whiteboard/whiteboard-reasoning.md` and `whiteboard-knowledge.md` if they exist {src:commands/tg-whiteboard.md:33-34}. The vault is read first; a ticket tracker is a connector that is off until first use {src:commands/tg-whiteboard.md:14}.
- Search: `$TOLLGATE_HOME/scripts/search/tg-search reference --situation whiteboard --stakes medium` for your own reference store. It prints `not set up` or `no match` with no store; the command then says "Reference coverage unverified" and carries on {src:commands/tg-whiteboard.md:62} {src:commands/tg-whiteboard.md:65}.
- Writes: `{knowledge}/whiteboard/YYYY-MM/YYYY-MM-DD-{idea_slug}.md`, creating the month folder if needed {src:commands/tg-whiteboard.md:132}. It never edits the backlog; you paste the entry {src:commands/tg-whiteboard.md:235}.
- Chart check: `python3 $TOLLGATE_HOME/scripts/chart/chart_check --role idea-analyst --require-chart {note_path}` {src:commands/tg-whiteboard.md:141}. Exit 1 means fix and re-run; exit 2 means report and continue {src:commands/tg-whiteboard.md:144}.
- Vault git: it does not commit and runs no vault git line {src:commands/tg-whiteboard.md:239}.

## Hooks and gate lines

The note's frontmatter passes the vault frontmatter hook: `type: whiteboard`, upper case `status: ACTIVE`, a real `date:`, no empty string values {src:commands/tg-whiteboard.md:134} {src:commands/tg-whiteboard.md:150-153}. No gate line is written.

## Example

```
/tg-whiteboard stale facts in ticket state files go unnoticed
```

After three answers it writes a note with `verdict: BUILD` and a paste-ready entry for the backlog item that becomes T-001 {src:commands/tg-whiteboard.md:97} {src:commands/tg-whiteboard.md:155} {src:commands/tg-whiteboard.md:116}.
