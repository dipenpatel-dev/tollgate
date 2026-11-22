---
doc_type: config
repo: ""
source_file: ""    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: YYYY-MM-DD
format: ""         # yaml | toml | json | env
governs: ""        # what component or behavior this config controls
tags: []
links: []
---

## Purpose

[One paragraph. What this config file does and what it governs. No behavior claims without {src:} tags.]

## Dependencies

[Two lists. Depends on: files or settings this config needs. Used by: the code that reads this file, found by search, with the line that reads it.
Link a repo file that has a page with both forms: [[name]] and [name](../path/name.md). No page yet: wiki link only plus "(no doc yet)".]

## Behavior

[Description of config fields and their effects. For every key: the code line that reads it and what it changes. Say so when a key is read nowhere or leaves a feature inactive by default. Factual claims carry inline citation tags immediately after the claim.

Tag reference:
  {src:path/to/file:42}          cited from the source file and line
  {src:git:abc1234}              behavior confirmed via commit
  {src:docs:name-or-url}         external reference (RFC, library doc)
  {unverified}                   source not reachable during generation

Requires citation: field effects, defaults, required vs optional, env var overrides.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram when the config has conditional sections or environment specific branches. Skip for flat key-value files. -->

## Notes

[Edge cases, known limitations, maintenance notes. Every place where the code and its own description disagree, with citations. Inputs used without a check and writes to shared files, per the doc-gen Notes rule.]
