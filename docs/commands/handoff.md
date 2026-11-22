# /tg-handoff

**It writes the next skill's starter prompt into the ticket's state file and shows the prompt in chat.** Use it between two steps of the ticket chain, inside one session or when moving to a new thread. Nothing else is written, staged, committed or sent {src:commands/tg-handoff.md:5}. `/tg-close` is for session boundaries; this is for chain steps {src:commands/tg-handoff.md:5}. The chain itself is in [skill-chains](../skill-chains.md) {src:commands/tg-handoff.md:7}.

The command name is fixed: `/tg-handoff <next skill>` or `/tg-handoff <next skill> [JIRA-ID]`. Bare `/tg-handoff` prints the usage block and stops {src:commands/tg-handoff.md:15-21}. The next skill must be one of `/tg-ticket`, `/tg-support`, `/tg-spec`, `/tg-arch`, `/tg-dev`, `/tg-qa`; any other name stops it {src:commands/tg-handoff.md:23}.

## What it does

1. States the plan: read one state file, write three fields after you confirm, show the prompt, touch nothing else {src:commands/tg-handoff.md:31-35}. Runs `date` and does not trust the system date reminder {src:commands/tg-handoff.md:37}.
2. Finds the ticket. A supplied key is used if its state file exists; if not, it stops {src:commands/tg-handoff.md:45}. With no key it lists state files changed in the last 24 hours by file modification time {src:commands/tg-handoff.md:47-53}.
   - One candidate: that one {src:commands/tg-handoff.md:55}.
   - Two or more within 300 seconds: it asks you {src:commands/tg-handoff.md:56}.
   - Two or more more than 300 seconds apart: the newest {src:commands/tg-handoff.md:57}.
   - None: it asks you for the key {src:commands/tg-handoff.md:58}.
3. Reads the `## Skill Handoff State` block of the state file {src:commands/tg-handoff.md:64}.
4. Builds a starter prompt: the skill invocation, then two to four sentences naming the artifact to read, its status and the next gate {src:commands/tg-handoff.md:74-81}. The artifact depends on the next skill, for example the spec for `/tg-arch` and the design for `/tg-dev` {src:commands/tg-handoff.md:85-86}.
5. Shows the prompt and waits for an explicit yes {src:commands/tg-handoff.md:97-110}.
6. Upserts three fields in the block with targeted edits: `Next skill:`, `Starter prompt:` (in a fenced block) and `Last updated:` {src:commands/tg-handoff.md:116-120}.
7. Reads the three fields back and shows the path {src:commands/tg-handoff.md:130}.
8. Prints the prompt last, then stops. It does not start the next skill {src:commands/tg-handoff.md:136-150}.

## What it reads and writes

Folders are looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`: `{vault}` and `{tickets}`. If that prints `not set up`, it stops {src:commands/tg-handoff.md:3}. The folder of one ticket, `{ticket}`, is looked up with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which prints the flat folder or the one under its prefix folder. If that exits 1 with `not found`, the command says the ticket has no folder and stops {src:commands/tg-handoff.md:3}.

- Reads: `{ticket}/[JIRA-ID]-state.md` {src:commands/tg-handoff.md:32}.
- Writes: the same file, only the three fields above. If the block is missing it is added once, at the end of the file {src:commands/tg-handoff.md:66} {src:commands/tg-handoff.md:156} {src:commands/tg-handoff.md:162}.
- Shell: `date`, and `find {tickets} -name "*-state.md" -mmin -1440 -exec stat -f '%m %N' {} +` when no key is given {src:commands/tg-handoff.md:39-41} {src:commands/tg-handoff.md:50}.
- Scripts: only `tg_path` and `tg_ticket_dir` from `$TOLLGATE_HOME/scripts/core/` {src:commands/tg-handoff.md:3}. No `tg-search`, no vault git line.

## Hooks and gate lines

It never changes the `Status:` line; that belongs to the skill that finished the step {src:commands/tg-handoff.md:122}. Repeating the same command replaces the same three fields and adds no duplicates {src:commands/tg-handoff.md:124}.

## Stop points

- Confirm gate: cancel writes nothing and reports "Handoff cancelled. Nothing written." {src:commands/tg-handoff.md:110}.
- Missing state file, ambiguous ticket, missing artifact: it stops or asks rather than guessing {src:commands/tg-handoff.md:45} {src:commands/tg-handoff.md:56} {src:commands/tg-handoff.md:91}.
- If the handoff block holds patient-level detail it stops, flags it and waits {src:commands/tg-handoff.md:68}.

## What it never does

- Never runs git: no staging, commit or push {src:commands/tg-handoff.md:157}.
- Never posts to Jira, Slack, Confluence or Notion {src:commands/tg-handoff.md:158}.
- Never guesses the ticket {src:commands/tg-handoff.md:160}.
- Never copies PHI into the prompt or the file {src:commands/tg-handoff.md:164}.

## Where the command file disagrees with itself

- The role line says nothing else is written, but a missing handoff block is added to the file, which is more than three fields in one case {src:commands/tg-handoff.md:5} {src:commands/tg-handoff.md:66}. The command file counts that as part of the same state-file write.
- The `find` command uses the unresolved placeholder `{tickets}`; the `tg_path` lookup has to be done first. The same command also matches state files at any depth under `{tickets}`, so it finds both flat and prefix folders {src:commands/tg-handoff.md:3} {src:commands/tg-handoff.md:50}.

## Example

```
/tg-handoff /tg-arch PROJ-330
```

It confirms the state file exists, shows a prompt starting `/tg-arch PROJ-330` that points at the spec, and on your yes writes the three fields and prints the prompt to paste into a new thread {src:commands/tg-handoff.md:77-81} {src:commands/tg-handoff.md:104-107} {src:commands/tg-handoff.md:140-147}.
