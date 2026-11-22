---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/hooks/test_phi_strong_rules.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers:            # source files under test, relative paths from repo root
  - hooks/phi_patterns.py
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

This file tests the three strong rules of the PHI detector: a full street address, a date of birth written as a phrase or with a month name, and a phone number. It also checks that look-alike text stays quiet, that matching stays fast on long hostile input, and that its own source and the fake value builder hold nothing the detector would flag {src:tests/hooks/test_phi_strong_rules.py:3-4}. Every test value comes from the fake builders and is built at run time {src:tests/hooks/test_phi_strong_rules.py:7}.

## Dependencies

**Depends on.** [[phi_patterns]] and [phi_patterns](../../hooks/phi_patterns.md), imported as `Finding`, `Level`, `scan_for_phi` and `scan_levels` {src:tests/hooks/test_phi_strong_rules.py:25}. The fake value builders [[fake_phi]] and [fake_phi](fake_phi.md) {src:tests/hooks/test_phi_strong_rules.py:23}, and the clean text list [[clean_corpus]] and [clean_corpus](clean_corpus.md) {src:tests/hooks/test_phi_strong_rules.py:24}. The test puts its own folder and `hooks/` on `sys.path` before importing {src:tests/hooks/test_phi_strong_rules.py:20-21}. Standard library: `os`, `sys`, `time`, `unittest`.

**Used by.** No product code imports a test file. The folder is run by discovery on `test_*.py` (searched with `git grep -n -E "discover -s"`, 2026-11-20):
- Tests: `tests/hooks/run.sh` {src:tests/hooks/run.sh:198}, the CI workflow {src:.github/workflows/tests.yml:35}, `tests/system/run.sh` {src:tests/system/run.sh:20}, and the run line in its own header {src:tests/hooks/test_phi_strong_rules.py:9}.

## Behavior

The helper `labels` returns only the rule labels that `scan_levels` reports for one text {src:tests/hooks/test_phi_strong_rules.py:31-32}. The detector gives each label a level; unknown labels default to deny {src:hooks/phi_patterns.py:203-213}. The file has 28 tests in six classes.

**AddressRule (8 tests).**
- A full fake address gives exactly one finding, `ADDRESS` at deny {src:tests/hooks/test_phi_strong_rules.py:36-37}. The address rule is the last entry of the main pattern list {src:hooks/phi_patterns.py:158} and `ADDRESS` maps to deny {src:hooks/phi_patterns.py:206}.
- `scan_for_phi` also reports it, as `["ADDRESS"]` {src:tests/hooks/test_phi_strong_rules.py:39-40}, because the address rule sits in the list that function reads {src:hooks/phi_patterns.py:146} {src:hooks/phi_patterns.py:251-253}.
- The address inside a sentence is found {src:tests/hooks/test_phi_strong_rules.py:42-43}.
- Three partial forms stay quiet: a street part alone, street plus city with no zip, and a state with zip alone {src:tests/hooks/test_phi_strong_rules.py:45-52}. The pattern needs number, street words, a street suffix, city, two capital letters and five digits in order {src:hooks/phi_patterns.py:126-133}, and a street part alone is only a clue that never warns on its own {src:hooks/phi_patterns.py:285-286}.
- Extra spaces and tabs between the words still match {src:tests/hooks/test_phi_strong_rules.py:54-56}, since gaps allow one to three whitespace characters {src:hooks/phi_patterns.py:126}.
- An all upper case address still matches {src:tests/hooks/test_phi_strong_rules.py:58-60}. The patterns are compiled ignoring case {src:hooks/phi_patterns.py:183}, while the state letters stay case sensitive {src:hooks/phi_patterns.py:131}, which is why the test upper cases the whole text.

**BirthDateRule (6 tests).**
- `born on <month name date>` gives exactly `DOB` at deny {src:tests/hooks/test_phi_strong_rules.py:64-65}, and so does `birthday: <numeric date>` {src:tests/hooks/test_phi_strong_rules.py:67-68}. The second rule for `DOB` takes a birth label, an optional `on` or `is`, then a numeric or month name date {src:hooks/phi_patterns.py:157}. The label list includes `born` and `birthday` {src:hooks/phi_patterns.py:112}.
- `date of birth is 2 <month> 1900` (day first) and a short birth label followed by a month name date both give `DOB` {src:tests/hooks/test_phi_strong_rules.py:70-76}. The month date pattern has a day-first branch {src:hooks/phi_patterns.py:120-122}.
- A month name date with no birth word (`released on ...`) and a birth word with no date (`born in a small town`) stay quiet {src:tests/hooks/test_phi_strong_rules.py:78-82}, since the rule needs both parts {src:hooks/phi_patterns.py:157}.

