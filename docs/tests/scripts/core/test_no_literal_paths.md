---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/core/test_no_literal_paths.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/core/paths.py, scripts/core/tg_path, hooks]         # source files under test, relative paths from repo root
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

This test enforces one repo rule: no script holds a literal home path, a literal vault folder name or a literal hostname. Folder names must come from the path loader. The file scans every file under `scripts/` for those three kinds of text and fails if it finds any outside a short allowlist of the loader itself {src:tests/scripts/core/test_no_literal_paths.py:3}. It also checks its own scanner with three small self-tests, and runs a second, narrower scan of the `hooks` folder.

## Dependencies

**Depends on.**
- Standard library imports, as written: `os`, `pathlib`, `re`, `tempfile`, `unittest` {src:tests/scripts/core/test_no_literal_paths.py:10-14}. `os` is imported but not used anywhere in the file.
- The repo layout: `REPO` is three folders above the test file, `SCRIPTS` is `REPO/scripts` {src:tests/scripts/core/test_no_literal_paths.py:16-17}.
- Two loader files that are exempt from the scan: [[paths]] [paths](../../../scripts/core/paths.md) and [[tg_path]] [tg_path](../../../scripts/core/tg_path.md) {src:tests/scripts/core/test_no_literal_paths.py:18}.
- The `hooks` folder, read as plain files {src:tests/scripts/core/test_no_literal_paths.py:103}. No page covers the folder as a whole (no doc yet).
- No test harness module is used: this file does not import `throwaway_home`.

**Used by.**
- Product code: none. Searched with `git grep` for `test_no_literal_paths` outside `docs/` on 2026-11-20; the only hit is this file's own header {src:tests/scripts/core/test_no_literal_paths.py:2}.
- Found at run time by the folder runner, which uses `unittest discover` with the pattern `test_*.py` {src:tests/scripts/core/run.sh:6}, and by the end-to-end runner that calls every area runner {src:tests/system/run.sh:23}.
- Tests: this file is itself a test.

## Behavior

**Patterns.** Three lists of regular expressions are combined into one list of `(pattern, kind)` pairs {src:tests/scripts/core/test_no_literal_paths.py:32-34}.
- Home paths: `/Users/`, `/home/<letter>`, `/Volumes/`, `~/`, `Path.home()`, `expanduser("~...")` and `$HOME` forms {src:tests/scripts/core/test_no_literal_paths.py:20-23}.
- Folder strings: the dot-folders `.claude`, `.tollgate` and a legacy tool's dot-folder (assembled from two string pieces so this file does not contain the name itself), then `.cursor`, a numbered vault folder such as `02-tickets`, `Developer/`, and `_numbered_dir` {src:tests/scripts/core/test_no_literal_paths.py:25-26}.
- Hostnames: a quoted name ending in `.lan`, `.local`, `.internal`, `.home` or `.corp`, and private IPv4 ranges {src:tests/scripts/core/test_no_literal_paths.py:29-30}.

**Scanner functions.**
- `scan_text` goes line by line and, for each pattern, records the first match on that line as `(line number, kind, text)` {src:tests/scripts/core/test_no_literal_paths.py:40-44}. One line can therefore produce several findings, one per pattern that matches.
- `scan_tree` visits every file under a root with `rglob`, skips folders, anything under `__pycache__` {src:tests/scripts/core/test_no_literal_paths.py:52-53}, and any path in the allowlist, compared as a path relative to `root.parent` {src:tests/scripts/core/test_no_literal_paths.py:49} {src:tests/scripts/core/test_no_literal_paths.py:54-56}. Files that cannot be read as text are skipped without a message {src:tests/scripts/core/test_no_literal_paths.py:57-60}. Each finding is formatted as `file:line kind 'match'` {src:tests/scripts/core/test_no_literal_paths.py:62}.

