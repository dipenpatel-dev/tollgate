---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/test_gate_hook.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["hooks/pre-prompt-expansion-check-gates.py", "hooks/gate_rules.py", "scripts/core/paths.py"]         # source files under test, relative paths from repo root
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

This file tests the gate hook that stops the `tg-arch`, `tg-dev` and `tg-qa` chain skills when the earlier ticket files are not in the right state. It runs the real hook file as a child process against throwaway ticket folders in a temp directory, with a fake ticket id `T-001` and no real data {src:tests/hooks/test_gate_hook.py:1-5} {src:tests/hooks/test_gate_hook.py:38-39}. It has 59 tests in 12 classes, covering allow, block, warn, override and fail closed behavior. It was not run while this page was written, so no claim here says a test passes; each claim says what the test asserts.

## Dependencies

**Depends on.**
- The hook under test, `hooks/pre-prompt-expansion-check-gates.py`: [[pre-prompt-expansion-check-gates]] and [pre-prompt-expansion-check-gates](../../hooks/pre-prompt-expansion-check-gates.md). The test starts it as an executable file {src:tests/hooks/test_gate_hook.py:32} {src:tests/hooks/test_gate_hook.py:100}.
- The rule functions `hooks/gate_rules.py`: [[gate_rules]] and [gate_rules](../../hooks/gate_rules.md). One test replaces `check_arch` in them with a function that raises {src:tests/hooks/test_gate_hook.py:103-118}.
- The state file writer in `hooks/state_file_io.py`: [[state_file_io]] and [state_file_io](../../hooks/state_file_io.md). Only `write_state_atomic` is imported, to rewrite a state file while the hook reads it {src:tests/hooks/test_gate_hook.py:36} {src:tests/hooks/test_gate_hook.py:580}.
- The path loader `scripts/core/paths.py`: [[paths]] (no doc yet). The hook finds it through `TOLLGATE_HOME`, which the test points at the repo root {src:tests/hooks/test_gate_hook.py:84-88} {src:hooks/pre-prompt-expansion-check-gates.py:148-164}.
- The recorded payload `tests/hooks/fixtures/pre-prompt-expansion-check-gates/tc-01-typed-arch.json` {src:tests/hooks/test_gate_hook.py:31} {src:tests/hooks/test_gate_hook.py:612}.
- Standard library only: `datetime`, `json`, `os`, `subprocess`, `sys`, `tempfile`, `threading`, `unittest`, `typing`.
- Environment set by the test for every case: `TOLLGATE_KNOWLEDGE` (the temp vault), `TOLLGATE_HOME` and `TOLLGATE_GATE_LOG` {src:tests/hooks/test_gate_hook.py:84-88}. The child process also receives the rest of the developer's environment {src:tests/hooks/test_gate_hook.py:97-99}.

**Used by.** Product code: none; nothing in the product imports a test file. Tests: this file is picked up by the unit test step of the hook runner, `python3 -m unittest discover -s tests/hooks -p 'test_*.py'` {src:tests/hooks/run.sh:198}, and by the same command in the CI workflow {src:.github/workflows/tests.yml:35}. Searched 2026-11-20: the whole worktree except `.git`, `docs/`, caches and virtual environments for `test_gate_hook`; the only hits were the two lines above through the discovery pattern, and no file names it directly.

## Behavior

**Setup.** Every case gets a fresh temp folder with a vault, a flat ticket folder `02-tickets/T-001` and a log file path {src:tests/hooks/test_gate_hook.py:77-88}. The helper `put` writes `T-001-<suffix>.md` files {src:tests/hooks/test_gate_hook.py:90-94}. `run_hook` runs the hook with the payload on stdin and a 30 second limit {src:tests/hooks/test_gate_hook.py:96-101} {src:tests/hooks/test_gate_hook.py:45}. A block is exit 0 with a JSON `decision` of `block`; an allow is exit 0 with empty output; a warning is exit 0 with a JSON `systemMessage` that says "Gate not checked" and no `decision` {src:tests/hooks/test_gate_hook.py:120-137}. The hook prints those shapes in its `main` function {src:hooks/pre-prompt-expansion-check-gates.py:445-456}.

