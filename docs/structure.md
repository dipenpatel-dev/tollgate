# File Structure and Layout

Created by Dipen Patel.

This document shows where everything lives after a full install. Three locations work together every session.

---

## The Full Layout After Install

Everything lives under one base folder, named after you. The folders beside the vault use a stem: `tollgate` for a new install. An older install keeps the stem it saved, so its folders are never renamed.

```
~/Developer/dipen/                   ← your base folder (default: from your name)
│
├── tollgate-dotfiles/               ← this repo: commands, hooks, standards, config
│                                       git tracked, shareable with team
│
├── tollgate-knowledge/              ← your Obsidian vault
│                                       PHI-adjacent content lives here
│                                       git only if you chose local or remote
│
├── tollgate-scripts/                ← reusable scripts Claude generates
│                                       git tracked (optional)
│
├── tollgate-code/                   ← read-only mirror of the repos Claude reads
├── tollgate-dev/                    ← your active working checkouts
└── tollgate-library/                ← epubs and documents, outside the vault
```

The stem only names these folders. Commands have the fixed `tg-` prefix on every machine, and look the vault folders up when they run, so nothing depends on the stem.

```
commands   →  /tg-ticket   /tg-spec   /tg-arch   /tg-dev   /tg-qa   /tg-close  ...
variables  →  $TOLLGATE_KNOWLEDGE   $TOLLGATE_SCRIPTS   $TOLLGATE_MEETINGS   $CLAUDE_DOTFILES
```

Claude Code runtime:

```
tollgate-dotfiles/
        |
        | install.sh copies commands and config into
        ↓
~/.claude/                            Claude Code reads from here at runtime
        |
        | commands read and write state, logs, and decisions to
        ↓
tollgate-knowledge/                   your Obsidian vault ($TOLLGATE_KNOWLEDGE)
```

---

## 1. The Repo: {stem}-dotfiles/

> What is here before and after install. This is the folder you cloned and version-control.

