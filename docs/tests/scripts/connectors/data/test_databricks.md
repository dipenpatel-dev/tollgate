---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/data/test_databricks.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/data/databricks.py, scripts/connectors/registry.py, scripts/chart/data_source.py, scripts/qa/scan_notebooks.py]         # source files under test, relative paths from repo root
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

Tests for the Databricks connector. They check the four connector life-cycle rules (off until first use, key stored nowhere on disk, on survives a restart, off returns to not set up), the guard that lets only one read-only statement through, bound parameters, the 500 row cap, logging of counts only, the table reading source used by charts, the notebook source used by the scanner, the table definition export, and the redaction of a secret in a table comment during that export. No real workspace is called: a stub object answers every request.

## Dependencies

**Depends on.**
- Under test: [[databricks]] / [databricks](../../../../scripts/connectors/data/databricks.md) imported as `dbx` {src:tests/scripts/connectors/data/test_databricks.py:31}; [[registry]] / [registry](../../../../scripts/connectors/registry.md) and `connect` {src:tests/scripts/connectors/data/test_databricks.py:30}. Through the connector: [[data_source]] / [data_source](../../../../scripts/chart/data_source.md) for the identifier and sort checks {src:scripts/connectors/data/databricks.py:34}, and [[scan_notebooks]] / [scan_notebooks](../../../../scripts/qa/scan_notebooks.md) for the scanner {src:scripts/connectors/data/databricks.py:35}, and [[comms_common]] / [comms_common](../../../../scripts/connectors/comms/comms_common.md) for the secret redaction and the count line {src:scripts/connectors/data/databricks.py:36}.
- Test helpers: [[connector_helpers]] / [connector_helpers](../../../harness/connector_helpers.md) for `MockClient`, `FakeSecretStore` and `assert_no_network` {src:tests/scripts/connectors/data/test_databricks.py:28}; [[throwaway_home]] / [throwaway_home](../../../harness/throwaway_home.md) {src:tests/scripts/connectors/data/test_databricks.py:29}.
- Standard library: `base64`, `contextlib`, `io`, `json`, `logging`, `os`, `pathlib`, `sys`, `tempfile`, `unittest`, `uuid` {src:tests/scripts/connectors/data/test_databricks.py:11-21}.

**Used by.** Run by [[run]] / [run](run.md) through the pattern `test_*.py` {src:tests/scripts/connectors/data/run.sh:6}. `git grep` for `test_databricks` outside `docs/` finds no other reference (searched 2026-11-20). The only other hit for the name is a hook test method called `test_databricks_deny_then_ask` {src:tests/hooks/test_hooks.py:111}, which is a different test.

## Behavior

Fixtures.
- `Stub` is a fake http object. It records each request {src:tests/scripts/connectors/data/test_databricks.py:45}, answers the statements address with the state and rows it was given, cut to the `row_limit` the client sent {src:tests/scripts/connectors/data/test_databricks.py:46-54}, answers the tables address {src:tests/scripts/connectors/data/test_databricks.py:55-56}, answers the notebook export address with base64 notebook text when the encoded path is in the URL, else 404 {src:tests/scripts/connectors/data/test_databricks.py:57-62}.
- `Base.setUp` makes a throwaway home, copies the environment, installs a fake secret store and the stub as the http factory, and registers the connector {src:tests/scripts/connectors/data/test_databricks.py:71-81}. `tearDown` resets the store and factory and restores the environment {src:tests/scripts/connectors/data/test_databricks.py:83-88}.
- `turn_on` passes a fake key through an environment variable to `connect.main on databricks` and deletes the variable afterwards {src:tests/scripts/connectors/data/test_databricks.py:90-96}.

`TestCon` (four tests):
1. CON-01: with nothing set up, `check` exits non-zero, prints `databricks: not set up` and makes no call {src:tests/scripts/connectors/data/test_databricks.py:109-114}.
2. CON-02: turning on stores the key through the store, and no file under the repo or the throwaway home contains the key bytes {src:tests/scripts/connectors/data/test_databricks.py:116-130}.
3. CON-03: after turning on and clearing the registry, `check` reaches the client once, posts to the statements address with a Bearer header holding the key and the warehouse id in the body {src:tests/scripts/connectors/data/test_databricks.py:132-144}. The code builds exactly those parts {src:scripts/connectors/data/databricks.py:120} {src:scripts/connectors/data/databricks.py:150}.
4. CON-04: after turning off, `check` is not set up again and makes no call {src:tests/scripts/connectors/data/test_databricks.py:146-153}.

