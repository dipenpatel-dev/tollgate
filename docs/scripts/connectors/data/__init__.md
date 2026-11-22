---
doc_type: module
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: module         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/connectors/data/__init__.py"    # relative path from repo root, e.g., engine/core/assembler.py
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

This file marks the folder `scripts/connectors/data/` as a Python package, so the data connectors `databricks.py` and `secrets_tool.py` can be imported as `connectors.data.databricks` and `connectors.data.secrets_tool`. It holds no code.

## Dependencies

**Depends on.** Nothing. The file is empty: 0 bytes (checked with `wc -c`, 2026-11-20), and the read tool reported empty content.

**Used by.** Importing `connectors.data.<module>` loads this package first. Product code: none; searched 2026-11-20 with `git grep` for `connectors.data` and `connectors/data` across the repo except `docs/`, and no product file imports from the package. The two modules in it are run as scripts.
Tests: `tests/scripts/connectors/data/test_databricks.py` (`from connectors.data import databricks as dbx`) and `tests/scripts/connectors/data/test_secrets_tool.py` (`from connectors.data import secrets_tool as st`). The test runner lists `connectors/data` as a test area in `tests/system/run.sh` line 22.

## Behavior

No behavior. There is no line of code to cite: the file has no lines. It sets no `__all__`, defines no name and imports nothing, so importing the package has no side effect.

## Diagram: module level (L2, required)

```mermaid
flowchart TD
  Pkg["Empty package marker"] --> Dbx["Databricks connector"]
  Pkg --> Sec["Secrets tool"]
```

## Diagram: function level (L3, optional)

None: no function has branching that the signature does not show.

## Notes

- The sibling `scripts/connectors/__init__.py` and `scripts/connectors/comms/__init__.py` are also 0 bytes (checked with `wc -c`, 2026-11-20).
- The two scripts in this folder add the parent `scripts/` folder to `sys.path` themselves and import `connectors.registry` that way {src:scripts/connectors/data/secrets_tool.py:30-31}{src:scripts/connectors/data/databricks.py:32-33}, so they run directly with `python3 path/to/file.py`.
- No input reaches a file path, command, network address or outbound text, and nothing is written.
