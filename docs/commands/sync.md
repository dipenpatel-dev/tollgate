# /tg-sync

**It checks open, time-sensitive facts in your active ticket state files, asks you one question per fact, and updates only the facts you verify.** Use it before facts go stale. It is scoped to state files only: no vector search, no Jira, no Slack, no vault rebuild {src:commands/tg-sync.md:7} {src:commands/tg-sync.md:11-12}.

The command name is fixed: `/tg-sync`, with no argument {src:commands/tg-sync.md:2} {src:commands/tg-sync.md:4}. Its frontmatter calls it a 10-minute session {src:commands/tg-sync.md:3}.

## When to use it

The command lists three triggers: `/tg-start` prompting it when stale time-sensitive facts are found, more than 2 days since the last session on an active ticket, or any time you want a quick verification pass {src:commands/tg-sync.md:20-22}. See Notes: the `/tg-start` prompt is not found in the `/tg-start` command file.

## What it does

1. Reads every active ticket state file. For each it finds the top-level `Status:` or `**Status:**` line near the top. Any value whose first token is `CLOSED` (including annotated forms) marks the ticket closed and it is excluded. Per-fact `STATUS:` lines in the body are not used for this choice {src:commands/tg-sync.md:28-35}. It then lists the active tickets with key, title and last known status {src:commands/tg-sync.md:37}.
2. Extracts open facts: fact blocks tagged `[EPHEMERAL:time-sensitive]` or `[EPHEMERAL:client-dependent]` whose STATUS is `OPEN` or `REOPENED` {src:commands/tg-sync.md:43-44}.
3. PHI gate before going on: if a fact looks like it holds patient identifiers, MRNs, DOBs, raw clinical data or copied system output, it stops, flags that entry, skips it and shows no PHI {src:commands/tg-sync.md:46-48}.
4. Sorts time-sensitive before client-dependent, oldest log date first within each type, and caps the run at 15 questions. Extra facts are deferred with a "run /tg-sync again" note {src:commands/tg-sync.md:51-55}.
5. Shows the full numbered list first (key, description, type, open-since date, last log line, one question) and waits for all answers before changing any file {src:commands/tg-sync.md:61-76}.
6. For each verified fact, rereads the state file just before writing, changes only that fact block, and keeps everything else. If the block changed since step 2, it skips it and reports "requires manual review" {src:commands/tg-sync.md:82-87}.
7. Prints a short summary: verified, resolved, still open, skipped, deferred {src:commands/tg-sync.md:100-110}.

Log updates it makes: resolved adds `| CLOSED YYYY-MM-DD` and sets `STATUS: CLOSED`; still open adds `| VERIFIED YYYY-MM-DD`; reopened adds `| REOPENED YYYY-MM-DD` and sets `STATUS: REOPENED`; a new blocker is added as a new fact block {src:commands/tg-sync.md:90-93}. If you confirm a whole ticket is closed, all its facts are closed whatever their own STATUS {src:commands/tg-sync.md:95-96}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{tickets}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-sync.md:9}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-sync.md:9}. The name `tickets` exists in the path loader {src:scripts/core/paths.py:35}.

- Reads: ticket state files, found by scanning both folder levels, `{tickets}/*/*-state.md` and `{tickets}/*/*/*-state.md` {src:commands/tg-sync.md:28}.
- Writes: those same state files, one fact block at a time {src:commands/tg-sync.md:82-84}. It writes no new files, no landing note and no archive.
- Scripts: only `$TOLLGATE_HOME/scripts/core/tg_path`, which exists {src:commands/tg-sync.md:9}. It calls no search, no state-check script and no cost script.
- Vault git: the command has no commit step, so it commits nothing. For the vault git modes see [tg_vault_git](../scripts/core/tg_vault_git.md).

## Hooks and gate lines

It touches no ticket gate line. It edits the per-fact `STATUS:` lines inside the body, which are separate from the ticket-level `Status:` line {src:commands/tg-sync.md:34-35}. It names no hook.

## Stops

- PHI in a fact: flag and skip that entry {src:commands/tg-sync.md:46-48}.
- It waits for all your answers before any write {src:commands/tg-sync.md:76}.
- A fact whose block changed during the run is skipped for manual review {src:commands/tg-sync.md:86-87}.

## Notes

- How it finds ticket folders. The command reads every file matching `{tickets}/*/*-state.md` or `{tickets}/*/*/*-state.md` {src:commands/tg-sync.md:28}. That covers a flat vault (`02-tickets/KEY/`) and a nested one (`02-tickets/PREFIX/KEY/`, for example `02-tickets/PROJ/PROJ-312/PROJ-312-state.md`).
- The frontmatter description says it "surfaces open blockers and pending decisions". The body only extracts facts tagged `[EPHEMERAL:time-sensitive]` or `[EPHEMERAL:client-dependent]` with STATUS `OPEN` or `REOPENED`; it has no step for untagged blockers or decisions {src:commands/tg-sync.md:3} {src:commands/tg-sync.md:43-44}.
- The `/tg-start` "Step 4b" prompt named in the command was not found: the `/tg-start` command file has no text "4b" and no mention of `/tg-sync` (searched `commands/tg-start.md`) {src:commands/tg-sync.md:20}.
- The command text still contains the unfilled placeholder `{NAME}` (the user's name) in four places {src:commands/tg-sync.md:22} {src:commands/tg-sync.md:31-32} {src:commands/tg-sync.md:71} {src:commands/tg-sync.md:95}. The "Folders" line also says `{tickets}` "name vault folders" in plural though only one folder is used {src:commands/tg-sync.md:9}.

## What it never does

- It never uses vector search, Jira, Slack or a vault rebuild {src:commands/tg-sync.md:12}.
- It never displays PHI {src:commands/tg-sync.md:47-48}.
- It never changes anything outside the fact block you verified {src:commands/tg-sync.md:83-84}.

## Example

```
/tg-sync
```

It lists the open facts across active tickets, for example "PR#67 was open as of Apr 29. Still open, merged, or closed?", waits for your answers, then adds `| VERIFIED` or `| CLOSED` to each fact's log {src:commands/tg-sync.md:61-76} {src:commands/tg-sync.md:71-74} {src:commands/tg-sync.md:90-92}.
