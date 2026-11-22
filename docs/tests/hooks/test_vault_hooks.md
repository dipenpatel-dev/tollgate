---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/hooks/test_vault_hooks.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers:            # source files under test, relative paths from repo root
  - hooks/pre_tool_write_vault_frontmatter.py
  - hooks/pre_tool_write_scan_claims.py
  - hooks/claim_patterns.py
  - hooks/vault_doc_standard_check.sh
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

Tests for the three hooks that guard writes to markdown notes: one that refuses a bad frontmatter block before a write, one that refuses a note carrying an uncited status word, and one that reminds the writer after the write when the frontmatter is missing or incomplete. Each test runs the hook as a subprocess and reads its output.

## Dependencies

**Depends on.**
- `hooks/pre_tool_write_vault_frontmatter.py`: [[pre_tool_write_vault_frontmatter]] ([page](../../hooks/pre_tool_write_vault_frontmatter.md)).
- `hooks/pre_tool_write_scan_claims.py` and its helper `hooks/claim_patterns.py`: [[pre_tool_write_scan_claims]] ([page](../../hooks/pre_tool_write_scan_claims.md)), [[claim_patterns]] ([page](../../hooks/claim_patterns.md)).
- `hooks/vault_doc_standard_check.sh`: [[vault_doc_standard_check]] ([page](../../hooks/vault_doc_standard_check.md)).
- Standard library: `json`, `os`, `subprocess`, `tempfile`, `unittest`, `pathlib`. The shell hook also needs `python3`, `awk`, `head` and `grep` {src:hooks/vault_doc_standard_check.sh:17} {src:hooks/vault_doc_standard_check.sh:50}.
- Environment variable `TOLLGATE_KNOWLEDGE`, set by the test for the vault hooks {src:tests/hooks/test_vault_hooks.py:42}.

**Used by.** No product code. Searched with `git grep` outside `docs/` on 2026-11-20.
- Tests: found by `unittest discover` in the hook test runner {src:tests/hooks/run.sh:198} and in CI {src:.github/workflows/tests.yml:35}.

## Behavior

**Harness.** `run()` executes a hook script from `hooks/` with a payload on stdin and an environment made of the current one plus overrides {src:tests/hooks/test_vault_hooks.py:28-30}. `write()` builds a Write tool payload {src:tests/hooks/test_vault_hooks.py:33-34}. The base class makes a temporary folder with a `vault` subfolder, resolves it with `realpath` (so a macOS temp symlink cannot confuse the prefix check) and sets `TOLLGATE_KNOWLEDGE` to it {src:tests/hooks/test_vault_hooks.py:38-42} {src:hooks/pre_tool_write_vault_frontmatter.py:43} {src:hooks/pre_tool_write_vault_frontmatter.py:46-47}. The folder is removed after each case {src:tests/hooks/test_vault_hooks.py:44-45}.

**`VaultFrontmatter` (4 cases).**
- A note with `status: active` inside the vault is denied. The test expects exit 0 with a JSON decision `deny` and the text ALL_CAPS in the reason {src:tests/hooks/test_vault_hooks.py:50-54}. The hook prints the deny JSON and exits 0 {src:hooks/pre_tool_write_vault_frontmatter.py:27-35}, and the status rule requires capitals {src:hooks/pre_tool_write_vault_frontmatter.py:83-87}.
- A note with `status: ACTIVE` and `type: ticket_spec` produces no output and exit 0 {src:tests/hooks/test_vault_hooks.py:57-58}.
- A bad note written outside the vault, and a bad note inside the vault with `TOLLGATE_KNOWLEDGE` set to an empty string, both print nothing {src:tests/hooks/test_vault_hooks.py:61-64}. An unset variable exits 0 at once {src:hooks/pre_tool_write_vault_frontmatter.py:109-110}; the path filter checks the vault prefix {src:hooks/pre_tool_write_vault_frontmatter.py:46-47}.
- A field set to an empty quoted string (`owner: ""`) is denied {src:tests/hooks/test_vault_hooks.py:67-69} {src:hooks/pre_tool_write_vault_frontmatter.py:96-101}.

**`ClaimHook` (3 cases).**
- A line holding a capitalised status word with no citation is denied; the reason names the line number {src:tests/hooks/test_vault_hooks.py:74-78} {src:hooks/pre_tool_write_scan_claims.py:75-80}. The scan pattern is four capitalised words {src:hooks/claim_patterns.py:20-22}.
- The same word followed by `(source: ci run)` is allowed, and a `.py` file holding the word as an identifier is allowed {src:tests/hooks/test_vault_hooks.py:81-82}. A citation is `(source:` text `)` or `(unverified` {src:hooks/claim_patterns.py:26-30}; only `.md` paths are scanned {src:hooks/pre_tool_write_scan_claims.py:58-63}.
- A word inside a fenced code block is not scanned {src:tests/hooks/test_vault_hooks.py:85} {src:hooks/claim_patterns.py:63-68}.

