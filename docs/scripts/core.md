# Scripts: core

Core holds the one place that knows where folders are, plus small tools that need no other area.

## The path loader

`scripts/core/paths.py` turns a logical name into a folder. `scripts/core/tg_path <name>` does the same for shell scripts: it prints the folder, exits 1 with `not set up` on stderr when it cannot resolve (also for an unknown name), and exits 2 with a usage line when it is not given exactly one name. {src:scripts/core/tg_path:18-29}

How it decides, in order:

1. The paths file named by `TOLLGATE_PATHS`. Simple `name: path` lines; a line with an empty value is dropped, and a later duplicate line replaces an earlier one. `~` and `$VARS` are expanded. {src:scripts/core/paths.py:72} {src:scripts/core/paths.py:88-89} {src:scripts/core/paths.py:60}
2. For the vault only, `TOLLGATE_KNOWLEDGE`. {src:scripts/core/paths.py:128-131}
3. A default for the name: a folder inside the vault, a folder in the Tollgate home (`~/.tollgate`), or an environment variable. {src:scripts/core/paths.py:101-112}
4. If none answers, it raises `NotSetUp`. {src:scripts/core/paths.py:100} {src:scripts/core/paths.py:115}

The vault layout comes from one table, `LAYOUT`, in `paths.py`. Every script, hook and the installer takes folder names from it, or from a paths-file line of the same name. {src:scripts/core/paths.py:29-32}

| Name | Default |
|---|---|
| `vault` | `$TOLLGATE_KNOWLEDGE` (no default; `NotSetUp` if unset) {src:scripts/core/paths.py:100} |
| `landing` | `00-landing` inside the vault {src:scripts/core/paths.py:33} |
| `system_map` | `01-system-map` inside the vault {src:scripts/core/paths.py:34} |
| `tickets` | `02-tickets` inside the vault {src:scripts/core/paths.py:35} |
| `knowledge` | `03-knowledge-base` inside the vault {src:scripts/core/paths.py:36} |
| `education` | `04-education` inside the vault {src:scripts/core/paths.py:37} |
| `conversations` | `05-conversations` inside the vault {src:scripts/core/paths.py:38} |
| `chat_threads` | `06-chat-threads` inside the vault {src:scripts/core/paths.py:39} |
| `reference` | `08-reference` inside the vault {src:scripts/core/paths.py:40} |
| `memory`, `output` | `memory` and `output` inside the vault {src:scripts/core/paths.py:41-42} |
| `meetings` | `meetings` inside the vault {src:scripts/core/paths.py:50} |
| `references` | `references` inside the vault. The installer writes a `references:` line pointing at the `-library` folder, so it normally lives outside the vault {src:scripts/core/paths.py:50} {src:install.sh:945-946} |
| `standards` | no default. Unset means the optional standards search collection is off {src:scripts/core/paths.py:113-115} |
| `state` | `$TOLLGATE_STATE_DIR`, else `state` in the Tollgate home {src:scripts/core/paths.py:103-105} |
| `cache`, `logs`, `index` | in the Tollgate home {src:scripts/core/paths.py:51-55} {src:scripts/core/paths.py:106-107} |
| `repos` | `$TOLLGATE_CODE_DIR` (`NotSetUp` if unset) {src:scripts/core/paths.py:108-112} |

Example: `echo "output: ~/notes/out" > "$TOLLGATE_PATHS"`, then `tg_path output` prints the expanded path.

Other helpers in `paths.py`:

- `folder_name(key)`: the folder name relative to the vault for a layout key. A paths-file line wins; a path outside the vault gives only its last part. {src:scripts/core/paths.py:185-200}
- `file_value(name)`: the folder a paths-file line gives, for names `get_path` does not know. {src:scripts/core/paths.py:135-141}
- `ticket_folder(key)` and `iter_ticket_folders()`: find ticket folders kept flat (`<tickets>/KEY`) or by prefix (`<tickets>/PREFIX/KEY`, case-insensitive). A key that is not letters, a hyphen and digits is refused, and a folder whose real location is outside the tickets folder is skipped. {src:scripts/core/paths.py:237-262} {src:scripts/core/paths.py:265-291}
- `layout_dirs()` and the command line forms `python3 paths.py layout` and `python3 paths.py dirs`: list the layout and the folders the installer creates. {src:scripts/core/paths.py:308-313} {src:scripts/core/paths.py:318-322}

Rule SCR-02: no script except `paths.py` and `tg_path` holds a literal folder, home path or host. `tests/scripts/core/test_no_literal_paths.py` scans all of `scripts/` and allows those two files. {src:tests/scripts/core/test_no_literal_paths.py:17-18}

