---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/test_redirect_settings.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/registry.py, scripts/connectors/connect.py]         # source files under test, relative paths from repo root
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

This file checks two safety rules of the connector framework. First, the web client never follows a redirect, so a key header is never sent to a second address, and the address rule allows only https or http on the local machine. Second, connector settings (plain, non-secret values) survive on, off and restart, never hold a secret-looking name, and never end up in the secret store or hold the key.

## Dependencies

**Depends on.**
- Standard library: `contextlib`, `http.server`, `io`, `json`, `pathlib`, `sys`, `threading`, `unittest`, `uuid` {src:tests/scripts/connectors/test_redirect_settings.py:10-18}.
- [[connector_helpers]] / [connector_helpers](../../harness/connector_helpers.md): `FakeSecretStore` {src:tests/scripts/connectors/test_redirect_settings.py:26}.
- [[throwaway_home]] / [throwaway_home](../../harness/throwaway_home.md) {src:tests/scripts/connectors/test_redirect_settings.py:27}.
- [[registry]] / [registry](../../../scripts/connectors/registry.md) and [[connect]] / [connect](../../../scripts/connectors/connect.md) {src:tests/scripts/connectors/test_redirect_settings.py:28}.
- Import folders built from the file location {src:tests/scripts/connectors/test_redirect_settings.py:20-24}.
- Loopback networking: two small servers bind `127.0.0.1` with an operating-system chosen port {src:tests/scripts/connectors/test_redirect_settings.py:31-34}.

**Used by.** Searched with `git grep` for the file name, excluding `docs/` (2026-11-20). No product code names it.
- Found by the pattern `test_*.py` in the connectors runner {src:tests/scripts/connectors/run.sh:6}, called by the end-to-end runner for the area `connectors` {src:tests/system/run.sh:22-23}. See [[run]] / [run](run.md).
- Tests: no other test imports it.

## Behavior

**Class `TestRedirect`** (no throwaway home, no fake store)
1. `test_redirect_not_followed_no_header_forwarded`: a "target" server records the headers of any request it gets {src:tests/scripts/connectors/test_redirect_settings.py:41-45}. A "first" server answers every GET with status 302 and a `Location` pointing at the target {src:tests/scripts/connectors/test_redirect_settings.py:53-57}. The test calls the framework's real web client against the first server with a key in two headers {src:tests/scripts/connectors/test_redirect_settings.py:64-68}. It must raise `RedirectRefused`, the target must have seen nothing, and the message must contain `302` but not the key, not `127.0.0.1`, and not `Location` {src:tests/scripts/connectors/test_redirect_settings.py:65} {src:tests/scripts/connectors/test_redirect_settings.py:74-79}. The code gives the opener a handler that never builds a follow-up request {src:scripts/connectors/registry.py:68-70} {src:scripts/connectors/registry.py:236}, turns a 3xx into `RedirectRefused` {src:scripts/connectors/registry.py:241-245}, and the message holds only the status code {src:scripts/connectors/registry.py:242-244}. Both servers are shut down and closed in a `finally` block {src:tests/scripts/connectors/test_redirect_settings.py:69-73}.
2. `test_address_rule`: `http://example.com/x`, `ftp://example.com` and `file:///etc/x` raise `ValueError`; `https://example.com`, `http://127.0.0.1:9` and `http://localhost/` pass {src:tests/scripts/connectors/test_redirect_settings.py:81-86}. The rule is https anywhere, or http only to `127.0.0.1`, `localhost` or `::1` {src:scripts/connectors/registry.py:96-100}.

