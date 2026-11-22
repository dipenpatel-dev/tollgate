---
doc_type: config
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: config         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/search/routing.yaml"    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
format: "yaml"         # yaml | toml | json | env
governs: "how search results are nudged by question type and by file trust tier"        # what component or behavior this config controls
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

The tuning file for the search router. It says which collections count more for which kind of question (intent), how a situation name or a command name picks an intent, which words in a path mark a file as verified or only observed, and what weights to use when the intent is unclear. Editing the numbers retunes search with no code change.

## Dependencies

**Depends on.**
- Nothing at run time. Collection names used as keys (`vault`, `tickets`, `references`, `code`, `standards`, `knowledge`) must match the names in `config.py` to have any effect {src:scripts/search/config.py:29-36}. Page: [[config]] and [config](config.md).
- The Python package `yaml` (PyYAML) to read it; without the package, or without the file, the loader returns an empty dict and every key behaves as absent {src:scripts/search/config.py:157-163}.

**Used by.**
- Product code: the file is located by `ROUTING_FILE` in `config.py` {src:scripts/search/config.py:25}, loaded by `load_routing` {src:scripts/search/config.py:156-165}, and read by `router.py` {src:scripts/search/router.py:222}, `intent.py` {src:scripts/search/intent.py:46} {src:scripts/search/intent.py:55} and `config.tier_words` {src:scripts/search/config.py:170}. Pages: [[router]] and [router](router.md), [[config]] and [config](config.md), [[intent]] and [intent](intent.md).
- Tests: no test file names `routing.yaml` (git grep, 2026-11-20).

## Behavior

**`intents`** gives one weight per collection for each of five intents: `teach`, `verify`, `build`, `decide`, `draft` {src:scripts/search/routing.yaml:17-22}. The router reads the weights of the resolved intent {src:scripts/search/router.py:95}. A weight is not used as a raw multiplier: it is divided by the largest positive weight in its row and mapped to a multiplier between 0.9 and 1.1 {src:scripts/search/router.py:107} {src:scripts/search/router.py:115}. In `teach`, `code: 0.2` becomes `0.9 + 0.2 * 0.2 = 0.94` {src:scripts/search/routing.yaml:18}. A weight of 0 switches the collection off for that intent {src:scripts/search/router.py:110-111}; the shipped file has no zero. A collection absent from a row gets the top weight {src:scripts/search/router.py:109}. A row that is missing or all zeros falls back to `equal_weights` {src:scripts/search/router.py:96-97}. The intent `draft` is reachable only by passing it explicitly, for example `--intent draft` {src:scripts/search/query_index.py:43} {src:scripts/search/query_index.py:61}, because no entry in `situation_map` or `skill_map` maps to it.

**`situation_map`** maps a situation name to an intent: `arch_design` to `teach`, `spec_define` and `qa_review` to `verify`, `dev_implement` to `build`, `support_triage` to `decide` {src:scripts/search/routing.yaml:24-29}. It is read when no explicit intent is given {src:scripts/search/intent.py:38-41} {src:scripts/search/intent.py:46}. A name that maps to an unknown intent is logged and ignored {src:scripts/search/intent.py:47-49}. `reference_query.py` does not pass its situation to the router, so this map does not affect it {src:scripts/search/reference_query.py:46}.

**`skill_map`** maps the last word of a command name, after the final hyphen and in lower case, to an intent {src:scripts/search/intent.py:56-58}. Entries: `spec`, `qa` to `verify`; `arch` to `teach`; `dev` to `build`; `support`, `ticket` to `decide` {src:scripts/search/routing.yaml:31-37}. The only caller is the grounding tool {src:scripts/search/ground.py:47}.

**`tiers`** sets the path words for tier 1 (verified): `rca`, `decision`, `pattern`; and tier 3 (observed): `meeting`, `conversation`, `landing`, `slack`, `chat`, `thread` {src:scripts/search/routing.yaml:39-41}. They are read by `tier_words`, which replaces the built-in list for each tier number found here {src:scripts/search/config.py:168-177}. The shipped lists are identical to the built-in defaults {src:scripts/search/config.py:98-101}, so deleting the section changes nothing and only edits matter. A word matches a whole token of a path segment, with an optional trailing `s` {src:scripts/search/config.py:217-218}. Tier 3 costs a result 0.05; tier 1 and 2 cost nothing {src:scripts/search/config.py:89}.

**`equal_weights`** is read for ambiguous questions and as the fallback above {src:scripts/search/router.py:93} {src:scripts/search/router.py:97}. For ambiguous questions only the question "is the weight above zero" is used, because the multiplier is then fixed at 1.0 {src:scripts/search/router.py:110-113}. So the values `0.34`, `0.33` and `0.2` {src:scripts/search/routing.yaml:44-49} do not change the order of results for ambiguous questions. They act only in the fallback for a named intent.

## Diagram

Skipped: the file is a flat set of lookup tables with no conditional sections.

## Notes

**Code and its own description disagree.**
- The header says the file covers "the three collections" {src:scripts/search/routing.yaml:2}. It lists six: `vault`, `tickets`, `references`, `code`, `standards`, `knowledge` {src:scripts/search/routing.yaml:18} {src:scripts/search/routing.yaml:44-49}.
- The comment says an intent "never hides a collection" {src:scripts/search/routing.yaml:6}; the next lines say a weight of 0 does {src:scripts/search/routing.yaml:7}, and the code agrees with the second statement {src:scripts/search/router.py:110-111}.
- The comment says layout folders set the tier "first, before any word" {src:scripts/search/routing.yaml:12-13}. The code does check layout folders first {src:scripts/search/config.py:227-231}, but it also treats any folder named `rca`, `rcas`, `decisions` or `patterns` as verified {src:scripts/search/config.py:105} {src:scripts/search/config.py:230}, which the comment does not list.

**Limits.**
- A syntax error in this file is not caught: `yaml.safe_load` raises and every search fails {src:scripts/search/config.py:164}.
- The file is read again on every use, with no cache {src:scripts/search/config.py:156-165}.
- Nothing checks that collection names in `intents` exist; unknown names are ignored because the router walks only the open collections {src:scripts/search/router.py:108}.

**Inputs that reach a file path, command, network address or outbound text without a check.** None: the file holds numbers, names and words. Intent names are compared with a fixed list {src:scripts/search/intent.py:23} {src:scripts/search/intent.py:47}. Tier words are only compared with path pieces {src:scripts/search/config.py:218}.

**Writes to shared files.** None: nothing in the repo writes this file; it is edited by hand (search of `routing.yaml` across `scripts/`, 2026-11-20, found only readers and comments).
