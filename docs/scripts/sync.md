# Scripts: sync

Sync scripts move knowledge into the vault and keep it tidy. Each one gets its folders from the path loader, through `scripts/core/tg_path` in shell scripts {src:scripts/sync/sync_repos.sh:17} {src:scripts/sync/sync_repos.sh:18} and `core.paths.get_path` in Python {src:scripts/sync/sweep:36}. The nightly job in `docs/scripts/cron.md` calls most of them {src:scripts/cron/nightly_index.sh:125} {src:scripts/cron/nightly_index.sh:130} {src:scripts/cron/nightly_index.sh:131}.

## Sweep

`scripts/sync/sweep [--yes] [--staging-dir DIR] [--vault DIR]` flushes the knowledge staging folder (`output/knowledge-staging`) into the vault and the index {src:scripts/sync/sweep:21} {src:scripts/sync/sweep:47} {src:scripts/sync/sweep:343}.

1. It reads each staged record (a small JSON file) and prints the plan: the note it will write and the index step {src:scripts/sync/sweep:96} {src:scripts/sync/sweep:352} {src:scripts/sync/sweep:353}.
2. Without `--yes` it stops there. It writes nothing and does not open the index {src:scripts/sync/sweep:354} {src:scripts/sync/sweep:355}.
3. With `--yes` it writes the vault note, adds the record to the `knowledge` collection of the index, and deletes the staging file {src:scripts/sync/sweep:312} {src:scripts/sync/sweep:319} {src:scripts/sync/sweep:320} {src:scripts/sync/sweep:48}.
4. If the index step fails, the vault note stays, the staging file is marked `vault_written`, and the next sweep retries only the index {src:scripts/sync/sweep:322} {src:scripts/sync/sweep:324} {src:scripts/sync/sweep:311}.

The last line is `processed=N written=N synced=N partial=N skipped=N` {src:scripts/sync/sweep:68} {src:scripts/sync/sweep:69}. Exit 2 means not set up {src:scripts/sync/sweep:344} {src:scripts/sync/sweep:346}.

The `/tg-sweep` command runs the script with no flag first, states what it will write, and only after a yes runs it again with `--yes` {src:commands/tg-sweep.md:8} {src:commands/tg-sweep.md:11} {src:commands/tg-sweep.md:14} {src:commands/tg-sweep.md:17}.

A record needs `id`, `date`, `ticket`, `record_type`, `source_repo`, `source_ref`, `summary` and `detail` {src:scripts/sync/sweep:52}. Each field used in a file name may hold only letters, digits, dot, underscore and hyphen, and a record that breaks this is refused and skipped {src:scripts/sync/sweep:104} {src:scripts/sync/sweep:105} {src:scripts/sync/sweep:117} {src:scripts/sync/sweep:162} {src:scripts/sync/sweep:163}.

Records go to:

- decisions and corrections: `03-knowledge-base/decisions/<date>-<ticket>.md` {src:scripts/sync/sweep:154} {src:scripts/sync/sweep:54};
- patterns: `03-knowledge-base/patterns/<date>-<ticket>.md` {src:scripts/sync/sweep:159} {src:scripts/sync/sweep:55};
- repo docs: `01-system-map/repos/<repo>.md` {src:scripts/sync/sweep:161} {src:scripts/sync/sweep:56};
- approvals: `approval-<id>.md` in the folder of the ticket, found by `_ticket_dir` {src:scripts/sync/sweep:156}. An existing ticket folder, flat (`<tickets>/KEY`) or under its prefix folder (`<tickets>/PREFIX/KEY`), is used as found through the shared ticket lookup {src:scripts/sync/sweep:138-140}. A ticket with no folder yet gets `<tickets>/PREFIX/KEY` {src:scripts/sync/sweep:141-143}. A key that is not letters, a hyphen and digits keeps the flat `<tickets>/KEY` {src:scripts/sync/sweep:144}.

## Other sync scripts

