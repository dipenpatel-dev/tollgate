---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/chart/test_chart_check.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/chart/chart_check, scripts/chart/chart_rules.py, scripts/chart/chart_rules.json, scripts/core/paths.py]         # source files under test, relative paths from repo root
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

This file tests the chart checker, the command that reads Mermaid diagrams in a document and reports the ones that break the chart standard. One class runs the command as a separate process and checks exit codes and messages. A second class loads the command as a module and checks the finding rules directly. Documents are made up inside the tests.

## Dependencies

Depends on:
- The command under test, [[chart_check]] ([chart_check](../../../scripts/chart/chart_check.md)), a file with no `.py` ending that is loaded by path {src:tests/scripts/chart/test_chart_check.py:21} {src:tests/scripts/chart/test_chart_check.py:45-50}.
- The rules file it reads, [[chart_rules]] ([chart_rules](../../../scripts/chart/chart_rules.md)), through the command {src:scripts/chart/chart_check:28-30}.
- The temporary-home helper [[throwaway_home]] ([throwaway_home](../../harness/throwaway_home.md)), imported from `tests/harness` {src:tests/scripts/chart/test_chart_check.py:22} {src:tests/scripts/chart/test_chart_check.py:25}.
- The path loader [[paths]] ([paths](../../../scripts/core/paths.md)), which the command calls to find a ticket folder {src:scripts/chart/chart_check:207-209}.
- Standard library: `importlib.machinery`, `importlib.util`, `os`, `pathlib`, `subprocess`, `sys`, `tempfile`, `unittest` {src:tests/scripts/chart/test_chart_check.py:10-17}.

Used by:
- Product code: none.
- Tests (runners): found by `unittest discover` in the folder runner {src:tests/scripts/chart/run.sh:6}, see [[run]] ([run](run.md)); that runner is run by the system runner {src:tests/system/run.sh:23}.

## Behavior

Shared pieces:
- `ROOT` is three folders above the test file; `CHECK` is `scripts/chart/chart_check` under it {src:tests/scripts/chart/test_chart_check.py:19-21}. The test puts the harness folder, the chart folder and `scripts` at the front of the import path {src:tests/scripts/chart/test_chart_check.py:22-24}.
- `chart(body)` wraps text in a Mermaid code fence; the fence marker is built by repeating one backtick three times, so the test file itself holds no literal fence {src:tests/scripts/chart/test_chart_check.py:27-31}.
- `GOOD_DOC` holds a flowchart and a sequence diagram {src:tests/scripts/chart/test_chart_check.py:34-37}. `BAD_DOC` holds a state diagram, a pie chart and a flowchart with a round node {src:tests/scripts/chart/test_chart_check.py:38-41}.
- `run(args, env)` starts the command with the current Python (`sys.executable`) and `-B`, with a copy of the real environment plus any overrides, and returns the finished process {src:tests/scripts/chart/test_chart_check.py:53-58}.
- `load_module()` loads the command file as a module named `chart_check_mod` {src:tests/scripts/chart/test_chart_check.py:45-50}.

Command tests (class `TestChartCheckCli`; each gets a temporary folder, removed afterwards {src:tests/scripts/chart/test_chart_check.py:62-65}):

