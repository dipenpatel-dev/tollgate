---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: scripts/core/hooks/precompact_hook.sh    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "cat heredoc (line 10)"    # function or line that executes when the script runs
requires: [bash, cat]       # external commands or tools this script depends on
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

A helper meant to be called by a PreCompact hook entry. When run, it prints a fixed reminder to save the session state before the context window is compressed, then exits. It reads nothing and writes no file.

## Dependencies

**Depends on.**
- `bash` (shebang) {src:scripts/core/hooks/precompact_hook.sh:1} and `cat`, used to print the text. {src:scripts/core/hooks/precompact_hook.sh:10}
- The reminder names the `/save` command. It does not call it. {src:scripts/core/hooks/precompact_hook.sh:14}
- No environment variable, no repo file and no other page.

**Used by.** No product code calls this script. A repo search for `precompact_hook` outside `docs/` (git grep, 2026-11-20) finds only the script itself and the test. `settings.json` wires a different file for PreCompact, `hooks/pre-compact-checkpoint-warn.sh`. {src:settings.json:252} The repo's own overview page says the same. {src:docs/scripts/core.md:63}
- Tests: `tests/scripts/core/test_bootstrap.py` runs it. {src:tests/scripts/core/test_bootstrap.py:136}

## Behavior

1. Prints a block starting with `<precompact_warning>` and ending with `</precompact_warning>` to standard output. {src:scripts/core/hooks/precompact_hook.sh:10-22}
2. The block says compression is imminent, tells the reader to run `/save` first, and if that is not possible to write a short summary of what was decided, what was done and what is pending. {src:scripts/core/hooks/precompact_hook.sh:12-18}
3. Exits with status 0 on the next line, always. {src:scripts/core/hooks/precompact_hook.sh:24}

The script has no `set -e` and no branch, so nothing in it can produce another exit status except `cat` failing to write, which the script ignores because the `exit 0` follows. {src:scripts/core/hooks/precompact_hook.sh:24}

Test: `test_precompact_prints_warning` runs the script with a copy of the real environment and asserts exit 0 and that the output contains `<precompact_warning>`. {src:tests/scripts/core/test_bootstrap.py:135-138} It checks only that tag, not the reminder text, so a change to the message body would not fail it. It does not depend on a machine path or Python version (it runs `bash` on the repo path built from the test file's own location). {src:tests/scripts/core/test_bootstrap.py:18}

## Diagram

None: the script is straight-line (print, exit), so no diagram is needed.

## Notes

- **Header versus code.** The header says it "prints a reminder to checkpoint". {src:scripts/core/hooks/precompact_hook.sh:5} It does print one. The header also says it is not wired into `settings.json` by this package. {src:scripts/core/hooks/precompact_hook.sh:6} That holds: `settings.json` names a different script. {src:settings.json:252} The `Date:` header field is empty. {src:scripts/core/hooks/precompact_hook.sh:4}
- **Duplicate of the wired hook.** `hooks/pre-compact-checkpoint-warn.sh` prints almost the same text; the differences are "to vault" against "to the vault", "If /save is not possible, write" against "If /save is not possible: write", and "After /save or summary" against "After /save or the summary". {src:hooks/pre-compact-checkpoint-warn.sh:14} {src:hooks/pre-compact-checkpoint-warn.sh:15} {src:hooks/pre-compact-checkpoint-warn.sh:20} {src:scripts/core/hooks/precompact_hook.sh:14} {src:scripts/core/hooks/precompact_hook.sh:15} {src:scripts/core/hooks/precompact_hook.sh:20} The wired copy says its output goes only to the debug log and never to Claude's context or the terminal. {src:hooks/pre-compact-checkpoint-warn.sh:5} This page did not test that claim; if it holds, wiring this helper would show the reminder to nobody. `[uncertain]`
- **Unchecked inputs.** None: the script takes no argument, reads no environment variable and builds no path, command or address from outside data. {src:scripts/core/hooks/precompact_hook.sh:10-24}
- **Shared-file writes.** None: it writes only to standard output.
