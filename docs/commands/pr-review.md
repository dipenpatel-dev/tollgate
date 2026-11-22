# /tg-pr-review

Reads someone else's pull request, writes a brief, and drafts up to three comments. It posts nothing: you decide what to post {src:commands/tg-pr-review.md:17} {src:commands/tg-pr-review.md:218}.

The command name is fixed: `/tg-pr-review N`, with optional `--repo owner/repo` and `--nits` {src:commands/tg-pr-review.md:24-26}.

## When to use

When you are asked to review a pull request. It cannot block a merge {src:commands/tg-pr-review.md:17}.

## What it does

1. Parses the arguments and finds the repo from the current folder's git remote unless `--repo` is given. If the remote is the vault repo or the lookup fails, it asks which repo {src:commands/tg-pr-review.md:29} {src:commands/tg-pr-review.md:39-43}.
2. Fetches the pull request with read-only `gh` commands only (`pr view`, `pr diff`, `api` with GET) {src:commands/tg-pr-review.md:35} {src:commands/tg-pr-review.md:48-50}.
3. Reads the ticket chain before producing any finding: the vault ticket folder first, the tracker connector only if the folder is missing or a stub, then the parent ticket. With no ticket found, `intent` is marked NOT EVALUATED {src:commands/tg-pr-review.md:59-70}.
4. Runs the review rules against added lines only. Red rules: `secret`, `phi-log`, `phi-doc`, `dyn-exec`, `breaking`. Yellow rules: `coverage`, `impact`, `intent` {src:commands/tg-pr-review.md:78} {src:commands/tg-pr-review.md:86-93}. Style rules run only with `--nits` {src:commands/tg-pr-review.md:97}.
5. Applies the output gates: no line numbers, every named artifact verified (else downgraded from a statement to a question), stale-ticket warning, PHI redaction, roles instead of names {src:commands/tg-pr-review.md:105-113}.
6. Ranks findings and drafts at most three comments; the rest go under "NOTED, NOT COMMENTED" {src:commands/tg-pr-review.md:127}.
7. Writes the brief and prints it, with the draft count, the file path and any gates that fired {src:commands/tg-pr-review.md:165} {src:commands/tg-pr-review.md:211-216}.

The command must not call the Skill tool during the run {src:commands/tg-pr-review.md:15}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{vault}`, `{tickets}` and `{output}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-pr-review.md:10}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-pr-review.md:10}.

- Reads: the pull request through the code host client, read only {src:commands/tg-pr-review.md:35}, and the ticket folder `{ticket}/` first {src:commands/tg-pr-review.md:63}. The ticket tracker is a connector that is off until first use; with no setup it prints `not set up`, the command continues with the vault copy and says the tracker was not read {src:commands/tg-pr-review.md:64}. A name, status, date or dependency in the output must come from a live tracker read; otherwise it is tagged unverified {src:commands/tg-pr-review.md:72}.
- Writes: one review brief at `{output}/reviews/YYYY/YYYY-MM-DD-pr-N.md`, creating the year folder if needed {src:commands/tg-pr-review.md:165}. Nothing is written to the pull request, and the command never calls a write endpoint of the code host {src:commands/tg-pr-review.md:17}.
- It runs no search and no vault git line, and no commit.

## Hooks and gate lines

No gate line applies. The brief carries no line numbers and no names, and a value shaped like a patient identifier is never quoted, in line with the phi scan hooks {src:commands/tg-pr-review.md:105} {src:commands/tg-pr-review.md:111} {src:commands/tg-pr-review.md:113}.

## Example

`/tg-pr-review 42` on a pull request for T-001 prints the brief and two draft comments. You copy the ones you want into the pull request yourself {src:commands/tg-pr-review.md:211} {src:commands/tg-pr-review.md:218}.
