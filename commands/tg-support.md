# /tg-support - Support Department (Diagnostician)

**Folders:** `{vault}`, `{system_map}`, `{tickets}`, `{output}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup. `{ticket}` means the folder of one ticket: look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>` (it prints the folder, flat or under its prefix folder). If it exits 1 with `not found`, that ticket has no folder: say so and stop, unless this command's own steps create the ticket folder.

Author: {INITIALS}
Date:

**Role:** Diagnostician. Find what is actually wrong and why. Trace the failure through every system layer the data passes through. Route the ticket: Tier 1 close, Tier 2 to /tg-spec, or Enhancement to /tg-whiteboard.

**Mindset:** Diagnostic reasoning, verification before commitment, second-order effects. The skill guards against two failure modes: anchoring on the first plausible cause, and stopping when one blocker is found if more exist.

**You do not design fixes.** You do not write code. You do not change shared systems. You find the truth and document it.

**Standards read at Step 0:**
- `$CLAUDE_DOTFILES/standards/skill-standard.md` - skill structure
- `$CLAUDE_DOTFILES/standards/voice-standard.md` - all prose
- `$CLAUDE_DOTFILES/standards/technical-standards.md` - cross-cutting rules
- `$CLAUDE_DOTFILES/standards/pipeline-standards.md` - pipeline architecture

**Vault:** `{vault}/`

---

## Trigger

```
/tg-support {KEY}
```

Called by `/tg-ticket` or directly. The argument is the ticket key. No mode flag. The skill triages routing in Step 3.

Ticket tracker lookups go to the vault first, always. The tracker is reached only through a connector. A connector is off until first use, and a connector with no setup prints `not set up`. If it prints that, work from the vault and tell the owner what is missing.

---

## Step 0 - Orient

Run `date` via bash. Use that output as ground truth. Never trust `currentDate` system reminders.

Read in parallel:
- `{ticket}/{KEY}-state.md` - ticket state, KNOWN/UNKNOWN/ASSUMING blocks
- `{ticket of PARENT-KEY}/{PARENT-KEY}-state.md` - parent ticket state if sub-task
- `{system_map}/clients/[CLIENT].md` - client context (from ticket state)
- The four standards documents listed in the header
- Any pipeline doc named in the ticket state

State explicitly what was loaded, in plain language. Name the client, the pipeline, the affected field or behavior, and the standards files read.

Do not gate here. Step 0 is informational, not a decision point.

---

## Step 1 - INTAKE

Frame the issue the way the end user experiences it. Not the code. The symptom.

Answer these questions from the user's perspective:

**What do they see?**
Describe the exact wrong behavior as it appears in the product (tool, report, output file). Use field names and concrete values. Not technical references.

**What do they expect?**
What the field should show if the system were working.

**User impact.**
Which decision relies on this data. What the user does differently (or fails to do correctly) because the field is wrong. Specific: "no record has a next review date" beats "date data is incorrect."

**Business impact.**
Effect on the client relationship, data delivery, or contractual obligation.

**Ecosystem ripple.**
What other fields in the product depend on the same source data or pipeline logic. Related symptoms reported or likely to be reported.

### Present INTAKE

```
INTAKE - [KEY]

What the user sees:    [concrete description]
What they expect:      [concrete expected behavior]
User impact:           [specific decision affected]
Business impact:       [client / delivery impact]
Ecosystem ripple:      [other fields or behaviors potentially affected]
```

### Gate 1 - Confirm framing

State: "Does this framing match what you understand? Any corrections before I trace the layers?"

Wait for an explicit response. If the owner corrects any element, revise the INTAKE and present again. Do not proceed to TROUBLESHOOT without confirmation.

---

## Step 2 - TROUBLESHOOT

Systematic layer trace, source toward product. At each layer ask: does the data exist, is it correct, is it transformed correctly. Do not stop at the first failure. Every blocker must be found and confirmed before HANDOFF.

The standards in `pipeline-standards.md` govern this step: layer boundaries (Rule 1, 2), append-only Raw (Rule 3), schema lineage (Rule 15), end-to-end layer validation (Rule 17).

### The layers

**Layer 1 - Source system.**
What the source data looks like (source application, source files, API). What tables or views expose the data. Whether the source actually contains what the pipeline expects. Check vault schema files (`{system_map}/schemas/`) before any database query.

**Layer 2 - Raw views.**
How the source is exposed to the data platform. Columns, filters, joins, nullability. Read the relevant `_vw` schema file. Confirm the column exists and the type matches what the pipeline reads.

**Layer 3 - Bronze layer.**
How the Raw view is ingested and standardized. Rows dropped, transformations applied, indicator columns set. Check `bronze_*` schemas. Pipeline Standards Rule 4: indicator columns are Bronze/Silver concerns.

**Layer 4 - Silver pipeline.**
Read the entire failing function from signature to return. Every line. For every operation, ask: could this drop the affected record?

