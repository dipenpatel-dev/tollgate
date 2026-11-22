---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/test_host_allowlist.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
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

This file checks the connector host allowlist: a key goes only to a host on the connector's built-in list, or to a host the owner recorded with `--allow-host`. It checks the rule when a connector is turned on and again on every request, and it checks that address tricks (look-alike suffixes, odd characters, ports, IP literals) are refused. It has 15 tests in 4 classes {src:tests/scripts/connectors/test_host_allowlist.py:124} {src:tests/scripts/connectors/test_host_allowlist.py:131} {src:tests/scripts/connectors/test_host_allowlist.py:151} {src:tests/scripts/connectors/test_host_allowlist.py:205}.

## Dependencies

- Product code under test: [[registry]] ([registry](../../../scripts/connectors/registry.md)) and [[connect]] ([connect](../../../scripts/connectors/connect.md)) {src:tests/scripts/connectors/test_host_allowlist.py:30}.
- Test helpers: [[connector_helpers]] ([connector_helpers](../../harness/connector_helpers.md)) for `FakeSecretStore`, `MockClient`, `assert_no_network` and the saved real host table {src:tests/scripts/connectors/test_host_allowlist.py:27} {src:tests/scripts/connectors/test_host_allowlist.py:28}; `throwaway_home` (a temporary home with its own state file) {src:tests/scripts/connectors/test_host_allowlist.py:29}.
- Standard library: `contextlib`, `io`, `json`, `os`, `pathlib`, `sys`, `unittest`, `unittest.mock` {src:tests/scripts/connectors/test_host_allowlist.py:12} {src:tests/scripts/connectors/test_host_allowlist.py:19}.
- Run by: [[run]] ([run](run.md)), the folder runner, which runs every `test_*.py` file in the folder with `unittest discover`, so this file is picked up by its name {src:tests/scripts/connectors/run.sh:6}. Searched `tests/` for the file name on 2026-11-21: no runner names it directly.

## Behavior

**Fixture.** `Base.setUp` registers a `jira` factory {src:tests/scripts/connectors/test_host_allowlist.py:83} {src:tests/scripts/connectors/test_host_allowlist.py:84}, then replaces the registry host table with the real one saved by the helper, so the helper's `.invalid` additions are gone for these tests {src:tests/scripts/connectors/test_host_allowlist.py:85-87}. It uses a throwaway home with `TOLLGATE_NONINTERACTIVE=1` {src:tests/scripts/connectors/test_host_allowlist.py:88-90}, a fake secret store {src:tests/scripts/connectors/test_host_allowlist.py:91-92} and no test http factory, so the real `UrlHttp` is in use {src:tests/scripts/connectors/test_host_allowlist.py:93}. `tearDown` restores the store, factory, host table and factory list {src:tests/scripts/connectors/test_host_allowlist.py:96-103}. The helper `on` puts a fake key in `TG_HOST_KEY`, patches `registry.interactive` to the value of the `terminal` argument and calls `connect.main(["on", ...])` with `--key-from-env`, returning the exit code and the error text {src:tests/scripts/connectors/test_host_allowlist.py:105-116}.

**Allowed (1 test).** Eleven built-in addresses across Jira, Slack, Notion, Databricks and Calendar, including a mixed-case host, all turn on with exit 0 {src:tests/scripts/connectors/test_host_allowlist.py:32-44} {src:tests/scripts/connectors/test_host_allowlist.py:125-128}.

**Refused (3 tests).**
- 26 bad addresses, each tried through `connect.main`, must exit 1, must not print the fake key, must leave the connector off and must leave nothing in the secret store {src:tests/scripts/connectors/test_host_allowlist.py:46-73} {src:tests/scripts/connectors/test_host_allowlist.py:132-138}. The list covers a login in the address, plain http, an unlisted host, the suffix placed at the end, after `#`, after `?` and after `/`, a backslash, a trailing dot, a port, an out-of-range port, an IPv4 literal, an IPv6 literal, a decimal IP, the bare suffix, a look-alike label, a look-alike dot character, a space, an empty host, another connector's host, look-alike Notion, Slack and Databricks hosts, a Notion subdomain, and a connector name with no list {src:tests/scripts/connectors/test_host_allowlist.py:47-72}.
- The same 26 addresses must make `registry.check_host` raise `ValueError` {src:tests/scripts/connectors/test_host_allowlist.py:140-143}.
- The refusal text for an unlisted Jira host contains `--allow-host jira.corp.example` {src:tests/scripts/connectors/test_host_allowlist.py:145-148}.