**Arch, dev and qa rules (9 tests).** These prove the per skill rules reach the user through the hook.
- `test_10`: a spec with an approved status line plus a state file `SPEC_APPROVED` lets `tg-arch` through {src:tests/hooks/test_gate_hook.py:153-156} {src:hooks/gate_rules.py:187-194}.
- `test_11`: no spec file blocks, and the message names the spec path and the line `/tg-spec T-001` {src:tests/hooks/test_gate_hook.py:158-162}. The hook adds the file path when the reason says `spec.md` and ends with the "run first" line {src:hooks/pre-prompt-expansion-check-gates.py:288-292} {src:hooks/pre-prompt-expansion-check-gates.py:299}.
- `test_12`: a state value `ROUTED` blocks; the message lists `SPEC_APPROVED` and never the value found {src:tests/hooks/test_gate_hook.py:164-169} {src:hooks/gate_rules.py:175-177}.
- `test_13`: a design whose status is `DESIGN_COMPLETE` blocks `tg-dev` even with state `DESIGN_APPROVED`; replacing it with an approved design allows {src:tests/hooks/test_gate_hook.py:173-178}. `test_13b`: state `DESIGN_COMPLETE` blocks even with an approved design {src:tests/hooks/test_gate_hook.py:180-183}. The allowed states are `DESIGN_APPROVED` and `IN_DEV` {src:hooks/gate_rules.py:39}. `test_14`: `IN_DEV` allows {src:tests/hooks/test_gate_hook.py:185-188}.
- `test_15`: a full chain with state `DEV_COMPLETE` lets `tg-qa` through {src:tests/hooks/test_gate_hook.py:192-194} {src:tests/hooks/test_gate_hook.py:145-149}. `test_16`: a validation file with no status line blocks and the message names `edge-case-validation.md` {src:tests/hooks/test_gate_hook.py:196-200}. `test_17`: state `IN_DEV` blocks; the message names `DEV_COMPLETE` and never `IN_DEV` {src:tests/hooks/test_gate_hook.py:202-206}.