**PhoneRule (7 tests).**
- A labeled phone gives exactly `PHONE` at ask {src:tests/hooks/test_phi_strong_rules.py:86-87}. The labeled pattern is kept in a separate list {src:hooks/phi_patterns.py:163-165} and maps to ask {src:hooks/phi_patterns.py:207}.
- `scan_for_phi` returns nothing for it {src:tests/hooks/test_phi_strong_rules.py:89-90}, because the main list has no phone rule and the separate list is meant to be invisible to it {src:hooks/phi_patterns.py:161-162}.
- Unlabeled phones, with parentheses or with dashes, give exactly `PHONE_UNLABELED` at warn {src:tests/hooks/test_phi_strong_rules.py:92-94} {src:hooks/phi_patterns.py:208}.
- Two labeled phones count once {src:tests/hooks/test_phi_strong_rules.py:96-97}: the labeled match is blanked before the bare number scan {src:hooks/phi_patterns.py:266-267}, and findings are collected as a set of labels {src:hooks/phi_patterns.py:508}.
- A labeled and an unlabeled phone give `["PHONE", "PHONE_UNLABELED"]` in that order {src:tests/hooks/test_phi_strong_rules.py:99-101}, since findings sort by strength then label {src:hooks/phi_patterns.py:511}.
- A phone label with no number (`phone: unknown, mobile: none`) is quiet {src:tests/hooks/test_phi_strong_rules.py:103-104}.
- A phone shaped group inside a longer digit run (`id 555-555-0100-1111`) is quiet {src:tests/hooks/test_phi_strong_rules.py:106-108}, because the bare rule refuses a start after a digit, dash or dot and an end before one {src:hooks/phi_patterns.py:141-144}.

**NegativeGuards (4 tests).** An ISO date alone and with a timestamp, order ids, versions, a UUID, an IP address, and `see 10 Example Street` all give no findings {src:tests/hooks/test_phi_strong_rules.py:112-122}. Every entry of the clean text list gives no findings at any level {src:tests/hooks/test_phi_strong_rules.py:124-125}.

**BoundedMatching (2 tests).** Six long inputs (3000 repeats of capitalized words, digits, spaces after `born`, space and colon pairs after `phone`, and many street words) must each scan in under two seconds {src:tests/hooks/test_phi_strong_rules.py:27-28} {src:tests/hooks/test_phi_strong_rules.py:129-141}. The patterns use named upper limits on every repeat for this reason {src:hooks/phi_patterns.py:46-52} {src:hooks/phi_patterns.py:114-115}.

**SourceFilesStayFake (1 test).** It opens `test_phi_strong_rules.py` and `fake_phi.py` and asserts the detector finds nothing in either text {src:tests/hooks/test_phi_strong_rules.py:144-148}.

## Diagram

None: the tests call plain functions on strings; the only fixtures are two helper modules.

## Notes

- **Time dependent.** The speed cases compare wall clock time against a fixed two second limit {src:tests/hooks/test_phi_strong_rules.py:27} {src:tests/hooks/test_phi_strong_rules.py:131-132}. A loaded machine or a slow CI runner can fail them with no code change. They also prove only that these six inputs are fast, not that every input is.
- **Code and description disagree (phi_patterns header).** The header says the phone rules "live in LEVELED_PATTERNS" {src:hooks/phi_patterns.py:15-16}. That list holds one rule, the labeled phone {src:hooks/phi_patterns.py:163-165}. The unlabeled rule is a separate compiled pattern {src:hooks/phi_patterns.py:186}.
- **Header of this file.** It names three rules {src:tests/hooks/test_phi_strong_rules.py:4}. The file also covers the unlabeled phone, the quiet guards, timing and the source check. Nothing in it is wrong, it is only narrower than the content.
- **Not tested here.** The name rules, the context windows, chunked scanning of text over 64 KB {src:hooks/phi_patterns.py:275}, and text normalization of look-alike letters {src:hooks/phi_patterns.py:239-244}. Other test files in this folder cover those.
- **Version and machine dependence.** No machine path is used; the two source files are found next to the test {src:tests/hooks/test_phi_strong_rules.py:19} {src:tests/hooks/test_phi_strong_rules.py:147}. The module under test uses `from __future__ import annotations` to allow `list[str]` style annotations {src:hooks/phi_patterns.py:37}, so older Python versions were fine for those; the future import was kept from when the minimum was 3.9 and is not needed on 3.12.
- **Inputs without a check.** All inputs are built from the fake builders. The only file reads are the two fixed names in the last test {src:tests/hooks/test_phi_strong_rules.py:146-147}.
- **Shared file writes.** None.
