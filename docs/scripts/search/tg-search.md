---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/search/tg-search"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-22
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "case dispatch on the first argument"    # function or line that executes when the script runs
requires: [dirname, scripts/core/tg_path, python]       # external commands or tools this script depends on
tags: []
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
---

## Purpose

`tg-search` is one fixed command that fronts five Python search tools (query, ground, reference, add, health). The point is that a single permission rule in the settings file covers all five, so a command file can run a search without a permission prompt. The file has no `.sh` extension, so the doc-gen extension map does not match it; this page was written with the `shell` template on purpose.

## Dependencies

**Depends on.**
- `bash` (shebang `#!/usr/bin/env bash`) {src:scripts/search/tg-search:1}
- `dirname`, to find its own folder {src:scripts/search/tg-search:22}
- `scripts/core/tg_path`, a Python helper that prints the state folder: [[tg_path]] / [tg_path](../core/tg_path.md) {src:scripts/search/tg-search:46}
- Five sibling Python scripts, one per tool: `query_index.py`, `ground.py`, `reference_query.py`, `reference_add.py`, `vault_health.py` {src:scripts/search/tg-search:29-33}. Their pages are [[query_index]] / [query_index](query_index.md), [[ground]] / [ground](ground.md), [[reference_query]] / [reference_query](reference_query.md), [[reference_add]] / [reference_add](reference_add.md) and [[vault_health]] / [vault_health](vault_health.md).
- Environment variable `TOLLGATE_PYTHON`, the Python to use {src:scripts/search/tg-search:43}
- The venv under the state folder, `<state>/venv/bin/python3`, built by `scripts/core/setup_venv.sh`: [[setup_venv]] / [setup_venv](../core/setup_venv.md) {src:scripts/search/tg-search:47} {src:scripts/core/setup_venv.sh:32}
- `python3` from the path, as the last choice {src:scripts/search/tg-search:51}

**Used by.** Product code. The command files in the repo hold the text `$TOLLGATE_HOME/scripts/search/tg-search`. The installer rewrites every `$TOLLGATE_HOME/` in each command file it installs, this one included, to the absolute path of the repo copy {src:install.sh:1155}, because Claude Code refuses any command that holds an unresolved variable ("A variable in this command can't be checked before it runs"), and that refusal comes before any permission rule is read (sandbox session, 2026-11-19: a rule with the literal `$TOLLGATE_HOME` text did not stop the prompt, a rule with the absolute path did, also with a heredoc and `2>/dev/null`) {unverified}. The command files that call it:
- `commands/tg-ticket.md`: query {src:commands/tg-ticket.md:69}, health {src:commands/tg-ticket.md:80}
- `commands/tg-start.md`: health {src:commands/tg-start.md:40}, reference {src:commands/tg-start.md:84}
- `commands/tg-retrieve.md`: query with stdin {src:commands/tg-retrieve.md:25}
- `commands/tg-spec.md`: reference {src:commands/tg-spec.md:83} and {src:commands/tg-spec.md:242}
- `commands/tg-dev.md`: ground {src:commands/tg-dev.md:118}, reference {src:commands/tg-dev.md:158} and {src:commands/tg-dev.md:284}
- `commands/tg-whiteboard.md`: reference {src:commands/tg-whiteboard.md:62}
- `commands/tg-arch.md`: reference {src:commands/tg-arch.md:93} and {src:commands/tg-arch.md:188}
- `commands/tg-qa.md`: ground {src:commands/tg-qa.md:88}, reference {src:commands/tg-qa.md:120} and {src:commands/tg-qa.md:302}
- `commands/tg-learn.md`: query {src:commands/tg-learn.md:76}
- `settings.json`, the permission rule that lets the command run without a prompt: `Bash($TOLLGATE_HOME/scripts/search/tg-search:*)` {src:settings.json:274}, which the installer writes with the absolute repo path. A second rule with a doubled dollar sign sits next to it {src:settings.json:275}; the installer turns `$$` into one literal `$` {src:tests/installer/test_merge_settings.py:182-184}, so the doubled form becomes a rule that keeps the text `$TOLLGATE_HOME` unexpanded. That literal rule no longer matches any command, because the installed commands hold the absolute path; it is kept only because the merge tests expect it.

One command file calls the `add` tool: `commands/tg-reference-import.md`, in its step that adds the copied folder to the index, once per import and only after the owner's yes {src:commands/tg-reference-import.md:91}. It is covered by the same permission rule as the other tools. The other hits for `tg-search add` and `reference_add` (searched 2026-11-22, excluding `.git`, `docs/` and virtual environments) are the wrapper itself, the Python tool and its tests, and `build_index.py` comments.

`commands/tg-dev.md` and `commands/tg-qa.md` also mention `tg-search reference` in prose rules, which is not a call {src:commands/tg-dev.md:612} {src:commands/tg-qa.md:809} {src:commands/tg-qa.md:878}. `install.sh` does not name this script at all: its rewrite covers every `$TOLLGATE_HOME/` in the command text {src:install.sh:1155} (searched `install.sh` for `tg-search`, 2026-11-22); the permission rule reaches the user's settings through the settings template (searched `scripts/` and `hooks/` for `tg-search`, 2026-11-22). The checks that prove both are INS-01 and INS-11 in `tests/installer/test_ins.sh` {src:tests/installer/test_ins.sh:55} {src:tests/installer/test_ins.sh:313}.

