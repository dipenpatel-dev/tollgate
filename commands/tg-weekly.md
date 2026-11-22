# /tg-weekly - Last Week Summary

**Folders:** `{vault}`, `{tickets}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup. `{ticket}` means the folder of one ticket: look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>` (it prints the folder, flat or under its prefix folder). If it exits 1 with `not found`, that ticket has no folder: say so and stop, unless this command's own steps create the ticket folder.

**Role:** Surface what moved last Mon–Fri across all clients (or one client). Three output layers: signal list, product translation, pushback prep. Book-backed narrative.

**Vault:** `{vault}/`

---

## Trigger
`/tg-weekly [CLIENT?]`

- No argument: all clients, grouped by client
- With client name (e.g. `/tg-weekly [CLIENT]`): filtered to that client only
- Time window: always last Mon–Fri calculated from today. If today is Monday, use the prior week - not the week that just started.

---

## Step 0 - Announce the plan

State:
- Which clients will be covered (or which client if filtered)
- The calculated time window (Mon DD – Fri DD)
- What sources will be read
- What the output will contain

Wait for confirmation before reading.

---

## Step 1 - Calculate time window

Run `date` to confirm today's date.
Calculate last Mon–Fri from today's actual date - do not rely on session context.
State the window explicitly before proceeding: "Window: Mon May 12 – Fri May 16."

---

## Step 2 - Read all signals

**Jira** - tickets with activity in the window:
- Status transitions (moved to In Progress, Done, Blocked)
- Comments or updates posted in the window
- Drop: tickets with no activity in the window

**Vault** - `{tickets}/*/` and `{tickets}/*/*/` state files and session logs:
- Session log files dated within the window
- KNOWN blocks that reference activity in the window
- Richer "what actually happened" detail that Jira does not capture

**Slack** - client channels, last 7 days:
- Unresolved threads containing a question, concern, or decision
- Drop: acknowledgment-only threads, resolved chatter

**Calendar** - meetings in the window:
- Client calls that occurred - note if outcomes were captured in vault
- Drop: events with no work outcome

---

## Step 3 - Synthesize: signal vs noise

Filter the raw reading into a signal list:

- **Changed:** tickets closed, decisions made, blockers resolved, fixes deployed
- **Stuck:** tickets with no movement where movement was expected
- **Coming:** immediate next actions required this week

State what was dropped and why in one line before presenting the signal list. If nothing was dropped, say so. This transparency lets {NAME} correct the filter before the narrative layers are built.

---

## Step 4 - Explain-back gate

Present the signal list only. Do not produce translation or pushback layers yet.

> "Does this signal list match what you remember from last week? Anything missing or incorrectly included?"

Wait for confirmation or correction before continuing to Step 5.

---

Apply these principles to build the translation and pushback layers:
- Conclusion first: the outcome leads, not the mechanism
- Concrete specifics, never "some records had issues": always "4 of 7 sub-tickets closed, 3 remain"
- Answer the question the reader is most likely to have, plainly and accurately
- Say what the update means for the reader, not only what happened to the system

---

## Step 6 - Produce output

Group by client. For each client:

```
── [CLIENT] ─────────────────────────────────────────

Signal
  [TICKET-ID]  [ticket name]          [STATUS] - [one-line context]

Say it as
  [TICKET-ID]  [one sentence - outcome for the client, no jargon, no mechanism]

Prepare for
  "[Likely question from product or non-technical stakeholder]"
    [Answer in client voice. Conclusion first. Concrete. No internal tooling names.]
```

Rules:
- Signal: only items that changed in the window. No unchanged backlog items.
- Say it as: what this means for the client's data or delivery - not what happened in the pipeline.
- Prepare for: one to three questions per client, surfaced before they are raised. If no sticky area exists for a client, omit the section.
- If a client had zero movement in the window, say "No movement last week" explicitly - do not skip the client silently.

---

## Step 7 - After review

> "After the call, run `/tg-close` to log outcomes, decisions, and action items from the discussion."
