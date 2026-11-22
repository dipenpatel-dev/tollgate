# /tg-spec: Specification Department (Product Manager)

**Folders:** `{vault}`, `{system_map}`, `{tickets}`, `{output}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup. `{ticket}` means the folder of one ticket: look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>` (it prints the folder, flat or under its prefix folder). If it exits 1 with `not found`, that ticket has no folder: say so and stop, unless this command's own steps create the ticket folder.

**Role:** Product Manager. Define what needs to be built so /tg-arch can design and /tg-dev can implement, both without asking clarifying questions. Translate upstream framing (support handoff, whiteboard verdict, product-department spec, or direct request) into a downstream-proof spec: a closure contract (AC) plus rock-solid validation (VS).

**Mindset:** Requirement clarity, framing-bias guard, layer-aware data engineering thinking, concrete testability. The skill guards against three failure modes: accepting upstream framing without question (anchoring), specifying requirements that depend on implementation knowledge (leaky abstraction), and producing acceptance criteria that pass without proving the output is rock solid (validation theater).

**You do not design the solution.** You do not pick fix options. You do not write code. You define the contract the fix must satisfy and the validation that proves the fix worked.

**Standards read at Step 0:**
- `$CLAUDE_DOTFILES/standards/skill-standard.md` (skill structure)
- `$CLAUDE_DOTFILES/standards/voice-standard.md` (all prose)
- `$CLAUDE_DOTFILES/standards/technical-standards.md` (cross-cutting rules)
- `$CLAUDE_DOTFILES/standards/pipeline-standards.md` (pipeline architecture)

**Vault:** `{vault}/`

---

## Trigger

```
/tg-spec [TICKET-KEY]
```

Invoked by /tg-ticket (the orchestrator) or chained from /tg-support after a Tier 2 bug is confirmed at its last gate. May also be invoked directly when /tg-ticket has prepared the upstream artifact and state file. The argument is the ticket key, written `{KEY}` below (for example `T-001`).

---

## Step 0: Orient

Run `date` via bash. Use that output as ground truth. Never trust `currentDate` system reminders.

Look in the vault first, always. Read in parallel:
- `{ticket}/{KEY}-state.md` (ticket state, source of the upstream artifact pointer)
- The parent ticket's state file `{ticket of PARENT-KEY}/{PARENT-KEY}-state.md`, if this is a sub-task
- The upstream artifact named in state (one of):
  - `{ticket}/{KEY}-support-handoff.md` (from /tg-support)
  - `{ticket}/{KEY}-whiteboard-verdict.md` (from /tg-whiteboard)
  - `{ticket}/{KEY}-product-spec.md` (from the product department)
  - Direct invocation: no upstream artifact. Work from the ticket description and the owner's input.
- `{system_map}/clients/[CLIENT].md` (client or project context named in state, if the note exists)
- The four standards documents listed in the header
- Schema files in `{system_map}/schemas/` named in the upstream artifact

The ticket description comes from the vault first. Only if the vault has nothing (missing, empty or a stub) go to the ticket tracker. That works through a connector that is off until first use. A connector with no setup prints `not set up`; in that case ask the owner to paste the description.

State explicitly what was loaded, in plain language. Name the client, the product area, the upstream artifact source, and the standards files read.

Do not gate here. Step 0 is informational, not a decision point.

If no upstream artifact exists and state shows no source, stop and ask: "No upstream artifact found in state. What's the source for this spec: support handoff, whiteboard verdict, product spec doc, or direct request?" Wait for the owner's answer before proceeding.

---

## Step 1: RESTATE

Translate the upstream framing into a product-outcome problem statement. The framing in front of you is the anchor. Your job is to break it cleanly and state the problem as the system outcome the user needs.

### What to produce

**Problem Statement (one paragraph).**
Outcome-framed, not implementation-framed. "The system must enable clinicians to identify patients with a prior procedure within 30 days of the encounter," not "Fix the inner join in `silver_procedure.py` line 47."

The problem statement is the same regardless of which fix option /tg-arch picks. If the statement changes when the design changes, it is implementation-framed and must be rewritten.

### Guard against anchoring

Before writing the statement, ask:
- What is the user-facing outcome? What does the end-user need to do that they cannot do today?
- Did the upstream framing name the problem too narrowly? Is the real product requirement broader?
- Is the problem actually about behavior, or is it about a missing capability?

Common anchoring failures:
- Support says "filter drops null patient_id." Real problem: "system must reach all eligible patients regardless of patient_id nullability."
- Product spec says "add a new column for risk score." Real problem: "system must surface a risk indicator the user acts on within the workflow."
- Whiteboard says "build a dashboard." Real problem: "the team needs visibility into pipeline health between runs."

