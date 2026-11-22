---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/leak/test_leak.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["tests/leak/scan_leaks.py"]         # source files under test, relative paths from repo root
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

This file tests the leak scanner: the tool that walks a repo folder and reports private terms (rule LEK-01), personal file paths (LEK-02), key and token shapes, attribution lines and filled-in date headers (LEK-03), a bad LICENSE holder (LEK-04), and political analysis inside the `influence.md` or `tg-influence.md` command file (CMD-04). All data is made up at run time inside a temporary folder, so the test file avoids holding a whole literal key {src:tests/leak/test_leak.py:2-5}.

## Dependencies

**Depends on.**
- [[scan_leaks]] ([scan_leaks](scan_leaks.md)): imported as a module {src:tests/leak/test_leak.py:19} and also started as a child process {src:tests/leak/test_leak.py:21} {src:tests/leak/test_leak.py:107}.
- Standard library: `io`, `os`, `struct`, `subprocess`, `sys`, `tempfile`, `unittest`, `zlib` {src:tests/leak/test_leak.py:7-14}.

**Used by.**
- Product code: none (searched `git grep` for `test_leak` outside `docs/`, 2026-11-20).
- Tests and runners: found by the leak runner's `test_*.py` discovery {src:tests/leak/run.sh:10}, see [[run]] ([run](run.md)). It is listed by name in the scanner's allowlist so the scanner does not flag it {src:tests/leak/allowed_fixtures.txt:7}. The CI workflow runs it, once per operating system, through the leak runner's no-argument mode {src:.github/workflows/tests.yml:40} {src:.github/workflows/tests.yml:41} {src:tests/leak/run.sh:10}. See [[tests]] ([tests](../../.github/workflows/tests.md)).

## Behavior

**Setup.** Every case extends `Base`. `setUp` makes a temporary folder holding a valid LICENSE and writes a denylist file next to it (the folder path plus `-deny.txt`, so it sits outside the scanned tree) {src:tests/leak/test_leak.py:45-50}. `tearDown` removes both {src:tests/leak/test_leak.py:52-55}. The `scan` helper loads the denylist unless told not to, builds a `Scanner` and returns its hits {src:tests/leak/test_leak.py:57-61}. The fake term and name are built from two halves at run time {src:tests/leak/test_leak.py:22-23}. A helper builds a real tiny PNG with a text chunk, to test image metadata {src:tests/leak/test_leak.py:33-41}.

**LEK-01, denylist terms (class `Lek01`).**

| Case | What it proves |
|---|---|
| 01a | An upper-case copy of the term in a text file is found; the scanner lower-cases the text first {src:tests/leak/test_leak.py:68-71} {src:tests/leak/scan_leaks.py:214}. |
| 01b | The term inside JSON and HTML files gives two hits {src:tests/leak/test_leak.py:73-76}. |
| 01c | The term inside a binary file and inside PNG text metadata is found, one file each {src:tests/leak/test_leak.py:78-82}. The scanner pulls printable strings out of anything with a zero byte near the start {src:tests/leak/scan_leaks.py:153} {src:tests/leak/scan_leaks.py:158-159}. |
| 01d | A file whose name holds the term is a hit even with clean content {src:tests/leak/test_leak.py:84-86} {src:tests/leak/scan_leaks.py:216-217}. |
| 01e | A clean tree gives no hits {src:tests/leak/test_leak.py:88-90}. |
| 01f | Files under `.git` are skipped {src:tests/leak/test_leak.py:92-94} {src:tests/leak/scan_leaks.py:185}. |
| 01g | The printed report never contains the term, because it is masked {src:tests/leak/test_leak.py:96-102}. |
| 01h | The denylist path can come from the environment variable or the `--denylist` flag; both give exit 1, and the output names LEK-01 without the term {src:tests/leak/test_leak.py:104-115} {src:tests/leak/scan_leaks.py:315}. |
| 01i | An allowlist entry by bare file name hides a hit in that file {src:tests/leak/test_leak.py:117-120} {src:tests/leak/scan_leaks.py:142-148}. |

**LEK-02, personal paths (class `Lek02`).** Two personal-looking paths in a shell file give two hits {src:tests/leak/test_leak.py:124-126}. Generic forms (`$HOME`, a bracketed name, `you`, `user`, `runner`, `~`) give none {src:tests/leak/test_leak.py:128-131}; the scanner's generic-name list holds those names {src:tests/leak/scan_leaks.py:43-47}. An allowlist entry for LEK-02 hides that rule only: a second rule in the same file still reports {src:tests/leak/test_leak.py:133-138}. A path inside a binary file is found {src:tests/leak/test_leak.py:140-142}.

**LEK-03, keys, attribution, date header (class `Lek03`).**
- Four key shapes (cloud access key, GitHub token, API secret key, private key block) in one file give four hits, and the report text holds none of the first three secrets {src:tests/leak/test_leak.py:146-156}. The key patterns live in the scanner {src:tests/leak/scan_leaks.py:52-63}.
- A quoted credential assignment gives one hit and the masked detail hides the value {src:tests/leak/test_leak.py:158-163}.
- Both attribution phrases give two hits {src:tests/leak/test_leak.py:165-169}.
- A date header with a value is a hit; a header with nothing after the colon, or only a space, is not {src:tests/leak/test_leak.py:171-176} {src:tests/leak/scan_leaks.py:68}.
- A date line at line 5 is a hit and the same kind of line at line 80 is not, so only the first 30 lines count {src:tests/leak/test_leak.py:178-187} {src:tests/leak/scan_leaks.py:39}.
- A clean file gives no hits {src:tests/leak/test_leak.py:189-191}.

