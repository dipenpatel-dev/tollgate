---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/test_gate_rules.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["hooks/gate_rules.py"]         # source files under test, relative paths from repo root
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

This file tests the pure rule functions that decide whether the `tg-arch`, `tg-dev` and `tg-qa` skills may run: reading a `Status:` line from file text, and the per skill checks built on it. It uses synthetic text only, with the fake id `T-001`, and calls the functions directly with no subprocess {src:tests/hooks/test_gate_rules.py:1-6} {src:tests/hooks/test_gate_rules.py:24}. It has 49 tests in 7 classes. It was not run while this page was written, so each claim says what a test asserts.

## Dependencies

**Depends on.**
- The module under test, `hooks/gate_rules.py`: [[gate_rules]] and [gate_rules](../../hooks/gate_rules.md). The test adds the `hooks/` folder to `sys.path` and imports it as `gr` {src:tests/hooks/test_gate_rules.py:20-24}.
- Standard library only: `os`, `sys`, `unittest`.

**Used by.** Product code: none. Tests: the unit test step of the hook runner finds this file by the pattern `test_*.py` {src:tests/hooks/run.sh:198}, and the CI workflow runs the same command {src:.github/workflows/tests.yml:35}. The leak scanner skips this file for one rule, by name {src:tests/leak/allowed_fixtures.txt:17}. Searched 2026-11-20: the whole worktree except `.git`, `docs/`, caches and virtual environments for `test_gate_rules`; those were the only hits.

## Behavior

**Setup.** `state(value)` builds a state file text with one `Status:` line {src:tests/hooks/test_gate_rules.py:26} {src:tests/hooks/test_gate_rules.py:31-32}. `spec_allows(text)` calls `check_arch` with the given spec text and a fixed state `SPEC_APPROVED`, so every spec test runs the whole arch rule, not the reader alone {src:tests/hooks/test_gate_rules.py:35-37} {src:hooks/gate_rules.py:187-194}. A false result there shows only that arch blocks, not which part of the rule blocked.

**SpecStatusLineTests (8).** These prove the spec file needs exactly one clean `Status:` line with the approved value.
- A spec whose `Status:` line holds the approved value passes {src:tests/hooks/test_gate_rules.py:43-44} {src:hooks/gate_rules.py:36}.
- The approved value in square brackets, the approved value followed by a pipe and `DRAFT`, and a bare `Status:` all fail {src:tests/hooks/test_gate_rules.py:46-49} {src:hooks/gate_rules.py:145-146} {src:hooks/gate_rules.py:161}.
- The old dated approval line, with a hyphen or with an em dash written as an escape, no longer counts {src:tests/hooks/test_gate_rules.py:51-53} {src:hooks/gate_rules.py:143-144}.
- A status line inside a backtick fence or a tilde fence does not count; a line after a closed fence does {src:tests/hooks/test_gate_rules.py:55-63} {src:hooks/gate_rules.py:107-123}.
- Trailing spaces pass; extra words after the value fail; a line starting `Note: ` fails {src:tests/hooks/test_gate_rules.py:65-68} {src:hooks/gate_rules.py:138-142}. A CRLF file passes {src:tests/hooks/test_gate_rules.py:70-72} {src:hooks/gate_rules.py:47}.
- `test_validation_and_design_use_their_own_values`: the name mentions validation, but the body checks only `check_dev` with three design values: the spec value fails, `DESIGN_COMPLETE` fails and `DESIGN_APPROVED` passes with state `IN_DEV` {src:tests/hooks/test_gate_rules.py:74-77} {src:hooks/gate_rules.py:37}. Nothing in that test touches the validation file.

**FenceTrackingTests (8).** These prove the fence rules follow CommonMark. A status line inside a fence is hidden, and an unclosed fence hides everything after it {src:hooks/gate_rules.py:107-123}.
- A fence opened with backticks and ended with tildes, or the reverse, does not close, so the status stays hidden {src:tests/hooks/test_gate_rules.py:84-86} {src:hooks/gate_rules.py:98-104}.
- A four backtick fence is not closed by a three backtick line {src:tests/hooks/test_gate_rules.py:88-89}. A closing line that carries text such as `python` does not close {src:tests/hooks/test_gate_rules.py:91-92}. A closing run longer than the opening run does close {src:tests/hooks/test_gate_rules.py:94-95}.
- An opening line may carry info text {src:tests/hooks/test_gate_rules.py:97-98}. A fence indented four spaces is not a fence, so the status after it counts {src:tests/hooks/test_gate_rules.py:100-101} {src:hooks/gate_rules.py:28} {src:hooks/gate_rules.py:46}. A backtick fence line with a backtick in its info text is not a fence {src:tests/hooks/test_gate_rules.py:103-104} {src:hooks/gate_rules.py:93-94}.
- `read_status` on a backtick fence followed by a tilde fence finds no status {src:tests/hooks/test_gate_rules.py:106-108}.

**TextHandlingTests (3).** These prove odd characters cannot hide or split a status line.
- U+2028 does not split a line, so `x` plus U+2028 plus a status line fails, and two status words joined by U+2028 read as one value {src:tests/hooks/test_gate_rules.py:112-116} {src:hooks/gate_rules.py:82-84}. A lone carriage return does not split {src:tests/hooks/test_gate_rules.py:118-119}.
- A BOM at the start does not hide the first line, for text and for bytes, and a design file starting with a BOM passes `check_dev` {src:tests/hooks/test_gate_rules.py:121-125} {src:hooks/gate_rules.py:67-79}. The text case holds a literal U+FEFF character typed into the source line, which cannot be seen in an editor {src:tests/hooks/test_gate_rules.py:122}.

