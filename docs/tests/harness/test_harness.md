---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/harness/test_harness.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [tests/harness/throwaway_home.py, tests/harness/throwaway_home.sh, tests/harness/real_guard.py, tests/harness/connector_helpers.py]         # source files under test, relative paths from repo root
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

Thirteen tests, named HAR-01 to HAR-13, for the helpers that every other Tollgate test relies on: the throwaway home, the real-state guard, the fake secret store, the mock client and the no-network check. If these helpers were wrong, a test suite could touch the real settings or vault without anyone noticing. The module docstring now names HAR-01..HAR-13 {src:tests/harness/test_harness.py:2}, which matches the thirteen test methods, the last one (HAR-13) new in the cleanup {src:tests/harness/test_harness.py:26} {src:tests/harness/test_harness.py:131} {src:tests/harness/test_harness.py:147}.

## Dependencies

**Depends on.**
- Standard library: `getpass`, `os`, `socket`, `subprocess`, `sys`, `tempfile`, `unittest` {src:tests/harness/test_harness.py:3} {src:tests/harness/test_harness.py:4} {src:tests/harness/test_harness.py:5} {src:tests/harness/test_harness.py:6} {src:tests/harness/test_harness.py:7} {src:tests/harness/test_harness.py:8} {src:tests/harness/test_harness.py:9}.
- Repo helpers, found by adding the file's own folder to `sys.path` {src:tests/harness/test_harness.py:12}: `throwaway_home` ([[throwaway_home]] and [throwaway_home](throwaway_home.md)) {src:tests/harness/test_harness.py:14}, `real_guard` ([[real_guard]] and [real_guard](real_guard.md)) {src:tests/harness/test_harness.py:15}, and `connector_helpers` ([[connector_helpers]] and [connector_helpers](connector_helpers.md)) {src:tests/harness/test_harness.py:16}.
- The shell twin `throwaway_home.sh`, run through `bash` in HAR-12 {src:tests/harness/test_harness.py:132} {src:tests/harness/test_harness.py:138}.

**Used by.** Run by `tests/harness/run.sh` ([[run]] and [run](run.md)), which discovers `test_*.py` files {src:tests/harness/run.sh:5}. Searched `git grep` for `HAR-0`, `HAR-1` and `test_harness` outside `docs/` (2026-11-20): nothing else runs it, and it is not in the CI workflow (searched `.github/workflows/tests.yml` for `harness`, 2026-11-20). Overview of the folder: [[harness]] and [harness](../harness.md).

## Behavior

All thirteen are methods of one `unittest.TestCase` {src:tests/harness/test_harness.py:25}. A small helper `put(path, text)` writes a file {src:tests/harness/test_harness.py:20} {src:tests/harness/test_harness.py:21} {src:tests/harness/test_harness.py:22}. Every file the tests create lives in a temp folder, either from `throwaway_home` or from `tempfile.TemporaryDirectory`.