```
{stem}-dotfiles/
│
├── install.sh                    ← run this once after cloning (and again to update or --uninstall)
│
├── README.md                     ← start here
├── SECURITY.md                   ← how to report a vulnerability, what is in and out of scope
│                                    (Tollgate is a guardrail for a cooperative model, not a sandbox;
│                                    native Windows is out of scope, use WSL)
├── VERSION, LICENSE
│
├── CLAUDE.md                     ← identity template (placeholders filled in at install)
│                                    Claude reads the installed copy at ~/.claude/CLAUDE.md
│
├── standards/                    ← the governing documents
│   ├── voice-standard.md         ← writing rules: conclusion first, bracket test,
│   │                                two voices, no intensifiers, no template filler
│   ├── technical-standards.md    ← code quality: type hints, 40-line limit,
│   │                                no magic numbers, explicit write modes
│   ├── pipeline-standards.md     ← pipeline rules: layer boundaries, idempotency,
│   │                                null handling, schema lineage
│   ├── coding-standards.md       ← Python and SQL formatting detail and examples
│   └── skill-standard.md         ← structural rules every skill file must follow
│                                    read this before writing a new skill
│
├── settings.json                 ← hook wiring and tool permissions template
│                                    merged into ~/.claude/settings.json at install by
│                                    installer/merge_settings.py: your own hooks, permissions
│                                    and env are kept, only Tollgate's entries are replaced
│                                    settings.local.json (machine specific) is in .gitignore
│
├── commands/                     ← the 29 commands, shipped with their final names
│   │                                install.sh copies these to ~/.claude/commands/
│   │                                under the same name, with your name and company filled in,
│   │                                and every $TOLLGATE_HOME/ script call rewritten to the
│   │                                absolute repo path (Claude Code refuses a command with an
│   │                                unresolved variable before it reads any permission rule;
│   │                                see docs/install.md and docs/variables.md)
│   │
│   ├── tg-ticket.md              ← /tg-ticket    route a ticket into the chain
│   ├── tg-support.md             ← /tg-support
│   ├── tg-spec.md                ← /tg-spec
│   ├── tg-arch.md                ← /tg-arch
│   ├── tg-dev.md                 ← /tg-dev
│   ├── tg-qa.md                  ← /tg-qa
│   │
│   ├── tg-start.md               ← /tg-start        open a session, vault state, blockers
│   ├── tg-close.md               ← /tg-close        session log, memory, prints the vault commit text
│   ├── tg-draft.md               ← /tg-draft        write any message going to another person
│   ├── tg-weekly.md              ← /tg-weekly       client call prep, talking points
│   ├── tg-status.md              ← /tg-status       current state for a client or ticket
│   ├── tg-learn.md               ← /tg-learn        structured learning sessions
│   ├── tg-sync.md                ← /tg-sync         10-minute fact hygiene
│   ├── tg-save.md                ← /tg-save         mid-session checkpoint
│   ├── tg-whiteboard.md          ← /tg-whiteboard   idea validation before backlog
│   ├── tg-pull-notes.md          ← /tg-pull-notes   meeting transcript into vault
│   ├── tg-explore.md             ← /tg-explore      learn a new system area or pipeline
│   ├── tg-handoff.md             ← /tg-handoff      write the next chain skill's starter prompt
│   │                                                into the ticket state file
│   ├── tg-explain.md             ← /tg-explain      what was built
│   ├── tg-reference-import.md    ← /tg-reference-import  add reference material to the library and the search
│   ├── tg-retrieve.md            ← /tg-retrieve     grounded passages from the search index
│   ├── tg-sweep.md               ← /tg-sweep        flush knowledge staging to vault and index
│   ├── tg-doc-gen.md             ← /tg-doc-gen      code documentation generator
│   ├── tg-pr-review.md           ← /tg-pr-review    inbound PR review brief
│   ├── tg-influence.md           ← /tg-influence    communication rewrite
│   ├── tg-think-calibrate.md     ← /tg-think-calibrate  higher-order thinking calibrator
│   └── tg-devops.md, tg-sre.md, tg-terraform.md    engineer roles for those areas
│
├── memory/                       ← feedback memories (committed to the repo)
│   └── MEMORY.md                 ← index of all memory files
│                                    symlinked into ~/.claude/projects/.../memory/
│
├── hooks/                        ← Claude Code hooks (wired in settings.json)
│   │                                Each file header carries Trigger / Scope / Action.
│   │                                Full reference: docs/hooks.md
│   │
│   ├── pre-submit-vault-inject.sh          ← UserPromptSubmit: injects vault search results into
│   │                                         every prompt, withholds excerpts that hold PHI
│   ├── pre-prompt-expansion-check-gates.py ← UserPromptExpansion and PreToolUse Skill: blocks the
│   │                                         tg-arch, tg-dev and tg-qa commands until the earlier
│   │                                         Status lines are right
│   ├── pre-tool-write-scan-phi.py          ← PreToolUse Write, Edit, NotebookEdit:
│   │                                         scans content for PHI by level (deny, ask, warn)
│   ├── pre-tool-write-guard-path.sh        ← blocks writes to the read-only code directory
│   │                                         ($TOLLGATE_CODE_DIR) and to *-gate-override.md files
│   ├── pre-tool-write-require-read.py      ← blocks a write to a guarded state file that was
│   │                                         not read earlier in the session
│   ├── pre-tool-bash-scan-phi.py           ← PreToolUse Bash: scans the command text and the
│   │                                         script files it names for PHI
│   ├── pre-tool-bash-databricks-ask.py     ← asks before Databricks commands that return rows,
│   │                                         with a summary of the data requested
│   ├── pre-tool-bash-guard-code-dir.py     ← Bash side of the code directory guard
│   ├── pre-tool-bash-guard-gate-override.py ← denies a Bash command that writes a *-gate-override.md file
│   ├── pre-tool-bash-gate-pr-create.py     ← blocks `gh pr create` until you approve the PR details
│   ├── pre-tool-read-ask-sensitive-path.py ← asks before reading a file on the sensitive path list
│   ├── git_commit_guard.sh                 ← asks before any git commit
│   ├── git_push_guard.sh                   ← asks before any git push, denies protected branches
│   ├── git_readonly_guard.sh               ← closes the option holes in the auto-approved git reads
│   ├── co_authored_by_check.sh             ← blocks a commit with a Co-Authored-By line
│   ├── guard_worktree_remove.sh            ← blocks removing a worktree with unmerged work
│   ├── secret-command-guard.sh             ← blocks command shapes that print a credential
│   ├── scrub_secrets.py                    ← denies credential values before a tool runs, redacts
│   │                                         them in output after it runs
│   ├── pre_tool_write_scan_claims.py       ← markdown writes: flags uncited status words
│   ├── pre_tool_write_vault_frontmatter.py ← blocks invalid frontmatter in vault markdown
│   ├── post-tool-bash-scan-secrets.py      ← PostToolUse: warns when tool output holds credentials
│   │                                         (advisory, it cannot remove the output)
│   ├── post-tool-result-scan-phi.py        ← PostToolUse: warns when any tool result holds PHI
│   │                                         (advisory)
│   ├── post-tool-read-record.py            ← PostToolUse Read: records reads of guarded files
│   ├── vault_doc_standard_check.sh         ← PostToolUse Write, Edit: vault doc frontmatter check
│   ├── pre-compact-checkpoint-warn.sh      ← PreCompact: checkpoint reminder before context
│   │                                         compression
│   ├── pre-commit-secrets                  ← git pre-commit hook (not a Claude Code hook)
│   │                                         blocks credential commits in any git repo
│   │                                         install: cp hooks/pre-commit-secrets <repo>/.git/hooks/pre-commit
│   ├── git-pre-push                        ← git pre-push hook (not a Claude Code hook)
│   │                                         blocks direct pushes to protected branches
│   │
│   ├── lib/protected_paths.py              ← helper, not a hook entry: the list of Tollgate's own files
│   │                                         the model must not write (~/.claude/settings.json,
│   │                                         credentials.sh, ~/.claude/tollgate-config, ~/.tollgate/,
│   │                                         ~/.claude/tollgate/, the shell profiles, the files named by
│   │                                         TOLLGATE_CONNECTORS, TOLLGATE_PATHS and TOLLGATE_CONFIG, the repo
│   │                                         hooks/ and settings.json). Used by the Write and Bash guards
│   │
│   └── helpers, not hooks: gate_rules.py, phi_patterns.py, read_guard_common.py,
│                           sql_summary.py, state_file_io.py, claim_patterns.py,
│                           git_ask_before_run.py, gh_pr_create_detect.py, scrub_secrets.sh,
│                           secret_var_registry.txt
│
├── scripts/                      ← small programs the commands and hooks call
│   ├── core/                     ← path loader (paths.py), tg_path, tg_vault_git, venv setup,
│   │                                worker launchers, hook helpers
│   ├── requirements.txt          ← libraries for the venv (chromadb, pyyaml, beautifulsoup4), version bounded
│   ├── requirements-epub.txt     ← optional: ebooklib (AGPL-3) so the index can read epub books
│   ├── requirements-extras.txt   ← optional: anthropic and aiohttp for the index context pass
│   ├── search/                   ← the only search: tg-search is the one command the commands
│   │                                call (query, ground, reference, health); build_index.py,
│   │                                query_index.py, embedder, reference store
│   ├── cache/, state/, sync/, cron/    cached pulls, ticket state tools, sweeps, scheduled jobs
│   ├── chart/, qa/, validation/        chart checks and review checks
│   └── connectors/               ← plug-in point for outside tools (Jira, Notion, Slack, Plane...)
│
├── cursor-rules/                 ← Cursor IDE policy (optional, advanced)
│   ├── 00-policy.mdc
│   └── 01-context.mdc
│
├── installer/
│   ├── merge_settings.py         ← merges Tollgate's hooks, permissions and env into
│   │                                ~/.claude/settings.json without touching your own entries
│   └── manifest.py               ← records what the installer added, so an update can remove
│                                    what upstream dropped and --uninstall removes only that
│
├── templates/
│   └── code-docs/                ← templates for the per file docs under docs/
│
├── tools/
│   └── port/                     ← maintainer tool: rewrites a source file or folder into Tollgate form
│
├── tests/
│   ├── hooks/                    ← hook and gate unit tests, hook inventory check, plus the v1 files
│   │                                test_git_readonly_no_index.py, test_secret_shapes.py and
│   │                                test_self_protection.py
│   ├── installer/                ← installer tests, merge, lifecycle and vault git tests, plus
│   │                                test_mcp_pins.py, test_python_hint.py, test_requirements.py
│   ├── commands/                 ← command checks (names, placeholders, search calls)
│   ├── scripts/                  ← tests for each scripts/ folder, including connectors/test_host_allowlist.py
│   │                                and search/test_epub_optional.py
│   ├── e2e/, system/             ← end to end stream and system checks
│   ├── harness/, leak/           ← throwaway home helpers, leak scanner
│   ├── rag_eval/                 ← retrieval evaluation: golden questions for vault search
│   └── fixtures/                 ← sample tickets and vaults
│
├── .github/
│   ├── dependabot.yml            ← weekly update pull requests for the GitHub Actions and for scripts/ (pip)
│   └── workflows/
│       └── tests.yml             ← runs the hook, installer, command, harness and other tests on every push
│
└── docs/
    ├── prerequisites.md          ← apps to install and tokens to collect
    ├── setup.md                  ← step-by-step from clone to first session
    ├── connections.md            ← how each service connects and known issues
    ├── connectors.md             ← the connector framework
    ├── overview.md               ← what the system is and why it works this way
    ├── skill-chains.md           ← ticket types, chains, gates, when to stop
    ├── gate-lines.md             ← the exact state and approval lines the gates check
    ├── walkthrough.md            ← complete bug ticket with fake data
    ├── system-design.md          ← architecture, departments model, how to adopt
    ├── hooks.md                  ← every hook: what it does, when it fires, testing, recovery
    ├── variables.md              ← the shared list of variable names and placeholders
    ├── structure.md              ← this file
    ├── future.md                 ← planned improvements and team-level roadmap
    ├── install.md, settings.md   ← per file docs for install.sh and settings.json
    └── commands/, hooks/, installer/, scripts/, tests/, tools/ ← per file docs that mirror the code folders
```

