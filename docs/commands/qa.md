# /tg-qa

Reviews the whole merged change as an adversary, runs the validation scenarios, and ends with a verdict and a routing slip. It never fixes anything {src:commands/tg-qa.md:9}.

The command name is fixed: `/tg-qa {KEY}` {src:commands/tg-qa.md:32}.

## When to use it

After `/tg-dev` has applied the final block. Run it in a fresh thread. Re-run it after each fix round; each run increments the round counter in the state file and in the findings file {src:commands/tg-qa.md:35} {src:commands/tg-qa.md:798}. It reviews the aggregate merged diff across all blocks, never one block {src:commands/tg-qa.md:35}.

## What it reads

Folders are looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`; if that prints `not set up`, it stops {src:commands/tg-qa.md:3}. `{ticket}` is the folder of one ticket, looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which finds flat or prefix folders {src:commands/tg-qa.md:3}.

- State, spec, design and validation files in `{ticket}/`, plus the support handoff on the Tier 2 bug path {src:commands/tg-qa.md:44-48}
- The five standards files and the schema files named by the design {src:commands/tg-qa.md:49-50}
- The merged diff `git diff main..HEAD` and `git log --oneline main..HEAD` in the working checkout recorded in the state file {src:commands/tg-qa.md:56-57}
- Background notes through `$TOLLGATE_HOME/scripts/search/tg-search ground`, once per run after the refusal checks {src:commands/tg-qa.md:88}. If the index is not grounded and the state file flags `phi_surface` or `touches_live_state`, it stops and asks you; otherwise it prints one line and continues. A missing or not-set-up script never blocks {src:commands/tg-qa.md:97} {src:commands/tg-qa.md:99}. Blocks whose session log says "Grounding: not grounded" are reviewed first {src:commands/tg-qa.md:109}.
- Reference notes through `tg-search reference` (situation `qa_review`), medium stakes before layer 1 and high stakes before the independent review. It never blocks the run {src:commands/tg-qa.md:120} {src:commands/tg-qa.md:302} {src:commands/tg-qa.md:882}.

## What it writes

- A review file `{KEY}-review-N-qa-integration.md` with an independent reviewer's findings. The reviewer is one fresh Sonnet agent given only the file path, and never sees the layer 1 findings. Two passes at most {src:commands/tg-qa.md:856} {src:commands/tg-qa.md:842-844} {src:commands/tg-qa.md:68}.
- The validation file: results filled in, and its `Status:` flipped from `DOCUMENTED` to `VALIDATED` only when every scenario is resolved. A scenario marked PENDING-LIVE counts as unresolved {src:commands/tg-qa.md:248}.
- `{KEY}-qa-findings.md`: layer 1 and layer 2 findings, reconciliation, the compliance gate (four threat questions and a scan of ten places PHI could leak), routing and verdict {src:commands/tg-qa.md:545-550} {src:commands/tg-qa.md:469-484}. The grounding line goes last under "Sources reviewed" {src:commands/tg-qa.md:107}.
- The state file `Status:` line, set to `QA_APPROVED` or `QA_BLOCKED`, plus the round, verdict, counts, routing and next-command lines {src:commands/tg-qa.md:656-665}.
- A session-log entry, the same entry in the output archive, and a tracker comment draft. It never posts the draft {src:commands/tg-qa.md:685} {src:commands/tg-qa.md:671}.

## Vault git

The command never commits the vault. After writing the findings file and the state update it looks up the mode with `$TOLLGATE_HOME/scripts/core/tg_vault_git` {src:commands/tg-qa.md:689-691}:

- `none`: skip git and list the files written {src:commands/tg-qa.md:692}.
- `local`: print the add and commit lines {src:commands/tg-qa.md:693}.
- `remote`: print the add, commit and push lines {src:commands/tg-qa.md:694}.

It prints them and never runs them; you run them {src:commands/tg-qa.md:696}. On an approved verdict it also prints the code push command `git -C [REPO_PATH] push origin feature/{KEY}` for you to run; it does not execute it {src:commands/tg-qa.md:716-717}.

## Gate lines it uses

| File | Before it runs | What it writes |
|---|---|---|
| State | `Status: DEV_COMPLETE`, and `last_block_applied` names the final block {src:commands/tg-qa.md:44} | `QA_APPROVED` or `QA_BLOCKED` {src:commands/tg-qa.md:656} |
| Spec | the approved status line (source: commands/tg-qa.md:45) | nothing |
| Design | `Status: DESIGN_APPROVED` {src:commands/tg-qa.md:46} | nothing |
| Validation | `Status: DOCUMENTED` or `Status: VALIDATED` {src:commands/tg-qa.md:47} | `Status: VALIDATED` {src:commands/tg-qa.md:248} |

The gate blocks `/tg-qa` if any of these is missing or malformed {src:commands/tg-qa.md:25}. A missing validation file, an incomplete implementation, an unapproved spec or design each stop the run and route to `/tg-dev`, `/tg-spec` or `/tg-arch` {src:commands/tg-qa.md:71-77}. Hooks that still apply: the PHI scan, the secret guard and the git guards.

## Stops and gates

Four confirm points: gate 1 (layer 1 findings), gate 2 (reconciliation, you adjudicate disagreements), gate 4 (the compliance gate, you say `proceed`), then the verdict, where you say `acknowledged` {src:commands/tg-qa.md:269} {src:commands/tg-qa.md:386-406} {src:commands/tg-qa.md:530} {src:commands/tg-qa.md:681}. If gate 1 finds PHI in the diff, nothing goes to the reviewer; the work goes back to `/tg-dev` first {src:commands/tg-qa.md:297}.

## Verdict

The verdict is approved only with zero CRITICAL, zero HIGH, the compliance gate passed and every MEDIUM closed in the session. Anything else is blocked {src:commands/tg-qa.md:539-540}. Each finding is routed to dev, arch, spec or support by where its root cause sits {src:commands/tg-qa.md:416-421}.

## Example

```
/tg-qa T-001
```

It finds the state at `DEV_COMPLETE` and the validation file at `DOCUMENTED`, runs the scenarios, reviews the diff, sends it to an independent reviewer, and reconciles. It finds one HIGH idempotency gap rooted in the design, so it writes `QA_BLOCKED` and prints a starter prompt for `/tg-arch T-001` {src:commands/tg-qa.md:656} {src:commands/tg-qa.md:730-731}.
