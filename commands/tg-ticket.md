# /tg-ticket - Ticket Orchestrator

**Folders:** `{vault}`, `{system_map}`, `{tickets}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup. `{ticket}` means the folder of one ticket: look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>` (it prints the folder, flat or under its prefix folder). If it exits 1 with `not found`, that ticket has no folder: say so and stop, unless this command's own steps create the ticket folder.

Author: {INITIALS}
Date:

**Role:** Orient on a ticket, surface the system context that belongs in its description, classify its type, and route it to the right skill chain. Makes every ticket readable to someone who arrives cold, through a context block in the description and a comment trail that tells the full story from start to completion.

**Vault:** `{vault}/`

---

## Trigger

```
/tg-ticket {KEY}
```

If no key is given, ask which ticket.

Vault first, always. The ticket tracker and the chat tool are reached only through connectors. A connector is off until first use, and a connector with no setup prints `not set up`. If a connector prints that, work from the vault and say which source is missing. Never post to the tracker or the chat tool.

---

## The chain and the gate

This command routes. It does not run the later steps itself. The chain commands are:

1. `/tg-spec {KEY}` writes the spec and ends with the spec file Status set to `APPROVED` and the state file Status set to `SPEC_APPROVED` (source: hooks/gate_rules.py).
2. `/tg-arch {KEY}` writes the design with Status `DESIGN_COMPLETE` while drafting, then `DESIGN_APPROVED` in both the design file and the state file after the owner's explain-back (source: hooks/gate_rules.py).
3. `/tg-dev {KEY}` moves the state to `IN_DEV`, then `DEV_COMPLETE` (source: hooks/gate_rules.py).
4. `/tg-qa {KEY}` writes the edge-case validation file with Status `DOCUMENTED` or `VALIDATED` (source: hooks/gate_rules.py).

Ordering is enforced by the gate (the hooks), not by this command. Never skip a step, never write a later step's status line to get past the gate, and never tell the owner to bypass it. If a chain command is blocked, route back to the missing earlier step and name it. Each chain command starts in a fresh thread; this command never auto-invokes the next one.

---

## Two layers, always in this order

**Layer 1 - Core steps.** Runs every invocation.

**Layer 2 - Stakes check.** Runs before orientation starts.

Stakes classification:
- Low: quick coordination with no system context gap, no routing decision needed
- Medium: routing decision required, or first touch on a ticket, or system context partially unknown
- High: sensitive personal data adjacent, cross-team impact, ticket is blocked, or bug with unclear root cause

For medium and high stakes, slow down: read more sources before forming any view, and name the next-most-likely reading of the ticket before committing to one.

---

## Step 1 - ORIENT

Gather everything before saying anything. No opinion before reading.

**1a - Vault first**
- `{ticket}/{KEY}-state.md` - if found and Status is SUPPORT_COMPLETE or higher, surface the handoff block and skip re-orienting; proceed to CLASSIFY with the existing chain context
- `{ticket of PARENT-KEY}/{PARENT-KEY}-state.md` - parent and siblings if applicable
- `{system_map}/clients/[CLIENT].md` - if client-specific
- `{system_map}/pipelines/` - if pipeline-related

**1b - Ticket tracker**
Only if the vault file is missing or a stub, and only through the tracker connector. Pull: title, description, acceptance criteria, all comments, status, priority, parent, subtasks, issue type.

**1c - Vector search**
```bash
$TOLLGATE_HOME/scripts/search/tg-search query "[ticket keywords]" --top 8 2>/dev/null
```
Read any result with score 0.5 or higher. If the script is missing or prints `not set up`, search the vault with grep instead and say so.

**1d - Sensitive data check**
Does this ticket touch regulated personal data, client records, or individual-level flows?
If yes: flag immediately, state the compliance implication, wait for acknowledgment before continuing. Stakes are now High.

**1e - Vault coverage check**
Count vector results with score 0.5 or higher. If fewer than 3:
```bash
$TOLLGATE_HOME/scripts/search/tg-search health --top 5 2>/dev/null
```
Include the result under VAULT COVERAGE in the output.

---

## Step 2 - CONTEXT BLOCK

Assemble the system context that belongs in this ticket's description. Pull from the vault, the tracker (if connected) and vector search. Leave blanks for anything not found and flag what is missing.