Two requirements apply to the code folders above. The hooks and the settings merge need Python 3.12 or later; the installer checks this by running `python3` {src:install.sh:147} {src:install.sh:148}. Hooks fail closed (`onFailure: block`) only on Claude Code 2.1.295 or newer, and the installer warns when the version is older {src:install.sh:8}.

---

## 2. Claude Code Runtime: ~/.claude/

> What Claude Code actually reads at runtime. install.sh creates this from the repo.

```
~/.claude/
│
├── CLAUDE.md                     ← your identity written in, behavior rules active
│                                    generated by install.sh from the repo template
│
├── credentials.sh                ← reads API tokens from the OS credential store at runtime
│                                    (Keychain on macOS, Secret Service on Linux, Credential Manager on Windows)
│                                    generated by install.sh, never committed anywhere
│                                    sourced by your shell profile and MCP server commands
│
├── settings.json                 ← merged from the repo template by installer/merge_settings.py
│                                    Tollgate's entries are replaced, your own hooks,
│                                    permissions and env are kept. It also writes an env block:
│                                    TOLLGATE_KNOWLEDGE, TOLLGATE_CODE_DIR, CLAUDE_DOTFILES,
│                                    TOLLGATE_INITIALS, TOLLGATE_TICKET_PREFIX, TOLLGATE_HOME,
│                                    TOLLGATE_PATHS, TOLLGATE_CONNECTORS, and TOLLGATE_PYTHON
│                                    when you chose vault search
│                                    machine specific, never commit this file
│
├── tollgate-config               ← your saved answers (names and folders only, never a secret)
│
├── tollgate/
│   ├── paths.yaml                ← folder map file (TOLLGATE_PATHS), holds references and vault_git
│   ├── connectors.yaml           ← which connectors are on (TOLLGATE_CONNECTORS)
│   ├── manifest.json             ← what Tollgate installed, for updates and --uninstall
│   ├── installed-version         ← the Tollgate version that installed it
│   └── removed/                  ← copies of command files an update or uninstall removed
│
├── commands/                     ← your installed commands (copied at install)
│   ├── tg-ticket.md
│   ├── tg-support.md
│   ├── tg-spec.md
│   ├── tg-arch.md
│   ├── tg-dev.md
│   ├── tg-qa.md
│   ├── tg-start.md
│   ├── tg-close.md
│   ├── tg-draft.md
│   ├── ...                       ← 29 tg-*.md files in all
│   └── my-own-command.md         ← your own command files are never touched
│
└── projects/
    └── -Users-{you}-{working-dir}/
        └── memory/               ← symlink → {stem}-dotfiles/memory/
                                     feedback memories, committed back to the repo
```

