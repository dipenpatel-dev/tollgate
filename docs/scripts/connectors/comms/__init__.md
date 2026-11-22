---
doc_type: module
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: module         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/connectors/comms/__init__.py"    # relative path from repo root, e.g., engine/core/assembler.py
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

An empty package marker. It makes the `scripts/connectors/comms/` folder a regular Python package so the chat, tracker, notes, calendar and git connectors can share one helper through `from connectors.comms import comms_common`.

## Dependencies

**Depends on.** Nothing. The file has 0 bytes and 0 lines (checked with `wc -c` and `wc -l`, 2026-11-20).

**Used by.**
- Product code: the comms connectors import the package to reach the shared helper, for example `scripts/connectors/comms/calendar_connector.py` {src:scripts/connectors/comms/calendar_connector.py:36}, `scripts/connectors/comms/commits_connector.py` {src:scripts/connectors/comms/commits_connector.py:33}, `scripts/connectors/comms/jira_connector.py` {src:scripts/connectors/comms/jira_connector.py:27}, `scripts/connectors/comms/notion_connector.py` {src:scripts/connectors/comms/notion_connector.py:30} and `scripts/connectors/comms/slack_connector.py` {src:scripts/connectors/comms/slack_connector.py:38}. Found with `git grep` for `connectors.comms` (2026-11-20).
- Tests: `tests/scripts/connectors/comms/test_calendar.py` {src:tests/scripts/connectors/comms/test_calendar.py:16} and the other `test_*.py` files in that folder.

## Behavior

None. The file holds no code, so nothing runs when it is imported. Its only effect is that the folder is a regular package. A folder without this file also imports, as a namespace package {src:docs:https://docs.python.org/3/reference/import.html#namespace-packages}, so the marker is a convention rather than a requirement.

## Diagram: module level (L2, required)

```mermaid
flowchart TD
  Pkg["Comms package"] --> Common["Shared helper"]
  Pkg --> Cal["Calendar connector"]
  Pkg --> Git["Commits connector"]
  Pkg --> Chat["Chat and tracker connectors"]
```

## Diagram: function level (L3, optional)

None: no function has branching that the signature does not show.

## Notes

- Code and description: no description exists to compare, since the file is empty.
- Inputs that reach a path, command or address: none, no code.
- Shared file writes: none, no code.