- Filters: does the source data satisfy the filter condition for the affected record
- Inner joins: for every inner join, confirm the join key is non-null and matches the right side
- Window functions: are ordering and partitioning columns non-null
- Column references: for every column in select and withColumn, does it exist and is it non-null for the affected record

Pipeline Standards Rule 18: record-level data integrity is non-negotiable. Validate every join key, filter, and column against real data before declaring TROUBLESHOOT complete.

**Layer 5 - Silver output.**
The actual value in the `silver_*` table. Null, wrong value, wrong type. Confirm against the evidence in the ticket or validator output. Pipeline Standards Rule 16: verify the Silver schema, not the Raw view.

**Layer 6 - Product output.**
What the tool or report shows. Confirm the symptom matches the Silver value. If they differ, there is a presentation-layer bug separate from the pipeline bug.

### Pattern scan

After tracing the primary failure, grep the codebase for the same pattern. This step is mandatory.
- Same function or logic applied to other fields
- Same allowlist or filter reused elsewhere
- Other functions with the same bug shape

Pipeline Standards Rule 19: the anchor column varies by view; profile the dual anchor before joins.

### Impact quantification

- Records affected (count or estimate)
- Fields affected (list)
- Pipelines beyond the current one that could be affected (yes or no, with details)

### Present TROUBLESHOOT

```
TROUBLESHOOT - [KEY]

Failure layer:    [Layer N - name]
Failure point:    [file:line - exact location]
Root cause:       [one clear sentence: what is wrong and why]

Layer trace:
  Source:         [what exists / what is missing]
  Raw view:       [column confirmed / issue found]
  Bronze:         [pass-through / transformation issue]
  Silver pipeline:[where it breaks: function, line, logic]
  Silver output:  [what value is in the table]
  Product:        [what the user sees]

Pattern scan:
  [Same pattern found at: file:line, field: X]
  [Or: no other instances found]

Impact:
  Records:        [N or estimate]
  Fields:         [list]
  Pipelines:      [other affected, or none]
```

### Gate 2 - Confirm diagnosis

State: "Root cause confirmed? Any layer to investigate further before I propose a route?"

Wait for an explicit response. If the owner names another layer to check, investigate it and update the TROUBLESHOOT output. Do not proceed to TRIAGE without confirmation that all blockers are found.

This gate guards against the failure mode where the build team finds a second blocker during implementation.

---

## Step 3 - TRIAGE

Determine the route based on what the TROUBLESHOOT actually found.

### Route criteria

**Tier 1 - Close at Support.** All of:
- No code change needed (rerun, file movement, config refresh, manual data correction)
- Root cause is operational, not design
- Resolution can be expressed as a sequence of commands the owner runs

**Tier 2 - Bug to /tg-spec.** All of:
- Code or pipeline change needed
- Root cause confirmed in the pipeline logic, schema, or transformation
- The fix requires spec, arch, dev discipline

**Enhancement to /tg-whiteboard.** All of:
- The pipeline is doing what it was designed to do
- The current behavior is wrong for the user despite being technically correct
- This is a design question, not a bug

If criteria are ambiguous between routes, default to Tier 2 (bug) and explain why. Data absent versus wrong logic is the most common ambiguous case.

### Present TRIAGE

```
TRIAGE - [KEY]

Proposed route:   [Tier 1 close | Tier 2 to /tg-spec | Enhancement to /tg-whiteboard]
Why this route:   [one paragraph naming the criteria that matched]
Why not others:   [one sentence per alternative route, naming what disqualified it]
```

### Gate 3 - Explain-back

This gate is non-negotiable. It is the learning step.

State:

> "Before I write the handoff, explain back what we found and the route you're choosing. Two sentences in your own words. The first names the root cause. The second names the route and why it fits."

Wait for the owner's explain-back. The skill does not write the handoff or chain to the next skill until the owner has stated the diagnosis and route in their own words.

If the owner replies "skip" or "proceed," resist once: "Two sentences. This is the learning gate." If the owner insists after that, proceed. The owner is the principal.

If the explain-back reveals the owner is missing something important about the diagnosis or the route, say so and re-present the TROUBLESHOOT or TRIAGE output. The gate is not a checkbox. It verifies that the diagnosis became understanding.

---

## Step 4 - HANDOFF

The artifact produced depends on the route confirmed at Gate 3. All files go in `{ticket}/`.

### Tier 1 - Operational close

Write `{ticket}/{KEY}-resolution.md`:

```markdown
# Resolution - {KEY} - [title]
Author: {INITIALS}
Date: YYYY-MM-DD
Status: RESOLVED_TIER_1

## Root Cause
[file:line or operational issue: one clear sentence]

## Failure Layer
[Operational / Config / File movement / Rerun needed]

## Resolution Steps
1. [command or action]
2. [command or action]
3. [verification step]

## Verification
[How to confirm the resolution worked: specific check the owner runs]

## Why No Code Change
[One paragraph: the operational nature of the cause and why /tg-spec is not needed]
```

Update `{ticket}/{KEY}-state.md`:
- Status: RESOLVED_TIER_1
- Next skill: none (closed at Support)

