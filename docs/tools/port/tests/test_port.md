---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tools/port/tests/test_port.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["tools/port/port.py", "tools/port/run.sh"]         # source files under test, relative paths from repo root
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

Unit and end-to-end tests for the port tool. They check the text rewrites (paths, prefixes, initials, deny list, dates, attribution lines, em dashes), the leftover scanner, and the folder-level behavior of `run` (permission bits, dry run, repeat runs, refusals, binary files, one-file source, the command-line launcher).

## Dependencies

**Depends on.**
- `tools/port/port.py`, imported by adding its folder to `sys.path` {src:tools/port/tests/test_port.py:10} {src:tools/port/tests/test_port.py:11} {src:tools/port/tests/test_port.py:12}. Page: [[port]] / [port](../port.md).
- `tools/port/run.sh`, started once as a real command {src:tools/port/tests/test_port.py:221}. Page: [[run]] / [run](../run.md).
- Standard library: json, os, stat, subprocess, sys, tempfile, unittest.

**Used by.** Nothing in product code. It is run by hand or by test discovery; searched `git grep` for `test_port` and `tools/port` across the repo, excluding `docs/` (2026-11-20). The leak scanner lists this file as an allowed fixture for two rules, because it holds fake emails and tokens on purpose {src:tests/leak/allowed_fixtures.txt:15}.

## Behavior

**Setup.** Each test gets a fresh temporary folder with `src` and a `repo/out` destination, and a rewriter built from a fixed fake config {src:tools/port/tests/test_port.py:15} {src:tools/port/tests/test_port.py:26} {src:tools/port/tests/test_port.py:27} {src:tools/port/tests/test_port.py:28} {src:tools/port/tests/test_port.py:29} {src:tools/port/tests/test_port.py:32}. The helper `go` calls `run` with that folder as the root and output sent to the null device {src:tools/port/tests/test_port.py:45} {src:tools/port/tests/test_port.py:47}.

**Rewrite tests (`RewriteTypes`).**
- Two path keys of different length are replaced longest first {src:tools/port/tests/test_port.py:55} {src:tools/port/tests/test_port.py:57}. A path that only starts with the key (`/home/tester2`) is untouched {src:tools/port/tests/test_port.py:59} {src:tools/port/tests/test_port.py:60}.
- Ticket prefixes, a skill prefix and initials are replaced {src:tools/port/tests/test_port.py:63} {src:tools/port/tests/test_port.py:65}. A deny-list term is replaced, case-insensitively, including a multi-word one {src:tools/port/tests/test_port.py:69} {src:tools/port/tests/test_port.py:71}.
- A `Date:` header value is blanked, change log dates are stripped, and a date in the body is kept {src:tools/port/tests/test_port.py:73} {src:tools/port/tests/test_port.py:76} {src:tools/port/tests/test_port.py:79}. The same for shell comments and for the bold Markdown form {src:tools/port/tests/test_port.py:81} {src:tools/port/tests/test_port.py:83} {src:tools/port/tests/test_port.py:86} {src:tools/port/tests/test_port.py:88} {src:tools/port/tests/test_port.py:91}.
- An attribution line is removed, and its line number is recorded as 2 {src:tools/port/tests/test_port.py:93} {src:tools/port/tests/test_port.py:98}. Em dashes become a comma or a period depending on the next word, and are recorded on source lines 1, 3 and 4 {src:tools/port/tests/test_port.py:99} {src:tools/port/tests/test_port.py:100} {src:tools/port/tests/test_port.py:101}.
- JSON stays parseable after a rewrite, YAML and Python text are rewritten as plain text {src:tools/port/tests/test_port.py:103} {src:tools/port/tests/test_port.py:105} {src:tools/port/tests/test_port.py:107} {src:tools/port/tests/test_port.py:109} {src:tools/port/tests/test_port.py:111}.
- A second rewrite of already rewritten text changes nothing {src:tools/port/tests/test_port.py:113} {src:tools/port/tests/test_port.py:117}.

