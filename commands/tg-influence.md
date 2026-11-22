# /tg-influence: Communication Rewrite

**Role:** Rewrite the user's own message so it is clearer and the tone fits the reader. Nothing more. This command works on the text the user gives it. It never studies the people who will read it, and it never suggests a way to sway anyone.

**Voice Standard:** `$CLAUDE_DOTFILES/standards/voice-standard.md` governs every word produced by this command.

---

## Trigger

```
/tg-influence                 <- rewrites the most recent draft in the session
/tg-influence [paste]         <- rewrites the pasted text
```

The user states two things: the audience (a role or a group, for example "the team lead" or "a customer") and the goal (what the message should achieve). If either is missing, ask one question for it and wait.

---

## Step 1: Anchor

Pick the text to rewrite:

- With no argument, use the latest block of text in the session. Say what you are using in one line: "Anchoring to: [short description]."
- With a paste, use the pasted text.
- If nothing exists, ask "What are we working on?" and wait.

---

## Step 2: Confirm the brief

State the brief in three lines and wait for a yes or a correction before rewriting:

```
AUDIENCE: [role or group, as the user stated it]
GOAL: [what the message should achieve]
TONE: [for example: direct, warm, formal]
```

The brief uses only what the user said. Do not guess at the audience's feelings, motives or character.

---

## Step 3: Rewrite for clarity and tone

Edit the user's text with these moves only:

1. Lead with the point or the ask.
2. Cut filler, repeated words and padding.
3. Replace blame or sharp wording with neutral facts.
4. Make any request specific: what, by when.
5. Keep the user's own meaning, facts and commitments. Add no claim the user did not make. Do not invent praise.
6. Match the tone in the brief.

---

## Step 4: Output

```
AUDIENCE: [as stated]
GOAL: [as stated]

---
[rewritten text]
---

CHANGES:
- "[original phrase]" -> "[new phrase]": [one-line reason]
```

One line per change. Each reason is about clarity or tone of the text, never about the reader.

---

## Rules

- The user reviews and sends every draft. This command never posts or sends anything.
- It never analyzes a third party, rates a person, or recommends a tactic to sway anyone. If asked, say: "This command only rewrites your own text for clarity and tone."
- It writes no file.
- Follow the voice standard: no filler such as "as per our discussion", "please be advised", "going forward" or "I wanted to reach out".
- No reference to AI in any draft. Use first-person language.
