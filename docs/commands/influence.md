# /tg-influence

**It rewrites your own message so it is clearer and the tone fits, and tells you why for each change.** It does nothing else {src:commands/tg-influence.md:3}.

The command name is fixed: `/tg-influence` rewrites the latest draft in the session, and `/tg-influence [paste]` rewrites the pasted text {src:commands/tg-influence.md:12-13}.

## When to use

You have a draft (an email, a ticket comment, a chat message) and you want it tighter. Give it the audience (a role or group) and the goal; if either is missing it asks one question and waits {src:commands/tg-influence.md:16}.

## What it does and does not do

1. Anchors to the text: the latest block in the session (it names what it is using), the pasted text, or it asks "What are we working on?" {src:commands/tg-influence.md:24-26}.
2. States the brief in three lines (audience, goal, tone) and waits for a yes or correction before rewriting. The brief uses only what you said {src:commands/tg-influence.md:32-40}.
3. Rewrites with six moves only: lead with the point, cut filler, replace blame with neutral facts, make requests specific, keep your meaning and facts, match the tone {src:commands/tg-influence.md:48-53}.
4. Prints the rewrite and one line per change, each reason about clarity or tone of the text, never about the reader {src:commands/tg-influence.md:64-71}.

It does not study or rate any person, guess motives, or suggest a way to sway someone. If asked, it says "This command only rewrites your own text for clarity and tone." {src:commands/tg-influence.md:78}. You review and send; it never posts anything {src:commands/tg-influence.md:77}.

## What it reads and writes

- Reads: your draft (latest text in the session, or what you paste) and the voice standard {src:commands/tg-influence.md:5}.
- Writes: nothing. It writes no file {src:commands/tg-influence.md:79}.
- It uses no folder lookup, no search and no vault git line.

## Hooks and gate lines

None. The leak scanner rule CMD-04 is meant to keep an influence command rewrite-only, and it checks any file named `influence.md` or `tg-influence.md` {src:tests/leak/scan_leaks.py:208}. The command file is `commands/tg-influence.md`, so the rule now matches it (checked 2026-11-20). The rule's own comments now name both files {src:tests/leak/scan_leaks.py:15} {src:tests/leak/scan_leaks.py:78}.

## Example

You paste "Hey, the report for `T-001` is late again, please fix asap" and say audience: "team lead", goal: "get a new date". You get "The `T-001` report is not ready. Can we agree on a new delivery date by Friday?" plus a line for each change, such as "late again" removed because it assigns blame and adds nothing {src:commands/tg-influence.md:67-68}.