**Allow paths and ticket choice (14 tests).** These prove the gate leaves other commands alone and picks the right ticket.
- `test_18`: `tg-ticket`, `tg-support`, `tg-spec`, `other-skill` and `close` print nothing and write no log line {src:tests/hooks/test_gate_hook.py:210-213}. The hook gates only the three names {src:hooks/pre-prompt-expansion-check-gates.py:71} {src:hooks/pre-prompt-expansion-check-gates.py:340-342}. The `skill` argument of `payload` is ignored here because `name` overrides it {src:tests/hooks/test_gate_hook.py:64-66}.
- `test_19`: arguments with no ticket id allow silently and log `no ticket id` {src:tests/hooks/test_gate_hook.py:215-217} {src:hooks/pre-prompt-expansion-check-gates.py:345-347}.
- `test_19b`: with `TOLLGATE_KNOWLEDGE` removed, a named ticket is allowed with a visible warning, and the log holds an `allow` line {src:tests/hooks/test_gate_hook.py:219-222} {src:hooks/pre-prompt-expansion-check-gates.py:347-350}. The test name says "allowed and logged", but it asserts a warning, so the allow is not silent.
- `test_19c`: ticket `T-777` has no folder; `arch`, `dev` and `qa` each warn and the warning names `T-777` and `02-tickets` {src:tests/hooks/test_gate_hook.py:224-226} {src:hooks/pre-prompt-expansion-check-gates.py:357-363}. The `02-tickets` text comes from the path loader layout table, so the test depends on that name {src:scripts/core/paths.py:35}.
- `test_19d`: the name promises "no warning when there is no ticket id or folder found". The body checks only that a missing id is silent, then writes a `ROUTED` state and expects a block {src:tests/hooks/test_gate_hook.py:228-231}. A missing folder is not tested for silence here; `test_19c` asserts the opposite for it.
- `test_20`: the tokens `../secret`, `T-001/../../x` and `a/b` are not ticket ids, so each is allowed and `no ticket id` is logged {src:tests/hooks/test_gate_hook.py:233-238}. The id pattern allows only letters, digits and one hyphen {src:hooks/pre-prompt-expansion-check-gates.py:66}. The ticket folder `T-001` exists but is empty, so a wrongly accepted token would block and fail the test.
- `test_20b`: a ticket folder that is a symlink to a place outside the vault is skipped; the result is a warning naming `T-002` and a log line starting `no ticket id` {src:tests/hooks/test_gate_hook.py:240-246} {src:hooks/pre-prompt-expansion-check-gates.py:167-176} {src:hooks/pre-prompt-expansion-check-gates.py:359}. The name says "allowed and logged"; the visible warning is the part the name omits.
- `test_20f`: `T-001,`, `(T-001)`, `T-001.` and `'T-001';` still block, because punctuation is stripped from each word end {src:tests/hooks/test_gate_hook.py:248-251} {src:hooks/pre-prompt-expansion-check-gates.py:67} {src:hooks/pre-prompt-expansion-check-gates.py:144}.
- `test_20g`: with a symlinked `T-002` named first and the real `T-001` second, the gate still blocks `T-001` {src:tests/hooks/test_gate_hook.py:253-258} {src:hooks/pre-prompt-expansion-check-gates.py:173-176}.
- `test_20c`: `UTF-8 T-001` and `T-001 UTF-8` both gate `T-001`; the word `UTF-8` looks like an id but has no folder {src:tests/hooks/test_gate_hook.py:260-263} {src:hooks/pre-prompt-expansion-check-gates.py:66}. `test_20d`: `UTF-8` alone warns and logs `no ticket id` {src:tests/hooks/test_gate_hook.py:265-268}. `test_20e`: lower case `t-001` is still gated {src:tests/hooks/test_gate_hook.py:270-272} {src:hooks/pre-prompt-expansion-check-gates.py:145}.
- `test_21`: a leftover `TOLLGATE_SKILL_PREFIX` of `ex`, empty or `zz-`, or none at all, changes nothing for `tg-arch`; the name `ex-arch` is allowed even with prefix `ex` {src:tests/hooks/test_gate_hook.py:274-280} {src:hooks/pre-prompt-expansion-check-gates.py:61}. `test_21b`: `zz-qa`, `tgqa`, `tg-qa-extra`, `qa`, `arch` and `dev` are allowed {src:tests/hooks/test_gate_hook.py:282-285} {src:hooks/pre-prompt-expansion-check-gates.py:134-139}.

**Nested layout and path settings (9 tests).** These prove the gate finds tickets kept under a prefix folder and follows the paths file.
- `test_27`, `27b`, `27c`: a ticket under `02-tickets/T/T-001` is found, blocks with the nested path in the message, allows when the files are good, and the prefix folder name `t` matches in any case {src:tests/hooks/test_gate_hook.py:299-314} {src:scripts/core/paths.py:237-262}.
- `test_27d`: when both `02-tickets/T-001` and `02-tickets/T/T-001` exist, the flat one is used {src:tests/hooks/test_gate_hook.py:357-361}. `test_27e`: a nested symlink pointing outside the vault is ignored and a warning is printed {src:tests/hooks/test_gate_hook.py:363-369}.
- `test_27f`: a `tickets:` line in a paths file moves the tickets folder, and the block message names the moved folder {src:tests/hooks/test_gate_hook.py:316-325} {src:scripts/core/paths.py:125-127}.
- `test_27h`: a `state:` line in the paths file moves the log; the file `gate_check.log` appears there, holds `block arch T-001`, and no `.tollgate` folder appears under the fake home {src:tests/hooks/test_gate_hook.py:327-343} {src:hooks/pre-prompt-expansion-check-gates.py:105-118}.
- `test_27i`: with `TOLLGATE_HOME` removed, a log file must exist under `<home>/.tollgate/state` {src:tests/hooks/test_gate_hook.py:345-352} {src:hooks/pre-prompt-expansion-check-gates.py:64}. The hook cannot find the loader in that case and allows with a warning {src:hooks/pre-prompt-expansion-check-gates.py:154-156} {src:hooks/pre-prompt-expansion-check-gates.py:351-356}. The test checks only that the file exists, not its content or the verdict.
- `test_27g`: without `TOLLGATE_HOME` the warning says `TOLLGATE_HOME is not set` {src:tests/hooks/test_gate_hook.py:354-355}.

