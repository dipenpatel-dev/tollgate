# /tg-ticket

Use it first on any ticket. It reads everything available, classifies the ticket and tells you which command runs next. It never runs the later steps itself {src:commands/tg-ticket.md:28}.

The command name is fixed: `/tg-ticket {KEY}`. If no key is given, it asks which ticket {src:commands/tg-ticket.md:17-20}.

## When to use it

You start work on a ticket, or pick one up cold. Run it with the ticket key.

## What it does

1. Looks in the vault first. Only if the vault file is missing or a stub does it go to the ticket tracker, and only through a connector. A connector is off until first use, and one with no setup prints `not set up`; the command then works from the vault and says which source is missing {src:commands/tg-ticket.md:22} {src:commands/tg-ticket.md:65}.
2. Runs a search for related notes with `$TOLLGATE_HOME/scripts/search/tg-search query "[ticket keywords]" --top 8` and reads results scoring 0.5 or higher. If the script is missing or prints `not set up`, it searches the vault with grep and says so {src:commands/tg-ticket.md:69-71}. With fewer than 3 such results it also runs `tg-search health --top 5` and shows it under VAULT COVERAGE {src:commands/tg-ticket.md:78-82}.
3. Checks whether the ticket touches regulated personal data. If so it flags it and waits for your acknowledgment {src:commands/tg-ticket.md:73-75}.
4. Shows an ORIENT block: context, known facts, unknowns, assumptions, contradictions. A high-confidence contradiction stops the run until you resolve it {src:commands/tg-ticket.md:107-148}.
5. Asks you for a two-sentence explain-back. This is the only pause point, and your framing drives the classification {src:commands/tg-ticket.md:156-164}.
6. Classifies the ticket (bug, new build, research, coordination, communication, documentation) and names the type it rejected {src:commands/tg-ticket.md:172-181}.
7. For bug, build and research tickets it writes the state file with `Status: ROUTED`, drafts the opening ticket comment, and prints a starter prompt for the first command of the chain in a fresh thread {src:commands/tg-ticket.md:198-201}. The other types it handles directly {src:commands/tg-ticket.md:232-233}.

## The chain and the gate

Bug: `/tg-support`, `/tg-spec`, `/tg-arch`, `/tg-dev`, `/tg-qa`. New build starts at `/tg-spec`. Research starts at `/tg-explore` {src:commands/tg-ticket.md:174-176}.

The gate, not this command, enforces the order (see `docs/gate-lines.md`). If a later command is blocked, go back to the missing step. Nothing here skips it {src:commands/tg-ticket.md:35}.

## Reads and writes

Folders are not fixed paths. The command looks up `{tickets}`, `{system_map}` and `{vault}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-ticket.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-ticket.md:3}. New tickets are created at `{tickets}/PREFIX/KEY/`, where PREFIX is the upper case letters before the hyphen {src:commands/tg-ticket.md:198}.

Reads `{ticket}/{KEY}-state.md`, the parent state, and the client and pipeline notes {src:commands/tg-ticket.md:59-62}. Writes the state file and a session log {src:commands/tg-ticket.md:198} {src:commands/tg-ticket.md:286}. It does no vault git and writes no archive copy. It never posts to the tracker or the chat tool; you post {src:commands/tg-ticket.md:315}.

## Example

    /tg-ticket T-001

It shows ORIENT, you answer in two sentences ("wrong totals in a report; find out why"), and it classifies a bug. It writes `T-001-state.md` with `Status: ROUTED` and prints a starter prompt for `/tg-support T-001` {src:commands/tg-ticket.md:198} {src:commands/tg-ticket.md:221-225}.
