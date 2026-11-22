# Install variables (shared contract)

This file is the single list of variable names for Tollgate. Every command, hook, script and test takes its folders and identity values from here. A name not in this file must not be used. A new name is added here first.

Rules:

1. No file in the repo holds a literal personal path, host, user name or initials. It reads a variable instead.
2. A variable never holds a secret. Secrets live in the user's own secret store (see `TOLLGATE_CONNECTORS`).
3. Scripts read folder locations through the central path loader (`scripts/core`), which reads `TOLLGATE_PATHS`. No script reads a folder variable directly except the loader.
4. Date fields in file headers stay empty.

## Existing variables

| Name | Meaning | Set by |
|---|---|---|
| `TOLLGATE_KNOWLEDGE` | The user's vault folder (tickets, notes, state). | installer; `env` block of settings |
| `TOLLGATE_CODE_DIR` | Read-only code folder the write guards protect. Empty means no protection and a visible warning. | installer; `env` block of settings |
| `TOLLGATE_MEETINGS` | The meetings folder. The installer writes what `scripts/core/tg_path meetings` prints for the vault: the `meetings:` line of the paths file when there is one, else `<vault>/meetings`; if that helper fails it writes `<vault>/meetings`. Written to the shell profile only. Scripts read this folder through the path loader (`meetings`), not from this variable. {src:install.sh:908-909} {src:install.sh:1525} | installer |
| `TOLLGATE_STATE_DIR` | Folder for per-session hook state. Default `$HOME/.tollgate/state`. | hooks; optional override |
| `TOLLGATE_CONFIG` | The saved-answers file written by the installer. Default `$HOME/.claude/tollgate-config`. Holds answers only, never a secret. | installer |
| `CLAUDE_DOTFILES` | Root folder of the installed Tollgate repo. Used to resolve hook paths. | installer; `env` block of settings |

## Existing variables used by hooks (unchanged)

| Name | Meaning |
|---|---|
| `TOLLGATE_SCRIPTS` | Folder where Claude saves reusable generated scripts. Written to the shell profile, and a placeholder in the settings template. Not the same as `TOLLGATE_HOME`. {src:install.sh:1526} |
| `TOLLGATE_PROTECTED_BRANCHES` | Branches the push guard protects. |
| `TOLLGATE_ALLOW_PROTECTED_PUSH` | One-time owner override for the push guard. |
| `TOLLGATE_PRE_PUSH_CMD` | Command the pre-push hook runs. |
| `TOLLGATE_SENSITIVE_PATHS` | Paths the read-ask hook treats as sensitive. |
| `TOLLGATE_DATA_APPROVED` | Approval code prefix for the data-query ask hook. |
| `TOLLGATE_GATE_LOG` | Log file for gate decisions. |
| `TOLLGATE_NONINTERACTIVE` | Installer: ask no questions, use flags. |
| `TOLLGATE_VAULT_GIT` | Installer input: `none`, `local` or `remote`. The `--vault-git` flag wins over it. The answer is saved as the `vault_git` line of the paths file, see Vault git setting below. {src:install.sh:116} |

## New variables

| Name | Meaning | Written by | Read by |
|---|---|---|---|
| `TOLLGATE_INITIALS` | The user's initials. Used in ticket and file naming. Letters only. | installer | commands, scripts, gate |
| `TOLLGATE_TICKET_PREFIX` | Ticket key prefix, for example `T` gives `T-001`. Letters only. | installer (A1) | commands, scripts, gate |
| `TOLLGATE_HOME` | Root folder of the installed Tollgate repo. The scripts tree is at `$TOLLGATE_HOME/scripts`. | installer | scripts, commands |
| `TOLLGATE_PATHS` | The folder map file. Maps logical names (vault, tickets, state, cache, output) to folders. It also holds the `vault_git` setting. The path loader reads it. {src:scripts/core/paths.py:70} | installer, path loader | `scripts/core` only |
| `TOLLGATE_CONNECTORS` | The file that records which connectors are on. A connector is off unless listed. Holds names and addresses only, never a key. | connector framework | connectors |

## Maintainer tool variables (never set by the installer)

| Name | Meaning |
|---|---|
| `TOLLGATE_DENYLIST` | Path to the owner's private leak denylist for the leak scanner and the porting tool. Set by the owner. The file is never in the repo. |
| `TOLLGATE_PORT_MAP` | Path to the owner's private path-to-variable mapping file for the porting tool. Set by the owner. Never in the repo. |