**What install.sh does to produce this:**

| File | How it gets there |
|---|---|
| `CLAUDE.md` | Copied from repo template, identity substituted with sed |
| `credentials.sh` | Generated fresh, reads the OS credential store at runtime |
| `settings.json` | Merged from the repo template by `installer/merge_settings.py`, placeholders such as `$CLAUDE_DOTFILES` and `$TOLLGATE_HOME` replaced with real paths |
| `commands/tg-*.md` | Copied from `commands/tg-*.md` under the same name, `{NAME}` and the company filled in |
| `tollgate/manifest.json` | Written by `installer/manifest.py` and `installer/merge_settings.py` |
| `memory/` | Symlinked from repo |

---

## 3. Your Vault: $TOLLGATE_KNOWLEDGE

> Your Obsidian knowledge base. Local, and git tracked only if you chose `local` or `remote` for the vault git setting. Commands read from and write to this every session.
>
> One env var points to the vault path after install:
> - `TOLLGATE_KNOWLEDGE`: the fixed name used by hooks and the path loader
>
> The vault search index is not in the vault. It lives in the `index` folder from the path loader, `~/.tollgate/index` unless the paths file says otherwise.

```
tollgate-knowledge/
│
├── 00-landing/                   ← rough notes, quick thoughts
│                                    start here when you have something to park
│
├── 01-system-map/                ← your system: pipelines, clients, architecture
│   ├── clients/
│   │   └── CLIENT-NAME.md        ← one file per client
│   ├── pipelines/
│   │   └── PIPELINE-NAME.md      ← one file per pipeline
│   ├── architecture/             ← how the system connects
│   ├── data-model/               ← schemas, layer definitions
│   └── platform-learning/        ← platform concepts added by /tg-learn and /tg-explore
│
├── 02-tickets/                   ← one folder per ticket
│   └── TG-200/
│       ├── TG-200-state.md            ← live state, every skill reads and updates this
│       ├── TG-200-support-handoff.md  ← written by /tg-support
│       ├── TG-200-spec.md             ← written by /tg-spec
│       ├── TG-200-design.md           ← written by /tg-arch
│       ├── TG-200-edge-case-validation.md  ← written by /tg-dev, finished by /tg-qa
│       ├── TG-200-qa-findings.md      ← written by /tg-qa
│       └── TG-200-session-YYYY-MM-DD.md  ← written by /tg-close
│
├── 03-knowledge-base/            ← durable knowledge that outlives any ticket
│   ├── decisions/                ← YYYY-MM-DD-topic.md
│   ├── learnings/                ← YYYY-MM-DD-topic.md
│   ├── patterns/                 ← YYYY-MM-DD-topic.md
│   └── whiteboard/               ← idea validation notes from /tg-whiteboard
│
├── 04-education/                 ← reference material, courses, reading notes
│
├── 05-conversations/             ← Claude conversation logs and learning notes
│
├── 06-chat-threads/              ← saved chat threads (low search weight)
│
├── 08-reference/                 ← doc mirrors of repos (/tg-doc-gen writes 08-reference/repos/ only when that folder exists; the installer does not create repos/)
│
├── meetings/                     ← meeting transcripts and summaries
│                                    $TOLLGATE_MEETINGS points here
│                                    /tg-pull-notes writes here
│                                    not made at install; the sync script makes it
│
├── memory/                       ← Claude memory files specific to this vault context
│
└── output/                       ← files the scripts write
                                  (the library folder tollgate-library sits beside the vault, not in it)
```

