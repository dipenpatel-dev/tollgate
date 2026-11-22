# /tg-dev

Builds one work block of an approved design and hands back a reviewed, squash-merged branch. It never re-designs {src:commands/tg-dev.md:9}.

The command name is fixed: `/tg-dev {KEY}` {src:commands/tg-dev.md:33}.

## When to use it

After `/tg-arch` has approved the design. Run it once per block, each time in a fresh thread; `last_block_applied` in the state file says which block is next {src:commands/tg-dev.md:36} {src:commands/tg-dev.md:53-54}. When the last block is done, it writes the validation scenarios and tells you to run `/tg-qa` {src:commands/tg-dev.md:55} {src:commands/tg-dev.md:570}.

## What it reads

Folders are looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`; if that prints `not set up`, it stops {src:commands/tg-dev.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-dev.md:3}.

- The ticket state, spec and design files in `{ticket}/`, and the support handoff on the Tier 2 bug path {src:commands/tg-dev.md:45-48}
- The five standards files {src:commands/tg-dev.md:49}
- Schema notes in `{system_map}/schemas/` named by the design {src:commands/tg-dev.md:50}
- Background notes from the knowledge index through `$TOLLGATE_HOME/scripts/search/tg-search ground`, once per block after gate A {src:commands/tg-dev.md:118}. The script prints a first line `STATE: ok`, `partial`, `empty` or `unavailable` {src:commands/tg-dev.md:123}. If the index is not grounded and the ticket state has `phi_surface` or `touches_live_state` true, it stops and asks you first. Otherwise it prints one line and continues {src:commands/tg-dev.md:127}. If the script is missing or prints `not set up`, it continues even on a flagged ticket {src:commands/tg-dev.md:129}.
- Reference notes through `tg-search reference`, twice (medium stakes before teaching, high stakes before the review). It never blocks the run {src:commands/tg-dev.md:158} {src:commands/tg-dev.md:284} {src:commands/tg-dev.md:616}.

## What it writes

- Code on a block branch `feature/{KEY}-B-NN` in the working checkout recorded in the state file, then squash-merged to `feature/{KEY}` {src:commands/tg-dev.md:72} {src:commands/tg-dev.md:86}. These code-branch commits are unchanged and expected {src:commands/tg-dev.md:633}.
- A review file `{KEY}-review-N-dev-bNN.md` with the independent reviewer's findings {src:commands/tg-dev.md:295} {src:commands/tg-dev.md:600}.
- State file updates and a session-log entry per block, plus the same entry in the output archive. The first line of the entry is the grounding line {src:commands/tg-dev.md:412-416} {src:commands/tg-dev.md:451-462}.
- On the final block only: `{KEY}-edge-case-validation.md` with the scenarios and no actual results {src:commands/tg-dev.md:493-495}.
- A tracker comment draft. It never posts it {src:commands/tg-dev.md:429}.

It never writes in `$TOLLGATE_CODE_DIR` {src:commands/tg-dev.md:629}.

## Vault git

The command never commits the vault. After the session log and archive it looks up the mode with `$TOLLGATE_HOME/scripts/core/tg_vault_git` {src:commands/tg-dev.md:466-468}:

- `none`: skip git and list the files written {src:commands/tg-dev.md:469}.
- `local`: print the add and commit lines {src:commands/tg-dev.md:470}.
- `remote`: print the add, commit and push lines {src:commands/tg-dev.md:471}.

It prints them and never runs them; you run them {src:commands/tg-dev.md:473}. The same step runs again on the final block, after the validation file is written {src:commands/tg-dev.md:521-534}. Only the vault is affected. Commits on the code branch in the working checkout still happen as before {src:commands/tg-dev.md:633}.

## Gate lines it uses

| File | Before it runs | What it writes |
|---|---|---|
| Design | `Status: DESIGN_APPROVED` {src:commands/tg-dev.md:46} | nothing |
| State | `DESIGN_APPROVED` (first block) or `IN_DEV` {src:commands/tg-dev.md:45} | `IN_DEV` when you say go at gate A {src:commands/tg-dev.md:107}, `DEV_COMPLETE` after the final block, plus `last_block_applied: B-NN` {src:commands/tg-dev.md:414-415} |
| Validation | none | `Status: DOCUMENTED` (final block only) {src:commands/tg-dev.md:501} |

The gate blocks `/tg-dev` if the design is not approved. The `Status:` line is edited in place, never repeated {src:commands/tg-dev.md:26}. Hooks that still apply: the code-folder write guard, the PHI scan on commands, and the git commit and push guards.

## Stops and gates

- Gate A: you say `go` to start a block. Gate B: you say `go` when the block is finished {src:commands/tg-dev.md:105} {src:commands/tg-dev.md:391}.
- It stops and sends you back to `/tg-arch` if a file outside the block scope must change, a library method does not exist, or a CRITICAL or HIGH review finding reveals a design flaw {src:commands/tg-dev.md:199-208} {src:commands/tg-dev.md:255-261} {src:commands/tg-dev.md:374-383}.
- It stops if the working checkout is missing on disk {src:commands/tg-dev.md:59}.
- Review ceiling: two reviews per block, by one fresh Sonnet agent given only the review file path {src:commands/tg-dev.md:590} {src:commands/tg-dev.md:578-580}.
- At the final block it also says in plain words what was built, then prints the starter prompt and stops {src:commands/tg-dev.md:542-544}.

## Example

```
/tg-dev T-001
```

Block B-01 of `T-001` starts. You say `go`. The state moves to `IN_DEV`. It teaches the concepts, writes the code, runs the review, fixes what you decide, squash-merges, prints the vault git lines for you to run, and prints a starter prompt for B-02 {src:commands/tg-dev.md:107} {src:commands/tg-dev.md:556}. After the last block the state reads `DEV_COMPLETE` and the validation file reads `Status: DOCUMENTED` {src:commands/tg-dev.md:570}.