## Optional script variables

All are optional. A script has a safe default or prints `not set up`.

| Name | Meaning |
|---|---|
| `CLAUDE_CONFIG_DIR` | The Claude config folder. `session_cost.py` and `sync_conversations.py` need it, or a `--sessions-dir` flag. Set by Claude Code, not by Tollgate. |
| `TOLLGATE_PYTHON` | Python interpreter for the search scripts, the vault-inject hook and the run scripts. The installer puts the venv python in the settings `env` block when a venv exists. `tg-search` uses it first, then the venv in the state folder, then `python3`. {src:scripts/search/tg-search:40} {src:install.sh:1768} |
| `TOLLGATE_BASE_PYTHON` | Interpreter `setup_venv.sh` uses to build the venv. Default `python3`. {src:scripts/core/setup_venv.sh:17} |
| `TOLLGATE_DOWNLOAD_MODEL` | Installer: `1` downloads the local embedding model without asking, `0` never does. Unset: asked in an interactive run (default yes), skipped in an unattended run. {src:install.sh:1582} |
| `TOLLGATE_CRON_LAUNCHER` | Program the installer hands the nightly job file to, instead of `launchctl`. Tests set it so the real scheduler is never called. {src:install.sh:1675} |
| `TOLLGATE_EMBEDDER` | Embedder for the index: `hash`, `local` or `auto`. A real model is only used when it is already on disk. The installer can download one once when you say yes; nothing else downloads a model. |
| `TOLLGATE_EMBED_MODEL` | Name of the local embedding model. |
| `TOLLGATE_EMBED_QUERY_PROMPT` | Name of the model's own prompt for search questions, for example `query` for the Snowflake Arctic models. Empty means plain questions. A name the model does not have is refused. |
| `TOLLGATE_EMBED_TRUST_REMOTE_CODE` | `1` lets the model run the code that ships with it. Some models need it. Off by default. |
| `TOLLGATE_RERANK` | Set to `1` to turn on the optional local re-ranker. |
| `TOLLGATE_RERANK_MODEL` | Name of the local re-ranker model. |
| `TOLLGATE_INDEX_SKIP` | Extra folder names the index builder skips. |
| `TOLLGATE_CONTEXT_PROVIDER` | Provider for optional context generation: `claude` or `ollama`. Off unless `--context` is passed. |
| `TOLLGATE_CONTEXT_MODEL` | Model for the `claude` context provider. |
| `TOLLGATE_OLLAMA_MODEL` | Model for the `ollama` context provider. |
| `TOLLGATE_OLLAMA_URL` | Address of the `ollama` server. |
| `TOLLGATE_EVAL_CASES` | Path to a golden questions file for the retrieval eval. |
| `TOLLGATE_BRIEF_SOURCES` | Comma separated source names the daily brief must report even when their file is missing. |
| `TOLLGATE_TZ` | Time zone name for the daily brief. Default is the system time zone. |
| `TOLLGATE_SESSION_STATE_WRITER` | Command the pre-compact helper calls to write session state. Unset means the helper logs `not configured` and does nothing. |
| `TOLLGATE_WORKER_ID` | Set by the bootstrap launchers for the worker they start. |
| `TOLLGATE_WORKER_TEMPLATES` | Folder of worker identity templates for the bootstrap launchers. Tollgate ships none; set this to your own folder. |