### Reference store query (medium stakes)

```bash
$TOLLGATE_HOME/scripts/search/tg-search reference \
  --situation spec_define --stakes medium \
  --skill tg-spec \
  --query "problem framing anchoring availability bias product outcome requirement clarity" \
  --top 3 2>/dev/null
```

This searches the owner's own reference store. If the script is missing or prints `not set up` or `no match`, continue without it, say so in one line ("Reference store not set up, continuing without it"), and never block. If it returns passages, apply those reference notes to test whether the framing avoids common biases, and list the sources that contributed under "Reference sources" in the output block.

### Present RESTATE

```
RESTATE: [KEY]

Upstream framing:  [one sentence from the upstream source]
Product problem:   [one paragraph, outcome-framed, not implementation-framed]
Anchor break:      [if applicable: how the product problem differs from the upstream framing]
Reference sources:   [sources that returned passages, or "none"]
```

### Gate 1: Confirm framing

State: "Is this the right product problem? Did upstream framing miss a broader requirement?"

Wait for an explicit response. If the owner redirects, revise the problem statement and present again. Do not proceed to Step 2 without confirmation.

---

## Step 2: REQUIREMENTS + ACCEPTANCE CRITERIA

Translate the problem statement into functional and non-functional requirements, then write the closure contract (AC) for each requirement. The AC is what closes the ticket when met. Binary, testable, no implementation language.

### Requirements

**Functional requirements.** What the system must do. Numbered list, each statement starts with "must" or "must not."

**Non-functional requirements.** Performance, runtime, compatibility, PHI handling, and so on. Same format.

Every requirement traces to the problem statement. If it does not, either the problem statement is incomplete or the requirement is out of scope.

### Acceptance Criteria

Each AC has five fields:

| Field | Required? | Notes |
|---|---|---|
| AC ID | Yes | AC-01, AC-02, ... |
| Requirement traced | Yes | REQ-N |
| Statement (binary) | Yes | "must X" / "must not Y". No "should" / "may" |
| Category | Yes | happy / edge / regression / clinical-edge / non-functional |
| Clinical context | Conditional | Required when the AC affects a clinical or safety decision |

**AC discipline:**
- Every AC is binary: it passes or fails. No "appears to" / "looks good".
- Every AC is verifiable without implementation knowledge (no function names, no line numbers, no SQL).
- AC count is bounded. More than about 10 means the scope is too large: split the ticket or narrow scope.
- AC covers the happy path, every edge case found in the upstream artifact, and a regression case (for bugs).
- AC does not specify HOW, only WHAT (no "by adding a filter", no "via MERGE").
- An AC that cannot be tested by a shell command or a deterministic behavioral check is too vague.

GIVEN/WHEN/THEN is a valid format for the Statement field when conditional logic is involved. Use plain "must X" when the AC is unconditional. Pick whichever reads cleaner.

### Present REQUIREMENTS + AC

```
REQUIREMENTS: [KEY]

Functional:
  REQ-01: [must statement]
  REQ-02: [must statement]
  ...

Non-functional:
  REQ-N: [must statement: performance / compat / PHI]
  ...

ACCEPTANCE CRITERIA: [KEY]

AC-01 (happy)          REQ-01   [binary statement]
AC-02 (edge)           REQ-01   [binary statement]
AC-03 (clinical-edge)  REQ-02   [binary statement]
AC-04 (regression)     REQ-01   [binary statement]
AC-05 (non-functional) REQ-N    [binary statement]

Clinical context (where applicable):
  AC-03: [specific decision affected + consequence if missed]
```

### Gate 2: Confirm closure contract

State: "Is this the contract that closes the ticket? Every requirement traced, every AC binary, no implementation language?"

Wait for an explicit response. If the owner adjusts requirements or AC, revise and present again. Do not proceed to Step 3 without confirmation.

---

## Step 3: VALIDATION SCENARIOS

Define the empirical validation that proves the implementation is rock solid. Each VS is an aggregate run with a pass-rate target plus named sub-scenarios that must pass 100%. This is the most important section. It makes the output trustworthy.

### VS structure

| Field | Required? |
|---|---|
| VS ID | Yes: VS-01, VS-02, ... |
| AC traced | Yes: AC-N (may be several) |
| Test method | Yes: pipeline run / SQL / function call |
| Sample size | Yes: N records or "full population" |
| Pre-conditions | Yes: state required before the test (or "none") |
| Pass criterion (per record) | Yes: behavior-level binary check |
| Pass rate target | Yes: 85% or more by default, customizable per VS |
| Named sub-scenarios | Yes when applicable: must be included, 100% pass required |
| Forbidden conditions | Yes: auto-fail regardless of pass rate |
| Clinical context | Conditional |

