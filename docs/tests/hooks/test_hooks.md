---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "tollgate"
source_file: "tests/hooks/test_hooks.py"
status: ACTIVE
last_updated: 2026-11-19
scores: []
covers: ["hooks/phi_patterns.py", "hooks/pre-tool-bash-scan-phi.py", "hooks/pre-tool-write-scan-phi.py", "hooks/post-tool-result-scan-phi.py", "hooks/post-tool-bash-scan-secrets.py", "hooks/pre-tool-write-guard-path.sh", "hooks/pre-tool-bash-databricks-ask.py", "installer/merge_settings.py"]
tags: [hooks, schema, detection, settings-merge]
links: []
---

## Purpose

Base unit tests for the hooks: the shape of hook output, failure behavior, PHI detection in tool results, the Databricks approval summary, and the settings merge used by the installer. {src:tests/hooks/test_hooks.py:5} Hook output is checked against the schema Claude Code enforces, where `hookEventName` is required. {src:tests/hooks/test_hooks.py:71} PHI shaped values are assembled at run time so none are literals in the file. {src:tests/hooks/test_hooks.py:36}

## Dependencies

Imports `extract_response_texts`, `scan_for_phi` and `scan_structured` from `hooks/phi_patterns.py`, and `merge_settings` from `installer/`. {src:tests/hooks/test_hooks.py:33-34} Runs hook scripts as processes through `run_hook`. {src:tests/hooks/test_hooks.py:55} Payload shapes for Bash and Read results were captured from a live session. {src:tests/hooks/test_hooks.py:43} Uses `unittest` only. Code under test: [phi_patterns](../../hooks/phi_patterns.md), [pre-tool-bash-scan-phi](../../hooks/pre-tool-bash-scan-phi.md), [pre-tool-write-guard-path](../../hooks/pre-tool-write-guard-path.md), [merge_settings](../../installer/merge_settings.md).

Run: `python3 -m unittest discover -s tests/hooks -p 'test_*.py'` {src:tests/hooks/test_hooks.py:15}

## Behavior

Six test classes, 26 test methods (counted with `grep -c "    def test_"` on 2026-11-19).

- `HookOutputSchema`: when a hook fires, its output has the right event name, and a valid decision (allow, deny, ask or defer) plus a reason for a before-tool hook, or a context string for an after-tool hook. {src:tests/hooks/test_hooks.py:39} {src:tests/hooks/test_hooks.py:73-76}
  - PHI in Bash output and in a nested Read result, and a secret on stderr, each produce valid after-tool output. {src:tests/hooks/test_hooks.py:80-82} {src:tests/hooks/test_hooks.py:85-86} {src:tests/hooks/test_hooks.py:90-91}
  - PHI in a Write, in a notebook edit and in a Bash command gives `deny`. {src:tests/hooks/test_hooks.py:94-95} {src:tests/hooks/test_hooks.py:98-99} {src:tests/hooks/test_hooks.py:108-109}
  - A Write into the code directory gives `deny`. {src:tests/hooks/test_hooks.py:103-105}
  - The Databricks gate denies the first attempt with a code, asks when the same command comes back with that code, and denies again when the command changed. {src:tests/hooks/test_hooks.py:115} {src:tests/hooks/test_hooks.py:119} {src:tests/hooks/test_hooks.py:122}
- `FailureModes`: the Write hook denies garbage input, stays silent on a null tool input, and clean results print nothing from the result hook or the secrets hook. {src:tests/hooks/test_hooks.py:127-128} {src:tests/hooks/test_hooks.py:131-132} {src:tests/hooks/test_hooks.py:136-137}
- `BashPhiHook`: the Bash scan hook denies on bad JSON with an internal error reason and on a missing pattern module. {src:tests/hooks/test_hooks.py:150-155} {src:tests/hooks/test_hooks.py:163-164} It denies PHI in the command and passes a clean command. {src:tests/hooks/test_hooks.py:167-168} {src:tests/hooks/test_hooks.py:171-172}
  - The last case, `test_known_limit_script_writing_phi_is_not_caught`, runs `python3 gen.py --out out.csv` and expects no decision. {src:tests/hooks/test_hooks.py:178-179} Its docstring says only command text is scanned. {src:tests/hooks/test_hooks.py:175} That is outdated: the Bash hook has a script file scan, covered by `ScriptFileScan`. {src:tests/hooks/test_phi_hook_levels.py:207} The known-limit test still passes only because the script `gen.py` does not exist when it runs, and the newer test for the same command says so by name. {src:tests/hooks/test_phi_hook_levels.py:305-306}
- `Detection`: PHI columns are flagged only when paired with data. {src:tests/hooks/test_hooks.py:182}
  - Flagged shapes: a CSV, a pipe table, JSON rows, a statement API result with rows, key equals value text, a prefixed label, and an ISO birth date. {src:tests/hooks/test_hooks.py:188-195}
  - Quiet shapes: catalog metadata as JSON or text, a describe listing, a statement result with no rows, a null value, and a log line that mentions a column. {src:tests/hooks/test_hooks.py:206-212}
- `ApprovalSummary`: the Databricks gate reason includes the table, a production catalog note, the filter, a missing limit note, and which PHI column is requested. {src:tests/hooks/test_hooks.py:228-229}
  - A query it cannot parse says so, and a delete says it modifies data. {src:tests/hooks/test_hooks.py:232-233}
  - Chained commands and quoted semicolons still produce a summary. {src:tests/hooks/test_hooks.py:236}
  - Metadata commands and an `echo` that only names the tool pass with no output. {src:tests/hooks/test_hooks.py:239-241}
- `SettingsMerge`: the merge keeps user settings and hooks, replaces hooks the installer owns, unions permissions, adds env values, and gives the same result when run twice. {src:tests/hooks/test_hooks.py:253-257}
  - The command line entry drops an old `TOLLGATE_SKILL_PREFIX` value from the user's env, keeps other env values and user hooks, and adds exactly one expansion hook, even when run twice. {src:tests/hooks/test_hooks.py:267-268} {src:tests/hooks/test_hooks.py:271-272} {src:tests/hooks/test_hooks.py:274} {src:tests/hooks/test_hooks.py:276-277}
  - A leftover skill prefix argument is refused with exit code 2 and no settings file is written. {src:tests/hooks/test_hooks.py:283-284}
  - Placeholder substitution stays JSON safe for paths with backslashes and quotes. {src:tests/hooks/test_hooks.py:287-288}

A schema failure means Claude Code would reject or ignore the hook output. A detection failure means PHI columns slip through or metadata starts raising false alarms. A merge failure means the installer could overwrite user settings.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The Bash scan hook is covered in more depth in [test_phi_hook_levels](test_phi_hook_levels.md) and [test_phi_safety_speed](test_phi_safety_speed.md). The known limit test says to update `docs/hooks.md` if it starts failing. {src:tests/hooks/test_hooks.py:177} The file header says the schema was verified on Claude Code 2.1.220. {src:tests/hooks/test_hooks.py:11} The skill prefix is gone: the merge tests no longer pass a prefix argument. {src:tests/hooks/test_hooks.py:8-9}
