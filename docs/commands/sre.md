# /tg-sre

Helps you define what reliable means for a pipeline: targets, error budgets, alerts, runbooks and postmortems {src:commands/tg-sre.md:8}.

The command name is fixed: `/tg-sre`.

## When to use

Defining uptime or latency targets, building alerts and dashboards, writing incident runbooks, reducing repetitive manual work, drafting postmortems {src:commands/tg-sre.md:10}.

## What it does

The core workflow is six steps {src:commands/tg-sre.md:18-23}:

1. Assess reliability: architecture, SLOs, incidents, toil. Vault first.
2. Define SLOs: pick the indicators and set targets.
3. Verify alignment: confirm the targets reflect user expectations before going on.
4. Implement monitoring: golden signal dashboards and alerting.
5. Automate toil.
6. Test resilience: chaos experiments, and verify recovery meets the recovery targets before marking the work complete.

It must set SLOs with a user impact justification and must not write alerts without actionable runbooks {src:commands/tg-sre.md:36-37}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{vault}`, `{system_map}` and `{tickets}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-sre.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-sre.md:3}.

- Reads: your architecture notes and incident history in the vault, your monitoring config {src:commands/tg-sre.md:18}.
- Writes: alert rules, runbooks and notes, with outputs dropped into `{system_map}/architecture/` or the ticket folder `{ticket}/` {src:commands/tg-sre.md:12}.
- It runs no search and no vault git line, and writes no archive copy.

## Hooks and gate lines

No gate line applies. It is not part of the spec, arch, dev, qa chain, so the gate does not read it. The normal write guards still apply to any file it writes.

## Example

`/tg-sre` then "define a 99.9% target for the nightly load in T-001". It shows the 43.2 minute monthly budget, drafts the alert rules, and asks you to confirm the target before building alerts {src:commands/tg-sre.md:49} {src:commands/tg-sre.md:20}.
