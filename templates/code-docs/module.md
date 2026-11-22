---
doc_type: module
repo: ""
source_file: ""    # relative path from repo root, e.g., engine/core/assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: YYYY-MM-DD
language: ""       # e.g., python
imports: []        # modules this file imports, as written in the import statement
exports: []        # public functions and classes; constants per the doc-gen exports rule
tags: []
links: []
---

## Purpose

[One paragraph. What this module does and why it exists. No behavior claims without {src:} tags.]

## Dependencies

[Two lists. Depends on: what this module imports, reads or needs at run time. Used by: what calls, imports or binds it, found by search.
Link a repo file that has a page with both forms: [[module-name]] and [module-name](../path/module-name.md). No page yet: wiki link only plus "(no doc yet)". Standard library and outside packages: plain name, no link.]

## Behavior

[Functional description of the module public interface. Factual claims carry inline citation tags immediately after the claim.

Tag reference:
  {src:path/to/file:42}          cited from the source file and line
  {src:git:abc1234}              behavior confirmed via commit
  {src:docs:name-or-url}         external reference (RFC, library doc)
  {unverified}                   source not reachable during generation

Requires citation: behavior assertions, data flow, dependency calls, error conditions, return values.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

```mermaid
flowchart TD
  %% Max 10 nodes. Code names go in the node alias; visible labels are plain English, 4 words at most.
```

## Notes

[Edge cases, known limitations, maintenance notes. Every place where the code and its own description disagree, with citations. Inputs used without a check and writes to shared files, per the doc-gen Notes rule.]
