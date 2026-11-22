---
doc_type: config
catalog_type: code_doc
doc_role: config
indexable: true
indexed: null
repo: "tollgate"
source_file: "settings.json"
status: ACTIVE
last_updated: 2026-11-21
scores: []
format: "json"
governs: "which hooks Claude Code runs, and which tool calls are pre approved, once merged into the user settings file"
tags: [hooks, permissions, settings]
links: []
---

## Purpose

`settings.json` in the repo root is a template, not the live file. It lists the hook scripts Claude Code runs and a short list of tool calls that never ask for permission. The installer merges it into `~/.claude/settings.json` after replacing the path placeholders with real paths. {src:install.sh:1769}

## Dependencies

Read by `installer/merge_settings.py`, which substitutes `$CLAUDE_DOTFILES`, `$TOLLGATE_KNOWLEDGE` and `$TOLLGATE_SCRIPTS` inside every string, and also a `$NAME` for every value the installer passes with `--set` (such as `$TOLLGATE_HOME`). {src:installer/merge_settings.py:413} It is called by [install](install.md) near the end of the install. {src:install.sh:1769} The merge rules are in [merge_settings](installer/merge_settings.md). The hook scripts it names are described in [hooks](hooks.md). `tests/hooks/check_hook_inventory.py` compares this file against the hook files and `docs/hooks.md`. {src:tests/hooks/check_hook_inventory.py:5}

## Behavior

The file has two top level keys, `hooks` and `permissions`. It has no `env` key. The merge adds the `env` values itself. {src:installer/merge_settings.py:418}

Fields on each hook entry:

| Field | Effect |
|---|---|
| event key (`UserPromptSubmit`, `PreToolUse` and so on) | When the hook group fires {src:settings.json:3} |
| `matcher` | Tool names the group applies to, as a `\|` list. Without it, or with an empty one, the group applies to every call of that event {src:settings.json:28} {src:settings.json:228} |
| `type` | Always `command` here {src:settings.json:7} |
| `command` | The script, quoted, with `$CLAUDE_DOTFILES` replaced by the repo path at install {src:settings.json:8} |
| `timeout` | Seconds before the hook is cancelled. Set on three entries only {src:settings.json:9} |
| `onFailure` | `block` on 24 of the 28 entries. The call is blocked when the hook cannot run, instead of going ahead {src:settings.json:21} |

Hook entries, in file order. A group with more than one script is shown as one row per script:

| Event | Matcher | Command (file in `hooks/`) | Timeout | onFailure |
|---|---|---|---|---|
| UserPromptSubmit | none | `pre-submit-vault-inject.sh` {src:settings.json:8} | 30 | none |
| UserPromptExpansion | none | `pre-prompt-expansion-check-gates.py` {src:settings.json:19} | 10 | block |
| PreToolUse | `Write\|Edit\|NotebookEdit` | `pre-tool-write-scan-phi.py` {src:settings.json:32} | none | block |
| PreToolUse | `Write\|Edit\|NotebookEdit` | `pre-tool-write-guard-path.sh` {src:settings.json:42} | none | block |
| PreToolUse | `Bash` | `pre-tool-bash-scan-phi.py` {src:settings.json:52} | none | block |
| PreToolUse | `Bash` | `pre-tool-bash-databricks-ask.py` {src:settings.json:62} | none | block |
| PreToolUse | `Bash` | `pre-tool-bash-guard-code-dir.py` {src:settings.json:72} | none | block |
| PreToolUse | `Bash` | `pre-tool-bash-guard-gate-override.py` {src:settings.json:82} | none | block |
| PreToolUse | `Bash` | `pre-tool-bash-gate-pr-create.py` {src:settings.json:92} | none | block |
| PreToolUse | `Write\|Edit` | `pre-tool-write-require-read.py` {src:settings.json:102} | none | block |
| PreToolUse | `Read` | `pre-tool-read-ask-sensitive-path.py` {src:settings.json:112} | none | block |
| PreToolUse | `Skill` | `pre-prompt-expansion-check-gates.py` {src:settings.json:122} | 10 | block |
| PreToolUse | `Bash` | `git_commit_guard.sh` {src:settings.json:133} | none | block |
| PreToolUse | `Bash` | `git_push_guard.sh` {src:settings.json:138} | none | block |
| PreToolUse | `Bash` | `co_authored_by_check.sh` {src:settings.json:143} | none | block |
| PreToolUse | `Bash` | `guard_worktree_remove.sh` {src:settings.json:148} | none | block |
| PreToolUse | `Bash` | `git_readonly_guard.sh` {src:settings.json:153} | none | block |
| PreToolUse | `Bash` | `secret-command-guard.sh` {src:settings.json:163} | none | block |
| PreToolUse | `Bash` | `scrub_secrets.py` {src:settings.json:168} | none | block |
| PreToolUse | `Write\|Edit\|NotebookEdit` | `scrub_secrets.py` {src:settings.json:178} | none | block |
| PreToolUse | `Write\|Edit\|NotebookEdit` | `pre_tool_write_scan_claims.py` {src:settings.json:183} | none | block |
| PreToolUse | `Write\|Edit` | `pre_tool_write_vault_frontmatter.py` {src:settings.json:193} | none | block |
| PostToolUse | none | `post-tool-bash-scan-secrets.py` {src:settings.json:204} | none | block |
| PostToolUse | none | `post-tool-result-scan-phi.py` {src:settings.json:213} | none | block |
| PostToolUse | `Read` | `post-tool-read-record.py` {src:settings.json:223} | none | none |
| PostToolUse | empty (every tool) | `scrub_secrets.py` {src:settings.json:232} | none | block |
| PostToolUse | `Write\|Edit` | `vault_doc_standard_check.sh` {src:settings.json:242} | none | none |
| PreCompact | none | `pre-compact-checkpoint-warn.sh` {src:settings.json:252} | none | none |

