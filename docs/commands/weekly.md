# /tg-weekly

**It summarizes what moved last Monday to Friday, grouped by client, in three layers: a signal list, a plain-language version for the client, and likely questions to prepare for.** Use it before a client or product conversation. The command gives no instruction to write a file, so the output stays in the chat {src:commands/tg-weekly.md:5} {src:commands/tg-weekly.md:94-108}.

The command name is fixed: `/tg-weekly [CLIENT?]`. With no argument it covers all clients, grouped by client. With a client name it covers that client only {src:commands/tg-weekly.md:12-15}.

## What it does

1. Announces the plan: which clients, the calculated window, which sources it will read and what the output holds. It waits for your confirmation before reading {src:commands/tg-weekly.md:22-28}.
2. Runs `date` and calculates the last Monday to Friday from the real date, not from session context. If today is Monday it uses the prior week, not the week that just started. It states the window out loud {src:commands/tg-weekly.md:34-36} {src:commands/tg-weekly.md:16}.
3. Reads signals from four sources {src:commands/tg-weekly.md:40}:
   - Jira: tickets with status moves or comments in the window; tickets with no activity are dropped {src:commands/tg-weekly.md:42-45}.
   - Vault: state files and session logs under `{tickets}` (both folder levels), session logs dated in the window, blocks that reference window activity, and detail Jira does not capture {src:commands/tg-weekly.md:47-50}.
   - Slack: client channels for the last 7 days, unresolved threads only {src:commands/tg-weekly.md:52-54}.
   - Calendar: client calls in the window, noting whether outcomes were captured in the vault {src:commands/tg-weekly.md:56-58}.
4. Filters to a signal list of what changed, what is stuck and what is coming, and says in one line what it dropped and why (or that nothing was dropped) {src:commands/tg-weekly.md:64-70}.
5. Explain-back gate: it shows the signal list only and asks "Does this signal list match what you remember from last week?". It waits for your confirmation or correction before building the other layers {src:commands/tg-weekly.md:76-80}.
6. Builds the translation and pushback layers with four writing principles: conclusion first, concrete numbers, answer the likely question, say what it means for the reader {src:commands/tg-weekly.md:84-88}.
7. Prints, per client, the sections Signal, Say it as and Prepare for {src:commands/tg-weekly.md:94-108}. A client with no movement gets an explicit "No movement last week" line {src:commands/tg-weekly.md:114}.
8. Ends by suggesting `/tg-close` after the call to log outcomes, decisions and action items {src:commands/tg-weekly.md:120}.

Output rules: Signal lists only items that changed in the window; Say it as is about what it means for the client's data or delivery; Prepare for has one to three questions per client and is omitted if the client has no sticky area {src:commands/tg-weekly.md:111-113}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{vault}` and `{tickets}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-weekly.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-weekly.md:3}. The vault read scans both folder levels {src:commands/tg-weekly.md:47}. Both names exist in the path loader {src:scripts/core/paths.py:35} {src:scripts/core/paths.py:56}.

- Reads: ticket state files and session logs in the vault, plus Jira, Slack and calendar data {src:commands/tg-weekly.md:42-58}.
- Writes: nothing. I searched the command for a write, commit or archive step and found none.
- Scripts: only `$TOLLGATE_HOME/scripts/core/tg_path`, which exists {src:commands/tg-weekly.md:3}. No search, cost or state-check script.
- Vault git: no commit step. For the vault git modes see [tg_vault_git](../scripts/core/tg_vault_git.md).

## Hooks and gate lines

It writes no gate line and names no hook.

## Stops

- Waits for your confirmation of the plan {src:commands/tg-weekly.md:28}.
- Waits for your answer at the explain-back gate before the translation and pushback layers {src:commands/tg-weekly.md:76-80}.

## Notes

- How it finds ticket folders. The vault read names both folder levels, `{tickets}/*/` and `{tickets}/*/*/` {src:commands/tg-weekly.md:47}. That covers a flat vault (`02-tickets/KEY/`) and a nested one (`02-tickets/PREFIX/KEY/`, for example `02-tickets/PROJ/PROJ-312/`).
- The command has no numbered Step 5. After Step 4 the text jumps to an unnumbered block of writing principles and then Step 6 {src:commands/tg-weekly.md:74} {src:commands/tg-weekly.md:84-92}.
- The role line promises a "book-backed narrative", but the command names no book or source for it {src:commands/tg-weekly.md:5}.
- With a client argument, the filter is stated for the grouping but not for each source; only the Slack and vault reads are described as client channels or state files without saying how they are narrowed {src:commands/tg-weekly.md:15} {src:commands/tg-weekly.md:47} {src:commands/tg-weekly.md:52}.
- The command text uses the unfilled placeholder `{NAME}` {src:commands/tg-weekly.md:70}.
- `/tg-status` scans both folder levels too: `{tickets}/*/` and `{tickets}/*/*/` state files for this client {src:commands/tg-status.md:36}.

## What it never does

- It never builds the translation or pushback layers before you confirm the signal list {src:commands/tg-weekly.md:76-80}.
- It never skips a client silently when nothing moved {src:commands/tg-weekly.md:114}.
- It never relies on session context for the date {src:commands/tg-weekly.md:35}.

## Example

```
/tg-weekly
```

On a Monday it states the prior Monday to Friday as the window, shows a signal list per client, waits for you to confirm it, then prints Signal, Say it as and Prepare for per client {src:commands/tg-weekly.md:16} {src:commands/tg-weekly.md:36} {src:commands/tg-weekly.md:76-80} {src:commands/tg-weekly.md:94-108}.
