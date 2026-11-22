# /tg-status

**It shows the current state of a client or a ticket. Client mode adds talking points for stakeholder questions; ticket mode gives a short sheet to keep open during a call.** Use it before a meeting or a call {src:commands/tg-status.md:5}. It writes nothing: the command file has no write step {src:commands/tg-status.md:24-118}.

The command name is fixed: `/tg-status [CLIENT]` or `/tg-status [TICKET-ID]`. With no argument it asks "Client status or ticket reference?". Keys matching `CD-\d+` or `S-\d+` are tickets; anything else is a client name {src:commands/tg-status.md:14-18}.

## What it does

Client mode {src:commands/tg-status.md:22}:

1. Runs `date` and states the window: 7 days back plus the rest of the current week {src:commands/tg-status.md:26-28}.
2. Reads four sources: Jira, the vault state files, the client's Slack channel and the calendar {src:commands/tg-status.md:30-45}.
3. Sorts into In progress, Recently done, Blocked and Coming up {src:commands/tg-status.md:49-53}.
4. Shapes the wording with the same narrative rules as `/tg-weekly`: outcome first, concrete numbers {src:commands/tg-status.md:57-61}.
5. Prints three layers: Signal, Say it as, Prepare for {src:commands/tg-status.md:65-77}.

Ticket mode {src:commands/tg-status.md:81}:

1. Reads the state file for status, confirmed approach, the known block, the next field, the unknown block and any blocker {src:commands/tg-status.md:87-92}.
2. Prints Done, Next, Blocker and Open, with no narrative and at most three lines per item {src:commands/tg-status.md:96-114}.

Rules for ticket mode: a blocker must name who owns the fix; the Open section is left out if nothing is open {src:commands/tg-status.md:115-116}. If there is no state file, it says so and offers `/tg-ticket {TICKET}` {src:commands/tg-status.md:118}.

## What it reads and writes

Folders are looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`: `{vault}` and `{tickets}`. If that prints `not set up`, it stops {src:commands/tg-status.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-status.md:3}.

- Reads: state files and session logs under both folder levels, `{tickets}/*/` and `{tickets}/*/*/` (client mode), and `{ticket}/[TICKET]-state.md` (ticket mode) {src:commands/tg-status.md:36-38} {src:commands/tg-status.md:87}.
- Reads in client mode: Jira, Slack and calendar signals {src:commands/tg-status.md:32} {src:commands/tg-status.md:40} {src:commands/tg-status.md:44}. The command file does not say how these are read. A connector is off until first use and prints `not set up` before then (see [connectors](../connectors.md)) {src:docs/connectors.md:7}.
- Writes: nothing, and no vault git line.
- Scripts: none. It does not call `tg-search`.

## Hooks and gate lines

None apply. It writes no file and touches no `Status:` line.

## Stops

- No argument: it asks one question and waits {src:commands/tg-status.md:16}.
- No state file for the ticket: it says so and stops at the offer {src:commands/tg-status.md:118}.
- `tg_path` prints `not set up`: it stops {src:commands/tg-status.md:3}.

## What it never does

- Never adds narrative, translation or pushback prep in ticket mode {src:commands/tg-status.md:117}.
- Never writes, commits or posts anything.

## Where the command file disagrees with itself

- The key test only knows `CD-` and `S-` keys, so a key with any other prefix is treated as a client name {src:commands/tg-status.md:18}.
- Client mode says to read state files "for this client" but never says how a state file is tied to a client {src:commands/tg-status.md:36}.

## Example

```
/tg-status PROJ-330
```

Prints the ticket name and status, then Done, Next, Blocker and Open from the state file {src:commands/tg-status.md:87-92} {src:commands/tg-status.md:96-111}.
