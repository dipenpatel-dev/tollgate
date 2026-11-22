---
doc_type: module
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: module         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/core/memory/__init__.py"    # relative path from repo root, e.g., engine/core/assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
language: "python"       # e.g., python
imports: []        # modules this file imports, as written in the import statement
exports: []        # public functions and classes; constants per the doc-gen exports rule
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

This is the package marker for `scripts/core/memory/`. It makes the folder importable as `core.memory` so the enum constants module beside it can be reached with an ordinary import.

## Dependencies

**Depends on.** Nothing. The file is empty: `wc -l` reports 0 lines and `ls -l` reports 0 bytes (checked 2026-11-20).

**Used by.** No product code imports `core.memory` (searched the repo for `core.memory`, `core/memory` and `_enums`, excluding `docs/`, 2026-11-20). One test imports a module from the package, which goes through this folder {src:tests/scripts/core/test_bootstrap.py:208}. The package holds one other file, [[_enums]] / [_enums](_enums.md).

## Behavior

The file contains no code, so nothing runs when the package is imported. There are no lines to cite; the claim rests on the file size of 0 bytes. It defines no names, so `from core.memory import X` for any name other than the `_enums` submodule fails.

## Diagram: module level (L2, required)

```mermaid
flowchart TD
  Marker["Empty package marker"] --> Enums["Enum constants"]
  Enums --> Test["Bootstrap test"]
```

## Diagram: function level (L3, optional)

None: no function has branching that the signature does not show.

## Notes

- The sibling `scripts/core/__init__.py` is also empty (0 bytes, checked 2026-11-20), so the `core` package carries no setup code either.
- No input reaches a file path, shell command, network address or outbound text, because the file has no code.
- The file writes nothing, so there is no shared-file write.
- No description in the file disagrees with the code, because the file has no text.
- The empty file is the only link in the chain between the test and the constants. The test would still pass if the file were deleted, because Python 3 can import a folder without an init file as a namespace package (not tested here). Do not rely on this page for whether removal is safe.