**StatusTests (8).** These prove what `read_status` accepts and rejects.
- It returns the value with trailing spaces removed {src:tests/hooks/test_gate_rules.py:129-132} {src:hooks/gate_rules.py:138-142}. Two different status lines are malformed; the same value twice is fine {src:tests/hooks/test_gate_rules.py:134-139} {src:hooks/gate_rules.py:147-149}.
- An empty file, a blank file, no status line, bytes that are not UTF-8, `None` and `Status:` with no value are all malformed {src:tests/hooks/test_gate_rules.py:141-147} {src:hooks/gate_rules.py:133-146}.
- Bytes input and CRLF input work {src:tests/hooks/test_gate_rules.py:149-153}. A status inside a fence is ignored in favor of the one after it {src:tests/hooks/test_gate_rules.py:155-157}. An indented `Status:` is not a top level line {src:tests/hooks/test_gate_rules.py:159-160} {src:hooks/gate_rules.py:141}.

**ArchRuleTests (7).** An approved spec plus state `SPEC_APPROVED` allows {src:tests/hooks/test_gate_rules.py:164-166}. A missing spec, a spec with no status line, a spec with another value and a lower case value each block, and the reason names `spec.md` or the expected line {src:tests/hooks/test_gate_rules.py:168-184} {src:hooks/gate_rules.py:152-166}. A wrong state blocks and the reason names `SPEC_APPROVED`; a missing state blocks and names `state file` {src:tests/hooks/test_gate_rules.py:186-194} {src:hooks/gate_rules.py:169-177}.

**DevRuleTests (6).** A design with the status `DESIGN_APPROVED` allows with state `DESIGN_APPROVED` or `IN_DEV` {src:tests/hooks/test_gate_rules.py:200-202} {src:hooks/gate_rules.py:39} {src:hooks/gate_rules.py:197-204}. State `DESIGN_COMPLETE` or `DEV_COMPLETE` blocks {src:tests/hooks/test_gate_rules.py:204-205} {src:tests/hooks/test_gate_rules.py:216-217}. A design with no status line blocks and names `design.md` and the expected line; a missing design blocks {src:tests/hooks/test_gate_rules.py:207-214}. With both files wrong the reason names both {src:tests/hooks/test_gate_rules.py:219-222} {src:hooks/gate_rules.py:180-184}.

**QaRuleTests (9).** The setup is a good set: state `DEV_COMPLETE`, spec, design and a validation file with the status `DOCUMENTED` {src:tests/hooks/test_gate_rules.py:226-233}.
- All good allows; the value `VALIDATED` also allows {src:tests/hooks/test_gate_rules.py:235-240} {src:hooks/gate_rules.py:38}.
- A validation value `PENDING`, or the old dated line alone, blocks and names `edge-case-validation.md` {src:tests/hooks/test_gate_rules.py:242-250} {src:hooks/gate_rules.py:207-218}. State `IN_DEV` blocks. A spec status that is not the approved value blocks and names `spec.md`. A missing design names `design.md` {src:tests/hooks/test_gate_rules.py:252-264}.
- The reason never repeats the status value found in a file: for state values `UNIQUE_STATUS_TEXT_9` and `IN_DEV` it names `DEV_COMPLETE` and not the value, and the same holds for arch and for a bad spec {src:tests/hooks/test_gate_rules.py:266-276} {src:hooks/gate_rules.py:152-166}. The reason never holds file body text {src:tests/hooks/test_gate_rules.py:278-282}.

## Diagram

No diagram: these are direct calls on strings, with no fixtures or mocks.

## Notes

**Tests that look wrong or cannot fail**
- `test_validation_and_design_use_their_own_values` does not test validation, despite its name {src:tests/hooks/test_gate_rules.py:74-77}.
- Every spec test that expects a false result goes through the full arch rule, so it cannot say whether the status reader or the state check blocked {src:tests/hooks/test_gate_rules.py:35-37}.
- Test numbers have gaps (1, 3, 4 and so on, with 2 absent) because dated and date shaped tests were removed {src:tests/hooks/test_gate_rules.py:9-10}. Two classes each have a test numbered 9 with different bodies {src:tests/hooks/test_gate_rules.py:70} {src:tests/hooks/test_gate_rules.py:152}.

**Coverage gaps.** No test calls `check_qa` with several problems at once, so the join of reasons is shown only for `check_dev` {src:tests/hooks/test_gate_rules.py:219-222} {src:hooks/gate_rules.py:180-184}. `lines_outside_fences` and `split_lines` are reached only through the other functions {src:hooks/gate_rules.py:82-123} (searched the test file for direct calls to them, 2026-11-20, none found). The hook handling, override files and fail closed behavior are tested elsewhere, in [test_gate_hook](test_gate_hook.md).

**Description against code.** The test header agrees with the module: the accepted values match {src:tests/hooks/test_gate_rules.py:3-5} {src:hooks/gate_rules.py:32-39}. The change log of the module under test still says "ASCII digits only" {src:hooks/gate_rules.py:15-16}, but the module holds no date or digit handling, since the date parsers were removed {src:hooks/gate_rules.py:12-13}.

**Machine and version dependence.** None found: the paths come from the file location, no clock is read (the date strings in the tests are fixed text), and no external program is run {src:tests/hooks/test_gate_rules.py:20-22} {src:tests/hooks/test_gate_rules.py:53}. It needs Python 3.7 or newer because the module under test uses a dataclass {src:hooks/gate_rules.py:21} {src:hooks/gate_rules.py:50}.

**Inputs without a check, and shared writes.** The tests pass strings to pure functions; no file, command or network is used and nothing is written.