**Failure handling (4 tests).** The class is named `FailOpenTests`, but three of the four assert fail closed behavior {src:tests/hooks/test_gate_hook.py:372}.
- `test_22`, `22b`: text that is not JSON, or JSON that is not an object, exits 2 with empty output, a stderr message and a `fail_closed` log line {src:tests/hooks/test_gate_hook.py:378-388} {src:hooks/pre-prompt-expansion-check-gates.py:424-430}.
- `test_23`: a forced `RuntimeError` inside `check_arch` blocks the gated skill; the block message holds `RuntimeError` and the log holds `fail_closed` {src:tests/hooks/test_gate_hook.py:390-395} {src:hooks/pre-prompt-expansion-check-gates.py:434-440}. Only `check_arch` is replaced, so the dev and qa paths are not tried {src:tests/hooks/test_gate_hook.py:110}.
- `test_23b`: `evaluate` is replaced by a function that raises, and a non gated command `tg-status` is still allowed, with a stderr warning and a `fail_open` log line {src:tests/hooks/test_gate_hook.py:397-414} {src:hooks/pre-prompt-expansion-check-gates.py:441-444}.

**Skill tool (7 tests).** These prove a skill the model calls itself is gated the same way as a typed command. The payload carries `tool_name`, `skill` and `args` {src:tests/hooks/test_gate_hook.py:417-424}, and a block is a `permissionDecision` of `deny` {src:tests/hooks/test_gate_hook.py:430-435} {src:hooks/pre-prompt-expansion-check-gates.py:446-451}.
- `test_30`, `30b`: state `ROUTED` is denied and the reason names `T-001`; a ready chain is allowed {src:tests/hooks/test_gate_hook.py:437-445}.
- `test_30c`: a leading slash in the skill name is ignored {src:tests/hooks/test_gate_hook.py:447-449} {src:hooks/pre-prompt-expansion-check-gates.py:399}.
- `test_30d`: the skill `status`, and a `Bash` tool call that carries a skill input, are not gated {src:tests/hooks/test_gate_hook.py:451-454} {src:hooks/pre-prompt-expansion-check-gates.py:394-396}.
- `test_30e`: an override file lets a model call through {src:tests/hooks/test_gate_hook.py:456-459}. `test_30f`: an internal error for a gated model call is denied {src:tests/hooks/test_gate_hook.py:461-465}. `test_30g`: bad JSON exits 2 {src:tests/hooks/test_gate_hook.py:467-468}.