`TestGuard` (four tests):
1. The guard lets through single `SELECT`, `SHOW` and `DESCRIBE` statements, a trailing semicolon, and `;` or `--` inside quotes {src:tests/scripts/connectors/data/test_databricks.py:157-160}, as the loop in `check_read_only` allows {src:scripts/connectors/data/databricks.py:69-86}.
2. It refuses drop, delete, insert, update, create, merge, two statements, line and block comments, an empty or blank statement, an open quote, and a `WITH` statement {src:tests/scripts/connectors/data/test_databricks.py:163-168}. The `WITH` case is refused only because `WITH` is not one of the three allowed first words {src:scripts/connectors/data/databricks.py:40} {src:scripts/connectors/data/databricks.py:92-93}; a read-only query written with a `WITH` clause cannot be sent.
3. A refused statement makes no http call {src:tests/scripts/connectors/data/test_databricks.py:170-174}; the check runs before the request is built {src:scripts/connectors/data/databricks.py:146}.
4. An `http://` address to a normal host raises `NotSetUp`, while `http://127.0.0.1:9` is accepted {src:tests/scripts/connectors/data/test_databricks.py:176-179}, matching `_check_address` {src:scripts/connectors/data/databricks.py:97-104}.

`TestQuery` (five tests):
1. A value goes in `parameters`, not in the statement text, and the catalog is sent {src:tests/scripts/connectors/data/test_databricks.py:183-189}; see {src:scripts/connectors/data/databricks.py:154-160}.
2. Asking for 10000 rows returns 500, `truncated` is true and the request asked for 501 {src:tests/scripts/connectors/data/test_databricks.py:191-196}; see {src:scripts/connectors/data/databricks.py:149} and {src:scripts/connectors/data/databricks.py:153}.
3. A statement whose state is `FAILED` raises an error that names the state and holds no row data {src:tests/scripts/connectors/data/test_databricks.py:198-201}; see {src:scripts/connectors/data/databricks.py:162-164}.
4. A client with no warehouse raises `NotSetUp` {src:tests/scripts/connectors/data/test_databricks.py:203-205}; see {src:scripts/connectors/data/databricks.py:147-148}.
5. The log line holds a row count and not the row value {src:tests/scripts/connectors/data/test_databricks.py:207-213}; see {src:scripts/connectors/data/databricks.py:170}.

`TestWarehouseSource` (four tests):
1. `fetch_rows` groups rows by id, de-duplicates the ids, binds them as parameters, builds `ORDER BY` and a quoted table name {src:tests/scripts/connectors/data/test_databricks.py:217-227}; see {src:scripts/connectors/data/databricks.py:220-248}. With `limit=1` the bucket for id 7 keeps two rows because the code keeps one extra row to show a cut {src:scripts/connectors/data/databricks.py:246}.
2. Unsafe table, id column and column names raise `ValueError` and make no call {src:tests/scripts/connectors/data/test_databricks.py:229-238}; the checks are `validate_identifier` calls {src:scripts/connectors/data/databricks.py:205} {src:scripts/connectors/data/databricks.py:209}.
3. An empty id list returns `{}` with no call {src:tests/scripts/connectors/data/test_databricks.py:240-243}; see {src:scripts/connectors/data/databricks.py:227-228}.
4. `fetch_summary` returns one dict per id {src:tests/scripts/connectors/data/test_databricks.py:245-248}; see {src:scripts/connectors/data/databricks.py:259}.

