# Test harness

Tests never touch your real Claude settings or vault. The harness gives every test a throwaway home folder and checks that your real files did not change.

Files are in `tests/harness/`. Run all checks with `tests/harness/run.sh`.

## Throwaway home

`throwaway_home.py` (Python) and `throwaway_home.sh` (bash) make a temp folder whose home is named `tgtester`, never your real user name. They point `HOME` and every `TOLLGATE_*` variable at that folder, run the command, then delete it. Any `TOLLGATE_*` value from your real shell is removed first, so nothing leaks in.

- Python: `with throwaway_home() as (home, env):` or `run_in_home(["cmd", "arg"])`.
- Bash: `source throwaway_home.sh; tg_make_home; tg_run_in_home cmd args; tg_clean_home`.

## Real-state guard

`real_guard.py` records a checksum of the real `~/.claude/settings.json` and of one real vault folder, runs your test, then checks both again. It only reads. A file or folder that is missing counts as a valid state: missing before must be missing after. Use it as `with RealStateGuard(vault_path=...):`.

## Connector helpers

`connector_helpers.py` has three tools.

- `MockClient`: records every request, returns canned answers, never opens a network connection.
- `FakeSecretStore`: records the names it was asked to store. Values stay in memory and never show in the request log.
- `assert_no_network()`: a block that fails the test if any code tries a socket connection or DNS lookup.

## Checks

| Id | What it proves |
|----|----------------|
| HAR-01 | The fake user name differs from the real user |
| HAR-02 | HOME and `TOLLGATE_*` point at the throwaway home; stray ones are removed |
| HAR-03 | The home is deleted after a run |
| HAR-04 | The home is deleted even when the test fails |
| HAR-05 | An unchanged run passes the guard |
| HAR-06 | A changed settings file fails the guard |
| HAR-07 | A changed vault folder fails the guard |
| HAR-08 | Missing files are handled; a file that appears is a change |
| HAR-09 | The fake secret store records names, not values |
| HAR-10 | The mock client records calls and makes no network call |
| HAR-11 | The no-network block catches a connection attempt |
| HAR-12 | The bash library gives the same isolation |