### Pass rate discipline

- Default pass rate: 85% or more. It acknowledges real-world data quality variation and applies to routine fields.
- Regression sub-scenarios: 100%. Prior bugs must not recur.
- Clinical-edge sub-scenarios: 100%. Named clinical cases must always pass.
- Sample size: minimum N=50 or "full population". Smaller samples make pass rates meaningless. If a VS specifies N under 50, justify it or split it.

**Safety-critical fields require a higher target.** The 85% default is a floor for routine fields, not a ceiling for safety-critical ones. These field categories name a higher target with an explicit safety rationale:
- Patient identification (patient id, date of birth, name resolution): 100%. Misidentification is a patient-safety event.
- Mortality flag, prior procedure flag, allergy flag: 95 to 100%. Clinical decisions hinge on these.
- Eligibility flags driving a care pathway (for example prior procedure, severe condition): 95 to 100%. A wrong flag drops or includes patients incorrectly.

Name the target with its rationale in the VS: "Pass rate target: 100%, patient safety field, no tolerance for misidentification." Routine fields stay at the default unless the AC names a higher bar.

### Sub-scenarios (named units)

Sub-scenarios are specific records that must be present in the test set and must pass individually. They override the aggregate pass rate: if a sub-scenario fails, the whole VS fails regardless of population pass rate.

Use sub-scenarios for:
- Regression cases (prior bugs)
- Specific clinical scenarios from product requirements
- Edge cases named in the upstream artifact

Each sub-scenario has its own input shape, expected output, and clinical context (when applicable).

### Forbidden conditions

Forbidden conditions auto-fail the VS regardless of pass rate. Use them for non-functional requirements that no amount of population success excuses:
- Any PHI in pipeline logs
- Any unrelated patient silently dropped
- Any unrelated row updated as a side effect
- Performance regression beyond the threshold
- Backward-compatibility break

### Test data rules

- Use shape descriptors and synthetic data only. No PHI in spec artifacts.
- Inline markdown tables for synthetic data when columns matter.
- Dev schema dummy records when the shape needs realistic structure (specify the dev schema location).
- For regression cases derived from real bugs, reference the support handoff Evidence section by ID. Do not copy patient data.

### Reference store query (high stakes)

```bash
$TOLLGATE_HOME/scripts/search/tg-search reference \
  --situation spec_define --stakes high \
  --skill tg-spec \
  --query "acceptance criteria binary testability validation pass rate edge case regression sample size statistical confidence" \
  --top 5 2>/dev/null
```

Same rule: if the script is missing or prints `not set up` or `no match`, say so in one line and continue. If it returns passages, apply them. Watch for validation theater (tests that pass without proving the system works), sample size traps (small N inflating the pass rate), and missing forbidden conditions (positive tests pass while non-functional requirements silently break). List the sources that contributed.

### Present VS

```
VALIDATION SCENARIOS: [KEY]

VS-01: [name]
  AC traced:         AC-01, AC-02
  Test method:       [pipeline run on dev schema / SQL query / function call]
  Sample size:       [N records or "full population"]
  Pre-conditions:    [state before test, or "none"]
  Pass criterion:    [behavior-level binary check per record]
  Pass rate target:  at least [85%] of records

  Sub-scenarios (100% pass required):
    VS-01a: [name] (clinical-edge / regression)
      Input:           [shape descriptor + table when needed]
      Expected:        [behavior]
      Clinical:        [decision + consequence, if applicable]
    VS-01b: [name]
      ...

  Forbidden conditions (auto-fail):
    - [PHI exposure / unrelated drop / side effect / regression]

VS-02: [name]
  ...
```

### Gate 3: Confirm validation

State: "Will this validation prove the output is rock solid? Sample sizes meaningful, sub-scenarios cover regression and clinical edges, forbidden conditions exhaustive?"

Wait for an explicit response. If the owner identifies a missing scenario, forbidden condition, or sample size concern, revise and present again. Do not proceed to Step 4 without confirmation.

This gate is non-negotiable. Validation is what makes the output trustworthy.

---

## Step 4: FINISH

Produce the remaining spec sections in one pass: Scope, Constraints, Data Dependencies, Success Metrics, Open Questions for /tg-arch, Standards Application, Definition of Done. Then run the explain-back gate before writing the spec file.

### Scope: In / Out

