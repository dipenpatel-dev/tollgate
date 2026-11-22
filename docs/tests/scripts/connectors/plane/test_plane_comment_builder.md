---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_comment_builder.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/plane_comment_builder.py, scripts/connectors/plane/plane_markdown.py, scripts/connectors/plane/vault_ticket_files.py, scripts/connectors/plane/plane_sync_settings.py]         # source files under test, relative paths from repo root
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

Tests for the Plane comment builder, which turns vault text into the comments that are posted to a Plane card. They check that raw html is shown as text, that the secret scanner finds each kind of secret and ignores ordinary text, that long text is cut to the limit with a pointer line, that new session text is read from an offset, that the spec and design extras are cut out of the right sections, and that the comment key is stable.

## Dependencies

**Depends on.**
- Under test: [[plane_comment_builder]] / [plane_comment_builder](../../../../scripts/connectors/plane/plane_comment_builder.md) for nine functions {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:15-25}. Through it: [[plane_markdown]] / [plane_markdown](../../../../scripts/connectors/plane/plane_markdown.md) {src:scripts/connectors/plane/plane_comment_builder.py:17} and [[vault_ticket_files]] / [vault_ticket_files](../../../../scripts/connectors/plane/vault_ticket_files.md) for the session file list {src:scripts/connectors/plane/plane_comment_builder.py:18}.
- Test support: [[plane_sync_test_support]] / [plane_sync_test_support](plane_sync_test_support.md) for `FAKE_TOKEN` and `make_settings` {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:26}. `make_settings` loads the shipped example settings file, so the secret patterns come from [[plane_sync_settings]] / [plane_sync_settings](../../../../scripts/connectors/plane/plane_sync_settings.md) {src:tests/scripts/connectors/plane/plane_sync_test_support.py:80-84} {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:28}.
- Standard library: `tempfile`, `unittest`, `pathlib` {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:11-13}.

**Used by.** Run by [[run]] / [run](run.md) through the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}. `git grep` for `test_plane_comment_builder` outside `docs/` finds no other reference (searched 2026-11-20).

## Behavior

Fixtures. `PATTERNS` are the secret patterns of the example settings {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:28}; the example file has no `secret_patterns` key (searched 2026-11-20), so the built-in default patterns apply {src:scripts/connectors/plane/plane_sync_settings.py:184}. The key block and the assignment test strings are joined from two pieces so the source file does not hold a whole secret {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:29-30}. `SPEC` and `DESIGN` are small markdown samples {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:31-35}.

`TestMarkdownAndSecrets` (five tests):
1. `test_raw_html_is_shown_as_text`: a script tag becomes `&lt;script&gt;` and `**bold**` becomes a strong tag {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:39-43}; the renderer escapes `<` and `>` {src:scripts/connectors/plane/plane_markdown.py:26-29} and renders bold {src:scripts/connectors/plane/plane_markdown.py:49}.
2. `test_each_pattern_catches_its_case`: the key block gives `private_key_block`, the assignment gives `named_secret_assignment`, and the fake token gives `long_mixed_token` {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:45-48}. Those three patterns are in the defaults {src:scripts/connectors/plane/plane_sync_settings.py:25-29} {src:scripts/connectors/plane/plane_sync_settings.py:40-43}. Only three of the ten default patterns have a test case here {src:scripts/connectors/plane/plane_sync_settings.py:24-44}.
3. `test_clean_text_has_no_hit`: ordinary text with a short sha, the word `token` and a file name gives `None`, and an empty pattern map gives `None` {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:50-53}.
4. `test_long_hyphenated_file_names_are_not_tokens`: a long name with many hyphens is not flagged {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:55-57}; the pattern refuses a candidate with three or more hyphens {src:scripts/connectors/plane/plane_sync_settings.py:42}.
5. `test_first_matching_pattern_name_is_returned`: with two patterns that both match, the first name wins {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:59-61}; the function returns at the first hit in map order {src:scripts/connectors/plane/plane_comment_builder.py:33-35}.

`TestCutAndKey` (four tests):
1. Text within the limit is returned unchanged {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:65-66}; see {src:scripts/connectors/plane/plane_comment_builder.py:41-42}.
2. A longer text is cut to exactly the limit and ends with a newline and the pointer line {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:68-71}; see {src:scripts/connectors/plane/plane_comment_builder.py:43-44}.
3. With a limit of 2 and a 7-letter pointer, the result is `"\npointer"`, which is longer than the limit {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:73-74}. The kept length is floored at zero {src:scripts/connectors/plane/plane_comment_builder.py:43}.
4. The comment key is 12 lowercase hex characters, the same for the same text, and different when one space is added {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:76-80}; see {src:scripts/connectors/plane/plane_comment_builder.py:127}.