The folder names above come from one table in `scripts/core/paths.py`. A line of the same name in the paths file changes a name, and commands pick it up because they look each folder up when they run.

**The vault git setting.** `vault_git: none | local | remote` is a line in `~/.claude/tollgate/paths.yaml`. `/tg-close` reads it with `scripts/core/tg_vault_git` and prints the `git add` and `git commit` lines for `local`, plus a `git push` line for `remote`, and only a list of files for `none`. It never runs them: you do. Commits on a code branch in `/tg-dev` are separate and unchanged.

---

## 4. Your Scripts Folder: $TOLLGATE_SCRIPTS

> Where Claude saves scripts it generates for recurring tasks. Reused instead of regenerated.
>
> The folder is `tollgate-scripts` for a new install. `$TOLLGATE_SCRIPTS` points to it.

```
your-scripts/                     ← path set by $TOLLGATE_SCRIPTS
│
├── databricks_row_count.py       ← example: generated once, called on every row-count task
├── schema_diff.py                ← example: compare two schema versions
└── null_check.py                 ← example: null audit across a table
```

Scripts here follow the same coding standards as all generated code (type hints, named constants, no secrets). Claude checks this folder before writing new code for a task it has done before.

---

## What the State File Looks Like

The file at `02-tickets/{KEY}/{KEY}-state.md` is the handoff contract between skills. Every skill reads it at Step 0 and updates it when done. The gate also finds `02-tickets/PREFIX/KEY/` (prefix matched without case). A real one:

