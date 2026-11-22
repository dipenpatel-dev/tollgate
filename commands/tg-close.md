# /tg-close - Session Closer

**Folders:** `{vault}`, `{landing}`, `{system_map}`, `{tickets}`, `{knowledge}`, `{conversations}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup. `{ticket}` means the folder of one ticket: look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>` (it prints the folder, flat or under its prefix folder). If it exits 1 with `not found`, that ticket has no folder: say so and stop, unless this command's own steps create the ticket folder.

**Role:** Capture what happened, compound knowledge, update the system, close the loop.
Run at the end of every work block - even short ones.

**Vault:** `{vault}/`
**Dotfiles:** `$CLAUDE_DOTFILES/`

---

## Trigger
`/tg-close` or `/tg-close [JIRA-ID]`

---

## Closing Checklist

Seven items. Each binary. The pause point is the only moment that requires input.

```
CLOSE CHECKLIST
  [ ] Review    - session review; "what could still go wrong?" if ticket work done
  [ ] Log       - session log entry drafted + cost tracked
  [ ] Vault     - vault entries drafted (signal only)
  [ ] Memory    - corrections + validations drafted → memory files
  [ ] Health    - dead link delta + vault health check
  ─── PAUSE - review session log entry; confirm or adjust ───────────────────────
  [ ] Dotfiles  - baseline check; print the commit text if changed
  [ ] Commit    - write all vault files + security scan; print the commit text for the user
```

Items 1–5 run without waiting for input. The pause is the only moment you respond.
Items 6–7 run automatically after confirmation.

---

## Step 1 - Review (Item 1)

Look back at what happened this session:
- What was done or changed?
- What decisions were made and why?
- What was explicitly deferred, and why?
- What is still in progress or pending?
- Any corrections you made to your approach?
- Any non-obvious choices you confirmed without pushback?

**If ticket work was completed this session**, ask one question before moving on:
> "What could still go wrong in what we built?"

Wait for the answer. Capture it in the session notes under a "Risks and Unknowns"
section. Not to fix things now - to know. Five minutes of honest answer prevents
a week of surprise.

---

## Step 2 - Session Log (Item 2)

**Get actual date/time:**
```bash
date
```

**Run cost tracker:**
```bash
python3 $TOLLGATE_HOME/scripts/core/session_cost.py \
  --mode=close --tasks "[one-line tasks summary]"
```

Capture stdout. `session_cost.py` ships with Tollgate at `$TOLLGATE_HOME/scripts/core/session_cost.py`.
If the file is absent, write `Cost: not tracked (session_cost.py not installed)`. If it exits
non-zero, write `Cost: not tracked (pricing constants not set)`. Continue either way.

**Draft the session log entry** for `{landing}/session-log.md`. Do not write yet.

Check for an existing DRAFT entry for today:
- Found: replace it entirely (remove `[DRAFT]` marker)
- Not found: draft a new entry to prepend at the top

Entry format:
```markdown
## YYYY-MM-DD HH:MM TZ - [brief title]
Done: [what was completed - be specific]
Decided: [key decisions and WHY]
Pending: [what's next - specific enough to pick up cold]
Notes: [anything worth remembering]
Cost: [stdout from session_cost.py]
```

Keep the file to **20 entries maximum**. Remove the oldest if adding would exceed 20.

---

## Step 3 - Vault Entries (Item 3)

Draft all vault files. Do not write yet.

**Session notes** → `{ticket}/{KEY}-session-YYYY-MM-DD.md` (if ticket work
was done). If that filename already exists today, create `{KEY}-session-YYYY-MM-DD-2.md`.

```markdown
## YYYY-MM-DD - [brief title]
Done: [what was completed]
Decided: [key decisions - include WHY]
Not done: [what was explicitly deferred and why]
Pending: [what's next]
Notes: [anything worth remembering]

### Risks and Unknowns
[Answer from "what could still go wrong?" - omit section if no ticket work done]

### Related
- `{ticket}/{KEY}-spec.md`
- [[01-system-map/clients/client-name]]
```

