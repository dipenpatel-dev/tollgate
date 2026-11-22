# /tg-arch

**It turns an approved spec into an approved design: the approach, why it holds up, and a plan split into small work blocks.** Use it after `/tg-spec`, in a fresh thread. It does not write code {src:commands/tg-arch.md:9}.

The command name is fixed: `/tg-arch [TICKET-KEY]` {src:commands/tg-arch.md:25}.

## What it does

1. Checks the entry rules. The spec's first `Status:` line must hold the approved value and the state file's `Status:` must be `SPEC_APPROVED`; otherwise it stops {src:commands/tg-arch.md:54-55}. It also runs an AC diff check: if an earlier design adds acceptance criteria the spec lacks, it stops {src:commands/tg-arch.md:47}.
2. Presents 2 to 3 design options with one recommendation, then runs an independent review of the recommendation (stage `arch-rec`) before gate 1 {src:commands/tg-arch.md:84} {src:commands/tg-arch.md:104}.
3. Runs the systems pass: four threat-model questions, a named idempotency mechanism, null handling, join types, performance, downstream impact, standards check {src:commands/tg-arch.md:159-181}.
4. Splits the work into blocks (B-01, B-02, ...) with a binary done-when each and an Execution Specification per block {src:commands/tg-arch.md:229-246}.
5. Runs a standards compliance check and an Execution Specification gate, then writes the design file {src:commands/tg-arch.md:296-312} {src:commands/tg-arch.md:318-327}.
6. Runs a second independent review (stage `arch-design`), updates the state file, writes the session log and archive, verifies AC coverage, then asks you to explain back in three sentences {src:commands/tg-arch.md:472} {src:commands/tg-arch.md:488} {src:commands/tg-arch.md:517-526} {src:commands/tg-arch.md:530-537}.

Four gates. Gate 1 confirms the recommendation, gate 2 the system integrity, gate 3 the block plan, gate 4 is the learning gate {src:commands/tg-arch.md:147-149} {src:commands/tg-arch.md:219-221} {src:commands/tg-arch.md:284-286} {src:commands/tg-arch.md:530-537}. If you say "skip" at gate 4 it pushes back once, then proceeds {src:commands/tg-arch.md:537}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{tickets}`, `{system_map}`, `{output}` and `{vault}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-arch.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-arch.md:3}.

- Reads: the ticket state file, the spec, the support handoff (Tier 2 bug path), the client note and schema files if they exist, and the standards documents {src:commands/tg-arch.md:37-43}. The vault is read first; outside services are connectors that are off until first use and print `not set up` with no setup {src:commands/tg-arch.md:45}.
- Writes: `{KEY}-design.md`, the state file update, review files `{KEY}-review-N-arch-rec.md` and `{KEY}-review-N-arch-design.md`, a session log, and an archive copy under `{output}` {src:commands/tg-arch.md:292} {src:commands/tg-arch.md:589} {src:commands/tg-arch.md:498} {src:commands/tg-arch.md:513}.
- Search: `$TOLLGATE_HOME/scripts/search/tg-search reference`, twice (medium stakes before the first review, high stakes in the systems pass) {src:commands/tg-arch.md:93} {src:commands/tg-arch.md:188}. It searches your own reference store. If it is missing or prints `not set up` or `no match`, the command says so in one line and carries on {src:commands/tg-arch.md:100}.
- Reviews: each independent review is one fresh Sonnet agent given only the review file path. There are exactly two; only you can raise that ceiling {src:commands/tg-arch.md:581} {src:commands/tg-arch.md:616}.
- Vault git: it never commits or pushes. It looks up the vault git mode with `$TOLLGATE_HOME/scripts/core/tg_vault_git`. Mode `none`: it skips git and lists the changed files. Mode `local`: it prints the add and commit lines, with message `{KEY}: design approved`, for you to run. Mode `remote`: it prints the add, commit and push lines {src:commands/tg-arch.md:550}. See [tg_vault_git](../scripts/core/tg_vault_git.md).

## Gate lines it must leave behind

Exact upper case, one `Status:` line per file, no dated approval line {src:commands/tg-arch.md:468} {src:commands/tg-arch.md:643}.

- Entry needs the spec line `Status: APPROVED` (source: commands/tg-arch.md:38) and the state line `Status: SPEC_APPROVED` {src:commands/tg-arch.md:37}.
- While drafting: design file `Status: DESIGN_COMPLETE` and state `Status: DESIGN_COMPLETE` {src:commands/tg-arch.md:331} {src:commands/tg-arch.md:489}.
- On your approval after the explain-back: design file and state both `Status: DESIGN_APPROVED`. It reads both files back before printing the starter prompt {src:commands/tg-arch.md:542-546}.

`/tg-dev` refuses to start unless both approved values hold {src:commands/tg-arch.md:544}. See `docs/gate-lines.md` for the line rules.

## Hooks that apply

- The arch gate hook runs the same two entry checks before this command starts. Only you can allow a one-time override, from a terminal; the command never writes an override file {src:commands/tg-arch.md:57}.
- The write guards, the patient-data scan and the status-citation check on markdown writes. The PHI pre-check also runs before each review dispatch {src:commands/tg-arch.md:615}.

## Example

Ticket `T-001`, spec approved. Type `/tg-arch T-001`. You get two options, pick the one that merges on a named key, confirm the threat model, and confirm a plan of 3 blocks. After you explain back the approach, why it holds, and how the blocks run, the command sets `DESIGN_APPROVED` in the design and state files and prints the starter prompt for `/tg-dev T-001` {src:commands/tg-arch.md:542-543} {src:commands/tg-arch.md:563}.
