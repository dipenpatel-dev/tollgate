# /tg-spec

**It turns a ticket into a written, owner-approved spec: what to build and how to prove it works.** Use it first, before any design. It does not design or code {src:commands/tg-spec.md:9}.

The command name is fixed: `/tg-spec [TICKET-KEY]`. It is invoked by `/tg-ticket`, chained from `/tg-support` after a confirmed Tier 2 bug, or run directly {src:commands/tg-spec.md:24} {src:commands/tg-spec.md:27}.

## What it does

1. Reads the ticket state and the upstream note (support handoff, whiteboard verdict, product spec) from the vault. With no upstream note and no source in the state, it stops and asks where the spec comes from {src:commands/tg-spec.md:36-42} {src:commands/tg-spec.md:53}.
2. Restates the problem as an outcome, not a fix, and guards against anchoring on the upstream framing {src:commands/tg-spec.md:59-66}.
3. Writes numbered requirements and binary acceptance criteria (AC) {src:commands/tg-spec.md:113-141}.
4. Writes validation scenarios: sample size (at least 50 or justified), pass rate (85% default, higher for safety fields), named sub-scenarios at 100%, forbidden conditions {src:commands/tg-spec.md:181-210}.
5. Fills in scope, constraints, data dependencies, success metrics, open questions for the design step, standards and the definition of done {src:commands/tg-spec.md:291}.
6. Asks you to explain back, in two sentences, what is built and how it is proven. Only then it writes the spec file {src:commands/tg-spec.md:359-366}.

There are four gates, one per step. Each waits for your answer. Gate 4 is the learning gate; if you say "skip" it pushes back once, then proceeds {src:commands/tg-spec.md:107} {src:commands/tg-spec.md:175} {src:commands/tg-spec.md:283} {src:commands/tg-spec.md:368}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{tickets}`, `{system_map}`, `{output}` and `{vault}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-spec.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-spec.md:3}.

- Reads: the ticket state file, the parent ticket state for a sub-task, the upstream note, the client and schema notes if they exist, and the four standards documents {src:commands/tg-spec.md:36-45}. The vault is read first. The ticket tracker is a connector that is off until first use; with no setup it prints `not set up` and the command asks you to paste the description {src:commands/tg-spec.md:47}.
- Writes: `{KEY}-spec.md`, the state file update, a session log, and the same entry in the archive under `{output}` {src:commands/tg-spec.md:380} {src:commands/tg-spec.md:465} {src:commands/tg-spec.md:472}.
- Search: `$TOLLGATE_HOME/scripts/search/tg-search reference`, twice (medium stakes after the restate, high stakes before the validation gate) {src:commands/tg-spec.md:83} {src:commands/tg-spec.md:242}. It searches your own reference store. If it is missing or prints `not set up` or `no match`, the command says so in one line and carries on {src:commands/tg-spec.md:90}.
- Vault git: it never commits or pushes. It looks up the vault git mode with `$TOLLGATE_HOME/scripts/core/tg_vault_git`. Mode `none`: it skips git and lists the changed files. Mode `local`: it prints the add and commit lines, with message `{KEY}: spec approved`, for you to run. Mode `remote`: it prints the add, commit and push lines {src:commands/tg-spec.md:484}. See [tg_vault_git](../scripts/core/tg_vault_git.md).

## Gate lines it must leave behind

The arch gate reads these two lines. Both are upper case and exact, one `Status:` line per file {src:commands/tg-spec.md:465} {src:commands/tg-spec.md:380}.

- Spec file: the first `Status:` line holds the approved value from the template, `Status: APPROVED` (source: commands/tg-spec.md:386).
- State file: the one `Status:` line is `Status: SPEC_APPROVED` {src:commands/tg-spec.md:466}.

The command reads both files back before it ends, and `/tg-arch` refuses to start unless both hold {src:commands/tg-spec.md:476-480}. The header has an `Author:` line with your initials and an empty `Date:` field; no dated approval line is written {src:commands/tg-spec.md:461}.

## Hooks that apply

- The write guards that protect the code folder and scan for patient data.
- The status-citation check on markdown writes.
- The arch gate checks this command's output when you start `/tg-arch` {src:commands/tg-spec.md:480}.

## Example

Ticket `T-001`: "export drops rows with no patient id". Type `/tg-spec T-001`. You confirm the restated problem ("all eligible patients must be exported, even with a missing id"), confirm three AC, confirm one validation run of 500 rows with a named edge case, then explain back in two sentences. The command writes `T-001-spec.md` and sets the state to `SPEC_APPROVED`. Next, open a fresh thread and run `/tg-arch T-001` {src:commands/tg-spec.md:466} {src:commands/tg-spec.md:500}.