**Class `TestSettings`** (throwaway home, fake store, random fake key {src:tests/scripts/connectors/test_redirect_settings.py:90-95}; the home sets the non-interactive flag {src:tests/harness/throwaway_home.py:44}). `on` runs `connect on fakeconn` with the key on stdin plus extra arguments {src:tests/scripts/connectors/test_redirect_settings.py:101-104}.
3. `test_con05_settings_survive_on_off_restart`: turn on with `--set warehouse=w1 --set catalog=c=2`; settings read back as `w1` and `c=2`, so only the first `=` splits {src:tests/scripts/connectors/test_redirect_settings.py:107-109} {src:scripts/connectors/connect.py:71-72}. Then it sets a number and a list, turns off, and confirms the connector is off but a fresh read still returns the old and new settings {src:tests/scripts/connectors/test_redirect_settings.py:110-115}. `status` prints `warehouse = w1` even for an off connector {src:tests/scripts/connectors/test_redirect_settings.py:116-119} {src:scripts/connectors/connect.py:126-128}. Turning on again keeps the earlier settings {src:tests/scripts/connectors/test_redirect_settings.py:120-121} {src:scripts/connectors/registry.py:374-377}. The connectors file must not contain the key {src:tests/scripts/connectors/test_redirect_settings.py:122-123}.
4. `test_old_file_without_settings_works`: a file from before settings existed (address and `on` only) gives empty settings, accepts new ones, and stays on {src:tests/scripts/connectors/test_redirect_settings.py:125-130} {src:scripts/connectors/registry.py:352} {src:scripts/connectors/registry.py:358-362}.
5. `test_con06_secret_looking_name_refused_nothing_written`: names `api_key`, `Token`, `client_SECRET`, `db-password` each give a non-zero code, the error says "secret store", the connectors file does not exist and the store is empty {src:tests/scripts/connectors/test_redirect_settings.py:132-140}. Calling `set_settings` with a `password` name raises and writes no file {src:tests/scripts/connectors/test_redirect_settings.py:141-143}. The rule is a case-insensitive search for `key`, `token`, `secret` or `password` inside the name {src:scripts/connectors/registry.py:330} {src:scripts/connectors/registry.py:342-345}, and `cmd_on` runs it before anything is written {src:scripts/connectors/connect.py:78}.
6. `test_bad_value_type_refused`: a setting whose value is a map raises `ValueError` {src:tests/scripts/connectors/test_redirect_settings.py:145-147} {src:scripts/connectors/registry.py:346-348}.

## Diagram

None: the redirect case sets up two servers in a straight line (client, first server, target), and the settings cases share a short fixture.

## Notes

- **Code and description.** The docstring says "No key header follows a redirect; settings stay out of secrets" {src:tests/scripts/connectors/test_redirect_settings.py:6}. The redirect case proves the first half. "Settings stay out of secrets" is only a name rule on the setting names {src:scripts/connectors/registry.py:342-345}: the value is not inspected, so a real key stored under a harmless name such as `endpoint` would be accepted. The test does not cover that.
- **Name rule is a substring match.** Names such as `keyspace` or `token_limit` would be refused as well, and names such as `pwd` or `auth` would pass {src:scripts/connectors/registry.py:342}. The test covers four refused names only {src:tests/scripts/connectors/test_redirect_settings.py:134}.
- **Proxy [uncertain].** The real client builds its opener from the default handlers, which read proxy variables from the environment {src:scripts/connectors/registry.py:236}. The plane test support turns proxies off explicitly {src:tests/scripts/connectors/plane/plane_sync_test_support.py:64}. This test does not, so a proxy setting on the machine could change how the loopback call is made. Not run.
- **Loopback and threads.** The test needs to bind and connect on `127.0.0.1` {src:tests/scripts/connectors/test_redirect_settings.py:32}. The servers run in background threads marked daemon {src:tests/scripts/connectors/test_redirect_settings.py:33}. The first server has no `Content-Length` header on its 302 reply {src:tests/scripts/connectors/test_redirect_settings.py:54-57}; the test works because the client raises on the status alone.
- **Cleanup gap.** `TestSettings` does not reset the registry's web factory, but it never sets one {src:tests/scripts/connectors/test_redirect_settings.py:93-99}. In `test_con06`, `err` is shared across the loop and checked once at the end {src:tests/scripts/connectors/test_redirect_settings.py:133-138}, so the text check applies to the combined output, not to each name.
- **Unchecked inputs.** The tests use fixed local addresses. In the code under test the connectors file path comes from `TOLLGATE_CONNECTORS` with no check {src:scripts/connectors/registry.py:264-268}; the client calls `check_address` on every request URL {src:scripts/connectors/registry.py:230}.
- **Writes to a shared file.** The code under test writes the connectors file with a plain `write_text`, no temp file, no lock {src:scripts/connectors/registry.py:318}. One case writes the file by hand {src:tests/scripts/connectors/test_redirect_settings.py:127}; all writes land in the throwaway home.
- **Python version.** No version-specific calls and no machine path found.