```
CLIENT CONTEXT
  Client:     [client name, or "N/A (internal)" for internal or system tickets]
  Catalog:    [data catalog name]
  Schema:     [schema name]
  Pipeline:   [job or pipeline name]
  Notebook:   [notebook path in the repo]
  Table(s):   [relevant table names]
  Git:        [branch name or file link if known]
```

If the ticket description already contains a context block, note that. No need to re-propose it. If all fields are blank and no system is involved, omit the block.

---

## Step 3 - ORIENT output

```
ORIENT - [KEY] - [title]

CONTEXT
  [What this ticket is in plain language: one sentence]
  [Why it exists: what problem or gap is being closed]

CLIENT CONTEXT  <- omit if empty or already in the ticket description
  Client:     [...]
  Catalog:    [...]
  Schema:     [...]
  Pipeline:   [...]
  Notebook:   [...]
  Table(s):   [...]
  Git:        [...]

VAULT COVERAGE  <- omit if N is 3 or more
  Vector hits 0.5 or higher: N  [LOW: vault context is thin for this area]

CONTRADICTIONS  <- emit before KNOWN; omit entirely if none
  [CONTRADICTION] State file says X. New data says Y. Which is current?

KNOWN (verified from vault / tracker / code)
  - [fact]  [source: file / tracker / code path]

UNKNOWN (gaps that cannot be answered from current sources)
  - [gap]

ASSUMING (proceeding on these unless corrected)
  - [assumption]

EPHEMERAL FLAGS  <- omit if none
  [UNVERIFIED: confirm before using in external comms]
  - [fact]  [EPHEMERAL:time-sensitive] open N days
```

**CONTRADICTIONS rules:**
High-confidence: emit `[CONTRADICTION]` and STOP. Do not proceed until the owner resolves it. After resolution, re-emit the full ORIENT and continue.
Low-confidence: emit `[INCONSISTENCY - low confidence]` inline in KNOWN without pausing.
Evidence priority: run log, then tracker comment, then chat message, then vault ASSUMING.

Show the ORIENT output. Stop if CONTRADICTIONS is non-empty.

---

## EXPLAIN-BACK GATE

After ORIENT, before classifying:

> "In two sentences: what is this ticket about, and what do you think needs to happen?"

Wait for the owner's answer. The owner's framing, not the ticket title, drives the classification.
If the two sentences surface something the ORIENT missed, update KNOWN before continuing.
If the owner's framing and the ORIENT conflict, surface the gap.

For research or gap assessment tickets: also ask which product definition applies before proceeding. A shared product name across clients does not mean the same definition applies. Confirm which definition, which version, and which product variant. Do not anchor any assessment until this is confirmed. A wrong product anchor invalidates the entire analysis.

This is the only pause point.

---

## Step 4 - CLASSIFY

Based on the owner's explain-back, the tracker issue type, title and description:

| Type | Signals | Chain |
|---|---|---|
| **Bug** | issue type Bug or Sub-task; "wrong", "null", "incorrect", "mismatch", "not populating", "excluded", "error", "fix" | `/tg-support` -> `/tg-spec` -> `/tg-arch` -> `/tg-dev` -> `/tg-qa` |
| **New Build** | issue type Story or Epic; "build", "create", "implement", "add capability" | `/tg-spec` -> `/tg-arch` -> `/tg-dev` -> `/tg-qa` |
| **Research** | "investigate", "understand", "scope", "explore", "assess", "analyze", "what is" | `/tg-explore` -> (confirm) -> `/tg-spec` -> ... |
| **Coordination** | "loop in", "unblock", "follow up", "contact", "coordinate", "waiting on" | Handle directly |
| **Communication** | "notify", "update client", "draft message", "inform" | Handle directly |
| **Documentation** | "document", "update vault", "write runbook", "capture" | Handle directly |

Before proposing the classification, name the next-most-likely type and say why it does not apply. A classification without a rejected alternative is not a decision.

```
CLASSIFICATION: [Type]
CHAIN: [skill1] -> [skill2] -> ...

[One sentence: why this classification fits]
[One sentence: why the next-most-likely type was rejected]
```

No additional wait. The explain-back gate was the confirmation moment.

---

## Step 5 - ROUTE

