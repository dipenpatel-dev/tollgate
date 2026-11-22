# /tg-devops

Plans and checks the way code moves from a repo to a running system, and refuses to deploy to production without your explicit yes {src:commands/tg-devops.md:8} {src:commands/tg-devops.md:23}.

The command name is fixed: `/tg-devops`.

## When to use

Setting up CI, a deployment pipeline, environment promotion (dev to staging to prod), release automation, production troubleshooting or an incident runbook {src:commands/tg-devops.md:10}.

## What it does

The core workflow is seven steps {src:commands/tg-devops.md:18-24}:

1. Assess the application and environments, looking in the vault first for design notes.
2. Design the pipeline structure and deployment strategy.
3. Implement the workflow configs.
4. Validate: lint configs, run tests, confirm no destructive changes.
5. Plan the rollout: target environment, summary, rollback command, validation plan.
6. Approve and deploy: for production or customer-facing targets it presents the summary and rollback plan, asks for explicit approval, and stops with a blocked verdict if approval is withheld.
7. Monitor: set up alerts and confirm the rollback procedure is ready before going live.

It must not deploy to production without explicit approval, use the `latest` tag in production, or store secrets in code or CI variables {src:commands/tg-devops.md:36-39}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{vault}`, `{system_map}` and `{tickets}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-devops.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-devops.md:3}.

- Reads: your repo and any existing design notes in the vault {src:commands/tg-devops.md:18}.
- Writes: pipeline files in your repo, with notes dropped into `{system_map}/architecture/` or the ticket folder `{ticket}/` {src:commands/tg-devops.md:12}.
- It runs no search and no vault git line, and writes no archive copy.

## Hooks and gate lines

No gate line applies. It is not part of the spec, arch, dev, qa chain, so the gate does not read it. The normal write guards still apply to any file it writes.

## Example

`/tg-devops` then "set up CI for ticket T-001". It proposes a pipeline, lints it, shows the rollout plan with the rollback command, and stops for your approval before anything reaches production {src:commands/tg-devops.md:21-23}.