**Promotion gate:** Did this session produce a finding a future session should know?
If yes: promote to `{system_map}/` or `{knowledge}/patterns/` - not the session
file. Session files are archival.

**State file:** Update `{ticket}/{KEY}-state.md` with current handoff block.

**Ephemeral lifecycle check:** Did any ephemeral fact change state? Update its log in
the state file. Ticket closing? Close all associated ephemeral facts.

**Decision** (only if real architectural or design decision):
`{knowledge}/decisions/YYYY-MM-DD-[topic].md`

**Learning** (only if unexpected finding, real failure root cause, or genuine insight):
`{knowledge}/learnings/YYYY-MM-DD-[topic].md`

**Pattern** (only if a reusable solution that will recur):
`{knowledge}/patterns/YYYY-MM-DD-[topic].md`

**Conversation file** (always - every session):
`{conversations}/YYYY/MM-Month/YYYY-MM-DD-NN-topic.md`

> `{conversations}/` is gitignored. Never stage or commit these files.

- `NN` = session number for the day - check existing files to determine next number
- `topic` = 2–4 word slug; create folder if missing

```markdown
# YYYY-MM-DD - Topic Title

**Ticket / context:** CD-XXX or "no ticket"
**Session number:** NN of that day

---

D: [{NAME}'s message - verbatim or closely paraphrased]

C: [Claude's response - distilled to the key point or decision]

---

## Notable corrections this session

[Corrections {NAME} made, what was wrong, what changed. Most valuable entries.]

## Related

- [[02-tickets/...]]
```

Capture every meaningful exchange. Prioritize corrections, key decisions, architectural
insights, things that required iteration. Skip routine tool execution.

**Rule:** Only draft entries for genuine signal. Routine implementation does not warrant
a decision or learning entry.

---

## Step 4 - Memory (Item 4)

Scan the session for corrections and validations.

**Corrections** - any moment {NAME} redirected or pushed back:
- WHAT was corrected, WHY, HOW to apply going forward

**Validations** - any non-obvious choice {NAME} confirmed without pushback:
- WHAT the choice was, WHY it was non-obvious, that it should be repeated

Draft each as a memory file for
`~/.claude/projects/[your-project-hash]/memory/`:

```
---
name: [short-kebab-slug]
description: [one-line hook - used for retrieval]
metadata:
  type: feedback
---

[Rule: the guidance itself]

**Why:** [the reason {NAME} gave or implied]
**How to apply:** [when this kicks in]
```

Also draft a pointer line for `MEMORY.md`. Do not write yet.

---

## Step 5 - Health (Item 5)

Check that `{vault}` is accessible and the vault state at session open was clean. No script required. Template placeholder links (`[[wiki links]]`, `[[filename]]`) can be ignored.

---

## PAUSE POINT

Present the session log entry. You read it and confirms or adjusts. Nothing has
been written to disk yet.

```
CLOSE - YYYY-MM-DD HH:MM TZ

Does this accurately capture the session?

## YYYY-MM-DD HH:MM TZ - [title]
Done: ...
Decided: ...
Pending: ...
Cost: ...

[Flag any new dead links from Health check here]
```

After confirmation: proceed through items 6–7 without further input.

---

## Step 6 - Dotfiles (Item 6)

Does anything from this session represent a new baseline for Tollgate?

Examples:
- A QA pattern that caught a real class of bugs → `commands/tg-qa.md`
- A new guardrail or conduct rule → `CLAUDE.md`
- A Databricks/Unity Catalog pattern → `commands/tg-dev.md`
- A skill step that was missing or wrong → the relevant skill file

If yes - make the edit, then check what changed (read only):
```bash
git -C $CLAUDE_DOTFILES status
```

Do not commit or push. Print the commit text for the user to run:
```
git -C $CLAUDE_DOTFILES add -A
git -C $CLAUDE_DOTFILES commit -m "chore(skills): [what changed and why]"
```

