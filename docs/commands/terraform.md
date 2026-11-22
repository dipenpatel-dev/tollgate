# /tg-terraform

Turns manual cloud setup into versioned infrastructure code, and applies nothing until you approve the plan {src:commands/tg-terraform.md:8} {src:commands/tg-terraform.md:24}.

The command name is fixed: `/tg-terraform`.

## When to use

Provisioning cloud resources, data platform workspace configuration, access permissions, storage mounts, remote state setup, or any cloud resource that exists only as a manual click {src:commands/tg-terraform.md:10}.

## What it does

The core workflow is seven steps {src:commands/tg-terraform.md:18-24}:

1. Analyze the infrastructure, looking in the vault first for design notes.
2. Design composable modules.
3. Implement remote state with locking and encryption.
4. Secure the infrastructure.
5. Validate: `terraform fmt`, `terraform validate`, then `tflint`, fixing all errors first.
6. Plan: `terraform plan -out=tfplan`, summarizing creates, updates, deletes and any destructive action.
7. Approve and apply: it asks for explicit approval before `terraform apply tfplan`, and refuses to apply if approval is withheld or destructive changes are unacknowledged.

After any fix it returns to step 5 before re-running the plan {src:commands/tg-terraform.md:35}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{vault}`, `{system_map}` and `{tickets}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-terraform.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-terraform.md:3}.

- Reads: your existing Terraform files and any design notes in the vault {src:commands/tg-terraform.md:18}.
- Writes: `.tf` files in your repo, with outputs dropped into `{system_map}/architecture/` or the ticket folder `{ticket}/` {src:commands/tg-terraform.md:12}. It runs `terraform apply tfplan` only after your explicit approval {src:commands/tg-terraform.md:24}.
- It runs no search and no vault git line, and writes no archive copy. It must not commit `.terraform` directories {src:commands/tg-terraform.md:52}.

## Hooks and gate lines

No gate line applies. It is not part of the spec, arch, dev, qa chain, so the gate does not read it. The normal write guards still apply to any file it writes.

## Example

`/tg-terraform` then "put the storage account for T-001 in code". It writes the module, runs format, validate and lint, shows the plan with every create, update and delete, and waits for your yes before applying {src:commands/tg-terraform.md:22-24}.
