# /tg-support

Use it to find out why something is wrong, and to decide where the ticket goes next. It diagnoses. It never designs a fix and never changes code {src:commands/tg-support.md:12}.

The command name is fixed: `/tg-support {KEY}`. There is no mode flag; routing is decided in the triage step {src:commands/tg-support.md:27} {src:commands/tg-support.md:30}.

## When to use it

A ticket reports wrong, missing or odd data or behavior, and the cause is not yet known. `/tg-ticket` sends bugs here first. You can also run it directly with a ticket key {src:commands/tg-support.md:30}.

## What it does

1. Reads the ticket state, the parent ticket (if any), the client note, the four standards and any pipeline doc named in the state {src:commands/tg-support.md:41-45}.
2. INTAKE: describes the problem as the user sees it. You confirm the framing at gate 1 {src:commands/tg-support.md:55} {src:commands/tg-support.md:88}.
3. TROUBLESHOOT: traces the data layer by layer, source to product, runs a mandatory pattern scan for the same bug elsewhere, and counts the impact. You confirm that all blockers are found at gate 2 {src:commands/tg-support.md:96} {src:commands/tg-support.md:129} {src:commands/tg-support.md:136-140} {src:commands/tg-support.md:171-173}.
4. TRIAGE: picks one route. If the criteria are ambiguous it defaults to Tier 2 and says why {src:commands/tg-support.md:200}.
   - Tier 1: operational fix, no code change. It writes a resolution file and stops {src:commands/tg-support.md:234} {src:commands/tg-support.md:272}.
   - Tier 2: code or pipeline bug. It writes a support handoff and a starter prompt for `/tg-spec` {src:commands/tg-support.md:276} {src:commands/tg-support.md:341}.
   - Enhancement: the system works as designed. It writes a brief for `/tg-whiteboard` {src:commands/tg-support.md:358} {src:commands/tg-support.md:388}.
5. Gate 3, the learning gate: you explain the root cause and the route in two sentences before any handoff file is written. If you say "skip" it pushes back once, then proceeds {src:commands/tg-support.md:218-222}.

## Reads and writes

Folders are not fixed paths. The command looks up `{tickets}`, `{system_map}`, `{output}` and `{vault}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-support.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-support.md:3}.

Reads: the state file `{ticket}/{KEY}-state.md`, the parent state, the client and schema notes, and the standards {src:commands/tg-support.md:41-45} {src:commands/tg-support.md:103}. The vault is looked up first. The ticket tracker is reached only through a connector, which is off until first use; with no setup it prints `not set up` and the command works from the vault and tells you what is missing {src:commands/tg-support.md:32}.

Writes to `{ticket}/`: `{KEY}-resolution.md`, `{KEY}-support-handoff.md` or `{KEY}-enhancement-brief.md` (one, by route), the state file, and a session log; the same entry goes to the archive under `{output}` {src:commands/tg-support.md:230} {src:commands/tg-support.md:260} {src:commands/tg-support.md:264}.

It does no vault git and no search lookups. It runs no commit and never posts to the tracker or chat tool {src:commands/tg-support.md:398} {src:commands/tg-support.md:405}.

## Hooks and gate lines

It sets the state file `Status:` line to one of three values, by route: `RESOLVED_TIER_1`, `SUPPORT_COMPLETE` or `ENHANCEMENT_PROPOSED` {src:commands/tg-support.md:261} {src:commands/tg-support.md:319} {src:commands/tg-support.md:380}. For Tier 2 it must be the only `Status:` line and the first in the file {src:commands/tg-support.md:319}. See `docs/gate-lines.md`. The gate does not require this step for spec, arch, dev or qa. The write guards still protect `$TOLLGATE_CODE_DIR`, which this command only reads {src:commands/tg-support.md:403}.

## Example

    /tg-support T-001

You confirm the framing, then the diagnosis. Say the root cause is a filter that drops rows with an empty key. The route is Tier 2. The command writes `T-001-support-handoff.md`, sets the state to `SUPPORT_COMPLETE`, and prints a starter prompt for a fresh thread {src:commands/tg-support.md:276} {src:commands/tg-support.md:319} {src:commands/tg-support.md:338-341}.
