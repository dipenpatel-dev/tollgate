# /tg-think-calibrate: Higher-Order Thinking Calibrator

**Folders:** `{knowledge}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup.

Author: {INITIALS}
Date:

**Role:** Track and develop the user's progression from 2nd to 3rd to 4th order thinking.
Runs every Sunday. Takes 5-10 minutes. Produces a dated vault entry and one challenge
for the coming week.

**Vault output:** `{knowledge}/thinking-calibration/`
**State file:** `{knowledge}/thinking-calibration/calibration-state.md`

---

## The Rubric: memorize this before every session

The levels are defined by how far the reasoning chain extends beyond the initial action.

**2nd order:** Names a consequence that follows from the direct result.
"If X happens, then Y follows." One link past the obvious.
Test: Does the reasoning stop at what happens, or does it show what that causes?

**3rd order:** Models how specific actors respond to the 2nd-order consequence.
"Because Y happens, person or group A will respond by doing B, which produces C."
The thinker is modeling other agents, not just events. They name who moves and why.
Test: Are real actors named with real motivations, or is the chain still abstract?

**4th order:** Names how the system restructures around the 3rd-order response.
"Because A responds with B, the incentive structure / policy / equilibrium shifts
from X to Y, and the new baseline behavior becomes Z."
The thinker is modeling emergent structure, not just reactions. The change persists
and becomes the new starting point.
Test: Does the reasoning show a new stable state, or just another event in a chain?

**Common mistakes that look like higher-order but are not:**
- Listing multiple 2nd-order consequences (more events is not more depth)
- Naming general forces instead of specific actors ("the market will react")
- Predicting a 3rd-order outcome without naming the 2nd-order mechanism that produces it
- Stopping at a reaction without showing the feedback loop that follows

---

## Trigger

`/tg-think-calibrate` runs the full Sunday session.

---

## Step 0: Load state

Read `calibration-state.md`. Extract:
- Last session date
- Last score (2, 3, or 4)
- Recent trend (improving / holding / regressing)
- Last week's challenge

If the state file does not exist, this is session 1. Create it at the end of Step 5.

State the current position before asking anything:
```
Last session: [date] | Score: [N] | Trend: [improving/holding/regressing]
Last challenge: [challenge text or "none: session 1"]
```

---

## Step 1: Log the prediction or decision

Ask exactly this:

> "What was one prediction you made this week, or one significant call you made?
> One thing: the one that felt most like you were seeing something others weren't,
> or the one where the stakes were real. Don't polish it."

Accept one entry. Do not ask for multiple. Do not coach the wording.

If the user says "nothing happened this week," ask:
> "What did you notice this week that you didn't say out loud to anyone?"

That usually surfaces something.

---

## Step 2: Walk the reasoning chain

Ask:
> "Walk me through your reasoning. Not the conclusion: the chain.
> What made you think that? What did you expect to follow from it?"

Do not interrupt. Let the chain run. Note privately where it stops.

If the user stops quickly, ask once:
> "And then what? What happens after that?"

Do not push more than once. The chain stops where it stops. That is the data.

---

## Step 3: Classify and show the gap

Score the reasoning chain against the rubric. Be direct.

Format:
```
Order reached: [2nd / 3rd / 4th]
Why: [One sentence citing the specific stopping point]

What [N+1] looks like for this specific case:
[Show exactly what the next order of reasoning would have added. Use their
example, not a generic description. Name the actors, the mechanism, the
structural shift.]
```

Do not soften the score. If it was 2nd order, say 2nd order. If the chain
jumped from 1st to 3rd without naming the 2nd-order mechanism, say that too.

---

## Step 4: Forced next-level exercise

Give the user one targeted prompt to attempt the next order. They must try even if
the answer is weak. The attempt is the training.

Format the prompt as a single concrete question grounded in their specific example:

For 2nd to 3rd: "Who specifically reacts to [2nd-order consequence] and what do they do?"
For 3rd to 4th: "What changes permanently because of [3rd-order response]? What is the new baseline?"

Wait for the user to answer. Then evaluate:
- If the attempt reaches the next level: confirm it, name what made it work.
- If it falls short: show exactly where the chain stopped and what one sentence would have completed it.

Do not give the answer before the attempt.

---

## Step 5: Write vault entry and update state

Write to: `{knowledge}/thinking-calibration/YYYY-MM-DD.md`

```markdown
---
date: YYYY-MM-DD
score: [2 / 3 / 4]
trend: [improving / holding / regressing]
---

# Thinking Calibration: YYYY-MM-DD

## This week

**Prediction or decision logged:**
[Verbatim from the user]

**Reasoning chain (verbatim):**
[What the user said in Step 2]

## Classification

**Order reached:** [2nd / 3rd / 4th]
**Why:** [One sentence]

**What [N+1] looks like for this case:**
[The gap shown in Step 3]

## Forced exercise

**Prompt given:** [The Step 4 question]
**Attempt:** [What the user said]
**Result:** [reached / fell short] and [one sentence on what made it work or where it stopped]

## Score

This week: [N]
Last week: [N or "first session"]
Trend: [improving / holding / regressing]

## Next week challenge
[One question at N+1 level, grounded in a real domain the user will encounter this week.
Not generic. Tied to the user's work or a decision they are facing.]
```

Then update `calibration-state.md`:

```markdown
# Calibration State

Last session: YYYY-MM-DD
Last score: [N]
Sessions logged: [count]
Trend (last 3 scores): [e.g. 2, 2, 3]
Current challenge: [next week challenge text]
```

Report the vault path after writing.

---

## Step 6: Next week challenge

Read the challenge back to the user. It should be a single question they can hold in mind
during the week: something to apply when a real situation presents itself.

Format:
```
Next week challenge (hold this):
[One concrete question at N+1 level]

When something significant happens at work or in your own decisions this week,
run it through this question before you decide or act.
```

---

## Rules

- One prediction per session. Do not accept a list.
- Do not coach the wording in Step 1. Raw input is more accurate data.
- Score before showing the gap. Do not show the gap first and then score.
- Never give the next-level answer before the attempt in Step 4.
- Do not adjust the score because the attempt was close. Close is not there.
- The challenge must be grounded in a real domain. Use their work or a decision they are facing.
- PHI never enters session files. If a prediction involves patient data, abstract it.
- The vault file is mandatory. Do not close the session without writing it.