`TestSessionText` (four tests). `setUp` writes two session files and one state file into a temporary folder {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:84-90}.
1. All text is read with a heading per file and the offsets are the file lengths 11 and 10 {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:92-95}; see {src:scripts/connectors/plane/plane_comment_builder.py:53-59}. The state file is left out because only names that contain `-session-` match {src:scripts/connectors/plane/vault_ticket_files.py:265}.
2. With an offset for the first file, only the second file's text comes back {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:97-100}; see {src:scripts/connectors/plane/plane_comment_builder.py:56}.
3. With offsets equal to the lengths, the text is empty and the offsets are unchanged {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:102-107}; see {src:scripts/connectors/plane/plane_comment_builder.py:57}.
4. Reading leaves the same set of file names in the folder {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:109-112}.

`TestExtras` (five tests):
1. A section runs from its `##` line to the next `##` line; a missing heading gives an empty string {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:116-119}; see {src:scripts/connectors/plane/plane_comment_builder.py:66-73}.
2. The mermaid block is the first one after the named heading, and a missing heading gives an empty string {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:121-124}; see {src:scripts/connectors/plane/plane_comment_builder.py:87-98}.
3. The spec extras hold the requirements, the acceptance criteria and the diagram, and leave out the earlier diagram and the budget section {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:126-131}; see {src:scripts/connectors/plane/plane_comment_builder.py:104-112}.
4. An empty spec and design give three `(extras:` lines that name what is missing {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:133-135}; see {src:scripts/connectors/plane/plane_comment_builder.py:106} {src:scripts/connectors/plane/plane_comment_builder.py:111}.
5. The validation extras drop a leading frontmatter block, and plain text is only stripped of outer newlines {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:137-140}; see {src:scripts/connectors/plane/plane_comment_builder.py:118-122}.

## Diagram

<!-- Skipped: pure function tests with samples held in constants; there are no mocks or shared fixtures beyond one temporary folder. -->

## Notes

- **Code and description disagree.** The header says the tests cover "html, secret patterns, cut, session text, extras, and a scan of real session logs" {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:2}. No test in the file scans real session logs; the session tests use two files made in a temporary folder {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:84-90}. The header also says "real HTTP goes to the local stub on 127.0.0.1" {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:5}, but this file starts no stub and makes no HTTP call. The `Date:` field is empty {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:4}.
- **A test that proves less than its name.** `test_reading_writes_nothing` compares file names only {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:110-112}. A write into an existing session file would not change the names, so it would pass.
- **A test that is tied to a shipped file.** The patterns come from the example settings file on disk and its lack of a `secret_patterns` key {src:tests/scripts/connectors/plane/plane_sync_test_support.py:42} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:82}. Adding that key to the example would change what the tests check. The fake token always has an upper case letter, a lower case letter and a digit, so it cannot miss the mixed-token pattern {src:tests/scripts/connectors/plane/plane_sync_test_support.py:47-49}. No machine path or Python version dependence found.
- **Not tested (product code the tests drive).**
  - The ticket id goes into a file pattern with no check in the builder {src:scripts/connectors/plane/vault_ticket_files.py:265}; an id with wildcard characters would match other session files, and the builder's own callers must check it.
  - The offsets are used as slice starts without a check, so a negative number would return the end of the file {src:scripts/connectors/plane/plane_comment_builder.py:56}. Offsets count characters, not bytes {src:scripts/connectors/plane/plane_comment_builder.py:55}.
  - Patterns from the settings go straight into `re.search`; a bad pattern would raise an error that is not caught here {src:scripts/connectors/plane/plane_comment_builder.py:34}.
  - The builder only reports a secret match; it does not stop outbound text by itself. Whether the text is blocked depends on the caller {src:scripts/connectors/plane/plane_comment_builder.py:31-36}. `cut_to_limit` can return more than the limit when the limit is shorter than the pointer line {src:scripts/connectors/plane/plane_comment_builder.py:43-44}.
- **Writes to shared files.** None. The builder only reads files {src:scripts/connectors/plane/plane_comment_builder.py:54}; the tests write inside a temporary folder that is removed afterwards {src:tests/scripts/connectors/plane/test_plane_comment_builder.py:85-87}.
