# /tg-draft

**It writes a message for another person (Jira, Slack, email or Notion) in your voice and shows it to you. You review it; nothing is sent.** Use it for any communication that goes to someone else {src:commands/tg-draft.md:3}. It posts nothing {src:commands/tg-draft.md:225}.

The command name is fixed. Forms {src:commands/tg-draft.md:13-18}:

- `/tg-draft jira [KEY]`
- `/tg-draft slack client [CLIENT]`
- `/tg-draft slack internal [topic]`
- `/tg-draft email [subject or sender]`
- `/tg-draft notion [page topic]`
- `/tg-draft status [CLIENT or topic]`

The command file also says it fires on its own whenever you ask Claude to write or help respond to something for another person {src:commands/tg-draft.md:21}. If the type or audience is unclear it asks one question: "Who is this going to and what do they need to walk away knowing?" {src:commands/tg-draft.md:23}.

## What it does

1. Applies the core recipe to every draft before showing it {src:commands/tg-draft.md:29}: conclusion first, make it tangible, say what it means for the reader, give the why in their language, human prose, one message per draft {src:commands/tg-draft.md:31-46}.
2. Uses the venue structure for the type: a Jira description, progress comment or resolution comment; an internal or client Slack message; an email reply; a Notion page {src:commands/tg-draft.md:53} {src:commands/tg-draft.md:120} {src:commands/tg-draft.md:136} {src:commands/tg-draft.md:154} {src:commands/tg-draft.md:175}.
3. Sets the stakes: Jira descriptions are medium or high, client Slack at least medium, Notion always high {src:commands/tg-draft.md:75} {src:commands/tg-draft.md:150} {src:commands/tg-draft.md:196}.
4. Shows the draft with a voice label, type and stakes, then notes on what to verify before sending {src:commands/tg-draft.md:204-217}. A second variant appears only when a genuinely different approach exists {src:commands/tg-draft.md:219}.

Email replies are drafted after reading the whole thread {src:commands/tg-draft.md:156}. The voice rules come from `standards/voice-standard.md`, which exists in the repo {src:commands/tg-draft.md:5}.

## What it reads and writes

- Reads: the voice standard file, the thread or ticket you point at {src:commands/tg-draft.md:5} {src:commands/tg-draft.md:156}.
- Writes: nothing. The draft appears in chat only {src:commands/tg-draft.md:202-217}.
- Folders: it uses no `tg_path` lookup.
- Scripts: none. No `tg-search`, no vault git line, no commit.

## Hooks and gate lines

None apply. No file is written and no `Status:` line is touched.

## Stop points

- Unclear type or audience: one question {src:commands/tg-draft.md:23}.
- Not enough context: it states exactly what is missing instead of writing vague text {src:commands/tg-draft.md:228}.

## What it never does

- Never sends or posts a draft {src:commands/tg-draft.md:225}.
- Never includes PHI: patient identifiers are stripped first {src:commands/tg-draft.md:227}.
- Never bundles two messages into one draft {src:commands/tg-draft.md:229}.

## Where the command file disagrees with itself

- It says to apply "all eight rules", but only six rules are listed {src:commands/tg-draft.md:29} {src:commands/tg-draft.md:31} {src:commands/tg-draft.md:46}.
- The Notion step applies Cialdini and Made to Stick frameworks, but the command file names no file that holds them {src:commands/tg-draft.md:196}.

## Example

```
/tg-draft jira PROJ-330
```

Shows a labelled draft (voice, type, stakes), the text between two rules, and notes on what to verify. You copy it and send it yourself {src:commands/tg-draft.md:204-217} {src:commands/tg-draft.md:225}.
