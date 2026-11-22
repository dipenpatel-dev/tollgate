# Plane connector

The `plane` connector keeps ticket cards in Plane in step with ticket files in your vault. It is off until you use it. With no setup it prints `plane: not set up`, tells you how to set it up, exits non-zero and makes no network call {src:scripts/connectors/plane/cli.py:162} {src:scripts/connectors/plane/cli.py:163} {src:scripts/connectors/plane/cli.py:195} {src:scripts/connectors/plane/cli.py:196} {src:scripts/connectors/plane/cli.py:197} {src:scripts/connectors/registry.py:325} {src:scripts/connectors/registry.py:326} {src:scripts/connectors/registry.py:327}. To write another connector, read `docs/connectors.md`.

## Files in `scripts/connectors/plane/`

| File | What it does |
|------|--------------|
| `plane_sync.py` | Entry point: `python3 plane_sync.py sync\|drift\|create ...`. It finds the scripts folder by itself {src:scripts/connectors/plane/plane_sync.py:14} {src:scripts/connectors/plane/plane_sync.py:16} {src:scripts/connectors/plane/plane_sync.py:19}. |
| `__main__.py` | The same entry for `python3 -m connectors.plane` {src:scripts/connectors/plane/__main__.py:5} {src:scripts/connectors/plane/__main__.py:12} {src:scripts/connectors/plane/__main__.py:15}. |
| `cli.py` | Argument parsing, the connector setup check, the `create` confirmation and the exit codes {src:scripts/connectors/plane/cli.py:76} {src:scripts/connectors/plane/cli.py:113} {src:scripts/connectors/plane/cli.py:177}. |
| `plane_sync_settings.py` | Reads and checks `plane-sync.json` {src:scripts/connectors/plane/plane_sync_settings.py:19} {src:scripts/connectors/plane/plane_sync_settings.py:175}. |
| `plane_sync_ledger.py` | The per-ticket record of what was already sent {src:scripts/connectors/plane/plane_sync_ledger.py:20} {src:scripts/connectors/plane/plane_sync_ledger.py:46} {src:scripts/connectors/plane/plane_sync_ledger.py:85}. |
| `vault_ticket_files.py` | Finds ticket folders, reads state files, writes a new ticket folder (create only) {src:scripts/connectors/plane/vault_ticket_files.py:83} {src:scripts/connectors/plane/vault_ticket_files.py:185} {src:scripts/connectors/plane/vault_ticket_files.py:245}. |
| `vault_ticket_creator.py` | The `create` command {src:scripts/connectors/plane/vault_ticket_creator.py:175}. |
| `plane_ticket_syncer.py` | The `sync` command {src:scripts/connectors/plane/plane_ticket_syncer.py:293}. |
| `plane_drift_checker.py` | The `drift` command. Read only {src:scripts/connectors/plane/plane_drift_checker.py:5} {src:scripts/connectors/plane/plane_drift_checker.py:90}. |
| `plane_comment_builder.py` | Builds comment text: secret scan, length cut, session and extras text {src:scripts/connectors/plane/plane_comment_builder.py:31} {src:scripts/connectors/plane/plane_comment_builder.py:39} {src:scripts/connectors/plane/plane_comment_builder.py:47}. |
| `plane_markdown.py` | A small markdown to HTML renderer with no outside library {src:scripts/connectors/plane/plane_markdown.py:2} {src:scripts/connectors/plane/plane_markdown.py:104}. |
| `plane_work_item_client.py` | The seven paced Plane API calls {src:scripts/connectors/plane/plane_work_item_client.py:2}. |

The folder also holds `plane_sync_settings.example.json` and `plane_ticket_state_template.md` {src:scripts/connectors/plane/vault_ticket_creator.py:36}.

## Set up