| Script | What it does |
|---|---|
| `sync_conversations.py [--full] [--sessions-dir DIR]` | Turns Claude session files into markdown in the `conversations` path, one file per session under `<year>/<month>/` {src:scripts/sync/sync_conversations.py:5} {src:scripts/sync/sync_conversations.py:247} {src:scripts/sync/sync_conversations.py:253}. The session folder is only read {src:scripts/sync/sync_conversations.py:7}. State goes to the `state` path {src:scripts/sync/sync_conversations.py:41} {src:scripts/sync/sync_conversations.py:71} {src:scripts/sync/sync_conversations.py:72}. Each transcript is scrubbed of credentials and scanned for PHI first; a hit means it is not written and a short record goes to `quarantine.log` in the state folder {src:scripts/sync/sync_conversations.py:317} {src:scripts/sync/sync_conversations.py:322} {src:scripts/sync/sync_conversations.py:323}. Without `--sessions-dir` it uses a `sessions` line of the paths file, else `CLAUDE_CONFIG_DIR/projects/<vault slug>` {src:scripts/sync/sync_conversations.py:57} {src:scripts/sync/sync_conversations.py:60} {src:scripts/sync/sync_conversations.py:63}. |
| `lint_wikilinks.py [--dry-run] [--full] [--skip-dir NAME]` | Converts markdown links that point at vault files into wiki links {src:scripts/sync/lint_wikilinks.py:5} {src:scripts/sync/lint_wikilinks.py:16}. `--dry-run` reports only {src:scripts/sync/lint_wikilinks.py:213}. It skips a built in list of folders and keeps its scan state in `lint_wikilinks_state.json` in the state folder {src:scripts/sync/lint_wikilinks.py:41} {src:scripts/sync/lint_wikilinks.py:43} {src:scripts/sync/lint_wikilinks.py:51}. It warns when two notes share a file name {src:scripts/sync/lint_wikilinks.py:227} {src:scripts/sync/lint_wikilinks.py:234}. |
| `sync_meetings.py --source DIR [--dry-run] [--full]` | Copies exported meeting notes (file names in the Gemini notes pattern) into `<meetings>/<year>/<month>/<date>_<slug>/notes.md` {src:scripts/sync/sync_meetings.py:59} {src:scripts/sync/sync_meetings.py:181} {src:scripts/sync/sync_meetings.py:189}. Never overwrites an existing `notes.md` {src:scripts/sync/sync_meetings.py:199} {src:scripts/sync/sync_meetings.py:200} {src:scripts/sync/sync_meetings.py:203}. Without `--source` it exits 1 {src:scripts/sync/sync_meetings.py:141} {src:scripts/sync/sync_meetings.py:143}. Each note is scrubbed and scanned for PHI before it is written; a hit goes to `.quarantine.log` in the meetings folder {src:scripts/sync/sync_meetings.py:157} {src:scripts/sync/sync_meetings.py:225} {src:scripts/sync/sync_meetings.py:230} {src:scripts/sync/sync_meetings.py:231}. This is the seam where a meeting connector plugs in: any tool that drops exported markdown into a folder works {src:scripts/sync/sync_meetings.py:7} {src:scripts/sync/sync_meetings.py:8}. |
| `sync_repos.sh [LIST]` | Mirrors the repos named in the list file (default `repos.list` in the state folder) into the `repos` path {src:scripts/sync/sync_repos.sh:12} {src:scripts/sync/sync_repos.sh:20}. With no list file it says so and exits 0 {src:scripts/sync/sync_repos.sh:25} {src:scripts/sync/sync_repos.sh:27} {src:scripts/sync/sync_repos.sh:28}. A new repo is cloned; an existing one is fetched and reset hard to the remote default branch, so the mirror is read only and local edits are lost {src:scripts/sync/sync_repos.sh:46} {src:scripts/sync/sync_repos.sh:71}. Any failure gives exit 1 after all repos were tried {src:scripts/sync/sync_repos.sh:85} {src:scripts/sync/sync_repos.sh:91}. |
| `vault_write_scan.py` | A library, not a command. `sync_conversations.py` and `sync_meetings.py` use it. It redacts secrets and scans the text with `hooks/scrub_secrets.py` and `hooks/phi_patterns.py` before a write, appends a quarantine line with no content, and reads and writes the JSON state files atomically {src:scripts/sync/vault_write_scan.py:5} {src:scripts/sync/vault_write_scan.py:6} {src:scripts/sync/vault_write_scan.py:7} {src:scripts/sync/vault_write_scan.py:64} {src:scripts/sync/vault_write_scan.py:74} {src:scripts/sync/vault_write_scan.py:83} {src:scripts/sync/vault_write_scan.py:98}. |

The Slack connector lives in `scripts/connectors/comms/` and the Databricks one in `scripts/connectors/data/`. See `docs/scripts/connectors-comms.md` and `docs/scripts/connectors-data.md`.

## Tests

`tests/scripts/sync/run.sh`.
