---
doc_type: config
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: config         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: ".github/dependabot.yml"    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
format: "yaml"         # yaml | toml | json | env
governs: "which parts of the repo GitHub Dependabot checks for newer versions, and how often"        # what component or behavior this config controls
tags: [ci, dependabot, dependencies]
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
---

## Purpose

The settings for GitHub Dependabot, the service that opens pull requests when a newer version of a dependency exists. It watches two things: the GitHub Actions the CI workflow uses, and the Python libraries listed under `scripts/`. It exists so the commit pins in the workflow and the version bounds in the requirements files are bumped by a reviewable pull request, not by hand. {src:.github/dependabot.yml:1}

## Dependencies

**Depends on.** GitHub's Dependabot service, which reads the file. The folders it points at: the repo root for Actions, which GitHub resolves to the workflow files {src:.github/dependabot.yml:3} {src:.github/dependabot.yml:4}, and `scripts/` for the pip files {src:.github/dependabot.yml:7} {src:.github/dependabot.yml:8}. See [tests](workflows/tests.md) for the workflow it updates and [prerequisites](../prerequisites.md) for the requirements files.

**Used by.** No file in the repo reads it. Only Dependabot does. The workflow names it in a comment beside the pinned checkout step {src:.github/workflows/tests.yml:20}, and `scripts/requirements.txt` has a comment on its bounds {src:scripts/requirements.txt:3}. Searched `git grep dependabot` over the repo except `docs/` (2026-11-21).

## Behavior

Keys, each read by Dependabot and by nothing in this repo:

| Key | Value | Effect |
|---|---|---|
| `version` | `2` | The file format version Dependabot expects {src:.github/dependabot.yml:1} |
| `updates[0].package-ecosystem` | `github-actions` | Check the `uses:` lines of the workflows {src:.github/dependabot.yml:3} |
| `updates[0].directory` | `/` | Where to look: the repo root {src:.github/dependabot.yml:4} |
| `updates[0].schedule.interval` | `weekly` | Check once a week {src:.github/dependabot.yml:6} |
| `updates[1].package-ecosystem` | `pip` | Check Python requirements files {src:.github/dependabot.yml:7} |
| `updates[1].directory` | `/scripts` | Where to look: the `scripts/` folder, which holds `requirements.txt`, `requirements-epub.txt` and `requirements-extras.txt` {src:.github/dependabot.yml:8} |
| `updates[1].schedule.interval` | `weekly` | Check once a week {src:.github/dependabot.yml:10} |

No other key is set (read the whole file, 2026-11-21): no `open-pull-requests-limit`, `cooldown`, `labels`, `reviewers`, `ignore` or `groups`, so Dependabot's own defaults apply to all of them.

## Diagram

Skipped. The file is a flat list of two entries with no conditional sections.

## Notes

The `npx` package pins in `install.sh` are not covered: Dependabot has no entry for them, and they sit in shell variables, not in a package file {src:install.sh:1468} {src:install.sh:1469} {src:install.sh:1470}. The installer comment tells the maintainer to bump them by hand, with a release at least 14 days old {src:install.sh:1466}. This file sets no `cooldown`, so a pull request for a Python library or an Action can name a release published the same day `[uncertain: depends on Dependabot defaults, which this repo cannot show]`.

Whether Dependabot reads all three `requirements*.txt` files in `scripts/`, or only `requirements.txt`, is not stated in this repo `[uncertain]`. Check the first pull requests it opens.

Inputs reaching a path, command, network address or outbound text: none are read by code in this repo; the two `directory` values are read by GitHub only. Shared file writes: none, the file is only read.