Write the session log to `{ticket}/{KEY}-session-YYYY-MM-DD.md` and append to `{output}/{KEY}/YYYY-MM-DD.md`. Both, never one. See Skill Standard Rule 13.

End output:

```
Tier 1 resolution written. Execute the steps in {KEY}-resolution.md. No /tg-spec needed.
```

The skill stops. The owner executes the resolution manually per Technical Standards Rule 24 (never auto-commit, never auto-execute).

### Tier 2 - Bug to /tg-spec

Write `{ticket}/{KEY}-support-handoff.md`:

```markdown
# Support Handoff - {KEY} - [title]
Author: {INITIALS}
Date: YYYY-MM-DD
Status: SUPPORT_COMPLETE

## Root Cause
[file:line: one clear sentence]

## Failure Layer
[Source gap / Raw view / Bronze / Silver pipeline / Output mapping]

## Evidence
[Concrete evidence: record identifier, field value, expected value, pipeline output vs raw source]
Sensitive data note: record identifiers in this file are internal use only. Do not paste them into external tools.

## System Impact
- Records affected: [N]
- Fields affected:   [list]
- Same-pattern locations: [file:line, or none]
- Other pipelines affected: [list, or none]

## User Impact
[What decision is degraded. Specific, not "data quality issue."]

## Fix Options (named, not designed)
Option A: [name]: [one sentence]
Option B: [name]: [one sentence]
Option C: [name]: [one sentence, if applicable]

## Open Unknowns
[What /tg-spec or /tg-arch will need to resolve]

## Risks
[What could go wrong with any fix: regression, coverage loss, client impact]

## Related Issues Found
[Other tickets or fields affected by the same root cause]
```

Update `{ticket}/{KEY}-state.md`:
- Status: SUPPORT_COMPLETE (this must be the only `Status:` line, the first in the file)
- Next skill: /tg-spec
- Root cause: [one line]

Write the session log and output archive (both, Skill Standard Rule 13).

### Stop and hand off to /tg-spec (next thread)

Do not auto-chain. Support handoffs can be substantial (multi-layer trace, evidence, multiple fix options). Chaining into /tg-spec in the same thread burns the cache window with no benefit. Start /tg-spec in a fresh thread. The gate, not this command, decides whether the next step may run.

End output:

```
Handoff written: {ticket}/{KEY}-support-handoff.md
Status: SUPPORT_COMPLETE

Chain step complete. Start a fresh thread for /tg-spec to keep context lean.

═══════════════════════════════════════════════════════════════
Next session starter prompt (copy into a new thread):
═══════════════════════════════════════════════════════════════

/tg-spec {KEY}

Support handoff is at {ticket}/{KEY}-support-handoff.md (Status: SUPPORT_COMPLETE).
/tg-spec reads the handoff and the four standards docs.
Produces the ticket-closure contract (AC) and empirical validation scenarios (VS).
Four gates: RESTATE / REQUIREMENTS+AC / VS / explain-back before /tg-arch.

Root cause confirmed: [one-line from handoff].
Fix options named (for /tg-arch): see handoff Fix Options section.

═══════════════════════════════════════════════════════════════
```

The skill stops here. The owner copies the starter prompt into a new thread to begin /tg-spec.

### Enhancement to /tg-whiteboard

Write `{ticket}/{KEY}-enhancement-brief.md`:

```markdown
# Enhancement Brief - {KEY} - [title]
Author: {INITIALS}
Date: YYYY-MM-DD
Status: ENHANCEMENT_PROPOSED

## What the user expects
[One paragraph: the gap between current behavior and user need]

## Current behavior
[What the system actually does, confirmed by the layer trace]

## Why this is not a bug
[One paragraph: the pipeline is doing what it was designed to do]

## Design question for /tg-whiteboard
[The decision /tg-whiteboard needs to validate before this becomes a ticket]
```

Update state:
- Status: ENHANCEMENT_PROPOSED
- Next skill: /tg-whiteboard

Write the session log and output archive.

End output:

```
Enhancement brief written. Invoke /tg-whiteboard {idea or topic} when ready to validate the design question.
```

The skill stops. Whiteboard is a separate human-driven decision. It does not auto-chain.

---

## Rules

- No fix design. Name options only, leave design to /tg-spec and /tg-arch.
- No code changes, no commits, no auto-execution. Read-only on all systems.
- No sensitive personal data in any artifact open-text field. Record identifiers go only in the Evidence section, under the internal-use-only marker. See Technical Standards Rule 1.
- Read schema files in the vault before pipeline code. Know what the source provides before blaming the code.
- Pattern scan is mandatory. Never skip it.
- All three gates fire as designed. Gate 3 is the learning gate and is non-negotiable.
- Code under `$TOLLGATE_CODE_DIR` is read-only. The active working location comes from the ticket state file, not hardcoded. See Technical Standards Rule 22.
- The session log and the output archive are both written. Never pick one.
- Never post to the ticket tracker or the chat tool. The owner does all external actions.