That is 28 entries across five events (1 UserPromptSubmit, 1 UserPromptExpansion, 20 PreToolUse, 5 PostToolUse, 1 PreCompact). {src:settings.json:3} No matcher names `MultiEdit`, which is not a current tool name. {src:tests/hooks/check_hook_inventory.py:20}

What the entries added since the first release do, from the header of each hook file:

| Hook | What it does |
|---|---|
| `git_commit_guard.sh` | Asks before any `git commit`, showing the command, the staged files and the draft message. {src:hooks/git_commit_guard.sh:4} |
| `git_push_guard.sh` | Asks before any `git push`, and denies a push to a protected branch (`TOLLGATE_PROTECTED_BRANCHES`) unless `TOLLGATE_ALLOW_PROTECTED_PUSH` is 1. {src:hooks/git_push_guard.sh:4} |
| `co_authored_by_check.sh` | Blocks a `git commit` whose command text holds a `Co-Authored-By` line. {src:hooks/co_authored_by_check.sh:4} |
| `guard_worktree_remove.sh` | Blocks `git worktree remove` when the branch checked out in that worktree is not merged into a base branch. {src:hooks/guard_worktree_remove.sh:4} |
| `git_readonly_guard.sh` | Denies the ways an auto-approved `git status`, `log`, `diff`, `show` or `config` can run a program, overwrite a file or read any file on disk. It closes the option based holes in the permission rules below. Since v1 it also denies `git diff --no-index` (long prefixes of 7 or more characters count) and a diff whose first two path arguments are both outside the repo, which git runs as a no-index diff by itself {src:hooks/git_ask_before_run.py:369} {src:hooks/git_ask_before_run.py:386} {src:hooks/git_ask_before_run.py:408} {src:hooks/git_ask_before_run.py:410} |
| `secret-command-guard.sh` | Blocks command shapes that print a credential or a private key. A speed bump, not a sandbox. {src:hooks/secret-command-guard.sh:4} |
| `scrub_secrets.py` | One scrubber with two modes. Text is first normalised, which removes zero-width characters and folds compatibility characters (done by `normalize_text` in `phi_patterns.py`) {src:hooks/scrub_secrets.py:112} {src:hooks/phi_patterns.py:243}. Before a tool runs, a real credential value in a command or in text being written is denied, and written text is also checked for a quoted `password`, `secret`, `token` or `api_key` assignment of 8 or more characters {src:hooks/scrub_secrets.py:83} {src:hooks/scrub_secrets.py:86} {src:hooks/scrub_secrets.py:217}; more key shapes are recognised than in the first release, for example Google and Hugging Face keys {src:hooks/scrub_secrets.py:62} {src:hooks/scrub_secrets.py:64}. After a tool runs, matches in the output are redacted and Claude gets the scrubbed copy. It cannot hide the raw result. Fails closed. {src:hooks/scrub_secrets.py:5} {src:hooks/scrub_secrets.py:10} |
| `pre_tool_write_scan_claims.py` | Scans markdown being written for uncited status words in capitals (the four words the claims check lists). {src:hooks/pre_tool_write_scan_claims.py:5} |
| `pre_tool_write_vault_frontmatter.py` | Blocks a write to a markdown file in the vault when its frontmatter is invalid. With `TOLLGATE_KNOWLEDGE` unset it allows everything. {src:hooks/pre_tool_write_vault_frontmatter.py:5} {src:hooks/pre_tool_write_vault_frontmatter.py:6} |
| `vault_doc_standard_check.sh` | After a write, checks a vault markdown file for the vault doc standard frontmatter. {src:hooks/vault_doc_standard_check.sh:4} |
| `pre-tool-bash-guard-gate-override.py` | Denies a Bash command that writes a `*-gate-override.md` file. The owner creates those from a terminal; reading one stays allowed. {src:hooks/pre-tool-bash-guard-gate-override.py:13} Since v1 the name is also caught when it is split by quotes {src:hooks/pre-tool-bash-guard-gate-override.py:62}, or built with a variable, command substitution, braces or a glob that could match `override.md`, and when an inline `python -c`, `node -e` or `perl -e` body mentions gate or override and writes {src:hooks/pre-tool-bash-guard-gate-override.py:75} {src:hooks/pre-tool-bash-guard-gate-override.py:86} {src:hooks/pre-tool-bash-guard-gate-override.py:94} |
| `pre-tool-write-guard-path.sh` | Also blocks a write to a `*-gate-override.md` file, next to its job of guarding `$TOLLGATE_CODE_DIR`. {src:hooks/pre-tool-write-guard-path.sh:4} It also blocks a write, by the model, to Tollgate's own files: asks `hooks/lib/protected_paths.py`, and a crash or missing helper blocks too {src:hooks/pre-tool-write-guard-path.sh:59} {src:hooks/pre-tool-write-guard-path.sh:60} |
| `pre-tool-bash-guard-code-dir.py` | The Bash side of the same list. It now always runs the protected files check, with `$TOLLGATE_CODE_DIR` added only when that variable is set. Without the helper module it exits 2 and blocks {src:hooks/pre-tool-bash-guard-code-dir.py:261} {src:hooks/pre-tool-bash-guard-code-dir.py:263} {src:hooks/pre-tool-bash-guard-code-dir.py:46-49} It splits the command at `;`, `&`, `|`, a newline, a carriage return, a backtick, `$(` and `)` before it checks each part, so a write placed after any of these is caught {src:hooks/pre-tool-bash-guard-code-dir.py:91-116} {src:hooks/pre-tool-bash-guard-code-dir.py:248-249} |
| `pre-prompt-expansion-check-gates.py` on `Skill` | The same gate as the typed command, for a skill the model calls itself. {src:settings.json:118} |