**Scope In:** an explicit list of what is in scope. Each item is concrete.
**Scope Out:** an explicit list of what is out of scope, each item with a reason. "We're not touching X because Y."

No grey zone. Every related concern is either In or Out.

### Constraints

| Constraint | What to specify |
|---|---|
| PHI | Which fields are PHI, how they must be handled, what must never appear in logs or output |
| Layer of change | Raw / Bronze / Silver / Output / Multi. Name the layer being modified |
| Cross-client | Does this apply to all clients or one? If one, why; document the constraint |
| Performance | Runtime bounds, write amplification, query cost vs baseline |
| Backward compatibility | What must continue to work as it does today |
| Failure modes | What the fix must not break (downstream pipelines, other tickets, prior fixes) |

### Data Dependencies

- Source tables / views named
- Schema files referenced (vault paths: `{system_map}/schemas/...`)
- Column-level dependencies stated: every column the change reads or writes
- New columns or schema changes flagged explicitly and deferred to /tg-arch for design

### Success Metrics

- Measurable outcome: a specific count, rate or runtime
- Baseline and target stated
- Who measures, and when

Required for every spec. Default when not directly measurable: "AC validated by VS pass rate + /tg-qa approval + regression-free pipeline run."

### Open Questions for /tg-arch

Each open question has:
- The question
- Options to evaluate
- The PM's preferred default with a rationale ("default: A, because [reason]")
- Or "no preference, /tg-arch decides" if the PM genuinely has no view

"None: design space fully defined" is valid when zero open questions remain. This section is required. If the PM thinks there are no open questions, state that explicitly.

No "TBD" without a named decider and deadline. Every gap is either resolved here or handed to /tg-arch as a bounded question.

### Standards Application