**LEK-04, LICENSE (class `Lek04`).** A personal full name passes {src:tests/leak/test_leak.py:199-200}. A missing LICENSE gives one hit {src:tests/leak/test_leak.py:202-204} {src:tests/leak/scan_leaks.py:260-262}. Company wording in the holder line gives one hit for each of five holders, such as an "Inc." name, an "LLC" name, a "Contributors" name, a "Labs" name and a "Technologies" name {src:tests/leak/test_leak.py:206-209} {src:tests/leak/scan_leaks.py:72-76}. A LICENSE with no copyright line gives one hit {src:tests/leak/test_leak.py:211-212} {src:tests/leak/scan_leaks.py:268-270}. A holder line with an email address gives one hit {src:tests/leak/test_leak.py:214-215} {src:tests/leak/scan_leaks.py:276-277}.

**CMD-04, the influence command file (class `Cmd04`).** The helper writes `commands/influence.md` and keeps only CMD-04 hits {src:tests/leak/test_leak.py:219-221}. A trust rating in a file named `commands/tg-influence.md` also gives a hit, which proves the shipped command name is checked too (case 04g, new in the cleanup) {src:tests/leak/test_leak.py:223-225} {src:tests/leak/scan_leaks.py:208}. A plain rewrite instruction gives none {src:tests/leak/test_leak.py:227-230}. A trust rating, an influence strategy or power map, and a sentence analysing a named person each give at least one hit {src:tests/leak/test_leak.py:232-241}. The same strategy text in a file named `other.md` gives none, because the scanner only applies the rule to the two influence file names {src:tests/leak/test_leak.py:243-245} {src:tests/leak/scan_leaks.py:208}.

**Command line (class `Cli`).** A clean folder run with a nonexistent allowlist and no denylist variable gives exit 0 {src:tests/leak/test_leak.py:249-254}; a missing denylist only prints a warning {src:tests/leak/scan_leaks.py:322-323}. A nonexistent folder gives exit 2 {src:tests/leak/test_leak.py:255-256} {src:tests/leak/scan_leaks.py:312-314}.

## Diagram

None: the cases are independent and share one small setup; there is no mock chain.

## Notes

**Code and description.** No disagreement found between this file's docstring and its code: the docstring lists LEK-01 to LEK-04 and CMD-04 {src:tests/leak/test_leak.py:2}, and each has cases. The file still needs the allowlist entry {src:tests/leak/allowed_fixtures.txt:7}, because it contains literal date-header lines such as `# Date: 2026-11-18` inside test strings {src:tests/leak/test_leak.py:173} {src:tests/leak/test_leak.py:181}, which match the date rule {src:tests/leak/scan_leaks.py:68}.

**Allowlist path mismatch.** The allowlist names `docs/tests/leak.md` for LEK-03 {src:tests/leak/allowed_fixtures.txt:13}. The pages for this folder now live under `docs/tests/leak/`, so that entry matches none of them. A page in this folder that quotes a key shape or attribution phrase would be flagged unless it is added to the list (this page and its siblings were written to avoid such text).

**Weak or misleading tests.**
- Case 04g asserts only that a CMD-04 hit exists for `tg-influence.md`, not which sub-rule fired {src:tests/leak/test_leak.py:225}.
- Case 01e is described as "clean tree and comments" but its tree has no text that would match the denylist's comment line, so it cannot catch a bug that stopped skipping comments {src:tests/leak/test_leak.py:88-90} {src:tests/leak/test_leak.py:50} {src:tests/leak/scan_leaks.py:117-118}.
- The CMD-04 cases 04b, 04c and 04d assert only that the hit list is not empty, so they do not show which sub-rule fired {src:tests/leak/test_leak.py:233-234} {src:tests/leak/test_leak.py:237-238} {src:tests/leak/test_leak.py:241}.
- The LEK-04 company wording list includes the words `ai`, `team`, `health` and `group` {src:tests/leak/scan_leaks.py:72-76}. No case checks that a real personal name containing one of those words is wrongly flagged.

**Not tested here.** Slack, Google and JWT key shapes {src:tests/leak/scan_leaks.py:56-59}, files over the size cap and unreadable files {src:tests/leak/scan_leaks.py:196-203}, symbolic links being skipped, and files or folders named `__pycache__` being skipped {src:tests/leak/scan_leaks.py:37} {src:tests/leak/scan_leaks.py:188}, the UTF-16 string pull {src:tests/leak/scan_leaks.py:161-162}, a denylist path that does not exist (exit 2) {src:tests/leak/scan_leaks.py:318-320}.

**Machine dependence.** The CLI cases assume `/nonexistent` and `/nonexistent-folder` are absent {src:tests/leak/test_leak.py:107} {src:tests/leak/test_leak.py:255}. Binary strings are matched with a bytes pattern that uses `%` formatting, which needs Python 3.5 or later {src:tests/leak/scan_leaks.py:159}. No other Python-version issue found.

**Unchecked inputs.** All data is constant or built in the test. The only path made from variable text is the denylist file name, the temporary folder path plus a fixed suffix {src:tests/leak/test_leak.py:49}. No test input reaches a network address or a shell string; the child processes take an argument list, not a shell command {src:tests/leak/test_leak.py:107-108}.

**Shared-file writes.** Everything is written inside a `TemporaryDirectory`, plus the sibling denylist file in the system temp folder {src:tests/leak/test_leak.py:46-50}. The sibling file is removed in `tearDown` {src:tests/leak/test_leak.py:54-55}. Writes are plain, not atomic, and nothing locks them, but each run uses its own random temp folder name so parallel runs do not share a file.