The protected list (`hooks/lib/protected_paths.py`, a helper that is not a hook entry and so not in the table above) names `~/.claude/settings.json`, `~/.claude/credentials.sh` and `~/.claude/tollgate-config` {src:hooks/lib/protected_paths.py:28}, `.zshrc`, `.bashrc`, `.bash_profile` and `.profile` in the home folder {src:hooks/lib/protected_paths.py:29}, the folders `~/.tollgate/` and `~/.claude/tollgate/` {src:hooks/lib/protected_paths.py:30}, and the `settings.json` {src:hooks/lib/protected_paths.py:31} and `hooks/` folder {src:hooks/lib/protected_paths.py:32} of the repo. It also protects the files named by the variables `TOLLGATE_CONNECTORS`, `TOLLGATE_PATHS` and `TOLLGATE_CONFIG` when they are set {src:hooks/lib/protected_paths.py:35} {src:hooks/lib/protected_paths.py:69-70}. Reads are not blocked. See [structure](structure.md). The template `settings.json` itself did not change in v1.

The validate-for-write hook is gone. The gate names only the fixed command names `tg-arch`, `tg-dev` and `tg-qa`; `TOLLGATE_SKILL_PREFIX` is no longer read. {src:hooks/pre-prompt-expansion-check-gates.py:8}

The `permissions.allow` list pre approves these calls: {src:settings.json:259}

