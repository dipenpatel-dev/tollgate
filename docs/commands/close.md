# /tg-close

**It closes a work block: it drafts the session log, vault notes and memory files, asks you to confirm one log entry, then writes the vault files and prints the commit text for you to run.** Use it at the end of every work block, even a short one {src:commands/tg-close.md:5-6}. It never commits anything itself {src:commands/tg-close.md:250} {src:commands/tg-close.md:277}.

The command name is fixed: `/tg-close` or `/tg-close [JIRA-ID]` {src:commands/tg-close.md:14}.

## What it does

The command lists seven checklist items with a pause between the fifth and sixth. The list below counts the pause as step 6 {src:commands/tg-close.md:20-32}.

1. **Review.** Looks back at what was done, decided, deferred and corrected. If ticket work was finished, it asks "What could still go wrong in what we built?", waits for the answer and keeps it under "Risks and Unknowns" {src:commands/tg-close.md:41-54}.
2. **Log.** Runs `date`, then `python3 $TOLLGATE_HOME/scripts/core/session_cost.py --mode=close --tasks "..."`. If the script is absent it writes `Cost: not tracked (session_cost.py not installed)`; if it exits non-zero it writes `Cost: not tracked (pricing constants not set)`. It drafts the entry for `{landing}/session-log.md` and replaces a draft for today if one exists. The file keeps 20 entries at most {src:commands/tg-close.md:60-91}.
3. **Vault entries.** Drafts the session notes, the state file handoff block, and only if there is real signal a decision, a learning or a pattern. A conversation file is drafted every session {src:commands/tg-close.md:97-137} {src:commands/tg-close.md:170-171}.
4. **Memory.** Drafts one memory file per correction or confirmed choice, plus a pointer line for `MEMORY.md` {src:commands/tg-close.md:177-202}.
5. **Health.** Checks that the vault is reachable and was clean at session open. It runs no script {src:commands/tg-close.md:208}.
6. **Pause.** Shows the session log entry and asks "Does this accurately capture the session?". Nothing is on disk yet at this point {src:commands/tg-close.md:214-220}.
7. **Dotfiles.** After you confirm, it checks whether the session created a new baseline for Tollgate, makes the edit if so, and runs the read-only `git -C $CLAUDE_DOTFILES status`. This runs on every close, even when nothing changed {src:commands/tg-close.md:237-257}.
8. **Commit.** Writes the vault files, scans them, then prints the commit text {src:commands/tg-close.md:263-285}.

## What it reads and writes

Folders are looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`: `{vault}`, `{landing}`, `{system_map}`, `{tickets}`, `{knowledge}` and `{conversations}`. If it prints `not set up`, the command stops and tells you to run setup {src:commands/tg-close.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-close.md:3}.

- Writes in the vault: `{landing}/session-log.md`, `{ticket}/{KEY}-session-YYYY-MM-DD.md` (with `-2` if that name exists today) and the ticket state file {src:commands/tg-close.md:75} {src:commands/tg-close.md:99-100} {src:commands/tg-close.md:122}.
- Optional vault files, only for real signal: `{knowledge}/decisions/`, `{knowledge}/learnings/`, `{knowledge}/patterns/` {src:commands/tg-close.md:127-134}.
- Writes a conversation file in `{conversations}/YYYY/MM-Month/` every session. That folder is gitignored and its files are never staged or committed {src:commands/tg-close.md:136-139}.
- Memory files go under the user's own `~/.claude/projects/[your-project-hash]/memory/`, outside the vault {src:commands/tg-close.md:185-186}.
- Script: `$TOLLGATE_HOME/scripts/core/session_cost.py` {src:commands/tg-close.md:67-71}. It exists in the repo.
- Script: `$TOLLGATE_HOME/scripts/core/tg_vault_git` for the vault git mode {src:commands/tg-close.md:272}. See [tg_vault_git](../scripts/core/tg_vault_git.md).
- It does not call `tg-search`.

## Commit text and vault git

The command prints the commit text and you commit. It never runs a git write {src:commands/tg-close.md:250} {src:commands/tg-close.md:277}.

- Dotfiles: it only runs `git -C $CLAUDE_DOTFILES status`, then prints the `add -A` and `commit` lines {src:commands/tg-close.md:245-254}.
- Vault: it looks up the mode with `tg_vault_git` {src:commands/tg-close.md:272}.
  - `none`: skip git and list the files written {src:commands/tg-close.md:273}.
  - `local`: print the add and commit lines {src:commands/tg-close.md:274}.
  - `remote`: print the add, commit and push lines {src:commands/tg-close.md:275}.
- If nothing was written to the vault, it skips this and says so {src:commands/tg-close.md:285}.

## Hooks and stop points

- Security scan before the commit text: a `grep` for token, password and patient markers over the files written this run. If anything flags, it stops, removes the text and scans again, and prints no commit text until clean {src:commands/tg-close.md:265-270}.
- Stops for your answer at the "could still go wrong" question and at the pause {src:commands/tg-close.md:52} {src:commands/tg-close.md:214-215}.
- It ends with a next-session starter prompt, every time {src:commands/tg-close.md:308} {src:commands/tg-close.md:365}.
- No gate line is written.

## What it never does

- Never commits or pushes: it prints the lines {src:commands/tg-close.md:277}.
- Never writes before the pause. The drafts stay in chat until you confirm {src:commands/tg-close.md:214-215}.
- Never puts PHI in the vault, memory files, session log or commit messages {src:commands/tg-close.md:362}.
- Never uses `cd` before git; it uses `-C /full/path` {src:commands/tg-close.md:364}.

## Where the command file disagrees with itself

- It says items 1 to 5 run without waiting for input, yet the review step waits for your answer to "what could still go wrong" {src:commands/tg-close.md:34} {src:commands/tg-close.md:52}.
- The health item is listed as "dead link delta + vault health check" and the pause shows "new dead links", yet step 5 runs no script and gives no way to measure a delta {src:commands/tg-close.md:28} {src:commands/tg-close.md:208} {src:commands/tg-close.md:228}.
- Memory files are drafted with "Do not write yet", and the commit step writes "all staged vault files". Memory lives outside the vault, so no step says when it is written, yet the final summary lists "memory files written" {src:commands/tg-close.md:202} {src:commands/tg-close.md:263} {src:commands/tg-close.md:298}.
- The checklist says dotfiles prints commit text "if changed", while step 6 says the status check runs every time {src:commands/tg-close.md:30} {src:commands/tg-close.md:256}.

## Example

```
/tg-close PROJ-330
```

It asks the risk question, drafts everything, shows the log entry and asks you to confirm. After you say yes it writes the vault files, prints the vault `git add` and `git commit` lines for you to run, and ends with a starter prompt for the next thread {src:commands/tg-close.md:214-220} {src:commands/tg-close.md:279-283} {src:commands/tg-close.md:308-323}.