**Bug / New Build / Research:**
1. Write the ORIENT output to `{tickets}/PREFIX/{KEY}/{KEY}-state.md`, where PREFIX is the letters before the hyphen in the key, upper case (for example `S` for `PROJ-312`); create the folder if absent. Set `Status: ROUTED` and `Next skill: [first in chain]`. The `Status:` line must be the only one, the first in the file. For New Build tickets that arrive with a product-department spec attached, copy or reference the spec at `{ticket}/{KEY}-product-spec.md` and set `Source: product-spec` in the state file. For tickets without an upstream artifact, set `Source: direct`.
2. If the CLIENT CONTEXT block is missing from the ticket description, note: "Context block ready. Paste it into the ticket description when you open the ticket." Present the block for easy copy.
3. Draft the opening ticket comment (Chapter 1, see below) for the owner to post.
4. Stop and produce a starter prompt for the first skill in the chain (do not auto-invoke).

### Stop and hand off (next thread)

Do not auto-invoke the next skill. The output of this command (ORIENT block plus comment draft) is substantial. Chaining into `/tg-support` or `/tg-spec` in the same thread consumes the cache window with no benefit. Start the next skill in a fresh thread. The gate decides whether that skill may run.

End output:

```
Ticket routed: {KEY}
Status: ROUTED
Next skill: [first in chain]
Source: [support-handoff-pending / product-spec / whiteboard-verdict-pending / direct]

Chain step complete. Start a fresh thread for the next skill to keep context lean.

═══════════════════════════════════════════════════════════════
Next session starter prompt (copy into a new thread):
═══════════════════════════════════════════════════════════════

[First skill invocation] {KEY}

State file at {ticket}/{KEY}-state.md (Status: ROUTED).
[One to two sentences naming the first skill, what it produces, and what
to expect. Bug: /tg-support produces a handoff. New build:
/tg-spec produces AC and VS. Research: /tg-explore produces a scope
brief in the vault.]

═══════════════════════════════════════════════════════════════
```

**Coordination / Communication / Documentation:**
Handle directly in Step 6.

---

## Step 6 - DIRECT HANDLING

### Coordination
- Identify who needs to be looped in and why
- Flag cross-team impact explicitly before anything is drafted
- Draft the message in the internal chat format

### Communication
- Apply the voice standard and the /tg-draft recipe implicitly
- Draft a client message (client voice) or an internal message (team voice)
- Label which voice. Never auto-send.

### Documentation
- Write or update the relevant vault doc
- Link related entries with `[[wiki links]]`

---

## Ticket comment narrative standard

Comments accumulate over the life of a ticket to tell the full journey. Each chapter is standalone. A reader who arrives at Chapter 3 understands the arc without going back.

**Chapter 1 - Opening** (post when the ticket starts)
```
[What this ticket is: one sentence]
[Starting point: what we know and don't know right now]
[First action: who owns what next]
```

**Chapter 2 - Progress** (post as work advances, one per meaningful update)
```
[Status: blocked / in progress / waiting on X]
[What was found or decided, and why]
[What's next and who owns it]
```

**Chapter 3 - Resolution** (post when done)
```
[What was done and confirmed working]
[Root cause for bugs, or delivery summary for builds]
[What to watch: what could still surface later]
```

Apply the voice standard to every comment. Active voice, no filler, no stock phrases that point back to an earlier chat. Ticket comments are technical, precise, first-person. The owner reviews and posts.

---

## Step 7 - DOCUMENT

Create `{ticket}/{KEY}-session-YYYY-MM-DD.md`:

```markdown
## YYYY-MM-DD - [brief title]
Author: {INITIALS}
Done: [what was completed]
Decided: [key decisions and WHY]
Pending: [what's next, specific enough to start cold]
Notes: [anything worth remembering]

### Related
- [[01-system-map/clients/client-name]]
- [[01-system-map/pipelines/pipeline-name]]
```

Update `{ticket}/{KEY}-state.md` with the current status.

---

## Rules

- Gather everything before saying anything. No opinion before reading.
- Vault first. A connector is used only when the vault has nothing, and `not set up` is reported, not worked around.
- The CLIENT CONTEXT block surfaces every time. Flag missing fields, do not invent them.
- The explain-back gate is the only pause point. The owner's framing drives classification.
- Every classification names the rejected alternative.
- Never skip a chain step and never bypass the gate. Route back to the missing step instead.
- Ticket comment drafts follow the three-chapter model.
- Code under `$TOLLGATE_CODE_DIR` is read-only. Never modify it.
- Never post to the ticket tracker, never send a chat message. The owner does all external actions.
- Sensitive personal data never enters the vault, memory, or commit messages.
