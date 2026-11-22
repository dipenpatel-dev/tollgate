---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "hooks/pre-compact-checkpoint-warn.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "cat heredoc block (line 10)"    # function or line that executes when the script runs
requires: [cat]       # external commands or tools this script depends on
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

This is a Claude Code PreCompact hook. Claude Code runs it just before it compresses the conversation to free up space. It prints a short reminder to save the session first, either with the `/save` command or by writing a short summary of what was decided, what was done and what is still open. It exists so work is not lost when older conversation is dropped.

## Dependencies

**Depends on.**
- `cat` only {src:hooks/pre-compact-checkpoint-warn.sh:10}. It reads no stdin, no files and no environment variables.
- The `/save` command named in the message {src:hooks/pre-compact-checkpoint-warn.sh:14}. No `/save` command file exists in this repo (searched outside `docs/` for the text `/save`, 2026-11-20; only this hook and `scripts/core/hooks/precompact_hook.sh` contain it).

**Used by.**
- Product code: `settings.json` runs it under PreCompact with no matcher and no `onFailure` {src:settings.json:247-255}.
- Near copy, not a caller: `scripts/core/hooks/precompact_hook.sh` prints almost the same block and says it is not wired into `settings.json` {src:scripts/core/hooks/precompact_hook.sh:6} {src:scripts/core/hooks/precompact_hook.sh:10-22}.
- Tests: `tests/hooks/run.sh` {src:tests/hooks/run.sh:179-183} with the fixture `tests/hooks/fixtures/pre-compact-checkpoint-warn/tc-01-any-input.json`. The copy under `scripts/core/hooks/` is tested separately {src:tests/scripts/core/test_bootstrap.py:136}.

## Behavior

1. The script prints a block of text wrapped in `<precompact_warning>` tags to stdout {src:hooks/pre-compact-checkpoint-warn.sh:10-22}. The heredoc delimiter is quoted, so nothing in the text is expanded {src:hooks/pre-compact-checkpoint-warn.sh:10}.
2. The text says compression is imminent, asks to run `/save` or to write a summary of decisions, work done and pending items, then to proceed {src:hooks/pre-compact-checkpoint-warn.sh:11-21}.
3. It exits 0 on every path {src:hooks/pre-compact-checkpoint-warn.sh:24}. There is no `set` line, no input handling and no branch, so the output never varies.

## Diagram

Skipped: the script is straight-line (one print, one exit), so a diagram adds nothing.

## Notes

**Code and description disagree, or cannot be checked.**
- The header says stdout goes to the debug log only, not to Claude's context or the user's terminal {src:hooks/pre-compact-checkpoint-warn.sh:5}, and that a PreCompact hook cannot inject into Claude's context {src:hooks/pre-compact-checkpoint-warn.sh:6}. Both are statements about Claude Code behavior, cited there to a closed feature request. I could not check them from this repo {unverified}.
- The message text speaks to Claude, telling it to run `/save` {src:hooks/pre-compact-checkpoint-warn.sh:14}. If the header is right that nobody reads the output, the reminder has no reader. The code does not settle this. The test only checks that the tag appears in the output and the exit code is 0 {src:tests/hooks/run.sh:182-183}.
- The header says the hook writes to the debug log {src:hooks/pre-compact-checkpoint-warn.sh:4}. The code writes only to stdout {src:hooks/pre-compact-checkpoint-warn.sh:10-22}; any log file is the harness's doing.
- The header says "exit 0 always" {src:hooks/pre-compact-checkpoint-warn.sh:5}, which matches the code {src:hooks/pre-compact-checkpoint-warn.sh:24}.

**Maintenance.** Two copies of nearly the same message exist, one under `hooks/` and one under `scripts/core/hooks/` {src:scripts/core/hooks/precompact_hook.sh:10-22}. They differ in a few words (for example "to the vault"), so an edit to one will not reach the other.

**Inputs that reach a path, command, address or outbound text.** None. The script reads nothing from its input and prints fixed text.

**Writes to shared files.** None.