1. Run any command below in a terminal. The first use asks for the Plane address (it must start with `https://`) and the key (typed hidden) {src:scripts/connectors/plane/cli.py:171} {src:scripts/connectors/plane/plane_work_item_client.py:129} {src:scripts/connectors/plane/plane_work_item_client.py:130} {src:scripts/connectors/connect.py:43} {src:scripts/connectors/connect.py:44}.
2. The key goes into your secret store (macOS Keychain or Linux `secret-tool`). It never goes into a file, an argument list or an environment variable kept on disk {src:scripts/connectors/secret_store.py:10} {src:scripts/connectors/secret_store.py:11} {src:scripts/connectors/secret_store.py:12}.
3. The name, address and on/off go into the file named by `TOLLGATE_CONNECTORS` {src:scripts/connectors/registry.py:264} {src:scripts/connectors/registry.py:318}.
4. Without a terminal use `python3 $TOLLGATE_HOME/scripts/connectors/connect.py on plane --address URL --key-stdin` {src:scripts/connectors/connect.py:10} {src:scripts/connectors/connect.py:88} {src:scripts/connectors/connect.py:89}.
5. Put a settings file named `plane-sync.json` in the same folder as the paths file (`TOLLGATE_PATHS`), or pass `--settings FILE`. Copy `scripts/connectors/plane/plane_sync_settings.example.json` and edit it {src:scripts/connectors/plane/plane_sync_settings.py:19} {src:scripts/connectors/plane/plane_sync_settings.py:85} {src:scripts/connectors/plane/plane_sync_settings.py:90} {src:scripts/connectors/plane/cli.py:78}.

`connect.py off plane` turns it off and removes the key {src:scripts/connectors/registry.py:383} {src:scripts/connectors/registry.py:390}.

## Commands

Run `python3 $TOLLGATE_HOME/scripts/connectors/plane/plane_sync.py [--settings FILE] COMMAND` {src:scripts/connectors/plane/plane_sync.py:3} {src:scripts/connectors/plane/cli.py:78}.

| Command | What it does |
|---------|--------------|
| `sync KEY [--extras spec\|dev] [--from-start]` | Writes the ticket's description, status and new session log text to its card. Only what changed is sent {src:scripts/connectors/plane/cli.py:88} {src:scripts/connectors/plane/cli.py:89} {src:scripts/connectors/plane/cli.py:90} {src:scripts/connectors/plane/cli.py:91} {src:scripts/connectors/plane/plane_ticket_syncer.py:103} {src:scripts/connectors/plane/plane_ticket_syncer.py:157} {src:scripts/connectors/plane/plane_ticket_syncer.py:244} {src:scripts/connectors/plane/plane_ticket_syncer.py:245}. |
| `drift KEY [KEY ...]` | Read only. Prints one line for each mismatch between a card and its state file: a missing card, a wrong number, a wrong name or a wrong description. Exit 2 when there is any mismatch {src:scripts/connectors/plane/cli.py:92} {src:scripts/connectors/plane/cli.py:93} {src:scripts/connectors/plane/plane_drift_checker.py:54} {src:scripts/connectors/plane/plane_drift_checker.py:57} {src:scripts/connectors/plane/plane_drift_checker.py:58} {src:scripts/connectors/plane/plane_drift_checker.py:44} {src:scripts/connectors/plane/plane_drift_checker.py:105}. |
| `create --prefix P --title T --priority X --scope S --repo R --type feature\|fix\|research [--yes]` | Makes the card first, then the ledger, then the ticket folder and state file {src:scripts/connectors/plane/cli.py:80} {src:scripts/connectors/plane/cli.py:81} {src:scripts/connectors/plane/cli.py:86} {src:scripts/connectors/plane/cli.py:87} {src:scripts/connectors/plane/vault_ticket_creator.py:94} {src:scripts/connectors/plane/vault_ticket_creator.py:139} {src:scripts/connectors/plane/vault_ticket_creator.py:140}. It always asks first. |

`create` asks `[y/N]` in a terminal. With no terminal it refuses unless you pass `--yes`. `sync` and `drift` never ask {src:scripts/connectors/plane/cli.py:117} {src:scripts/connectors/plane/cli.py:118} {src:scripts/connectors/plane/cli.py:120} {src:scripts/connectors/plane/cli.py:121} {src:scripts/connectors/plane/cli.py:124} {src:scripts/connectors/plane/cli.py:172}.

Details that matter:

- `sync` on the first run finds the existing card by its ticket id and builds the ledger from it. Existing session log text is treated as already sent unless you pass `--from-start`, which is valid only when no ledger exists {src:scripts/connectors/plane/plane_ticket_syncer.py:80} {src:scripts/connectors/plane/plane_ticket_syncer.py:87} {src:scripts/connectors/plane/plane_ticket_syncer.py:95} {src:scripts/connectors/plane/plane_ticket_syncer.py:96} {src:scripts/connectors/plane/plane_ticket_syncer.py:97} {src:scripts/connectors/plane/plane_ticket_syncer.py:314} {src:scripts/connectors/plane/plane_ticket_syncer.py:315}.
- A status change moves the card to the board column the `status_map` names and posts a generated status comment. An unknown status word moves nothing and gives exit 2 {src:scripts/connectors/plane/plane_ticket_syncer.py:159} {src:scripts/connectors/plane/plane_ticket_syncer.py:161} {src:scripts/connectors/plane/plane_ticket_syncer.py:149} {src:scripts/connectors/plane/plane_ticket_syncer.py:150} {src:scripts/connectors/plane/plane_ticket_syncer.py:290}.
- `--extras spec` adds the spec requirements, the acceptance criteria and the design diagram to the comment. `--extras dev` adds the edge case validation file {src:scripts/connectors/plane/plane_comment_builder.py:26} {src:scripts/connectors/plane/plane_comment_builder.py:101} {src:scripts/connectors/plane/plane_comment_builder.py:115} {src:scripts/connectors/plane/plane_ticket_syncer.py:183} {src:scripts/connectors/plane/plane_ticket_syncer.py:185}.
- `create` stops when the highest card number in Plane and the highest local ticket number differ, so numbers do not fork. It adopts a half finished card with the same title {src:scripts/connectors/plane/vault_ticket_creator.py:81} {src:scripts/connectors/plane/vault_ticket_creator.py:83} {src:scripts/connectors/plane/vault_ticket_creator.py:87} {src:scripts/connectors/plane/vault_ticket_creator.py:88}. It never overwrites an existing ticket folder {src:scripts/connectors/plane/vault_ticket_files.py:248} {src:scripts/connectors/plane/vault_ticket_files.py:250}.
- A ticket id whose prefix has no project in the settings is skipped with a `skip` line {src:scripts/connectors/plane/vault_ticket_files.py:65} {src:scripts/connectors/plane/vault_ticket_files.py:66} {src:scripts/connectors/plane/vault_ticket_files.py:75}.

## Where things come from

| Thing | Source |
|-------|--------|
| Address | The connector's entry in the connectors file (first use) {src:scripts/connectors/registry.py:376} |
| Key | The secret store {src:scripts/connectors/registry.py:402} |
| Workspace, project key per ticket prefix, status to board column map, new card column | The settings file {src:scripts/connectors/plane/plane_sync_settings.py:50} {src:scripts/connectors/plane/plane_sync_settings.py:186} {src:scripts/connectors/plane/plane_sync_settings.py:188} {src:scripts/connectors/plane/plane_sync_settings.py:189} {src:scripts/connectors/plane/plane_sync_settings.py:190} |
| Ticket folder | `tickets` from the path loader, then the shared lookup: `<tickets>/PREFIX/KEY/` or a flat `<tickets>/KEY/`. For a ticket that does not exist yet, the new folder goes under the prefix folder when one exists, else flat {src:scripts/connectors/plane/cli.py:133} {src:scripts/connectors/plane/vault_ticket_files.py:19} {src:scripts/connectors/plane/vault_ticket_files.py:83} {src:scripts/connectors/plane/vault_ticket_files.py:89} {src:scripts/connectors/plane/vault_ticket_files.py:95} {src:scripts/connectors/plane/vault_ticket_files.py:96} {src:scripts/connectors/plane/vault_ticket_files.py:97} |
| State file | `{KEY}-state.md` in that folder {src:scripts/connectors/plane/vault_ticket_files.py:186} |
| Other ticket files | `{KEY}-spec.md`, `{KEY}-design.md`, `{KEY}-edge-case-validation.md`, `{KEY}-session-*.md` {src:scripts/connectors/plane/plane_ticket_syncer.py:183} {src:scripts/connectors/plane/plane_ticket_syncer.py:185} {src:scripts/connectors/plane/vault_ticket_files.py:265} |
| Ledger (what was already sent) | `state` from the path loader, then `plane/{KEY}/plane_sync_ledger.json` {src:scripts/connectors/plane/cli.py:134} {src:scripts/connectors/plane/plane_sync_ledger.py:20} {src:scripts/connectors/plane/plane_sync_ledger.py:47} |
| New ticket template | `template_path` in the settings, else the file shipped next to the scripts {src:scripts/connectors/plane/vault_ticket_creator.py:36} {src:scripts/connectors/plane/vault_ticket_creator.py:120} |

The state file status is the `status:` line in its frontmatter. If that is missing, the first `Status:` line at column one outside a code fence is used (the gate line format) {src:scripts/connectors/plane/vault_ticket_files.py:171} {src:scripts/connectors/plane/vault_ticket_files.py:152} {src:scripts/connectors/plane/vault_ticket_files.py:153} {src:scripts/connectors/plane/vault_ticket_files.py:161}.

## Safety rules the code keeps