**Override (10 tests).** The override file is `T-001-gate-override.md` with one line `Override: <skill> <date> <reason>` {src:tests/hooks/test_gate_hook.py:476-477} {src:hooks/pre-prompt-expansion-check-gates.py:68}.
- `test_24`: today's date allows and logs `override arch T-001` {src:tests/hooks/test_gate_hook.py:479-482} {src:hooks/pre-prompt-expansion-check-gates.py:377-379}. `24b`: a line for `dev` does not unlock `arch`. `24c`: yesterday does not. `24d`: a line with no reason, or only spaces after the date, does not {src:tests/hooks/test_gate_hook.py:484-496} {src:hooks/pre-prompt-expansion-check-gates.py:266-268}.
- `test_24e`: a line inside a code fence is ignored, including a fence opened with `~~~` and closed with backticks {src:tests/hooks/test_gate_hook.py:505-509} {src:hooks/gate_rules.py:98-104}. `24f`: a line after a closed fence counts {src:tests/hooks/test_gate_hook.py:511-513}.
- `test_24g`: a symlinked override file is refused and `override_refused` is logged {src:tests/hooks/test_gate_hook.py:515-521} {src:hooks/pre-prompt-expansion-check-gates.py:251-253}. The real target holds a valid line, so a block proves the refusal.
- `test_24j`: a named pipe (FIFO) made with `os.mkfifo` at the override file path is refused, the gate blocks, and the log holds `not a regular file`; the pipe is removed afterwards {src:tests/hooks/test_gate_hook.py:523-531}. The helper `run_hook_short` runs the hook with a 5 second limit and fails the test with a message about a hang when the limit passes {src:tests/hooks/test_gate_hook.py:533-539}. The hook reads the file mode with `lstat` and refuses anything that is not a regular file before it opens the file, which is what keeps a pipe from blocking the read {src:hooks/pre-prompt-expansion-check-gates.py:255-260}.
- `test_24h`: a BOM before the line still counts {src:tests/hooks/test_gate_hook.py:541-543} {src:hooks/gate_rules.py:79}. `24i`: a date written in full width digits does not count {src:tests/hooks/test_gate_hook.py:545-548} {src:hooks/pre-prompt-expansion-check-gates.py:68}.

**Unreadable files (2 tests).** `test_27` makes the state file unreadable with `chmod 0`; the block message says `permission denied` and names the path, and the log holds `unreadable` {src:tests/hooks/test_gate_hook.py:552-562} {src:hooks/pre-prompt-expansion-check-gates.py:227-228} {src:hooks/pre-prompt-expansion-check-gates.py:296-298}. It skips when run as root {src:tests/hooks/test_gate_hook.py:553-554}. `test_27b`: a missing file is not called unreadable {src:tests/hooks/test_gate_hook.py:564-567}.

**Concurrency and leaks (3 tests).**
- `test_25`: a thread rewrites the state file 150 times with `write_state_atomic` while the hook runs 12 times; every run must allow {src:tests/hooks/test_gate_hook.py:571-590} {src:tests/hooks/test_gate_hook.py:43-44}.
- `test_26`: a marker string placed in the spec and state files never shows in stdout, stderr or the log {src:tests/hooks/test_gate_hook.py:592-599}. `test_26b`: an odd status value never shows in stdout or the log {src:tests/hooks/test_gate_hook.py:601-607}. The messages are built from rule reasons that name expected values only {src:hooks/gate_rules.py:152-166}.

**Fixture (1 test).** The recorded payload `tc-01-typed-arch.json` must say `UserPromptExpansion`, and the hook must block it with state `ROUTED` {src:tests/hooks/test_gate_hook.py:611-619}.

## Diagram

No diagram: each test is one subprocess call against a temp folder, and the two tests that patch the hook run it through `python -c` with no longer chain {src:tests/hooks/test_gate_hook.py:103-118}.

## Notes