**Recorded hosts (7 tests).**
- `--allow-host` without a terminal exits 1, mentions "terminal" and leaves the connector off {src:tests/scripts/connectors/test_host_allowlist.py:152-157}.
- With a terminal, `--allow-host Jira.Corp.Example` turns the connector on, stores `["jira.corp.example"]` (lowercased) under `allowed_hosts` in the state, and `check_host` then passes {src:tests/scripts/connectors/test_host_allowlist.py:159-165}.
- A recorded host does not cover another host, a subdomain of it, the same host on port 8443, or another connector {src:tests/scripts/connectors/test_host_allowlist.py:167-175}.
- A Plane address that is an IP with a port works only when recorded with exactly that port, and the same IP without the port is refused {src:tests/scripts/connectors/test_host_allowlist.py:177-183}.
- Eight malformed `--allow-host` values exit 1: a scheme, a path, a wildcard, a leading dot, a trailing dot, port 0, a non-numeric port and the empty string {src:tests/scripts/connectors/test_host_allowlist.py:185-190}.
- `turn_off` removes `allowed_hosts` from the state {src:tests/scripts/connectors/test_host_allowlist.py:192-196}.
- A state file whose `allowed_hosts` is a text value instead of a list is ignored, so the host is refused {src:tests/scripts/connectors/test_host_allowlist.py:198-202}.

**Every request (4 tests).**
- A state file that already points Jira at an unlisted host: `require` still returns a client, but a `get` through its `http` raises `ValueError` and makes no network or DNS call {src:tests/scripts/connectors/test_host_allowlist.py:206-214}.
- A client made for a listed host, then the state file edited to an unlisted host: a new client from `require` is refused on its first request, while the first client keeps its old address {src:tests/scripts/connectors/test_host_allowlist.py:216-225}.
- `UrlHttp("jira", env)` checks each URL it is given, not only the first one {src:tests/scripts/connectors/test_host_allowlist.py:227-231}.
- With a mock http factory set, turning on a listed host and calling `require` still works {src:tests/scripts/connectors/test_host_allowlist.py:233-236}.

## Diagram

Skipped: the fixture is one throwaway home, one fake store and a patched terminal flag, with no mock chain that needs a picture.

## Notes

- **Not covered.** Searched the file on 2026-11-21: no test for the `git-commits` exemption, for `http` to a loopback host with a recorded port, for a repeated `--allow-host`, for an address with an explicit `:443`, or for a refused Calendar, Slack or Databricks host beyond the look-alike cases listed. The "every request" tests use Jira only.
- **Per-request tests never reach the network.** They assert that no connect or DNS call happens inside the block {src:tests/scripts/connectors/test_host_allowlist.py:211} {src:tests/scripts/connectors/test_host_allowlist.py:222} {src:tests/scripts/connectors/test_host_allowlist.py:229}. A refused request is therefore proved by an exception plus no socket call, not by a server log.
- **Terminal flag is patched.** The "needs a terminal" test and the allow tests rely on a patch of `registry.interactive`, not on a real terminal {src:tests/scripts/connectors/test_host_allowlist.py:110-111}. The real terminal check, `isatty` on both streams, is not exercised here.
- **Fake key.** The key text is built from two string pieces so no secret-looking literal sits in the file {src:tests/scripts/connectors/test_host_allowlist.py:94}.
- **Unchecked inputs.** All addresses and keys are fixed test strings; nothing reaches a shell, a real network address or outbound text. The test writes the state file directly with `write_text` inside the throwaway home {src:tests/scripts/connectors/test_host_allowlist.py:118-121}. That write is not atomic and not locked, which is fine for a single-process test; it also changes shared module state (the host table, the factory list, the store), restored in `tearDown` {src:tests/scripts/connectors/test_host_allowlist.py:96-103}.
- **Import order.** The test imports the helper before the registry, and the helper edits the host table on import; `setUp` undoes that for these tests {src:tests/scripts/connectors/test_host_allowlist.py:27} {src:tests/scripts/connectors/test_host_allowlist.py:85-87}.