**Leftover tests (`Leftovers`).** One test checks one example of each kind: IP, email (and that the allowed address is not flagged), host name (and that `github.com` is not), token, secret assignment, political words, an unknown person name (and that a product name is not), a personal path, an `@handle` (and that a Python decorator in a `.py` file is not) {src:tools/port/tests/test_port.py:124} {src:tools/port/tests/test_port.py:126} {src:tools/port/tests/test_port.py:138}. Another runs the tool on a file with an IP and proves the report names the file, line and reason but not the address {src:tools/port/tests/test_port.py:140} {src:tools/port/tests/test_port.py:144} {src:tools/port/tests/test_port.py:145}.

**Folder tests (`Behaviour`).**
- Permission bits 0o755 and 0o640 survive {src:tools/port/tests/test_port.py:149} {src:tools/port/tests/test_port.py:153} {src:tools/port/tests/test_port.py:154}.
- A dry run leaves no destination folder {src:tools/port/tests/test_port.py:156} {src:tools/port/tests/test_port.py:159}.
- Running twice gives identical bytes and modes, and the expected rewritten text {src:tools/port/tests/test_port.py:161} {src:tools/port/tests/test_port.py:167} {src:tools/port/tests/test_port.py:168}.
- The source file is unchanged after a run {src:tools/port/tests/test_port.py:179} {src:tools/port/tests/test_port.py:183}.
- A destination outside the root, and a destination inside the source, each raise `SystemExit` {src:tools/port/tests/test_port.py:185} {src:tools/port/tests/test_port.py:189} {src:tools/port/tests/test_port.py:193} {src:tools/port/tests/test_port.py:196}. The first also proves the outside folder was not created {src:tools/port/tests/test_port.py:191}.
- A binary file is copied byte for byte {src:tools/port/tests/test_port.py:199} {src:tools/port/tests/test_port.py:205}. A single-file source works {src:tools/port/tests/test_port.py:207} {src:tools/port/tests/test_port.py:211}.
- The launcher runs with a private map file and deny-list file and gives the expected text and exit code 0 {src:tools/port/tests/test_port.py:213} {src:tools/port/tests/test_port.py:221} {src:tools/port/tests/test_port.py:223} {src:tools/port/tests/test_port.py:224}.

## Diagram

Skipped: the setup is one temporary folder per test with no mock chain.

## Notes

**Tests that are weak or machine-dependent.**
- `test_refuses_overlap` and `test_refuses_destination_outside_root` only check that `SystemExit` is raised, not which rule fired {src:tools/port/tests/test_port.py:189} {src:tools/port/tests/test_port.py:196}. Any other cause of `SystemExit` would also pass them; the overlap test sets the root to the parent of both folders so only the overlap rule should fire {src:tools/port/tests/test_port.py:197}.
- `test_cli_with_private_files` starts `run.sh`, which runs whichever `python3` is first on `PATH`, not the interpreter running the tests {src:tools/port/run.sh:5} {src:tools/port/tests/test_port.py:221}. A different Python version can behave differently from the rest of the file. It also needs the launcher's execute bit.
- `setUp` creates a temporary folder and nothing removes it; there is no `tearDown` {src:tools/port/tests/test_port.py:26}.
- Permission-bit checks assume a filesystem that keeps Unix modes {src:tools/port/tests/test_port.py:153} {src:tools/port/tests/test_port.py:154}.
- The fake paths such as `/home/tester` are just strings in the rewrite tests, not paths on the machine {src:tools/port/tests/test_port.py:16}.

**Not covered.** The deny-list file parser is exercised only through the one launcher test (a comment line and one arrow rule) {src:tools/port/tests/test_port.py:220}. Not tested: `merge_config` directly, the table-row date strip, symbolic links, the walk skip names, carriage-return line ends, the `Bearer` token form, the host-shaped name check, and a dry run that prints leftovers.

**Inputs with no check.** The tests build all inputs themselves in a temporary folder; none comes from outside.

**Writes to shared files.** None outside the temporary folders {src:tools/port/tests/test_port.py:26}.