`TestNotebooksAndSchemas` (four tests):
1. A notebook source with one readable and one missing path gives a report that names `nb1`, counts an `email` pattern, says `gone: not readable`, and does not print the address itself {src:tests/scripts/connectors/data/test_databricks.py:252-260}. The scanner says "not readable" for an unreadable notebook {src:scripts/qa/scan_notebooks.py:110-111} and the connector returns that marker when the export fails {src:scripts/connectors/data/databricks.py:195-196}.
2. `render_ddl` sorts columns by position, adds `NOT NULL`, doubles a single quote inside a comment; `write_if_changed` writes a new file, ignores a change in the date line only, and writes again when a column is added {src:tests/scripts/connectors/data/test_databricks.py:262-275}; see {src:scripts/connectors/data/databricks.py:292} {src:scripts/connectors/data/databricks.py:282-285} {src:scripts/connectors/data/databricks.py:304} {src:scripts/connectors/data/databricks.py:309-312}.
3. `export_schemas` redacts secrets in a table comment: the test builds a fake chat token from pieces, puts it in a table comment, and exports to a temporary folder with a `tally` dict {src:tests/scripts/connectors/data/test_databricks.py:278-284}. One file is written with no errors {src:tests/scripts/connectors/data/test_databricks.py:285}. The comment line reads `-- comment:   owner key [REDACTED:SLACK_TOKEN]`, the token itself is absent, and the `CREATE TABLE` line is intact {src:tests/scripts/connectors/data/test_databricks.py:286-289}. The tally is exactly `{"SLACK_TOKEN": 1}` {src:tests/scripts/connectors/data/test_databricks.py:290}. A second export of the same table reports the file as unchanged, which shows the stored text and the new text are compared in redacted form {src:tests/scripts/connectors/data/test_databricks.py:291-292}. The code redacts the rendered definition before the write and the compare, and adds to the tally {src:scripts/connectors/data/databricks.py:340} {src:scripts/connectors/data/databricks.py:321}.
4. `export_schemas` with one good table and one named `../evil` returns one written, none unchanged, one error, and only `tbl.sql` is on disk {src:tests/scripts/connectors/data/test_databricks.py:294-302}; the name check is a regular expression {src:scripts/connectors/data/databricks.py:337-339}.

## Diagram

<!-- Skipped: the only mock is one stub class that answers three addresses; the table above in Behavior covers it. -->

## Notes

- **Code and description.** The header says the tests prove the connector "only sends read-only single statements, binds parameters, caps rows and logs counts only" {src:tests/scripts/connectors/data/test_databricks.py:6-7}. Each of those has a test (see TestGuard and TestQuery above). The `Date:` field in the header is empty {src:tests/scripts/connectors/data/test_databricks.py:5}.
- **Tests that depend on the machine.** CON-02 walks every file under the repo root and the home folder {src:tests/scripts/connectors/data/test_databricks.py:121-130}; the time grows with the repo and any file it cannot open is skipped {src:tests/scripts/connectors/data/test_databricks.py:128-129}. No Python version dependence or fixed machine path found; the addresses end in `.invalid` or are loopback.
- **Tests that are loose.**
  - `test_allowed` and `test_refused` loop over many statements, but the first failing statement stops the loop {src:tests/scripts/connectors/data/test_databricks.py:157-168}; only the refused loop passes a `msg` that names the statement.
  - `test_export_schemas` does not check which of the two tables was counted as the error, only the totals {src:tests/scripts/connectors/data/test_databricks.py:300}.
- **Not tested (product code the tests drive).**
  - The printed `schemas:` line with the secret count, which `main` builds {src:scripts/connectors/data/databricks.py:391-394}; the test calls `export_schemas` directly. Redaction of a column comment or a table name is not tested either, though the whole rendered text is redacted {src:scripts/connectors/data/databricks.py:340}, and neither are two tokens of one kind in one table, which count once {src:scripts/connectors/comms/comms_common.py:74-75}.
  - The `--out` folder and `--warehouse`, `--catalog` flag values go to a file path and into the request body with no check on their value {src:scripts/connectors/data/databricks.py:390} {src:scripts/connectors/data/databricks.py:150-155}.
  - A table comment is written raw into a `-- comment:` line and the catalog, schema and name from the reply are written into the definition text unchecked {src:scripts/connectors/data/databricks.py:293-299}. Only the table name is checked before the file name is built {src:scripts/connectors/data/databricks.py:337}.
  - A notebook path is sent to the workspace after URL encoding and no other check {src:scripts/connectors/data/databricks.py:191}.
- **Writes to shared files.** The tests write only inside temporary folders. The product writes each definition file with `path.write_text`, which is not atomic and has no lock against a second writer {src:scripts/connectors/data/databricks.py:311}.
