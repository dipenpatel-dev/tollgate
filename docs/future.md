# Future Iterations

Created by Dipen Patel.

This document captures planned improvements and the direction the system is heading. Nothing here is committed. Items reflect intent, not schedule. Ordered by priority, not complexity.

---

## Priority 1: Team-Level Deployment

**Goal:** All team members run the same skill versions, shared patterns propagate automatically, and a common knowledge base replaces per-person silos.

**Why it is not built yet:** Adoption comes first. The team-level system has no value until individuals are actually running the chain on real tickets. Once each team member has worked two or three tickets, the patterns worth sharing will be obvious. Building the architecture before that signal exists risks designing for the wrong problems.

**When to build it:** After two to four weeks of individual adoption, when repeated corrections and patterns emerge across users.

---

### What the Team-Level System Looks Like

**Two-tier repo structure:**

```
team-repo/              shared by everyone, hosted on GitHub (org or team)
  ├── commands/         skill files, everyone gets identical versions
  ├── standards/        voice, technical, pipeline standards
  ├── CLAUDE.md         shared behavior rules (identity section blank)
  └── team-memory/      validated patterns from real tickets

personal-fork/          each person's fork of team-repo
  ├── memory/           personal feedback, stays in personal fork
  └── CLAUDE.md         identity filled in on top of team base
```

**How shared learning flows:**

1. A person works a ticket and `/tg-close` surfaces a correction or validated pattern
2. They decide: is this pattern worth sharing with the team?
3. If yes: they open a PR to `team-repo/team-memory/` with the memory file
4. The team lead reviews and merges
5. Everyone pulls `team-repo` on their next session and inherits the pattern

No automatic sync. PRs are the review gate. This keeps team memory intentional rather than noisy.

**Two-vault model:**

```
team-vault/             shared read/write, backed by private team GitHub repo
  ├── 01-system-map/    pipelines, clients, architecture, benefits everyone
  └── 03-knowledge-base/decisions/  team decisions that apply to all tickets

personal-vault/         each person's own vault, not shared
  ├── 02-tickets/       individual ticket state and session logs
  └── 03-knowledge-base/learnings/  personal learnings
```

Skills read from the team vault for system context and from the personal vault for ticket state. `/tg-close` writes session logs to the personal vault and may promote patterns to the team vault via PR.

**Install path for team members:**

```bash
# Fork the Tollgate repo to your personal account
git clone <your-fork-url> ~/Developer/tollgate
cd ~/Developer/tollgate
./install.sh
```

The installer needs one addition: a `team repo URL` prompt that sets the upstream remote so members can pull team updates without losing personal customizations.

**Uniform skills across the team:**

The core goal. Every team member runs the same `/tg-ticket`, `/tg-spec`, `/tg-arch`, `/tg-dev`, `/tg-qa`, and `/tg-support` versions. When the team lead merges a skill improvement, every member gets it on their next `git pull` and `./install.sh`. No divergence, no version drift.

---

## Priority 2: Vault Backup Without Running Git for You

**Current state:** The vault git setting (`vault_git`: `none`, `local` or `remote`) decides what `/tg-close`, `/tg-dev` and `/tg-qa` print at the end of a run. With `local` they print the `git add` and `git commit` lines, with `remote` they add a `git push` line, and with `none` they only list the files written. They never run the lines: you do. A separate scheduled job, `scripts/cron/backup_vault.sh`, makes an encrypted copy of the vault outside any session. {src:commands/tg-close.md:272}

**Open question:** Whether a command should ever run the vault commit or push itself. It does not today, on purpose: a command that commits your notes would act on your vault without your yes. If this changes, it needs a guard so a failed push (network down, merge conflict from another device) cannot block a session close, and it would be an explicit opt-in on top of the `vault_git` setting.

---

## Priority 3: Script Library Bootstrapping

**Current state:** `TOLLGATE_SCRIPTS` is a defined folder where Claude saves reusable scripts. The folder exists after install but contains nothing.

**Goal:** Ship a starter set of scripts for common data integration tasks (row counts, schema diffs, null checks, pipeline run status) that users can run immediately and that Claude builds on rather than regenerating from scratch.

**Format:** Each script in the `TOLLGATE_SCRIPTS` folder follows a standard header (Author, Date, Scope, Usage) and is callable by Claude during sessions.

---

## Priority 4: Skill Discovery for New Users

**Current state:** New users run `/tg-start` and are told to invoke `/tg-ticket [ID]`. They do not know which other skills exist or when to use them until they read the docs.

**Goal:** `/tg-start` on a first run detects that no vault state files exist and offers a two-minute orientation: lists available skills, explains when each is used, and suggests a first ticket as a guided example.

---

---

## Completed

These items were planned and are now shipped.

**Cross-platform installer.** The installer detects the OS at runtime and uses macOS Keychain on macOS, GNOME Secret Service on Linux (without `secret-tool` it refuses to store a token), and Windows Credential Manager on Windows. No tokens are stored in any file.

---

## Non-Goals

These will not be built:

- **Automatic memory sync without review.** Team memory should require a human decision to promote a pattern. Automatic sync produces noise and erodes trust in the memory layer.
- **Real-time collaboration.** Claude Code is a per-user tool. Shared sessions or simultaneous multi-user use are not in scope.
- **Replacing the tracker or Obsidian.** The vault is the first source. A tracker such as Jira is an optional connector. The system does not replace either tool.
