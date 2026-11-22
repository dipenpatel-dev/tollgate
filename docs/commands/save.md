# /tg-save

**It writes a quick checkpoint of the session to the session log so any AI, or the next session, can pick the work up if things crash or context runs out.** It is like Ctrl+S: it saves to disk and does not commit {src:commands/tg-save.md:5-7}.

The command name is fixed: `/tg-save` (it works out the session state itself) or `/tg-save [note]` (it also captures your note) {src:commands/tg-save.md:15-17}.

## When it runs

You can run it yourself. The command also says Claude runs it without being asked after every major decision or vault write, when the context feels heavy (roughly every 5 to 6 exchanges with a lot of output), and when you switch topics {src:commands/tg-save.md:20-23}. For a timer, the optional form is `/loop 30m /tg-save` {src:commands/tg-save.md:25-28}.

## What it does

1. Runs `date` and uses the exact output as the timestamp {src:commands/tg-save.md:34-38}.
2. Reads the conversation and extracts four things: done so far, decided so far (with why), in progress, pending. A note you passed is folded into the matching section {src:commands/tg-save.md:44-50}.
3. Opens `{landing}/session-log.md`. If there is already a `[DRAFT]` entry for today, it replaces that entry entirely. If not, it puts a new DRAFT entry at the top, below the header {src:commands/tg-save.md:56-61}. The entry carries a heading with date, time, timezone and title, then Done so far, Decided so far, In progress, Pending and Notes {src:commands/tg-save.md:65-71}.
4. If the log already has 20 or more entries (not counting the DRAFT), it removes the oldest non-DRAFT entry before adding {src:commands/tg-save.md:74}.
5. For a ticket session only, it also writes or appends `{output}/{JIRA-KEY}/YYYY-MM-DD.md`. It creates the folder if needed and, if today's file exists, appends a `## Session N` heading {src:commands/tg-save.md:80-87}.
6. Prints a confirmation block that says whether the log and the archive were written or skipped, and that `/tg-close` will finalize and commit {src:commands/tg-save.md:96-102}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{vault}`, `{landing}` and `{output}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-save.md:3}. The names `vault`, `landing` and `output` exist in the path loader {src:scripts/core/paths.py:33} {src:scripts/core/paths.py:42} {src:scripts/core/paths.py:56}.

- Reads: the conversation so far, and `{landing}/session-log.md` {src:commands/tg-save.md:44} {src:commands/tg-save.md:56}.
- Writes: `{landing}/session-log.md`, and for ticket sessions `{output}/{JIRA-KEY}/YYYY-MM-DD.md` with the orient output, findings so far, SQL or drafts, open questions and next steps. That archive is for manual browsing only: not indexed, not committed {src:commands/tg-save.md:56} {src:commands/tg-save.md:83} {src:commands/tg-save.md:88-89}.
- Scripts: only `$TOLLGATE_HOME/scripts/core/tg_path`, which exists {src:commands/tg-save.md:3}. No search script, no cost script.
- Vault git: it never commits or pushes. `/tg-close` owns that {src:commands/tg-save.md:109}. For the vault git modes see [tg_vault_git](../scripts/core/tg_vault_git.md).

## Hooks and gate lines

It writes no `Status:` gate line and names no hook. The one content rule is that PHI never enters the session log {src:commands/tg-save.md:112}.

## What it never does

- It never commits or pushes {src:commands/tg-save.md:109}.
- It never ends the session; it is a checkpoint only {src:commands/tg-save.md:110}.
- It never accumulates DRAFT entries; the DRAFT is a rolling snapshot, always replaced {src:commands/tg-save.md:111}.

## Notes

- The entry should let any AI pick the session up cold {src:commands/tg-save.md:113}.
- The command does not say what to do if `session-log.md` does not exist yet, so it relies on the model to create it.
- The 20-entry rule refers to the log's own entry count. The command does not say which heading pattern counts as an entry {src:commands/tg-save.md:74}.
- The ticket step is keyed to `/tg-ticket [KEY]` having been invoked and names the key `{JIRA-KEY}`, a Jira-style wording that matches the archive path only {src:commands/tg-save.md:80} {src:commands/tg-save.md:83}.

## Example

```
/tg-save switched to the retry design
```

It replaces today's DRAFT entry in `{landing}/session-log.md` with a fresh snapshot that includes your note, writes the ticket archive if a ticket is open, and prints a `SAVED` block {src:commands/tg-save.md:50} {src:commands/tg-save.md:59-61} {src:commands/tg-save.md:96-102}.
