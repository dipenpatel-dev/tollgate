---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/chart/test_mermaid_block.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/chart/mermaid_block.py]         # source files under test, relative paths from repo root
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

This file tests the small command that lists the Mermaid diagrams in a markdown file and copies one of them out without its code-fence lines. It checks the list output, the plain-text output, the error exits and the fallback when no clipboard tool exists.

## Dependencies

Depends on:
- The module under test, [[mermaid_block]] ([mermaid_block](../../../scripts/chart/mermaid_block.md)), imported by name after the `scripts/chart` folder is put on the import path {src:tests/scripts/chart/test_mermaid_block.py:18} {src:tests/scripts/chart/test_mermaid_block.py:19}.
- Standard library: `contextlib`, `io`, `pathlib`, `sys`, `tempfile`, `unittest` {src:tests/scripts/chart/test_mermaid_block.py:10-15}.

Used by:
- Product code: none.
- Tests (runners): the folder runner finds it through `unittest discover` with pattern `test_*.py` {src:tests/scripts/chart/run.sh:6}; see [[run]] ([run](run.md)). The system runner runs that folder runner {src:tests/system/run.sh:23}.

## Behavior

Fixture: `DOC` is a markdown string with two level-two headings, "First" and "Second", each followed by one Mermaid block; the second block holds a `subgraph` {src:tests/scripts/chart/test_mermaid_block.py:22-23}. A helper `call(args)` runs `mermaid_block.main(args)` with standard output and error captured, and returns the exit code and both texts {src:tests/scripts/chart/test_mermaid_block.py:26-30}. Each test writes `DOC` to a fresh temporary file `d.md` {src:tests/scripts/chart/test_mermaid_block.py:34-38}.

| Test | What it proves | Source line it exercises |
|---|---|---|
| `test_list` | With no block number the command exits 0 and prints "1. First", "2. Second" and the text "[has subgraph]" {src:tests/scripts/chart/test_mermaid_block.py:41-45}. | List mode prints number, heading and a subgraph flag {src:scripts/chart/mermaid_block.py:39-43} |
| `test_extract_stdout` | With block 1 and `--stdout` the output is exactly `flowchart TD\n  A --> B` and holds no fence marker {src:tests/scripts/chart/test_mermaid_block.py:48-51}. | The payload is the block text stripped, printed {src:scripts/chart/mermaid_block.py:90-93} |
| `test_range_and_missing` | Block 9 exits 1; a missing file exits 1; a file with no Mermaid block exits 1 {src:tests/scripts/chart/test_mermaid_block.py:54-58}. | Missing file {src:scripts/chart/mermaid_block.py:73-75}, no blocks {src:scripts/chart/mermaid_block.py:78-80}, range {src:scripts/chart/mermaid_block.py:86-88} |
| `test_no_clipboard_falls_back` | With the clipboard lookup replaced by one that finds nothing, block 1 exits 0, writes "Clipboard unavailable" to error output and prints the block text {src:tests/scripts/chart/test_mermaid_block.py:61-69}. | Fallback branch {src:scripts/chart/mermaid_block.py:95-98} |

How the clipboard test works: it swaps `mermaid_block.clipboard_command` for a lambda returning `None`, then restores the original in a `finally` {src:tests/scripts/chart/test_mermaid_block.py:62-66}. The swap takes effect because the copy function looks the name up in the module at call time {src:scripts/chart/mermaid_block.py:56}.

## Diagram

None: the tests have no fixture chain beyond one temporary file and one patched function.

## Notes

- Test that cannot fail for a stated reason: none found. Each assertion compares against a fixed expected value.
- Coverage gap: the real clipboard path is not tested. Every test that gives a block number either uses `--stdout` or removes the clipboard tool, so `copy_to_clipboard` never runs a real tool {src:scripts/chart/mermaid_block.py:54-63}. That is deliberate and keeps the test off the user's clipboard.
- Coverage gap that hides a code and description disagreement: `label_for` says in its docstring it returns the "Heading that precedes block `index`" {src:scripts/chart/mermaid_block.py:35}, but the code returns the nth level-two heading by position, whatever sits between {src:scripts/chart/mermaid_block.py:36}. The fixture has exactly one block under each heading {src:tests/scripts/chart/test_mermaid_block.py:22-23}, so position and "preceding" give the same answer and the test cannot show the difference. With two blocks under one heading, or a heading with none, the labels would be wrong.
- Coverage gap: `test_list` checks the words "1. First" but not the line-count text in the output {src:scripts/chart/mermaid_block.py:43}.
- The tests depend on no machine path and no Python version beyond what `mermaid_block.py` needs. The relative root uses `parents[3]` from the test file, so the file must stay four folders below the repo root {src:tests/scripts/chart/test_mermaid_block.py:17}.
- The test module mutates a module attribute for one test and restores it {src:tests/scripts/chart/test_mermaid_block.py:62-66}; if the restore did not run (it is in `finally`, so it does) tests running later in the same process would see no clipboard.
- Inputs without a check: the tests pass only paths and numbers they build themselves (temporary folder, fixed strings). No outside input reaches a path, command, address or outbound text.
- Shared-file writes: the tests write only inside a `TemporaryDirectory`, removed by cleanup {src:tests/scripts/chart/test_mermaid_block.py:35-36}. They are not atomic writes (`write_text`) and nothing is shared, so two writers cannot meet.