**Class `ScannerSelfTest`.**
- `test_flags_each_kind` builds a fake home path, a fake numbered folder and a fake hostname by joining string pieces at run time, so the test file itself stays clean {src:tests/scripts/core/test_no_literal_paths.py:68-73}. It asserts each of the three kinds appears in the scan of its line {src:tests/scripts/core/test_no_literal_paths.py:74-76}. This proves each of the three lists has at least one working pattern. It does not prove every pattern works.
- `test_clean_line_passes` scans `from core.paths import get_path` and expects no findings {src:tests/scripts/core/test_no_literal_paths.py:79}.
- `test_allowlist_respected` makes a temp tree with `scripts/core/paths.py` and `scripts/core/other.py`, each holding the same `~/.tollgate` text {src:tests/scripts/core/test_no_literal_paths.py:83-86}. It expects exactly 2 findings, both in `other.py` {src:tests/scripts/core/test_no_literal_paths.py:87-89}. The two findings are two kinds on the one line (the `~/` home path and the `.tollgate` folder). The allowlist matches only because the temp folder is named `scripts`, so the relative path equals the allowlist entry {src:tests/scripts/core/test_no_literal_paths.py:83} {src:tests/scripts/core/test_no_literal_paths.py:18}.

**Class `NoLiteralPaths`.**
- `test_scripts_have_no_literal_paths` scans the real `scripts` folder and fails with the list of offenders {src:tests/scripts/core/test_no_literal_paths.py:94-97}. I did not run it (the brief forbids running the suites), so this page does not say whether it passes today.
- `test_hooks_hold_no_numbered_vault_folder_name` reads each top-level file in `hooks` whose suffix is empty, `.py` or `.sh` and searches every line with one pattern {src:tests/scripts/core/test_no_literal_paths.py:101-107}. It fails if any line matches {src:tests/scripts/core/test_no_literal_paths.py:108}. See Notes: the pattern it picks is not the numbered-folder pattern.
- `test_loader_files_exist` checks that both allowlist files exist as files {src:tests/scripts/core/test_no_literal_paths.py:111-112}. This also shows the `scripts` folder exists, so the real scan cannot pass for lack of files.

## Diagram

None: the file has no fixtures or mock chains; each test calls the scanner on a string or a folder.

## Notes

- **Code and description disagree (hooks test).** The test name and docstring say the hooks hold no numbered vault folder name and take the tickets folder from the loader {src:tests/scripts/core/test_no_literal_paths.py:99-100}. The code compiles `FOLDERS[2]` {src:tests/scripts/core/test_no_literal_paths.py:101}. In the list, index 2 is the legacy dot-folder pattern on the first row {src:tests/scripts/core/test_no_literal_paths.py:25}. The numbered-folder pattern is index 4, on the next row {src:tests/scripts/core/test_no_literal_paths.py:26}. So the test checks for the legacy dot-folder, not for numbered folder names, and it cannot catch a literal `02-tickets` in a hook. As of 2026-11-20, `git grep -E "\b0[0-9]-[a-z][a-z-]+\b" -- hooks` finds nothing, so the rule currently holds, but only by luck of the content, not because this test guards it.
- **Code and description (module header).** The header says no script outside the path loader holds these strings {src:tests/scripts/core/test_no_literal_paths.py:3}. The scan covers `scripts/` with all patterns and `hooks/` with one pattern. Other folders (for example `installer` and `tools`) are not scanned.
- **Comment wording.** The comment on the allowlist test says "both hit lines in other.py" {src:tests/scripts/core/test_no_literal_paths.py:88}. The code produces two findings on one line, not two lines.
- **Unused import.** `os` is imported {src:tests/scripts/core/test_no_literal_paths.py:10} and never used.
- **Scan limits.** `scan_text` records only the first match of each pattern per line {src:tests/scripts/core/test_no_literal_paths.py:42-44}. Unreadable and binary files are skipped silently {src:tests/scripts/core/test_no_literal_paths.py:59-60}, and the hooks scan is not recursive and skips files with other suffixes {src:tests/scripts/core/test_no_literal_paths.py:103-104}.
- **Machine and version dependence.** None: the repo root comes from `__file__` {src:tests/scripts/core/test_no_literal_paths.py:16}, and nothing needs a particular Python version beyond `pathlib` and `re`.
- **Inputs that reach paths or commands.** No input from outside the file reaches a path, command or network address. Paths come from `__file__` {src:tests/scripts/core/test_no_literal_paths.py:16} or from a temp folder {src:tests/scripts/core/test_no_literal_paths.py:82}. Every file under `scripts/` is read as text with no size limit {src:tests/scripts/core/test_no_literal_paths.py:58}.
- **Writes to shared files.** The only writes are into a `TemporaryDirectory` that is deleted when the block ends {src:tests/scripts/core/test_no_literal_paths.py:82-86}. Nothing shared is written.
- **Header.** The `date:` field of the header is empty {src:tests/scripts/core/test_no_literal_paths.py:5}.