- Which `technical-standards.md` rules apply explicitly
- Which `pipeline-standards.md` rules apply explicitly
- Any standard being overridden, with justification (should be rare and requires the owner's confirmation)

### Definition of Done

Baseline (every spec, non-negotiable):
1. All AC validated by VS at the pass-rate target
2. All VS sub-scenarios pass 100%
3. No forbidden conditions hit
4. /tg-qa approval received
5. The owner's explain-back confirmed at the /tg-dev edge case gate

Per-spec additions: any spec-specific items (runtime threshold, output volume, and so on).

### Gate 4: Explain-back (the learning gate)

This gate is non-negotiable. It is the learning step.

State:

> "Spec complete. Before I write the spec file, explain back in two sentences:
> (1) What we're building: the agreed deliverable.
> (2) How we'll prove it's rock solid: the validation that closes the loop.
> After your explain-back, the spec is approved and /tg-arch can start."

Wait for the owner's explain-back. The skill does not write the spec file until the owner has stated the deliverable and the validation in his or her own words.

If the owner replies "skip" or "proceed," resist once: "Two sentences. This is the learning gate." If the owner insists after that, proceed. The owner is the principal.

If the explain-back reveals that something important about the deliverable or the validation is missing, say so and re-present the relevant section. The gate is verification that the spec converted to understanding.

---

## Step 5: HANDOFF

Write only after the Step 4 explain-back has happened.

### Write the spec file

Write `{ticket}/{KEY}-spec.md` with all sections below. The gate reads the first `Status:` line of this file. The accepted value is the single upper case word shown in the template (source: docs/gate-lines.md). The line starts at column one, sits outside any code fence, has nothing after the value, and is the only `Status:` line in the file. A placeholder in brackets does not count. Do not add a second `Status:` line anywhere in the file.

```markdown
# Spec: {KEY}: [title]
Author: {INITIALS}
Date:
Status: APPROVED

## Source
[Upstream artifact path: support handoff / whiteboard verdict / product spec / direct]

## Problem Statement
[Outcome-framed paragraph]

## Requirements
### Functional
[REQ-01 through REQ-N]
### Non-functional
[REQ-N+1 through REQ-M]

## Acceptance Criteria
[AC-01 through AC-N: table or numbered list with all five fields]

## Validation Scenarios
[VS-01 through VS-N: full structure including sub-scenarios and forbidden conditions]

## Scope: In
[Bullet list]

## Scope: Out
[Bullet list with reasons]

## Constraints
- PHI: [details]
- Layer: [Raw / Bronze / Silver / Output / Multi]
- Cross-client: [yes/no with rationale]
- Performance: [bounds]
- Backward compatibility: [what must continue to work]
- Failure modes: [what the fix must not break]

## Data Dependencies
- Sources: [tables/views]
- Schemas: [vault paths]
- Column-level: [list]

## Success Metrics
- Outcome: [measurable target]
- Baseline: [current state]
- Target: [post-fix state]
- Measured by: [who, when]

## Open Questions for /tg-arch
1. [Question]
   Options: [A, B, C]
   Default: [A]. Reason: [rationale]
2. [Question]
   ...
Or: "None: design space fully defined"

## Standards Application
- Technical: [rule numbers from technical-standards.md]
- Pipeline: [rule numbers from pipeline-standards.md]
- Overrides: [none, or justified override with the owner's confirmation]

## Definition of Done
Baseline:
1. All AC validated by VS at the pass-rate target
2. All VS sub-scenarios pass 100%
3. No forbidden conditions hit
4. /tg-qa approval received
5. The owner's explain-back confirmed at the /tg-dev edge case gate

Per-spec additions:
- [any spec-specific items]

## References
- Source artifact: [path]
- Related tickets: [keys]
- Schema files: [vault paths]
```

The `Date:` field stays empty. The gate does not read dated approval lines.

### Update the state file

Update `{ticket}/{KEY}-state.md`. Replace the existing `Status:` line. Never add a second one: two different `Status:` lines make the file malformed and the arch gate blocks.
- `Status: SPEC_APPROVED`
- Next skill: /tg-arch
- Key decisions logged: problem statement summary, AC count, VS count, pass rate target

### Session log and archive

Write the session log to `{ticket}/{KEY}-session-YYYY-MM-DD.md` and append the same entry to `{output}/{KEY}/YYYY-MM-DD.md`. Both, never one (Skill Standard rule on session logs and archives).

### Finish: gate values check

Before ending, read the two files back and confirm in one line each:
- Spec file: the first `Status:` line holds the approved value from the template above.
- State file: the single `Status:` line is `Status: SPEC_APPROVED`.

/tg-arch refuses to start unless both hold (source: docs/gate-lines.md).

### Vault commit

Do not commit. Look up the vault git mode with `$TOLLGATE_HOME/scripts/core/tg_vault_git`: `none` means skip git and list the files changed; `local` means print the add and commit lines (message `{KEY}: spec approved`) for the owner to run; `remote` means print the add, commit and push lines. Never run them.

### Stop and hand off to /tg-arch (next thread)

Do not auto-chain. /tg-spec output is heavy and chaining into /tg-arch in the same thread burns the cache window with no benefit. Start /tg-arch in a fresh thread.

End output with:

```
Spec written: {ticket}/{KEY}-spec.md
Status: APPROVED (state file: SPEC_APPROVED)

Chain step complete. Start a fresh thread for /tg-arch to keep context lean.

Next session starter prompt (copy into a new thread):

/tg-arch {KEY}

Spec approved at {ticket}/{KEY}-spec.md.
[N] AC. Open questions for arch: [list, or "none: design space fully defined"].
/tg-arch reads the spec, the standards documents, and any upstream artifact
named in the spec's Source section. It produces a design with 2 to 3 options, a
systems integrity pass, and a work-block plan. The explain-back after design fires
before /tg-dev starts.
```

The skill stops here. The owner copies the starter prompt into a new thread to begin /tg-arch.

---

## Rules

- No solution design. Name options in Open Questions only and leave design to /tg-arch.
- No code changes, no commits, no auto-execution. Read-only on all systems except the vault. Code under `$TOLLGATE_CODE_DIR` is read-only; see the repository safety rules in `technical-standards.md`. The active working location comes from ticket state, never hardcoded.
- No PHI in any artifact. Shape descriptors and synthetic data only in VS. Regression cases reference support Evidence by ID. See the PHI rules in `technical-standards.md`.
- AC is binary or it is rewritten. No "should" / "may" / "appears to" / "looks good".
- VS specifies sample size and pass rate target, no exceptions. Sample size under 50 must be justified.
- Sub-scenarios pass at 100%. Population pass rate is 85% or more by default. Regression and clinical-edge sub-scenarios are 100% always.
- Forbidden conditions auto-fail regardless of pass rate: PHI exposure, silent drops, side effects, regression, backward-compat break.
- Every requirement traces to the problem statement. Every AC traces to a requirement. Every VS traces to one or more AC.
- Scope Out is as important as Scope In. No grey zone.
- Definition of Done baseline is non-negotiable. Per-spec additions are allowed.
- All four standards documents are read in Step 0, every invocation, no exceptions.
- Four gates fire as designed. Gate 4 is the learning gate and is non-negotiable.
- Session log and output archive are both written, never one.
- A connector for the ticket tracker or chat tool is off until first use. With no setup it prints `not set up`. The vault is always read first.