| Test | What it proves | Lines |
|---|---|---|
| HAR-01 | The home folder's last name part, and `fake_user_name()`, both differ from the real login name | {src:tests/harness/test_harness.py:27} {src:tests/harness/test_harness.py:28} {src:tests/harness/test_harness.py:29} |
| HAR-02 | A child process run by `run_in_home` sees `HOME` equal to the throwaway home, a `TOLLGATE_KNOWLEDGE` inside it, and no stray `TOLLGATE_STRAY` variable, even though the parent set both | {src:tests/harness/test_harness.py:32} {src:tests/harness/test_harness.py:33} {src:tests/harness/test_harness.py:35} {src:tests/harness/test_harness.py:44} {src:tests/harness/test_harness.py:45} {src:tests/harness/test_harness.py:46} |
| HAR-03 | The whole temp root, not only the home, is gone after the `with` block | {src:tests/harness/test_harness.py:50} {src:tests/harness/test_harness.py:51} {src:tests/harness/test_harness.py:52} |
| HAR-04 | The temp root is also removed when the body raises, and the error still reaches the caller | {src:tests/harness/test_harness.py:56} {src:tests/harness/test_harness.py:59} {src:tests/harness/test_harness.py:60} |
| HAR-05 | A guard around a block that changes nothing does not raise | {src:tests/harness/test_harness.py:69} {src:tests/harness/test_harness.py:70} |
| HAR-06 | Rewriting the settings file between `record()` and `verify()` raises `AssertionError` | {src:tests/harness/test_harness.py:77} {src:tests/harness/test_harness.py:78} {src:tests/harness/test_harness.py:79} {src:tests/harness/test_harness.py:80} |
| HAR-07 | Adding a file to the guarded vault folder raises `AssertionError` | {src:tests/harness/test_harness.py:86} {src:tests/harness/test_harness.py:87} {src:tests/harness/test_harness.py:88} {src:tests/harness/test_harness.py:89} {src:tests/harness/test_harness.py:90} |
| HAR-08 | A missing file gives `MISSING`; missing before and after is clean; a file that appears is caught | {src:tests/harness/test_harness.py:96} {src:tests/harness/test_harness.py:97} {src:tests/harness/test_harness.py:101} {src:tests/harness/test_harness.py:102} {src:tests/harness/test_harness.py:103} |
| HAR-09 | `FakeSecretStore` reports the name as asked, lists it, and keeps the value out of `requests` | {src:tests/harness/test_harness.py:110} {src:tests/harness/test_harness.py:111} {src:tests/harness/test_harness.py:112} |
| HAR-10 | `MockClient` returns the canned response, records one call, inside the no-network block | {src:tests/harness/test_harness.py:116} {src:tests/harness/test_harness.py:118} {src:tests/harness/test_harness.py:119} |
| HAR-11 | `assert_no_network` still raises at block exit when the code inside swallowed the first error | {src:tests/harness/test_harness.py:122} {src:tests/harness/test_harness.py:125} {src:tests/harness/test_harness.py:126} |
| HAR-12 | The shell helpers set `HOME` and a `vault` folder under it, use a fake user name, and remove the root | {src:tests/harness/test_harness.py:134} {src:tests/harness/test_harness.py:143} {src:tests/harness/test_harness.py:144} {src:tests/harness/test_harness.py:145} |
| HAR-13 | With every `TOLLGATE_` variable removed from the environment and `set -u` on, the shell helpers still run a child command and the child sees a `TOLLGATE_KNOWLEDGE` ending in `/vault`. This guards the empty-list case of the unset loop on bash 3.2 | {src:tests/harness/test_harness.py:148} {src:tests/harness/test_harness.py:150} {src:tests/harness/test_harness.py:152} {src:tests/harness/test_harness.py:155} {src:tests/harness/test_harness.py:156} |

Details worth knowing:
- HAR-02 prints three values from a Python child and splits the output on whitespace {src:tests/harness/test_harness.py:36} {src:tests/harness/test_harness.py:43}. It sets the two variables in the real `os.environ` and deletes them in a `finally` {src:tests/harness/test_harness.py:40} {src:tests/harness/test_harness.py:41} {src:tests/harness/test_harness.py:42}.
- HAR-08 calls `file_checksum` directly and builds the guard twice, once with both paths and once with the settings path only {src:tests/harness/test_harness.py:96} {src:tests/harness/test_harness.py:97} {src:tests/harness/test_harness.py:99}.
- HAR-09 builds the fake value by joining three pieces, so a secret scanner does not flag the file {src:tests/harness/test_harness.py:107}.
- HAR-11 uses `socket.create_connection` to `127.0.0.1` port 9 {src:tests/harness/test_harness.py:125}. In CPython that function calls `getaddrinfo` first {src:docs:cpython-socket-create_connection}, and `getaddrinfo` is one of the three functions the helper replaces {src:tests/harness/connector_helpers.py:81}. So the test fires the lookup blocker; no connection to port 9 is ever tried.
- HAR-12 runs `bash -c` with a script that sources the library, makes a home, runs a child command that prints `HOME|TOLLGATE_KNOWLEDGE`, prints the root and cleans up {src:tests/harness/test_harness.py:133} {src:tests/harness/test_harness.py:134} {src:tests/harness/test_harness.py:135} {src:tests/harness/test_harness.py:136}. The caller's environment carries a fake `TOLLGATE_KNOWLEDGE` {src:tests/harness/test_harness.py:137}.
- HAR-13 builds its environment by dropping every key that starts with `TOLLGATE_` {src:tests/harness/test_harness.py:152}, so the list of variables to unset is empty. It uses `/bin/bash` when that file exists, to get the macOS bash 3.2 where the empty list used to fail {src:tests/harness/test_harness.py:153}. The comment on its first line states the purpose {src:tests/harness/test_harness.py:148}. The fix it guards sits in the library {src:tests/harness/throwaway_home.sh:20}.

