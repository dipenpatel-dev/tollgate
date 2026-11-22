---
name: tg-sync
description: 10-minute ephemeral fact hygiene session. Reads all active ticket state files, surfaces open blockers and pending decisions, asks one verification question per fact, updates state files from answers.
argument-hint: ""
---

# /tg-sync - Ephemeral Fact Hygiene

**Folders:** `{tickets}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup. `{ticket}` means the folder of one ticket: look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>` (it prints the folder, flat or under its prefix folder). If it exits 1 with `not found`, that ticket has no folder: say so and stop, unless this command's own steps create the ticket folder.

**Role:** Verify open ephemeral facts across all active tickets before they go stale.
Scoped to state files only - no vector search, no Jira, no Slack, no vault rebuild.



---

## When to run

- Prompted by `/tg-start` Step 4b when stale time-sensitive facts detected
- Any session that has been more than 2 days since the last ticket session on an active ticket
- Anytime {NAME} wants a quick verification pass

---

## Step 1 - Read all active state files

Read every file matching `{tickets}/*/*-state.md` or `{tickets}/*/*/*-state.md`. For each file, locate the
top-level handoff status line near the top of the file. This line appears as either
`Status:` or `**Status:**` (both forms are valid). Treat any value whose first token is
`CLOSED` as closed - including annotated forms like `**Status:** CLOSED (pending {NAME}
posting comment)`. Exclude those files.

Note: per-fact `STATUS:` lines (uppercase) inside the body of the file describe individual
ephemeral fact states - do NOT use these for ticket-level selection.

List the active tickets found: KEY, title if available, last known status.

---

## Step 2 - Extract open ephemeral facts

For each active state file, find all fact blocks tagged `[EPHEMERAL:time-sensitive]` or
`[EPHEMERAL:client-dependent]` where STATUS is `OPEN` or `REOPENED`.

**PHI gate (mandatory before proceeding):** If any fact text appears to contain patient
identifiers, MRNs, DOBs, raw clinical data, or copied system output - stop, flag the
specific entry, and skip it from the batch. Do not display PHI in any output.

**Step 2b - Sort and cap:**
Sort extracted facts: `time-sensitive` first, then `client-dependent`; within each type
sort by oldest LOG transition date first (most overdue at top).

Cap at 15 interactive questions per run. If more than 15 open facts exist, process the
top 15 and note: "N additional facts deferred - run /tg-sync again to continue."

---

## Step 3 - Present and ask

Show the full numbered list of facts at once before asking for any answers. For each fact:

```
[N] [TICKET KEY] - [fact description]
    Type: time-sensitive | client-dependent
    Open since: YYYY-MM-DD ([X days])
    Last log: [most recent LOG entry]
    Question: [one direct verification question]
```

Example questions:
- "[CLIENT] permission issue was blocking as of Apr 29. Is this still blocking, or resolved?"
- "PR#67 was open as of Apr 29. Still open, merged, or closed?"
- "Architecture review was pending from [name]. Has it been completed?"

Wait for all answers before updating any file.

---

## Step 4 - Update state files

For each verified fact, immediately before writing: reread the target state file to
capture any edits made since Step 1. Update only the specific fact block that was
verified. Preserve all other content unchanged.

If a fact block changed since Step 2 (different STATUS or new LOG entry): skip it,
report it as "requires manual review - state changed during /tg-sync."

**Status log updates:**
- Resolved: add `| CLOSED YYYY-MM-DD` to LOG, set `STATUS: CLOSED`
- Still open: add `| VERIFIED YYYY-MM-DD` to LOG, STATUS unchanged
- Reopened after closed: add `| REOPENED YYYY-MM-DD` to LOG, set `STATUS: REOPENED`
- New blocker identified: add as new ephemeral fact block in the state file

**Ticket close rule:** If {NAME} confirms a ticket is closed during /tg-sync, close all
associated ephemeral facts regardless of their individual STATUS.

---

## Step 5 - Summary

One paragraph: how many facts verified, how many resolved, how many still open, any
facts skipped (PHI flag or changed state), deferred count if cap was hit.

```
/tg-sync complete - [date]
Verified: N facts across M tickets
Resolved: N | Still open: N | Skipped: N | Deferred: N
[One sentence on anything notable]
```
