# /tg-start: Session Starter

**Folders:** `{landing}`, `{tickets}`, `{education}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup. `{ticket}` means the folder of one ticket: look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>` (it prints the folder, flat or under its prefix folder). If it exits 1 with `not found`, that ticket has no folder: say so and stop, unless this command's own steps create the ticket folder.

**Role:** Launch every session. Load what today's work needs, nothing more.

**Voice standard:** `standards/voice-standard.md` governs every word this command produces.

The vault is always read first. A ticket tracker or chat tool is a connector that is off until first use; a connector with no setup prints `not set up` and this command carries on without it.

---

## Invocation

```
/tg-start              full load: vault health, blockers, yesterday
/tg-start learn        learning state + blockers only
/tg-start ticket {KEY} ticket work: vault context for one ticket
```

If the mode is unclear, ask one question: "What are we working on today: ticket, learning, or a general session?" Do not go on until the mode is confirmed.

---

## Step 1: Date and mode

```bash
date
```

Use the output as the session date. Ignore any date stub in the context. State the mode and what it will load.

PAUSE POINT: wait for confirmation before going further.

---

## Step 2: Vault health

```bash
$TOLLGATE_HOME/scripts/search/tg-search health --top 5
```

Show the dead link count and the top gaps. If dead links are more than 10, flag `SEARCH DEGRADED`: search will return thin coverage. Exit 1 means links are degraded or the index is stale: report it, do not stop. Exit 2 or the text `not set up` means no vault is configured: log the skip. Never fail /tg-start because of this step.

---

## Step 3: Blockers

Find state files that hold a time-sensitive fact:

```bash
find {tickets} -name "*-state.md" -exec grep -l "EPHEMERAL:time-sensitive" {} +
```

The tag is exact and case sensitive. For each file, confirm `EPHEMERAL:time-sensitive` and `STATUS: OPEN` or `STATUS: REOPENED` sit in the same fact block. Flag it as stale if it has been open more than 7 days (use the latest OPEN or REOPENED log date). Also flag any state file whose state is BLOCKED.

For each flagged ticket, run the state check and add its findings:

```bash
python3 $TOLLGATE_HOME/scripts/state/ticket_state_check.py {KEY}
```

Exit 0 means no problems. Exit 1 means at least one problem (the output lists it). Exit 2 means not set up or the ticket folder is missing: log the skip.

```
BLOCKERS
  [N stale time-sensitive facts: refresh them before ticket work]
  [BLOCKED tickets]
```

If nothing applies, say "Nothing urgent."

---

## Layer 2: Reference query

Runs only for medium or high stakes, before the agenda is shown.

- Low: routine session, no blockers, familiar ticket. Skip.
- Medium: several tickets changed, a blocker open, or back after 3 or more days.
- High: a major design decision pending or a critical escalation.

```bash
$TOLLGATE_HOME/scripts/search/tg-search reference --situation session_start --stakes {level} --skill start --query "{2 to 4 terms describing today's challenge}" --top 3
```

It searches the user's own reference store. Apply any passage returned. If it prints `not set up` or `no match`, say so in one line and go on.

---

## Mode loads

### learn

Load `{education}/learning-state.md`. Run the blockers step only.

```
LEARNING SESSION: [date]

LEARNING STATE
  Current focus: [topic]
  Next: [topic]
  Last covered: [topic] on [date]

BLOCKERS
  [if any]  or  Nothing urgent.

Ready. Run /tg-learn continue or /tg-learn {topic}.
```

### ticket {KEY}

Load `{ticket}/{KEY}-state.md`, the spec, the design, and the latest session file in that folder. Find the folder with the `{ticket}` lookup. Run the state check from the blockers step for this key.

```
TICKET SESSION: [date]

TICKET CONTEXT
  [state, last session notes, open questions]

What are we working on?
```

### blank (full)

Run the vault health and blockers steps and the YESTERDAY section. No ticket context unless asked.

---

## Present and save

### YESTERDAY

Read the session cost log, `session-costs.jsonl`, in the output folder. Keep entries whose `date` is yesterday. Work out the duration from the `start` and `end` fields (HH:MM). Show the `tasks` label and duration for each entry, then a total. If there are none, leave the section out without comment.

### Agenda

```
TODAY: [Day, YYYY-MM-DD]  [MODE]

CHECKLIST
  Date, mode, vault, blockers, saved. Skips: [list with reasons, or none]

BLOCKERS
  [from the blockers step]

[MODE SECTION: learning state or ticket context, if any]

YESTERDAY: YYYY-MM-DD
  [tasks label]   [duration]
  Total           [sum]

What are we working on?
```

### Save

1. Archive copy: `{date}.md` in the `_start` folder of the output folder. For browsing only, not indexed.
2. Vault landing note: `{landing}/YYYY/MM/YYYY-MM-DD-start.md`. Frontmatter uses these fields and no others:

```yaml
---
type: session_start
status: ACTIVE
tags: [session/start]
date: YYYY-MM-DD
---
```

   Write the real session date in `date`. Use wiki links such as `[[{KEY}]]` for ticket references.
3. Session cost, silent on success:

```bash
python3 $TOLLGATE_HOME/scripts/core/session_cost.py --mode start
```

Confirm in one line which files were saved.

---

## Rules

- Run `date` every session.
- Pause after the mode is confirmed. State what will load and wait.
- Skip unavailable pieces gracefully. Log every skip with a reason. Never fail /tg-start because one step is unavailable.
- Never write personal or protected data into the vault or the archive. If it appears, stop and flag it.
- Do not commit. Committing is a separate, explicit step.
