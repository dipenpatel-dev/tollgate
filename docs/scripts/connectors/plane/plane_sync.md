---
doc_type: module
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: module         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/connectors/plane/plane_sync.py"    # relative path from repo root, e.g., engine/core/assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
language: "python"       # e.g., python
imports: [pathlib, sys, connectors.plane.cli]        # modules this file imports, as written in the import statement
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

The script you run by file path to use the plane connector: `python3 plane_sync.py sync|drift|create ...`. Unlike the package entry file, it finds the `scripts` folder on its own, so it works from any folder. It is a thin wrapper around the connector's `main` function.

## Dependencies

**Depends on.**
- Standard library: `pathlib`, `sys` {src:scripts/connectors/plane/plane_sync.py:11-12}.
- [[cli]] ([cli](cli.md)): `main` {src:scripts/connectors/plane/plane_sync.py:16}.
- Its own location on disk: the folder two levels above this file must be the `scripts` folder {src:scripts/connectors/plane/plane_sync.py:14}.

**Used by.**
- Product code: none found. Nothing under the repo outside the plane package and its tests names `plane_sync.py` (searched `git grep` for `plane_sync.py` and `connectors/plane` under the repo except `docs/`, 2026-11-20). People run it by hand.
- Tests: `tests/scripts/connectors/plane/test_plane_connector.py:95` and `tests/system/test_e2e.py:181` run it as a program. `tests/scripts/connectors/plane/test_plane_standards.py:31` lists it among files that must exist and `:21` exempts it from the type hint check.

## Behavior

On start it puts the `scripts` folder first on the module search path, found as the second parent of this file's resolved location {src:scripts/connectors/plane/plane_sync.py:14}. It then imports `main` {src:scripts/connectors/plane/plane_sync.py:16}. When run as the main program, it calls `main` with the command line minus the program name and exits with the returned number {src:scripts/connectors/plane/plane_sync.py:18-19}. Because the path edit runs on import as well, importing this file also changes the module path {src:scripts/connectors/plane/plane_sync.py:14}. The behavior of the commands is described in [[cli]] ([cli](cli.md)).

## Diagram: module level (L2, required)

```mermaid
flowchart TD
  Person["Person or test"] --> Script["Wrapper script"]
  Script --> Path["Add scripts folder"]
  Path --> Main["Connector command line"]
  Main --> Code["Exit code"]
```

## Diagram: function level (L3, optional)

None: no function has branching that the signature does not show. The file has no function.

## Notes

**Code and its own description.** The description says "python3 plane_sync.py sync|drift|create ..." {src:scripts/connectors/plane/plane_sync.py:3}. The parser accepts exactly those three commands {src:scripts/connectors/plane/cli.py:80-93}. The header's date field is empty {src:scripts/connectors/plane/plane_sync.py:4}. The scope line says it "finds the scripts folder by itself" {src:scripts/connectors/plane/plane_sync.py:6}. That holds only while the file stays exactly two folders below `scripts`.

**Inputs reaching a path, command, address or outbound text without a check.**
- The folder added to the module search path comes from this file's own location, not from user input {src:scripts/connectors/plane/plane_sync.py:14}. The entry goes first in the search order, so a `connectors` package in that folder takes priority over any other.
- `sys.argv[1:]` goes whole to `main` {src:scripts/connectors/plane/plane_sync.py:19}; this file checks nothing.

**Shared file writes.** None.

**Style.** The import after the path edit carries a `noqa: E402` mark to quiet the linter {src:scripts/connectors/plane/plane_sync.py:16}.
