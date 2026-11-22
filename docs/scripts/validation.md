# Validation: `scripts/validation/`

The folder holds one script, `validate_state_files.py`.

`validate_state_files.py PATH` checks ticket state files: a front matter block that is closed, well-formed lines, a ticket key (`ticket` or `ticket_id`) and a status {src:scripts/validation/validate_state_files.py:24} {src:scripts/validation/validate_state_files.py:28} {src:scripts/validation/validate_state_files.py:32} {src:scripts/validation/validate_state_files.py:35} {src:scripts/validation/validate_state_files.py:45} {src:scripts/validation/validate_state_files.py:47}. PATH is a file or a folder; for a folder it checks every `.md` file with `state` in its name, walking subfolders, so it works on `02-tickets/PREFIX/KEY/` layouts {src:scripts/validation/validate_state_files.py:52} {src:scripts/validation/validate_state_files.py:53} {src:scripts/validation/validate_state_files.py:55}.

Exit 0 when all are valid, 1 when some are not (file name and reason codes only, never file text), 2 for a bad path {src:scripts/validation/validate_state_files.py:15} {src:scripts/validation/validate_state_files.py:75} {src:scripts/validation/validate_state_files.py:76} {src:scripts/validation/validate_state_files.py:80} {src:scripts/validation/validate_state_files.py:81}. The reason codes are `no_front_matter`, `front_matter_not_closed`, `malformed_line`, `no_ticket_key`, `no_status` and `unreadable` {src:scripts/validation/validate_state_files.py:32} {src:scripts/validation/validate_state_files.py:35} {src:scripts/validation/validate_state_files.py:41} {src:scripts/validation/validate_state_files.py:46} {src:scripts/validation/validate_state_files.py:48} {src:scripts/validation/validate_state_files.py:65}.

It is a front matter check only. It does not check the `Status:` line the gate reads; `scripts/state/ticket_state_check.py` does that (see `docs/scripts/state.md`).

## Fixtures

`tests/fixtures/tickets/` holds synthetic ticket state files, sprint notes, board mappings and small vault layouts (invented values, generic ticket keys). One file, `BAD-001-state.md` under `vault_mixed/02-tickets/BAD-001/`, is deliberately malformed. `build_vault_100.py` generates 100 sample ticket folders on demand; the generated folders are not stored {src:tests/fixtures/tickets/build_vault_100.py:4} {src:tests/fixtures/tickets/build_vault_100.py:24} {src:tests/fixtures/tickets/build_vault_100.py:30}.

## Tests

`tests/scripts/validation/run.sh`