1. Every network call goes through the `http` object the framework hands in. The client imports only URL building helpers, no request library {src:scripts/connectors/plane/plane_work_item_client.py:2} {src:scripts/connectors/plane/plane_work_item_client.py:17} {src:scripts/connectors/plane/plane_work_item_client.py:160}.
2. Secret-looking text (keys, tokens, passwords, private key blocks, link credentials) stops a send. Nothing is sent and the line names the pattern {src:scripts/connectors/plane/plane_sync_settings.py:24} {src:scripts/connectors/plane/plane_sync_settings.py:25} {src:scripts/connectors/plane/plane_sync_settings.py:30} {src:scripts/connectors/plane/plane_ticket_syncer.py:107} {src:scripts/connectors/plane/plane_ticket_syncer.py:108} {src:scripts/connectors/plane/plane_ticket_syncer.py:252} {src:scripts/connectors/plane/plane_ticket_syncer.py:253}.
3. Comments are cut to `comment_max_chars` with a pointer to the vault files {src:scripts/connectors/plane/plane_ticket_syncer.py:212} {src:scripts/connectors/plane/plane_ticket_syncer.py:213} {src:scripts/connectors/plane/plane_comment_builder.py:39} {src:scripts/connectors/plane/plane_comment_builder.py:44}.
4. A call is never retried. Calls are spaced by `min_seconds_between_calls` {src:scripts/connectors/plane/plane_work_item_client.py:2} {src:scripts/connectors/plane/plane_work_item_client.py:142} {src:scripts/connectors/plane/plane_work_item_client.py:145} {src:scripts/connectors/plane/plane_work_item_client.py:146}.
5. Raw HTML and images in text are never sent as HTML {src:scripts/connectors/plane/plane_markdown.py:2} {src:scripts/connectors/plane/plane_markdown.py:105}.
6. Error lines hold the method, path and status only, never the address or key {src:scripts/connectors/plane/plane_work_item_client.py:49} {src:scripts/connectors/plane/plane_work_item_client.py:50} {src:scripts/connectors/plane/plane_work_item_client.py:57}.
7. Each posted comment carries an id made from its text, and the ledger remembers those ids, so a repeat run does not post the same comment twice {src:scripts/connectors/plane/plane_comment_builder.py:125} {src:scripts/connectors/plane/plane_ticket_syncer.py:242} {src:scripts/connectors/plane/plane_ticket_syncer.py:245}.

## Exit codes

`0` finished. `1` settings or file problem. `2` stopped on purpose, not set up, a ledger problem, or unknown status word. `3` Plane call failed {src:scripts/connectors/plane/cli.py:37} {src:scripts/connectors/plane/cli.py:38} {src:scripts/connectors/plane/cli.py:39} {src:scripts/connectors/plane/cli.py:40} {src:scripts/connectors/plane/cli.py:197} {src:scripts/connectors/plane/cli.py:200} {src:scripts/connectors/plane/cli.py:203} {src:scripts/connectors/plane/cli.py:206} {src:scripts/connectors/plane/cli.py:209}.

## Settings keys

Required: `workspace_slug`, `new_ticket_board_status`, `status_map`, and `prefix_table` (or set `TOLLGATE_TICKET_PREFIX`, which gives a one prefix table) {src:scripts/connectors/plane/plane_sync_settings.py:21} {src:scripts/connectors/plane/plane_sync_settings.py:50} {src:scripts/connectors/plane/plane_sync_settings.py:134} {src:scripts/connectors/plane/plane_sync_settings.py:137}. Optional: `external_source_name` (default `tollgate`), `blocked_words`, `secret_patterns`, `min_seconds_between_calls`, `http_timeout_seconds`, `page_size`, `comment_max_chars`, `template_path` {src:scripts/connectors/plane/plane_sync_settings.py:22} {src:scripts/connectors/plane/plane_sync_settings.py:23} {src:scripts/connectors/plane/plane_sync_settings.py:45} {src:scripts/connectors/plane/plane_sync_settings.py:49} {src:scripts/connectors/plane/plane_sync_settings.py:193}. Each prefix row takes `project_key` (default the prefix) and `number_width` (default 1) {src:scripts/connectors/plane/plane_sync_settings.py:121} {src:scripts/connectors/plane/plane_sync_settings.py:122}.

## Tests

`tests/scripts/connectors/plane/run.sh` runs against a stub Plane server that listens on `127.0.0.1` only. CON-01 to CON-04 are in `test_plane_connector.py`. No test makes an outside call.
