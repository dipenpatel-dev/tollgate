---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/test_scrub_secrets.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["hooks/scrub_secrets.py", "hooks/scrub_secrets.sh", "hooks/secret_var_registry.txt"]         # source files under test, relative paths from repo root
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

This file tests the secret scrubber hook in both of its modes: the check before a tool runs (deny a command or a file write that holds a credential value) and the check after a tool runs (redact credentials from tool output). It also covers the shell wrapper and the variable-name registry. It is a unit test module: each case starts the real hook script as a separate process and feeds it a fake hook payload on standard input.

## Dependencies

**Depends on.**
- [[scrub_secrets]] ([scrub_secrets](../../hooks/scrub_secrets.md)): the Python hook, started as a child process {src:tests/hooks/test_scrub_secrets.py:33}.
- hooks/scrub_secrets.sh (no doc yet): the shell wrapper, started by the last test {src:tests/hooks/test_scrub_secrets.py:115}.
- hooks/secret_var_registry.txt (no doc yet): the real registry file, read by every case that does not override the registry path {src:hooks/scrub_secrets.py:124}.
- Standard library only: `json`, `os`, `subprocess`, `tempfile`, `unittest` {src:tests/hooks/test_scrub_secrets.py:14-18}.

**Used by.**
- Product code: none. No product file imports or runs this test (searched `git grep` for the file name, 2026-11-20).
- Tests and CI: the CI step that runs `python3 -m unittest discover -s tests/hooks -p 'test_*.py'` picks it up {src:.github/workflows/tests.yml:35}. The system runner `tests/system/run.sh` also discovers the hooks folder {src:tests/system/run.sh:20}.

## Behavior

Helpers build the data. The fake GitHub token is split into pieces at run time so the file holds no whole key {src:tests/hooks/test_scrub_secrets.py:24-25}. The fake Anthropic-style key is built the same way {src:tests/hooks/test_scrub_secrets.py:28-29}. The `run` helper starts a hook script from the repo `hooks` folder with the payload as JSON on standard input, and merges any extra environment on top of the whole current environment {src:tests/hooks/test_scrub_secrets.py:32-34}. The `pre` helper builds a before-tool payload {src:tests/hooks/test_scrub_secrets.py:37-38}.

The `decision` helper insists on exit code 0 and returns `None` when the hook printed nothing, otherwise the parsed `hookSpecificOutput` block {src:tests/hooks/test_scrub_secrets.py:42-46}.

Before-tool cases (class `ScrubSecretsPre`):

| Case | What it proves |
|---|---|
| deny schema | A Bash command holding the fake GitHub token gives a deny block with event name `PreToolUse`, decision `deny` and a non-empty reason {src:tests/hooks/test_scrub_secrets.py:48-52}. The hook builds that block in `deny()` and exits 0 {src:hooks/scrub_secrets.py:174-182}. |
| fake key in a file write | Write, Edit and MultiEdit payloads with the fake key are all denied, and the reason text never repeats the key {src:tests/hooks/test_scrub_secrets.py:54-63}. The hook reads `content`, `new_string` and the `edits` list for those tools {src:hooks/scrub_secrets.py:186-191}. |
| fake key in a command | A curl command with the token in a header is denied {src:tests/hooks/test_scrub_secrets.py:65-67}. |
| literal export | An export of a token-named variable with a literal value is denied; the same export with `$(...)` as the value passes {src:tests/hooks/test_scrub_secrets.py:69-72}. The hook's export pattern refuses a value that starts with `$`, a backtick or `(` {src:hooks/scrub_secrets.py:107-109}. |
| clean input | A harmless Write and the command `ls -la` give no output at all {src:tests/hooks/test_scrub_secrets.py:74-76}. |
| bad input fails closed | The inputs `not json`, an empty string and `[]` each give exit code 2, empty standard output and the words "fails closed" on standard error {src:tests/hooks/test_scrub_secrets.py:78-82}. The hook exits 2 on unparsable input and on JSON that is not an object {src:hooks/scrub_secrets.py:257-264}. |
| registry name | A temporary registry file lists one name; a command assigning that name a long value is denied, and another name with the same value passes {src:tests/hooks/test_scrub_secrets.py:84-92}. The hook reads the path from `SCRUB_REGISTRY_PATH` {src:hooks/scrub_secrets.py:120-124}, drops text after `#` on each line {src:hooks/scrub_secrets.py:133}, and builds a name-and-value pattern needing 8 or more characters {src:hooks/scrub_secrets.py:143}. |

After-tool cases (class `ScrubSecretsPost`):