Tests, on their own line: `tests/scripts/search/test_tg_search.py` {src:tests/scripts/search/test_tg_search.py:21}, `tests/commands/test_commands.py` {src:tests/commands/test_commands.py:330}, `tests/scripts/search/test_ticket_flags.py` {src:tests/scripts/search/test_ticket_flags.py:37}, `tests/installer/test_merge_settings.py` {src:tests/installer/test_merge_settings.py:164}.

## Behavior

1. The script sets `set -u`, so an unset variable is an error, but not `set -e` {src:scripts/search/tg-search:20}. It records its own folder as `HERE` {src:scripts/search/tg-search:22}.
2. The first argument picks a script from a fixed list: `query` to `query_index.py`, `ground` to `ground.py`, `reference` to `reference_query.py`, `add` to `reference_add.py`, `health` to `vault_health.py` {src:scripts/search/tg-search:29-33}. The `add` entry is the newest one; its script takes a file or folder and optional `--tag` labels, per its own usage text {src:scripts/search/reference_add.py:13}. The wrapper passes those arguments through without reading them.
3. Anything else, including no argument, prints the usage line on stderr and exits 2 {src:scripts/search/tg-search:25} {src:scripts/search/tg-search:37}. A non-empty unknown word also prints `tg-search: unknown tool: <word>` first {src:scripts/search/tg-search:35}. With no argument only the usage line prints.
4. It removes the tool word from the arguments {src:scripts/search/tg-search:40}.
5. It picks the Python. If `TOLLGATE_PYTHON` is set and executable, that wins {src:scripts/search/tg-search:43}. Otherwise it asks `tg_path state` for the state folder, discarding the error text and treating a failure as empty {src:scripts/search/tg-search:46}. If that folder holds an executable `venv/bin/python3`, that is used {src:scripts/search/tg-search:47} {src:scripts/search/tg-search:48}. If still empty, it falls back to bare `python3` {src:scripts/search/tg-search:51}.
6. It replaces itself with the chosen Python running the sibling script and the remaining arguments {src:scripts/search/tg-search:53}. Because of `exec`, stdin, stdout and stderr go straight to the tool and its exit code is the exit code of `tg-search`.

Exit codes: 2 for a bad or missing tool name {src:scripts/search/tg-search:37}; anything else is whatever the Python tool returns {src:scripts/search/tg-search:53}. For `add` that is 0 added, 1 nothing to add or bad path, 2 not set up, per the tool's own usage text {src:scripts/search/reference_add.py:16}.

## Diagram

```mermaid
flowchart TD
    Start["Read tool name"] --> Known{"Known tool?"}
    Known -- no --> Usage["Print usage, exit 2"]
    Known -- yes --> Env{"Configured Python usable?"}
    Env -- yes --> Run["Run tool script"]
    Env -- no --> Venv{"State venv exists?"}
    Venv -- yes --> Run
    Venv -- no --> Bare["Use bare python3"]
    Bare --> Run
```

## Notes

**Code versus its header comment.**
- The header says it uses "$TOLLGATE_PYTHON if it is set and executable, else the venv ... if it exists, else python3" {src:scripts/search/tg-search:13} {src:scripts/search/tg-search:14}. The order matches the code. The header does not say that finding the venv itself runs `tg_path`, whose first line is `#!/usr/bin/env python3` {src:scripts/core/tg_path:1}. So bare `python3` is used for the state lookup even when a venv is the goal, and bare `python3` is also the last fallback {src:scripts/search/tg-search:51}. The tool is not guaranteed to run on the configured Python; that holds only when `TOLLGATE_PYTHON` or the venv exists.
- The header says an unknown tool prints the usage on stderr and exits 2 {src:scripts/search/tg-search:15}. True, but a missing tool name prints only the usage, without the `unknown tool` line {src:scripts/search/tg-search:35}.
- The header lists five tools and the code accepts five {src:scripts/search/tg-search:6} {src:scripts/search/tg-search:29-33}. They agree; the older page said four.
- The header `Date:` line is empty {src:scripts/search/tg-search:4}.
- Cosmetic: the `health)` case label is indented three spaces where the others use four {src:scripts/search/tg-search:33}. It has no effect on behavior.

**Inputs that reach a command or path with no check on the value.**
- All arguments after the tool name go to the Python script unchanged {src:scripts/search/tg-search:53}. They are quoted, so they are not run as shell code, but the wrapper does not check them; the Python tools own that. This now includes the path that `add` is told to read, so the wrapper does not limit which files `add` can be pointed at.
- `TOLLGATE_PYTHON` is run as a program {src:scripts/search/tg-search:53}. The only check is that it is an executable file {src:scripts/search/tg-search:43}; nothing checks that it is a Python.
- The state folder printed by `tg_path` is used to build the path of a program that is then run {src:scripts/search/tg-search:47} {src:scripts/search/tg-search:48}. The only check is that the file is executable. That folder comes from the paths file or environment that `tg_path` reads.
- The first argument is checked: only five exact words are accepted {src:scripts/search/tg-search:28-33}.

**Shared files.** The wrapper writes no file, so there is no write to guard in this script. The `add` tool it launches changes the reference store in the search index, which is shared state; atomicity and locking there belong to [[reference_add]] / [reference_add](reference_add.md), and this wrapper adds no guard between two `add` runs.

**Platform.** It needs only bash and `dirname`; it is not tied to one operating system.