| Test | What it proves | Code it exercises |
|---|---|---|
| `test_executable_with_shebang` | The command file has the execute permission and starts with `#!/usr/bin/env python3` {src:tests/scripts/chart/test_chart_check.py:72-74}. | The file's own first line {src:scripts/chart/chart_check:1} |
| `test_good_document_exits_zero` | `GOOD_DOC` for role `document-writer` exits 0 and prints nothing {src:tests/scripts/chart/test_chart_check.py:76-79}. | Clean run returns 0 {src:scripts/chart/chart_check:261} |
| `test_bad_document_exits_one_with_clear_message` | `BAD_DOC` exits 1; output names chart 1 at line 3 as not allowed, says "not a known chart type" for the pie chart, mentions "circle, hexagon or stadium", and ends with "Allowed here: class, flowchart, sequence." {src:tests/scripts/chart/test_chart_check.py:81-87}. | Message text {src:scripts/chart/chart_check:54-58}; the allowed list is sorted {src:scripts/chart/chart_check:179}; the three role types come from the rules file {src:scripts/chart/chart_rules.json:129-133} |
| `test_findings_never_repeat_document_text` | A state diagram whose node is a made-up word exits 1 and the word is absent from output and error text {src:tests/scripts/chart/test_chart_check.py:89-93}. | Findings carry only index, line and a fixed reason {src:scripts/chart/chart_check:178} |
| `test_er_blocked_without_ticket_flag` | An entity-relationship diagram with no ticket exits 1 {src:tests/scripts/chart/test_chart_check.py:95-98}. | `er` is not in the role's list {src:scripts/chart/chart_rules.json:129-133} |
| `test_er_allowed_when_ticket_touches_data_model` | In a throwaway home, a ticket state file under `02-tickets/TG/TG-5` with `touches_data_model: true` makes the same diagram pass (exit 0); the quoted text `"true"` does not (exit 1); `false` does not (exit 1); an unknown ticket `TG-9` does not (exit 1) {src:tests/scripts/chart/test_chart_check.py:100-117}. | Only the bare word true or false is read {src:scripts/chart/chart_check:199-201}; widening needs a real true {src:scripts/chart/chart_rules.py:87}; a missing ticket gives no state file {src:scripts/chart/chart_check:209-210} |
| `test_ticket_state_is_found_flat_and_under_a_lowercase_prefix_folder` | A ticket state file is found directly under the tickets folder (`TG-6`) and under a lower-case prefix folder (`tg/TG-7`); both exit 0 {src:tests/scripts/chart/test_chart_check.py:119-132}. | Flat first, then a prefix folder matched without regard to case {src:scripts/core/paths.py:248-261} |
| `test_ticket_folder_linked_outside_the_tickets_folder_is_not_used` | A ticket folder that is a symbolic link to a folder outside the tickets folder is ignored; exit 1 {src:tests/scripts/chart/test_chart_check.py:134-146}. | The inside-the-root check {src:scripts/core/paths.py:249} {src:scripts/core/paths.py:207-214} |
| `test_ticket_without_setup_exits_two` | With the vault setting empty and no paths file, a `--ticket` run exits 2 and error text holds "could not finish" {src:tests/scripts/chart/test_chart_check.py:148-160}. | Path loader raises, command converts it to exit 2 {src:scripts/chart/chart_check:253-254} {src:scripts/chart/chart_check:278} |
| `test_bad_ticket_key_exits_two` | The key `../x` exits 2 with "ticket key is not valid" {src:tests/scripts/chart/test_chart_check.py:162-165}. | Key pattern check {src:scripts/chart/chart_check:249-250} |
| `test_unknown_role_exits_two` | Role `no-such-role` exits 2 with "unknown role" {src:tests/scripts/chart/test_chart_check.py:167-170}. | {src:scripts/chart/chart_check:258-260} |
| `test_missing_file_exits_two` | A file that does not exist exits 2 {src:tests/scripts/chart/test_chart_check.py:172-174}. | {src:scripts/chart/chart_check:264-266} |
| `test_no_args_exits_two` | No arguments exits 2 {src:tests/scripts/chart/test_chart_check.py:176-177}. | The parser raises instead of exiting {src:scripts/chart/chart_check:221-223} |
| `test_require_chart` | Text with no chart exits 0 by default, and exits 1 with "no chart" when `--require-chart` is given {src:tests/scripts/chart/test_chart_check.py:179-184}. | {src:scripts/chart/chart_check:151-152} |
| `test_exception_line` | A state diagram with a `%% exception:` line that has a reason passes; with no reason it fails with "exception line has no reason" {src:tests/scripts/chart/test_chart_check.py:186-192}. | {src:scripts/chart/chart_check:118-123} {src:scripts/chart/chart_check:158-161} |
| `test_custom_rules_file` | A rules file whose role `r` allows nothing makes `GOOD_DOC` exit 1; a rules file holding `not json` exits 2 {src:tests/scripts/chart/test_chart_check.py:194-200}. | {src:scripts/chart/chart_check:241-243} {src:scripts/chart/chart_rules.py:38-41} |