**This runs every /tg-close without exception.** Even if nothing changed, run `status`
to confirm the working tree is clean.

---

## Step 7 - Commit (Item 7)

Write all staged vault files to disk now. Keep the list of every vault file written or changed this run.

**Security scan (automated, stops if PHI found):** scan the files on that list, not the vault history:
```bash
grep -iE "(xoxb|secret_|password|_API_TOKEN|MRN|SSN|patient)" <each file written this run> 2>/dev/null
```

If anything flags: stop. Remove it and scan again. Do not print the commit text until clean.

**Vault git:** Look up the mode with `$TOLLGATE_HOME/scripts/core/tg_vault_git`.
- `none`: skip git and list the files written.
- `local`: print the add and commit lines.
- `remote`: print the add, commit and push lines.

Never run them. Print them for the user to run:

```text
git -C {vault} add <the paths written this run>
git -C {vault} commit -m "session: YYYY-MM-DD [brief description]"
git -C {vault} push    (remote only)
```

If nothing was written to the vault, skip and say so.

---

## Confirm

```
Session closed.

Checklist:     Review ✓ | Log ✓ | Vault ✓ | Memory ✓ | Health ✓ | Dotfiles ✓ | Commit ✓

Session log:   {landing}/session-log.md updated
Vault entries: [list of files written, or "none"]
Memory:        [list of memory files written, or "none"]
Dotfiles:      [commit text printed / nothing to commit]
Vault commit:  [none: files listed / local or remote: commit text printed / nothing written]

Next session:
  [what to pick up - specific enough to start cold]
```

### Next-session starter prompt

**Mandatory after every /tg-close - no exceptions.** The starter prompt is load-bearing for session continuity. Without it, the next thread begins cold, loses context, and the work drifts off track. Always produce a copy-pasteable starter prompt so the next thread begins with context, not from scratch. Pattern:

```
═══════════════════════════════════════════════════════════════
Next session starter prompt (copy into a new thread):
═══════════════════════════════════════════════════════════════

[Skill invocation, e.g. /tg-arch [TICKET-ID] or /tg-start]

[Two to four sentences of context - what artifact to read, what the
state is, what the next gate or deliverable is. Specific enough that
the next thread does not need to recover state from the vault before
starting work.]

═══════════════════════════════════════════════════════════════
```

**Examples:**

After a /tg-spec session that produced an approved spec:
```
/tg-arch [TICKET-ID]

Spec is at {ticket}/[TICKET-ID]-spec.md (Status: APPROVED). /tg-arch
reads the spec + four standards docs at $CLAUDE_DOTFILES/ and produces
the design. Gate 2 (explain-back after design) is the chain-level pause.
```

After a /tg-support session that confirmed Tier 2 routing:
```
/tg-spec [TICKET-ID]

Support handoff at {ticket}/[TICKET-ID]-support-handoff.md
(SUPPORT_COMPLETE). Root cause: [one line]. /tg-spec produces AC + VS.
Four gates: RESTATE / REQUIREMENTS+AC / VS / explain-back.
```

After a session with no specific next chain step (fallback - still produce a starter prompt):
```
/tg-start

Last session pending: [from session log Pending field].
Open tickets to consider: [list from /tg-status].
```

The fallback `/tg-start` block is the floor - even when the chain has no obvious next step, the starter prompt block lands. Never end /tg-close without it. The habit of close-then-restart-with-context is what prevents drift across sessions.

---

## Rules
- Items 1–5 run without waiting for input
- The pause point is the only moment {NAME} provides input
- Items 6–7 run automatically after pause confirmation
- Only create vault entries for genuine signal
- PHI never enters vault, memory files, session log, or commit messages
- Never skip the dotfiles check - a clean tree is a confirmed state
- All git commands use `-C /full/path` - never `cd` + git
- Step 7 always ends with a next-session starter prompt - no exceptions; the close-then-restart-with-context habit prevents drift