| Case | What it proves |
|---|---|
| schema and redaction | A Bash response holding the fake token gives exit 0 and a `PostToolUse` block whose `additionalContext` carries the label `[REDACTED:GITHUB_TOKEN]` and not the token {src:tests/hooks/test_scrub_secrets.py:99-106}. The hook swaps each match for that label {src:hooks/scrub_secrets.py:238-241} and prints the sanitized copy as `additionalContext` {src:hooks/scrub_secrets.py:245-253}. |
| clean output | Output with nothing sensitive gives empty standard output {src:tests/hooks/test_scrub_secrets.py:108-109}. The hook returns without printing when nothing was found {src:hooks/scrub_secrets.py:242-243}. |
| skipped tool | A Write response holding the token is ignored {src:tests/hooks/test_scrub_secrets.py:111-112}. Write is in the hook's skip set {src:hooks/scrub_secrets.py:38}, checked at the top of the after-tool path {src:hooks/scrub_secrets.py:227-228}. |
| shell wrapper | The `.sh` wrapper gives the same deny decision for the fake token in a Bash command {src:tests/hooks/test_scrub_secrets.py:114-116}. The wrapper hands over to the Python script with `exec` {src:hooks/scrub_secrets.sh:6}. |

## Diagram

None: the test setup is one helper that starts a child process and a temporary registry file; there are no fixture chains or mock layers.

## Notes

**Code and description.** No disagreement between this file's header and its code. The header says the file tests both modes, the shell wrapper and the registry {src:tests/hooks/test_scrub_secrets.py:5}, and each of those has at least one case. The hook source keeps MultiEdit support with a comment saying it is not a current tool name {src:hooks/scrub_secrets.py:190}, so the MultiEdit branch of the deny test covers a payload shape the comment says Claude Code no longer sends.

**Coverage gaps (not tested here).** The NotebookEdit write path {src:hooks/scrub_secrets.py:192-193}, the Plane key and the JSON-quoted credential shapes {src:hooks/scrub_secrets.py:60-73} (searched: `tests/hooks/test_security_fixes.py` covers the Plane and JSON-quoted shapes, lines 319-323), the looser output-only patterns {src:hooks/scrub_secrets.py:92-104}, the `scrub_text` function other scripts import {src:hooks/scrub_secrets.py:272-287}, and the wrapper's registry pinning {src:hooks/scrub_secrets.sh:5}. The v1 additions are also not tested in this file: the wider key shapes {src:hooks/scrub_secrets.py:52} {src:hooks/scrub_secrets.py:59} {src:hooks/scrub_secrets.py:61-72}, the quoted `password`, `secret`, `token` or `api_key` assignment check that runs only on text being written {src:hooks/scrub_secrets.py:81-89} {src:hooks/scrub_secrets.py:217}, and the folding of zero-width and compatibility characters before matching {src:hooks/scrub_secrets.py:112-117} {src:hooks/scrub_secrets.py:167}. They are covered in [test_secret_shapes](test_secret_shapes.md) (searched this file for the labels `STRIPE_KEY`, `JWT`, `ASSIGNED_SECRET`, 2026-11-21: no hits).

**Tests that depend on the machine.**
- Every case except the registry one inherits the caller's whole environment {src:tests/hooks/test_scrub_secrets.py:34}. If the developer's shell already sets `SCRUB_REGISTRY_PATH`, the hook reads that file instead of the repo registry {src:hooks/scrub_secrets.py:121-123}.
- The repo registry holds placeholder names such as `EXAMPLE_DB_PASS` {src:hooks/secret_var_registry.txt:26}. The same name is used by the registry case with its own temporary file {src:tests/hooks/test_scrub_secrets.py:88}, so that case does not depend on the repo file.
- The hook scripts must keep their execute bit, because the tests run them directly {src:tests/hooks/test_scrub_secrets.py:33}. Both are executable today (checked with `ls -l`, 2026-11-20).
- Python version: the annotations use `dict | None` {src:tests/hooks/test_scrub_secrets.py:32}, which was safe on 3.9 only because of the `from __future__ import annotations` line {src:tests/hooks/test_scrub_secrets.py:12}. The line was kept from when the minimum was 3.9; it is not needed on 3.12. The header's run line passes a file path to `python3 -m unittest` {src:tests/hooks/test_scrub_secrets.py:9}; this page did not run it, so whether that form works on every supported Python is not checked.

**Tests that cannot fail.** None found. The deny and key-in-command cases overlap (both feed a token to a Bash command), but each asserts something different.

**Unchecked inputs.** The payload strings are constants and fake values; none reaches a file path, command or network address. The `file_path` values such as `/x/a.txt` are only scanned by the hook, never opened {src:tests/hooks/test_scrub_secrets.py:56-58}.

**Shared-file writes.** The only file written is the temporary registry under a `TemporaryDirectory` {src:tests/hooks/test_scrub_secrets.py:85-88}; it is removed when the block exits. Nothing is written to a shared file and no two writers are involved.