## Diagram

None: the file is thirteen independent test methods, with no shared fixtures or mock chains.

## Notes

- **A check that cannot fail.** The last two lines of HAR-11 create and close a socket "patch restored afterwards" {src:tests/harness/test_harness.py:128} {src:tests/harness/test_harness.py:129}. Creating a socket calls neither `connect` nor `getaddrinfo`, so this passes even if the helper forgot to restore them. Restoration is not tested anywhere in this file.
- **A test that does not prove what it names.** HAR-12 checks that `TOLLGATE_KNOWLEDGE` equals `home/vault` {src:tests/harness/test_harness.py:143}. The shell helper sets that variable explicitly {src:tests/harness/throwaway_home.sh:22}, so the check passes even if the `compgen` unset loop does nothing {src:tests/harness/throwaway_home.sh:19}. The Python version has a real stray-variable check in HAR-02 {src:tests/harness/test_harness.py:46}; the shell version has none. HAR-13 has the same limit: with no `TOLLGATE_` variable in the caller, it cannot show that a stray one is removed {src:tests/harness/test_harness.py:152}.
- **Docstring versus code.** The module docstring says HAR-01..HAR-13 {src:tests/harness/test_harness.py:2}, which matches the thirteen tests; HAR-13 is at {src:tests/harness/test_harness.py:147}. No disagreement is left.
- **Machine dependence.** HAR-02 splits on whitespace {src:tests/harness/test_harness.py:43}, so a temp folder path with a space breaks it. HAR-12 splits on `|` {src:tests/harness/test_harness.py:141}, breaks if the home path contains `|`, and builds a bash script by pasting the library path into `source "%s"` {src:tests/harness/test_harness.py:134} {src:tests/harness/test_harness.py:136}. A path with a double quote, a dollar sign or a backtick would be read by bash as code. The path comes from the file's own location {src:tests/harness/test_harness.py:11}, so no outside input reaches that command. HAR-12 also needs a `bash` on the `PATH` {src:tests/harness/test_harness.py:138}.
- **Python version.** `capture_output=True` needs Python 3.7 or later {src:tests/harness/test_harness.py:138}. The repo's stated minimum is 3.12 {src:tests/system/run.sh:8}, so this is fine. Nothing here depends on a newer version.
- **Not covered.** `keep=True`, `input_text`, `timeout` and `extra_env` of the throwaway helpers; the other `TOLLGATE_*` values set by `tollgate_env` and `USER` and `LOGNAME`; the guard's exception path (the guard must not verify when the body raised); unreadable files in `folder_checksum`; an empty folder created in a guarded vault (which the guard cannot see, see [[real_guard]]); `FakeSecretStore.delete`; `MockClient.post`. Searched the file for each name, 2026-11-20.
- **Shared-state writes.** HAR-02 mutates the process-wide `os.environ` {src:tests/harness/test_harness.py:32} {src:tests/harness/test_harness.py:33}. The change lasts only for the call and is undone in a `finally`, but tests in other threads would see it. All file writes go to temp folders {src:tests/harness/test_harness.py:63} {src:tests/harness/test_harness.py:49}. Nothing locks them, and nothing needs to.
- **Weak spots that can still fail.** HAR-09's last check {src:tests/harness/test_harness.py:112} passes today because `requests` only holds names {src:tests/harness/connector_helpers.py:37}. It would fail if a later change stored values, so it guards a regression, but it cannot fail on the current code.
- **Description versus code.** The docstring says "Synthetic data only" {src:tests/harness/test_harness.py:2}. That holds: the only paths and values are invented, such as `/real/looking/vault` {src:tests/harness/test_harness.py:32}. The only disagreement is the test range, given above.
