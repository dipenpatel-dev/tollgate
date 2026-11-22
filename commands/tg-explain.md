# /tg-explain: What Was Built

**Role:** Post-block explainer. Read the current diff and give a plain-language explanation of what was just built. Fires after a block commit. No praise, no padding, under 250 words total.

---

## Trigger

```
/tg-explain
```

Run by hand after a dev block commits. No arguments.

---

## Step 1: Read the diff

Run:

```bash
git diff HEAD~1 HEAD
```

If that returns nothing (uncommitted changes exist), run instead:

```bash
git diff --staged
```

If both return nothing, state "No diff found. Commit or stage your changes first." and stop.

---

## Step 2: Produce the explanation

Write exactly this structure, in plain language, under 250 words across all four sections:

```
WHAT WAS BUILT
[One paragraph, 3-5 sentences. What does this code do from the outside?
What problem does it solve? Write as if explaining to a teammate who has
not seen the ticket.]

HOW IT WORKS
[One paragraph, 3-5 sentences. The load-bearing logic only. What mechanism
makes this work? What would a maintainer need to understand to change this
safely?]

WHAT WOULD BREAK IT
- [Specific failure mode: wrong input type, missing dependency, environment
  assumption, edge case the code does not handle]
- [...]
(2-4 items)

WHAT TO CHECK IN THE DIFF
- [Specific line or function worth a second look. Name the function or
  variable. Flag anything non-obvious, any baked-in assumption, any place
  where a future change could silently break this.]
- [...]
(2-4 items)
```

---

## Rules

- Output the four sections and nothing else. No commentary before or after.
- No "this is a solid implementation", no praise, no framing.
- If the diff touches several files, the explanation covers the whole diff as one unit.
- If the diff is too large to explain clearly in 250 words, focus on the highest-risk or most non-obvious mechanism and say so in one sentence at the top.
- The command reads the diff only. It writes no file and sends nothing.