## The vault git setting

The paths file may hold a line `vault_git: none | local | remote`. It says how the vault is saved with git: `none` (plain files), `local` (a git repo with no remote) or `remote` (a git repo with a remote). {src:scripts/core/paths.py:144} {src:scripts/core/paths.py:147-148}

- `vault_git_mode()` reads the line, trims and lower-cases it. A valid value wins even if the vault folder says otherwise. A missing, empty or bad value is detected from the vault folder: no `.git` gives `none`, no remote (or a failing git, or a timeout of 20 seconds) gives `local`, any remote name gives `remote`. {src:scripts/core/paths.py:168-171} {src:scripts/core/paths.py:150-159}
- `scripts/core/tg_vault_git` is the command line form. It prints the mode, exits 1 with the `not set up` text when detection is needed and there is no vault, and exits 2 on any argument. Page: [tg_vault_git](core/tg_vault_git.md). {src:scripts/core/tg_vault_git:23-27} {src:scripts/core/tg_vault_git:19-21}
- The installer asks "How should your vault be saved? none / local / remote" (or takes a flag or `TOLLGATE_VAULT_GIT`), then writes the `vault_git:` line to the paths file, replacing any older one. {src:install.sh:971} {src:install.sh:984-985} It never runs the commit or push lines itself. {src:install.sh:951}

## Other core files

- `bootstrap/`: `bootstrap-dispatch.sh` and `bootstrap-{arch,dev,qa,spec}-{1,2}.sh` launch a worker session. Each is a wrapper that calls `_worker_common.sh` with a worker name and type. {src:scripts/core/bootstrap/bootstrap-dispatch.sh:11} {src:scripts/core/bootstrap/bootstrap-arch-1.sh:11} The common script writes an identity file under the state folder, writes a registry record for every type except `dispatch`, then starts `claude` with the identity as an appended system prompt. Templates come from `TOLLGATE_WORKER_TEMPLATES`, else `templates/workers` in `TOLLGATE_HOME`. {src:scripts/core/bootstrap/_worker_common.sh:27} {src:scripts/core/bootstrap/_worker_common.sh:43} {src:scripts/core/bootstrap/_worker_common.sh:46-50} {src:scripts/core/bootstrap/_worker_common.sh:67}
- `memory/_enums.py`: allowed values for memory notes (scope, confidence, status, data domain) and the score thresholds. {src:scripts/core/memory/_enums.py:13} {src:scripts/core/memory/_enums.py:25} {src:scripts/core/memory/_enums.py:33} {src:scripts/core/memory/_enums.py:49}
- `session_cost.py`: `--mode start` adds an open line and `--mode close` adds a closed line with token counts and cost to `session-costs.jsonl` in the output folder. It needs `CLAUDE_CONFIG_DIR` or `--sessions-dir` to find session logs. {src:scripts/core/session_cost.py:31} {src:scripts/core/session_cost.py:48} {src:scripts/core/session_cost.py:209} {src:scripts/core/session_cost.py:282} {src:scripts/core/session_cost.py:40-42} Prices are four constants in the file to edit by hand. {src:scripts/core/session_cost.py:26-29}
- `run.sh`: `run.sh [all|sweep|index|lint]` runs the sweep, link lint and index jobs by hand and needs `TOLLGATE_HOME`. A job whose script is missing is skipped. {src:scripts/core/run.sh:50-54} {src:scripts/core/run.sh:18-21} {src:scripts/core/run.sh:35} {src:scripts/core/run.sh:42}
- `setup_venv.sh`: makes a venv (default `venv` inside the state folder) and installs `requirements.txt`. `--force` deletes and recreates it. {src:scripts/core/setup_venv.sh:31-32} {src:scripts/core/setup_venv.sh:46-48} {src:scripts/core/setup_venv.sh:57} The shell command `tg-search` looks for this venv. {src:scripts/search/tg-search:44}
- `hooks/`: two helper scripts (`precompact_hook.sh`, `session_state_hook.sh`). They are not wired into `settings.json`; a hook entry may call them. {src:scripts/core/hooks/precompact_hook.sh:6} {src:scripts/core/hooks/session_state_hook.sh:7} Searched `settings.json`, `install.sh` and `hooks/` for both names on 2026-11-19; only the tests name them. The prompt search hook is `hooks/pre-submit-vault-inject.sh`, wired in `settings.json`. {src:settings.json:8}

## Tests

`tests/scripts/core/run.sh`. Files: `test_paths.py`, `test_vault_git.py`, `test_bootstrap.py`, `test_no_literal_paths.py`.
