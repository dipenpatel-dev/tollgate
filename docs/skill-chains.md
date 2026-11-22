# Skill Chains: How to Work a Ticket

Created by Dipen Patel.

> Every Tollgate command starts with `tg-`, for example `/tg-ticket`, `/tg-start` and `/tg-close`. The name is fixed: there is no prefix to choose at install time. There are 28 commands in `commands/`, one file each. {src:install.sh:1145-1148}

---

## The Model

Every ticket moves through the same phases: orient, specify, design, build, review.

Each phase is a skill. Each skill reads the output of the previous skill. You never start a phase cold because the previous skill left a state file in the vault.

The chain is not rigid. Bug tickets need `/tg-support` before the spec. Coordination tickets stop after `/tg-ticket`. Use the chain that matches the ticket type.

---

## Ticket Types and Their Chains

### Coordination ticket
A ticket where the work is investigation, a decision, or a status update. No code change.

```
/tg-start ticket [ID]
/tg-ticket [ID]
/tg-close
```

`/tg-ticket` orients you to the ticket from the vault first and drafts the opening comment. When the tracker connector (Jira, for example) is set up, it also checks the vault against the tracker for contradictions. Takes 10 minutes.

---

### Bug ticket
A ticket where production data is wrong and you need to trace root cause from source to silver.

```
/tg-start
/tg-ticket [ID]
/tg-support [ID]
/tg-spec [ID]
/tg-arch [ID]
[approve design]
/tg-dev [ID]
/tg-qa [ID]
/tg-close
```

`/tg-support` does the diagnostic work: INTAKE (reproduce the bug, classify it by tier), TROUBLESHOOT (trace source to silver), HANDOFF PACKAGE (root cause + fix recommendation). The spec and arch skills then build on the handoff.

---

### Build ticket
A new feature, new pipeline, or new schema change.

```
/tg-start
/tg-ticket [ID]
/tg-spec [ID]
/tg-arch [ID]
[approve design]
/tg-dev [ID]
/tg-qa [ID]
/tg-close
```

`/tg-spec` produces requirements, acceptance criteria, and success metrics. `/tg-arch` produces design options with a recommendation. You approve the design before implementation starts.

---

### Learning session
Not a ticket. A session to build understanding of Databricks, Unity Catalog, or a pipeline.

```
/tg-start learn
/tg-learn [topic]
/tg-close
```

`/tg-learn` builds mental models through questioning, challenges, and explain back. It tracks your learning state across sessions.

---

### Client call prep
Before a weekly client call.

```
/tg-start
/tg-weekly [CLIENT]
/tg-close
```

`/tg-weekly` pulls the client's recent tickets, surfaces anything that needs to be communicated, and builds a signal list and talking points for the call.

---

## How State Carries Forward

Each skill writes a state file in the vault at `02-tickets/{KEY}/{KEY}-state.md`. The gate also finds `02-tickets/PREFIX/KEY/` (prefix matched without case). The exact lines the skills write and check are listed in `docs/gate-lines.md`. The next skill reads this file to pick up where the last session left off.

If you close a session without `/tg-close`, the state file may be stale. Run `/tg-sync` at the start of the next session to verify state before continuing.

### Vault git and commits

How the vault is saved is one setting, `vault_git`, chosen at install time and stored in your paths file: `none`, `local` or `remote`. Commands read it with `$TOLLGATE_HOME/scripts/core/tg_vault_git`. {src:commands/tg-close.md:272}

- `none`: the vault is plain files. Commands list what they wrote and print no git lines.
- `local`: the vault is a git repo. Commands print the `git add` and `git commit` lines.
- `remote`: same, plus a `git push` line.

Commands never run those lines. `/tg-dev`, `/tg-qa` and `/tg-close` each print the vault lines at the end of their run, and you run them yourself. `/tg-close` prints the commit text and you commit. The one exception to "no commits by a command" is `/tg-dev`: it still commits each work block on a feature branch in the code repository (`feature/{KEY}-B-{NN}`, then a squash merge onto the ticket branch). That is code, not the vault.

---

## Gates and Pause Points

Every skill has at least one pause point where you confirm the output before the skill proceeds. This is not optional.

Key gates by skill:

| Skill | Gate |
|---|---|
| `/tg-ticket` | Explain back: you state your read of the ticket before the skill accepts it |
| `/tg-spec` | RESTATE gate: the skill restates the problem before writing requirements |
| `/tg-arch` | Design approval: you approve the recommended design before implementation |
| `/tg-dev` | TEACHING gate: you explain the approach before the skill writes code |
| `/tg-qa` | Full QA report: you review findings before routing to fix or approve |
| `/tg-close` | Session log review: you confirm the session record before the skill prints the vault commit text |

A gate is where your judgment replaces Claude's. Don't skip them.

**Hook enforced gates.** Three of these are also checked by a hook before the skill starts, so skipping them is not possible, whether you type the command or Claude calls the skill itself. `/tg-arch` is blocked until the spec shows `Status: APPROVED` and the state file shows `SPEC_APPROVED`. `/tg-dev` is blocked until the design shows `Status: DESIGN_APPROVED` and the state is `DESIGN_APPROVED` or `IN_DEV`. `/tg-qa` is blocked until the state is `DEV_COMPLETE`, the spec and design are approved, and the edge case validation file shows `Status: DOCUMENTED` or `Status: VALIDATED`. A block names the file and the line it expects. The hooks are written in Python and need Python 3.12 or later (`install.sh` lines 143-153), and they fail closed only on Claude Code 2.1.295 or later (`install.sh` lines 8, 401-435). The exact lines are in [Gate lines](gate-lines.md), and the hook is described in the [Hook Reference](hooks.md). Separately, `gh pr create` is blocked until you approve the PR details.

---

## When to Stop the Chain

Stop the chain when:
- The ticket scope changes and the current spec no longer matches. Restart `/tg-spec`.
- QA finds a design gap. Route back to `/tg-arch`, not `/tg-dev`.
- A blocker surfaces that requires a cross team decision. Flag it in your tracker (draft the note, you send it), run `/tg-close`, wait.

Never push code to resolve a design gap discovered in QA. Fix the design first.