Test-only variables: `TOLLGATE_REAL_VAULT` (path of the owner's real vault; the end to end test checksums two folders in it before and after its run and fails if they changed; never set by the installer), `TOLLGATE_TEST_PYTHON` (interpreter for tests that need `chromadb`; tests skip when it is missing) and `TOLLGATE_STRAY` (a marker used by one test to check that stray variables do not leak).

## Placeholders in command text

Command files are read by Claude, not run by a shell, so they use these fixed placeholders. They are not environment variables.

| Placeholder | Meaning |
|---|---|
| `{KEY}` | A ticket key: `TOLLGATE_TICKET_PREFIX`, a hyphen, a number. |
| `{INITIALS}` | The value of `TOLLGATE_INITIALS`. Used in an `Author:` line. |
| `{NAME}` | The user's name. The installer fills it into the installed command file, and fills the company name the same way. {src:install.sh:1153} |

There is no command prefix placeholder. Commands have the fixed `tg-` prefix and ship as `commands/tg-*.md`, so `/tg-arch` is the arch command on every machine. The installer still holds a guard (`_LEGACY_SED`) that maps leftover per-install prefix text from an older command file to `tg-`, `TOLLGATE_` and `tg`. Shipped commands do not use it. {src:install.sh:1143}

Folder names in commands are lower case markers such as `{vault}`, `{tickets}`, `{landing}` or `{system_map}`. They are not variables. The command looks each one up when it runs, with `$TOLLGATE_HOME/scripts/core/tg_path <name>`, which reads the paths file. If it prints `not set up`, the command stops and tells the user to run setup. {src:scripts/core/tg_path:25} {src:commands/tg-start.md:3}

Templates and examples inside a command may also hold fill-in markers, such as `{N}`, `{NN}`, `{path}` or `{query}`. Claude replaces these when it writes a file. They are not variables and need no entry here. A fill-in marker is lower case (letters, digits, underscore) or one of `N`, `NN`, `TOTAL`. Any other upper case marker must be one of the placeholders above, so a leftover like `{PREFIX_UPPER}` is an error.

The only variables a command text names are `$TOLLGATE_HOME`, `$TOLLGATE_CODE_DIR` and `$CLAUDE_DOTFILES` (the standards folder). A command does not name `$TOLLGATE_KNOWLEDGE` and never invents a new variable. It calls search only through the one command `$TOLLGATE_HOME/scripts/search/tg-search <query|ground|reference|health>`, never through an interpreter and a script path. The settings hold a permission rule for exactly that command. In the installed copy of a command, the installer replaces every `$TOLLGATE_HOME/` (the search call and every other script call) with the absolute repo path, so the search text matches the permission rule with the absolute path and an installed command holds no `$TOLLGATE_HOME` at all. The installer refuses a repo path that holds whitespace, because the rewritten calls hold the path unquoted. See [tg-search](scripts/search/tg-search.md). {src:scripts/search/tg-search:26} {src:settings.json:274} {src:install.sh:1155} {src:install.sh:160-165}

## Connector files and setup notes

Connectors keep non-secret files in the `state` and `cache` folders from the path loader. A key is never in any of these.

| File or folder | Written by |
|---|---|
| `TOLLGATE_CONNECTORS` file (names, addresses, on/off) | `scripts/connectors/connect.py` |
| `state/slack/cursor.json` | `slack` connector |
| `state/calendar/` | `calendar` connector |
| `state/plane/{KEY}/` (sync ledger) | `plane` connector |
| `plane-sync.json`, next to the paths file (workspace, project and state mapping) | the user, from `plane_sync_settings.example.json` |
| `state/secret-names.json` (names only, no values) | `secrets_tool.py` |
| `cache/<name>.json` | the pull connectors; `daily_brief.py` reads them |

Setup notes: `git-commits` reads local git history and needs no key. The framework still stores the non-secret word `local` as its key so every connector follows one path. The `jira` key is `login:token` for Basic auth, or one token for Bearer auth. A failed pull exits 0 (as in the source); a connector that is not set up exits 2.

## Reference store

The reference store is the user's own searchable library of documents (books, papers, standards, notes, anything). Tollgate ships none. The user decides what goes in and which vector store holds it.

| Item | Rule |
|---|---|
| Logical names in the paths file (`TOLLGATE_PATHS`) | `references` (folder of source documents; the installer points it at the `-library` folder beside the vault, only when the paths file has no `references:` line yet), `index` (where the vector store lives), `standards` (optional folder of standards notes; no default, unset means off). All are read through `scripts/core`. |
| `scripts/search/reference_add.py` | Adds a file or folder to the store. The user chooses tags, for example `design`, `security`. |
| `scripts/search/reference_query.py` | Flags `--situation --stakes --skill --query --top`. Returns passages with source and tag. The situation names a command asks for (for example `spec_define`, `arch_design`, `dev_implement`, `qa_review`) are mapped to the user's tags in the user's own file `references.yaml` next to the paths file. Empty by default. |
| No setup | With no store, or no match, it prints `not set up` or `no match`, exits 0 for no match and non-zero for not set up, makes no network call, and the calling command continues. |
| Names | No book, author or personal file is named anywhere in the repo. |

## Install answers

The installer asks for three answers and saves them in `TOLLGATE_CONFIG`: the vault folder (`TOLLGATE_KNOWLEDGE`), the initials (`TOLLGATE_INITIALS`) and the ticket prefix (`TOLLGATE_TICKET_PREFIX`). Non-interactive flags give the same result: `--vault`, `--initials`, `--ticket-prefix`. {src:install.sh:929}

It asks a fourth question, how the vault is saved, and writes the answer to the paths file, not to `TOLLGATE_CONFIG`. Flag: `--vault-git`. See the next section. {src:install.sh:984}

## Vault git setting

`vault_git: none | local | remote` is a line in the paths file (`TOLLGATE_PATHS`). It says how the user saves the vault. {src:scripts/core/paths.py:144}

| Value | Meaning | What a command prints at the end of a session |
|---|---|---|
| `none` | The vault is plain files, no git. | The list of files written. No git lines. |
| `local` | The vault is a git repo with no remote. | The `git add` and `git commit` lines. |
| `remote` | The vault is a git repo with a remote. | The `git add`, `git commit` and `git push` lines. |

Commands print these lines and never run them, and Tollgate never adds a remote. The user copies the lines and runs them. Commits on a code branch in `/tg-dev` are a separate thing and are unchanged. {src:commands/tg-close.md:272}

How the value is found:

1. The installer asks `none / local / remote`. The default is the saved line, else the mode detected from the vault folder, else `local`. `--vault-git` or `TOLLGATE_VAULT_GIT` answers it up front. A bad value stops the run with exit 2 before anything is written. {src:install.sh:966} {src:install.sh:118}
2. An unattended install with no mode given follows the folder: a vault with no `.git` is saved as `none`, so the setting never claims git the folder does not have. {src:install.sh:979}
3. Commands read it with `$TOLLGATE_HOME/scripts/core/tg_vault_git`. If the line is missing or not one of the three values, the mode is detected from the vault folder: no `.git` is `none`, a repo with no remote is `local`, a repo with a remote is `remote`. {src:scripts/core/paths.py:162} {src:scripts/core/paths.py:168}

See [tg_vault_git](scripts/core/tg_vault_git.md) and the tests in [test_vault_git](tests/installer/test_vault_git.md).

## Ticket and gate format

Spec files carry a line that starts with `Status:`. The gate reads that line. See `docs/gate-lines.md`. Ticket folder: `{ticket}/{KEY}-state.md`, where `{ticket}` is the folder of one ticket under `{tickets}`, the folder the path loader gives for `tickets` (default `02-tickets` in the vault). The gate looks for the ticket flat first (`{tickets}/KEY`), then nested (`{tickets}/PREFIX/KEY`), with the prefix folder matched without regard to case {src:hooks/pre-prompt-expansion-check-gates.py:184-186}. Commands look the folder up at run time with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>`, which prints it or exits 1 with `not found` {src:scripts/core/tg_ticket_dir:23-30}.

## Connector first use

A connector is off until a user tries to use it. The first use asks for the address and key, stores the key in the user's own secret store, writes the connector name and address into `TOLLGATE_CONNECTORS`, then turns it on. With no setup, a connector prints `not set up`, exits non-zero and makes no network call.

## Search models

Switching `TOLLGATE_EMBED_MODEL` needs a full rebuild (`build_index.py --full`). A normal build refuses to mix two models in one index and says so. Questions always use the model that built the index.

### Match the dotfiles search

These settings give the same embedding and re-ranking models as the personal dotfiles search. Download the models first with `scripts/search/download_model.py --yes-download` (it only runs when you start it on purpose, or when you say yes to the installer's offer of the default local model), because Tollgate loads local files only. {src:install.sh:1600}

```
TOLLGATE_EMBEDDER=local
TOLLGATE_EMBED_MODEL=Snowflake/snowflake-arctic-embed-l
TOLLGATE_EMBED_QUERY_PROMPT=query
TOLLGATE_EMBED_TRUST_REMOTE_CODE=1
TOLLGATE_RERANK=1
TOLLGATE_RERANK_MODEL=mixedbread-ai/mxbai-rerank-large-v2
```

Chunk sizes, the retrieval limits and the 0.3 score floor are already the same as the dotfiles values. The dotfiles collections are personal (seven of them); Tollgate keeps three generic ones.