```markdown
## TG-200 State

Status: SUPPORT_COMPLETE
Next skill: /tg-spec

Confirmed approach: quarantine_ind flag for null encounter_date records
Source: Data Platform approved 2026-06-02

KNOWN
  - 22 records have null encounter_date in raw_tavr
  - Root cause: Bronze filter added in TG-157 excludes null records
  - Raw count: 500, Bronze count: 478, Silver count: 478

UNKNOWN
  - Whether the client will resubmit the 22 records or provide a blanket correction

ASSUMING
  - quarantine_ind is the correct column name (verify with Data Platform)
```

When `/tg-spec` starts, it reads this file. It knows the root cause, the confirmed approach, and what is still open. It does not ask you to recap.

---

## Where Everything Comes From

| Thing | Repo location | Installed to | Who writes it |
|---|---|---|---|
| Command files | `commands/tg-*.md` | `~/.claude/commands/` (same names) | install.sh |
| Behavior rules | `CLAUDE.md` | `~/.claude/CLAUDE.md` | install.sh (with identity) |
| Permissions | `settings.json` | `~/.claude/settings.json` | install.sh |
| Hook wiring | `settings.json` | `~/.claude/settings.json` (global) | install.sh (settings merge) |
| What was installed | none | `~/.claude/tollgate/manifest.json` | install.sh |
| MCP config | none (registered via CLI) | `~/.claude.json` (user scope) | install.sh (`claude mcp add`) |
| Token loader | not in repo | `~/.claude/credentials.sh` | install.sh |
| Feedback memories | `memory/` | `~/.claude/projects/.../memory/` | /tg-close (with your approval) |
| Vault git setting | none | `vault_git:` line in `~/.claude/tollgate/paths.yaml` | install.sh asks; you can edit it |
| Vault search index | not in repo | the `index` folder from the path loader (default `~/.tollgate/index`) | install.sh (if you choose search), then `scripts/search/rebuild.sh` after adding docs |
| Client knowledge | not in repo | `vault/01-system-map/` | /tg-ticket |
| Ticket state | not in repo | `vault/02-tickets/{KEY}/` (or `02-tickets/PREFIX/KEY/`) | every skill in the chain |
| Decisions | not in repo | `vault/03-knowledge-base/` | /tg-close |
| Reusable scripts | not in repo | `$TOLLGATE_SCRIPTS/` | Claude during sessions |