**Tests that look wrong or cannot fail**
- `test_fixture_payload_shape_is_handled` rewrites `command_name` and its comment says the recorded fixture "still carries the old example prefix" {src:tests/hooks/test_gate_hook.py:616-617}. The fixture already says `tg-arch` {src:tests/hooks/fixtures/pre-prompt-expansion-check-gates/tc-01-typed-arch.json:1}, so the rewrite changes nothing and the comment is stale.
- `test_27i` passes on any log line at that path, including a plain allow, so it does not prove the old default path is used for a block {src:tests/hooks/test_gate_hook.py:352}.
- `test_25` has no check that the writer was still running while the hook ran. If the thread ends before the 12 runs, the test proves nothing about half written files {src:tests/hooks/test_gate_hook.py:574-590}.
- `test_24j` covers a named pipe only. A device file or a folder at the override path takes the same branch in the hook {src:hooks/pre-prompt-expansion-check-gates.py:258-260} but no test uses them (searched `tests/hooks/test_gate_hook.py` for `mkdir` and `mknod`, 2026-11-21: no hits). The mode check and the later read are two separate calls, so a file swapped in between is not covered {src:hooks/pre-prompt-expansion-check-gates.py:255} {src:hooks/pre-prompt-expansion-check-gates.py:225}.
- `test_26b` does not look at stderr, unlike `test_26` {src:tests/hooks/test_gate_hook.py:606-607}.
- Names that disagree with the body: `test_19b` and `test_20b` (allowed and logged, but a warning is printed), `test_19d` (see above), and the class `FailOpenTests`. Two classes both have a `test_27` and `test_27b` with different meanings {src:tests/hooks/test_gate_hook.py:299} {src:tests/hooks/test_gate_hook.py:552}.
- The file header says the scope is `UserPromptExpansion` payloads {src:tests/hooks/test_gate_hook.py:3}, but a whole class sends `PreToolUse` payloads {src:tests/hooks/test_gate_hook.py:427-428}.

**Coverage gaps.** The hook has its own ticket folder search used when the loader returns nothing {src:hooks/pre-prompt-expansion-check-gates.py:196-210}. It can differ from the loader only for an id with a digit in the prefix, because the loader refuses such an id and the hook accepts it {src:scripts/core/paths.py:203} {src:hooks/pre-prompt-expansion-check-gates.py:66}. No test uses such an id (searched `tests/hooks/test_gate_hook.py` for ids other than `T-001`, `T-002`, `T-777` and `UTF-8`, 2026-11-20).

**Machine and version dependence**
- The child process inherits the developer's environment, and only `TOLLGATE_STATE_DIR` and `TOLLGATE_PATHS` are removed in two tests {src:tests/hooks/test_gate_hook.py:97-99} {src:tests/hooks/test_gate_hook.py:333} {src:tests/hooks/test_gate_hook.py:347}. A `TOLLGATE_PATHS` file set in the shell would override `TOLLGATE_KNOWLEDGE` for the other tests, because an explicit paths line wins {src:scripts/core/paths.py:125-127}.
- Dates: `TODAY` and `YESTERDAY` are taken once at import {src:tests/hooks/test_gate_hook.py:40-41}, while the hook reads its own date at run time {src:hooks/pre-prompt-expansion-check-gates.py:433}. A run that crosses midnight can fail the override tests.
- The hook runs as a direct executable, so it needs its execute bit and a `python3` on the path {src:hooks/pre-prompt-expansion-check-gates.py:1}. The tests use `os.symlink`, `os.chmod` and `os.geteuid`, so they are not portable to Windows {src:tests/hooks/test_gate_hook.py:553}. CI runs on Ubuntu and macOS only {src:.github/workflows/tests.yml:17}.
- Python version: `capture_output` needs 3.7 or newer {src:tests/hooks/test_gate_hook.py:100}. No syntax newer than that is used in this file.

**Description against code.** The test header and change log match the hook: the prefix variable is not read {src:tests/hooks/test_gate_hook.py:8-9} {src:hooks/pre-prompt-expansion-check-gates.py:61}. The hook's own change log now records the empty-prefix rule as an earlier behaviour that the fixed names replaced {src:hooks/pre-prompt-expansion-check-gates.py:21-23}, so no disagreement is left; `test_21` and the hook code agree that a leftover `TOLLGATE_SKILL_PREFIX` changes nothing {src:tests/hooks/test_gate_hook.py:274-285}.

**Inputs without a check, and shared writes.** The tests write only inside their own temp folders, and the one shared file written by two parties, the state file in `test_25`, goes through the atomic writer {src:tests/hooks/test_gate_hook.py:580}. Nothing stops two writers at once in that test; there is one writer thread.