**`VaultDocStandard` (3 cases)** run the after-write shell hook with a payload that only names the file; the file is created by the test with `Path.write_text` {src:tests/hooks/test_vault_hooks.py:89-90}.
- A file with no frontmatter produces a `PostToolUse` message containing "no YAML frontmatter" {src:tests/hooks/test_vault_hooks.py:93-97} {src:hooks/vault_doc_standard_check.sh:45-47}.
- A file holding all six fields (`doc_type`, `status`, `date`, `last_updated`, `tags`, `links`) is silent {src:tests/hooks/test_vault_hooks.py:101-102} {src:hooks/vault_doc_standard_check.sh:52-54}.
- A file holding only `status` gets a message that mentions `doc_type`; a file outside the vault is silent {src:tests/hooks/test_vault_hooks.py:105-110} {src:hooks/vault_doc_standard_check.sh:56-58} {src:hooks/vault_doc_standard_check.sh:31-34}.

## Diagram

Skipped: each case writes at most one file and runs one hook; no mock chain.

## Notes

- **Code versus description (hook side).** The docstring of `pre_tool_write_vault_frontmatter.py` now says "Fails closed" and that an unset `TOLLGATE_KNOWLEDGE` still allows {src:hooks/pre_tool_write_vault_frontmatter.py:8}; that matches the code, which exits 2 on an internal error {src:hooks/pre_tool_write_vault_frontmatter.py:125-127}. The docstring of `pre_tool_write_scan_claims.py` says "Fails open" {src:hooks/pre_tool_write_scan_claims.py:7}, but the code exits 2 {src:hooks/pre_tool_write_scan_claims.py:91-94}. The header of `vault_doc_standard_check.sh` lists `doc_type` as an underscore value and `status` as capitals {src:hooks/vault_doc_standard_check.sh:6}, but the code only checks that each of the six keys is present {src:hooks/vault_doc_standard_check.sh:52-54}. This test file only covers presence, so the value rules for that hook are untested {src:tests/hooks/test_vault_hooks.py:101}.
- **A test that cannot fail on the thing it names.** `test_incomplete_names_missing_field_and_outside_is_silent` asserts that "doc_type" appears in the reminder {src:tests/hooks/test_vault_hooks.py:107}. The fixed tail of the reminder always contains `doc_type` {src:hooks/vault_doc_standard_check.sh:57}, so the assertion passes even if the hook failed to detect that `doc_type` was missing. It does not check the other missing fields.
- **Tests that pass on empty stdout alone.** The outside-vault, unset-variable, cited-claim, non-markdown and fenced-code cases assert only that stdout is empty {src:tests/hooks/test_vault_hooks.py:62} {src:tests/hooks/test_vault_hooks.py:64} {src:tests/hooks/test_vault_hooks.py:81-82} {src:tests/hooks/test_vault_hooks.py:85}. A hook that crashed and printed to stderr would also pass. Only the good-frontmatter case checks the exit code {src:tests/hooks/test_vault_hooks.py:58}.
- **Machine and version dependence.** No fixed machine paths: the repo root comes from `__file__` {src:tests/hooks/test_vault_hooks.py:22} and the vault from `tempfile`. The payload paths `/x/n.md` are never opened by the claim hook {src:tests/hooks/test_vault_hooks.py:74}. The shell hook uses `cd` and `pwd -P` to resolve real paths {src:hooks/vault_doc_standard_check.sh:29-30}.
- **Inputs reaching paths, commands, network or outbound text without a check.** In the hooks, the `file_path` from the payload is passed to `os.path.realpath` and compared by string prefix with the vault root {src:hooks/pre_tool_write_vault_frontmatter.py:47}; the shell hook passes the path to `head`, `awk` and `dirname` inside double quotes and never to a shell command string {src:hooks/vault_doc_standard_check.sh:44} {src:hooks/vault_doc_standard_check.sh:50}. The vault root is stored with a trailing slash {src:hooks/pre_tool_write_vault_frontmatter.py:43}, so a sibling folder with a similar name does not count as inside the vault. The reminder text that goes back to the model includes the file base name unescaped {src:hooks/vault_doc_standard_check.sh:46}. In the test file, no test input reaches a command or network address.
- **Writes to shared files.** The tests write only inside a temporary folder {src:tests/hooks/test_vault_hooks.py:39-41} {src:tests/hooks/test_vault_hooks.py:94} {src:tests/hooks/test_vault_hooks.py:109}; the hooks under test write nothing.