Rule tests (class `TestChartCheckRules`): the class loads the module once, loads the default rules and the allowed set for `document-writer` {src:tests/scripts/chart/test_chart_check.py:204-208}.
- `test_extract_charts_crlf_tilde_and_quoted` proves a block is found with Windows line ends, with tilde fences and inside a quoted (`>`) block; a Python fence gives none; an unclosed fence gives none {src:tests/scripts/chart/test_chart_check.py:216-226}. Code: {src:scripts/chart/chart_check:67-89}.
- `test_title_block_and_comments_skipped_when_naming_type` proves a front matter block and a `%%` comment line are skipped before the chart type is read {src:tests/scripts/chart/test_chart_check.py:228-230}. Code: {src:scripts/chart/chart_check:92-115}.
- `test_node_cap` proves a flowchart of 14 nodes gets the too-many-nodes finding and one of 6 gets none {src:tests/scripts/chart/test_chart_check.py:232-236}. The limit is 12 {src:scripts/chart/chart_rules.json:179}.
- `test_style_line_and_host_address` proves a `style` line and a dotted number address each give a finding {src:tests/scripts/chart/test_chart_check.py:238-240}. Code: {src:scripts/chart/chart_check:170-173}.
- `test_quoted_label_does_not_trigger_shape_rule` proves double parentheses inside a quoted label are not read as a forbidden shape {src:tests/scripts/chart/test_chart_check.py:242-243}. Code: quoted text is blanked first {src:scripts/chart/chart_check:129}.
- `test_cylinder_and_diamond_allowed` proves `[(Store)]` and `{Gate}` raise no finding {src:tests/scripts/chart/test_chart_check.py:245-246}. The forbidden list holds `((`, `{{` and `([` only {src:scripts/chart/chart_rules.json:180-184}.
- `test_read_flags_only_true_word` proves `true # note` reads as True and the word `maybe` is not kept {src:tests/scripts/chart/test_chart_check.py:248-254}. Code: {src:scripts/chart/chart_check:197-201}.

## Diagram

None: the tests use a flat setup. The only chain is a throwaway home holding a ticket state file, described in the table above.

## Notes

- Tests that depend on the machine: `test_executable_with_shebang` checks the execute permission of the real file {src:tests/scripts/chart/test_chart_check.py:73}. It fails on a checkout that drops file modes. Several tests use `symlink_to` {src:tests/scripts/chart/test_chart_check.py:142}, which needs a file system that allows symbolic links.
- Environment leak: `run()` starts from the real environment {src:tests/scripts/chart/test_chart_check.py:54} and adds overrides {src:tests/scripts/chart/test_chart_check.py:55-57}. Tests that pass no `env` (most of the command tests) therefore run with the caller's real `TOLLGATE_*` variables. The ticket tests pass a clean one built by the harness {src:tests/harness/throwaway_home.py:28-45}.
- Dead code: in `test_ticket_without_setup_exits_two` the first filter that drops `TOLLGATE_KNOWLEDGE` {src:tests/scripts/chart/test_chart_check.py:150} is undone by the next line that sets it to an empty string {src:tests/scripts/chart/test_chart_check.py:151}. The effect is the empty value the test wants.
- Weak assertion: for the unknown ticket `TG-9` the test only checks exit 1 {src:tests/scripts/chart/test_chart_check.py:116-117}. That exit also happens for any disallowed diagram, and the command says nothing about the missing ticket {src:scripts/chart/chart_check:255-256}, so the test cannot tell a missing ticket from a ticket without the flag.
- Coverage gap: the command prints the file's name before the findings {src:scripts/chart/chart_check:270}. `test_findings_never_repeat_document_text` plants its word in the document body only {src:tests/scripts/chart/test_chart_check.py:90}, so it does not cover the file name. The module's own description says findings never repeat text from the document {src:scripts/chart/chart_check:6-7}; the file name is printed, which is a small disagreement.
- Coverage gap: `--state FILE`, `--help` and several files in one run are not tested {src:scripts/chart/chart_check:229-234}.
- Python version: nothing here needs more than a recent Python 3, and the command is started with `sys.executable`, so it follows the runner's Python {src:tests/scripts/chart/test_chart_check.py:58}.
- Inputs without a check: the tests pass only paths and strings they build. The one string that looks like attack input, `../x`, is there to prove the command refuses it {src:tests/scripts/chart/test_chart_check.py:163}.
- Shared-file writes: tests write only inside temporary folders (`write_text`, not atomic) {src:tests/scripts/chart/test_chart_check.py:68-70}. The throwaway home is removed on exit {src:tests/harness/throwaway_home.py:58-59}. Nothing is shared between tests, so two writers cannot meet.
