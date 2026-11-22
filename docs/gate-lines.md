# Gate lines

This page is the single source for the exact lines that skills write and later skills check. If a skill file and this page disagree, this page wins and the skill file is a bug.

The gate reads one kind of line: `Status:`. It matches the dotfiles chain commands. Dated approval lines are no longer read.

## State file

Path: `$TOLLGATE_KNOWLEDGE/02-tickets/{KEY}/{KEY}-state.md`. The gate also finds `02-tickets/PREFIX/KEY/` (the prefix is the letters before the hyphen, matched without case), so a prefix folder between `02-tickets` and the key is fine.

Artifacts sit in the same folder:

- `{KEY}-spec.md`
- `{KEY}-design.md`
- `{KEY}-edge-case-validation.md`
- `{KEY}-qa-findings.md`

The ticket key is the argument of every chain skill, for example `T-001`.

## Status line

The state file has one `Status:` line. It is the first `Status:` line in the file. If a `## Skill Handoff State` block exists, the `Status:` line may sit inside it. A second `Status:` line with a different value is a malformed file; repeating the same value is accepted.

| Status value | Written by | Meaning |
|---|---|---|
| `ROUTED` | ticket | Ticket oriented, first skill chosen |
| `SUPPORT_COMPLETE` | support | Support handoff written |
| `RESOLVED_TIER_1` | support | Resolved without a build |
| `ENHANCEMENT_PROPOSED` | support | Enhancement path, no fix in support |
| `SPEC_APPROVED` | spec | Spec written after the explain-back |
| `DESIGN_COMPLETE` | arch | Design written, not yet approved |
| `DESIGN_APPROVED` | arch | Owner approved the design after the explain-back. Written to the design file and the state file |
| `IN_DEV` | dev | At least one block applied, more remain |
| `DEV_COMPLETE` | dev | Final block applied |
| `QA_BLOCKED` | qa | Review found blocking findings |
| `QA_APPROVED` | qa | Review passed |

The handoff skill never changes `Status:`.

## Status lines in the other files

The spec, design and edge-case validation files each carry their own first `Status:` line. The gate reads it the same way as the state file (same placement rule, same malformed rule).

| File | Accepted `Status:` value | Written by |
|---|---|---|
| `{KEY}-spec.md` | `APPROVED` | spec, after the explain-back |
| `{KEY}-design.md` | `DESIGN_APPROVED` (it starts as `DESIGN_COMPLETE`) | arch, after the owner's explain-back |
| `{KEY}-edge-case-validation.md` | `DOCUMENTED` or `VALIDATED` | dev writes `DOCUMENTED`; qa may flip it to `VALIDATED` |

Values are exact and upper case. `Status: approved` does not count. Anything else after the value (for example `APPROVED by me`) does not count.

## Placement rule

A `Status:` line counts only when it is outside fenced code blocks and starts at column one. A fence opens with 3 or more backticks or tildes and closes only with the same character, at least as many markers and no text after them. A placeholder never counts: `Status: [APPROVED]` is not a valid value. If a file has two `Status:` lines with different values, the file is malformed and the gate blocks.

## Last block applied

State key, spelled exactly `last_block_applied`. Values:

- `none` before the first block (a missing field means the same).
- `B-NN` after block NN is applied, with two digits, for example `B-03`.

The dev skill writes it after every block. The next dev run starts at the block after the one named. The qa skill checks that `Status:` is `DEV_COMPLETE` and that `last_block_applied` names the final block in the design work block plan.

## What each skill checks before it starts

| Skill | Checks |
|---|---|
| ticket, support, spec | No hard gate. Entry points. |
| arch | Spec `Status: APPROVED`. State `SPEC_APPROVED`. |
| dev | Design `Status: DESIGN_APPROVED`. State `DESIGN_APPROVED` (first block) or `IN_DEV` (later blocks). |
| qa | State `DEV_COMPLETE`. Spec `APPROVED`. Design `DESIGN_APPROVED`. Validation file `DOCUMENTED` or `VALIDATED`. |

## Override

The owner can let one skill through once. The owner creates `{KEY}-gate-override.md` from a terminal with one line: `Override: <skill> YYYY-MM-DD <reason>`. It works for that skill on that date only. This is the only dated line the gate reads. The model cannot write this file: the write guard denies Write, Edit and NotebookEdit, and a Bash guard denies shell commands that name it with a write verb or redirect (a pattern check on the command text, not a sandbox).

## Command names

The command names are fixed: the hook gates `/tg-arch`, `/tg-dev` and `/tg-qa`, whether you type them or Claude calls them through the Skill tool. There is no per-install prefix, and a leftover `TOLLGATE_SKILL_PREFIX` in the environment is ignored. {src:hooks/pre-prompt-expansion-check-gates.py:61}

## When the gate cannot check

If the arguments hold no ticket id, the gate allows and logs it. If an id is given but `TOLLGATE_KNOWLEDGE` is unset or no ticket folder with that id exists, the gate still allows, but it prints a visible warning that nothing was checked. If the gate itself fails while checking `arch`, `dev` or `qa`, it blocks that skill. {src:hooks/pre-prompt-expansion-check-gates.py:345-363}

Skills keep their stop wording in prose. A hook, if present, is a second layer, not a replacement.
