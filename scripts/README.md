# Tollgate scripts

Small helper programs that the commands and hooks call. Each area has its own folder. Python scripts need Python 3.9 or newer {src:docs/prerequisites.md:81}.

| Folder | What it holds |
|---|---|
| `core` | path loader, worker launchers, small tools, hook helpers |
| `search`, `cache` | reference search and cached pulls |
| `state`, `sync`, `cron` | ticket state, sweeps, scheduled jobs |
| `chart` | `chart_check`, which checks the Mermaid diagrams in documents against `chart_rules.json` {src:scripts/chart/chart_check:4}; the data source seam {src:scripts/chart/data_source.py:3}; `mermaid_block.py`, which copies one diagram out of a note {src:scripts/chart/mermaid_block.py:4} |
| `qa` | `scan_notebooks.py`, which counts sensitive-looking patterns in notebooks {src:scripts/qa/scan_notebooks.py:4} |
| `validation` | `validate_state_files.py`, which checks the front matter of ticket state files {src:scripts/validation/validate_state_files.py:4} |
| `connectors` | the plug-in point for outside tools |

## One rule about folders

No script writes a folder name, a home path or a host name. Every folder comes from the path loader in `core/paths.py`.

- Python: `from core.paths import get_path, NotSetUp`, then `get_path("vault")` {src:scripts/core/tg_path:15}.
- Shell: `"$TOLLGATE_HOME/scripts/core/tg_path" vault`. It prints the folder. If it cannot find one it exits 1 and prints `not set up` on stderr {src:scripts/core/tg_path:4} {src:scripts/core/tg_path:25} {src:scripts/core/tg_path:26}.
- Tickets live in the `tickets` folder, one level down under a prefix folder and then the key {src:scripts/core/paths.py:35}. Find a ticket folder with `ticket_folder(key)` or walk them with `iter_ticket_folders()` from `core.paths`, never by joining the key onto the tickets folder {src:scripts/core/paths.py:237} {src:scripts/core/paths.py:240} {src:scripts/core/paths.py:265}.

Names: `vault`, `landing`, `system_map`, `tickets`, `knowledge`, `education`, `conversations`, `chat_threads`, `reference`, `memory`, `output`, `meetings`, `references`, `state`, `cache`, `logs`, `index`, `repos`, `standards` (no default) {src:scripts/core/paths.py:32} {src:scripts/core/paths.py:50} {src:scripts/core/paths.py:56} {src:scripts/core/paths.py:114}. Details in `docs/scripts/core.md`.

## Setup

Run `core/setup_venv.sh` to make a venv with the libraries in `requirements.txt`. Most scripts run on plain `python3`. The vault census and backfill scripts, the session log backfill and the doc drift patrol in `state` import `pyyaml`, and the search scripts need `chromadb` {src:scripts/requirements.txt:7} {src:scripts/requirements.txt:8} {src:scripts/state/vault_census.py:36} {src:scripts/state/backfill_vault_frontmatter.py:47} {src:scripts/state/backfill_session_logs.py:19} {src:scripts/state/doc_drift_patrol.py:22}.

## Tests

Each area has `tests/scripts/<area>/run.sh`. Tests run in a throwaway home and never touch your real files.