| Entry | Meaning |
|---|---|
| `mcp__atlassian__getAccessibleAtlassianResources`, `mcp__atlassian__searchJiraIssuesUsingJql`, `mcp__atlassian__getJiraIssue` | Read only Jira lookups {src:settings.json:260} |
| `Bash(git config --get:*)`, `--get-all`, `--get-regexp`, `--list`, `-l` | Read only `git config` forms. There is no rule for plain `git config`, so a write such as `git config user.name X` asks {src:settings.json:263} |
| `Bash(git status:*)`, `Bash(git log:*)`, `Bash(git diff:*)` | Read only git commands, with `git_readonly_guard.sh` closing the option holes {src:settings.json:268} |
| `Bash(date)` | Print the date {src:settings.json:271} |
| `Bash(find $TOLLGATE_KNOWLEDGE/**)`, `Bash(find $TOLLGATE_SCRIPTS/**)` | Search the vault and scripts folders {src:settings.json:272} |
| `Bash($TOLLGATE_HOME/scripts/search/tg-search:*)`, once with the absolute repo path and once with the literal text `$TOLLGATE_HOME` | The one search command. It runs `query`, `ground`, `reference` or `health` and nothing else. The absolute form is the one that works: the installer rewrites `$TOLLGATE_HOME/` in each installed command to the same absolute path, for every script a command calls, and Claude Code refuses any command that holds an unresolved variable before it looks at a rule, so the literal form never matches a command {src:settings.json:274} {src:settings.json:275} {src:install.sh:1155} |
| `Bash($TOLLGATE_HOME/scripts/core/tg_path:*)`, `Bash($TOLLGATE_HOME/scripts/core/tg_ticket_dir:*)` | The two folder lookups every command starts with: where a vault folder is, and where one ticket's folder is. Both only print a path. They are written with the absolute repo path like the search rule; without them each installed command stopped at a permission prompt on its first lookup, which a real Claude session showed on 2026-11-21 {src:settings.json:276} {src:settings.json:277} |
| `Read($TOLLGATE_KNOWLEDGE/**)`, `Read($TOLLGATE_SCRIPTS/**)`, `Read($CLAUDE_DOTFILES/**)` | Read files in the vault, scripts and repo folders {src:settings.json:278} |

The search rule replaces the old per script rules: there is no rule that names an interpreter and a script path any more. See [tg-search](scripts/search/tg-search.md). The second form of the search rule is written `$$TOLLGATE_HOME` in the template, because `$$` stays a single literal `$` in the merge. It is kept because the merge tests expect it; it can be removed together with those tests. {src:settings.json:275} {src:installer/merge_settings.py:78}

`permissions.additionalDirectories` is an empty list. {src:settings.json:282} In the merge, the permission lists are unioned with the user's own lists, keeping order. {src:installer/merge_settings.py:72}

Existing Tollgate hook entries in the user file are removed first, then these are added, so a moved repo does not leave stale paths. The merge records what it added in the manifest, so a rule or hook dropped from this template later is removed on the next install and by `--uninstall`. {src:installer/merge_settings.py:128} {src:installer/merge_settings.py:194} {src:installer/merge_settings.py:198} Two broad allow rules that an early Tollgate shipped, `Bash(git config:*)` and a `query_index.py` rule, are removed on update even when the manifest does not list them, for users installed before the manifest recorded permissions. Only an exact text match is removed, and a rule that the current template still holds is kept. {src:installer/merge_settings.py:77} {src:installer/merge_settings.py:195-197}

## Diagram

Skipped. The file is a flat list of entries with no conditional sections.

## Notes

Several PreToolUse entries on `Write|Edit|NotebookEdit` run as separate groups, so each hook is its own entry. Two Bash groups hold several scripts in one group: the five git guards, and the two secret guards. {src:settings.json:129} {src:settings.json:159} The read before write hook is not matched on `NotebookEdit`. {src:settings.json:98}

Hooks with `onFailure: block` stop the call when the script cannot start or times out. Four entries do not set it: the vault inject hook, the read record hook, the vault doc check and the pre compact warning. {src:settings.json:8} {src:settings.json:223} {src:settings.json:242} {src:settings.json:252} `tests/hooks/check_hook_inventory.py` fails if a PreToolUse or UserPromptExpansion entry, or the PostToolUse secret and PHI scanners, lose their `onFailure` setting. {src:tests/hooks/check_hook_inventory.py:18} `onFailure: block` needs Claude Code 2.1.295 or later; the installer warns when it is older, and `--strict` stops. {src:install.sh:8} A hook can also handle its own internal error. The frontmatter hook fails closed: on an internal error it writes a message to stderr and exits 2, which blocks the write. {src:hooks/pre_tool_write_vault_frontmatter.py:126} {src:hooks/pre_tool_write_vault_frontmatter.py:127} The docstring at the top of that file now says "Fails closed" and agrees with the code. {src:hooks/pre_tool_write_vault_frontmatter.py:8} (An earlier docstring said "Fails open" and disagreed.)

The installer verifies after the merge that every hook command path is executable. {src:install.sh:1790}
