---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/test_guard_hooks.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["hooks/pre-tool-write-require-read.py", "hooks/post-tool-read-record.py", "hooks/read_guard_common.py", "hooks/pre-tool-bash-gate-pr-create.py", "hooks/git-pre-push", "hooks/pre-tool-write-guard-path.sh", "hooks/pre-tool-bash-guard-code-dir.py", "hooks/pre-tool-bash-databricks-ask.py", "hooks/sql_summary.py"]         # source files under test, relative paths from repo root
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

This file tests the guard hooks that stop an action: writing a guarded file that was not read first, running the pull request create command, pushing to a protected branch, writing into the read only code folder, writing a gate override file, and running Databricks data access without approval {src:tests/hooks/test_guard_hooks.py:5}. Each hook is run as its own process with a JSON payload on stdin, and the test reads the exit code and output {src:tests/hooks/test_guard_hooks.py:34-36}. It has 45 tests in 7 classes. It was not run while this page was written, so each claim says what a test asserts.

## Dependencies

**Depends on.**
- The seven hooks under test, started as executable files from the `hooks/` folder {src:tests/hooks/test_guard_hooks.py:25} {src:tests/hooks/test_guard_hooks.py:27-31} {src:tests/hooks/test_guard_hooks.py:35}. Pages that exist: [[pre-tool-write-guard-path]] and [pre-tool-write-guard-path](../../hooks/pre-tool-write-guard-path.md); [[pre-tool-bash-guard-code-dir]] and [pre-tool-bash-guard-code-dir](../../hooks/pre-tool-bash-guard-code-dir.md). No page yet: [[pre-tool-write-require-read]] (no doc yet), [[post-tool-read-record]] (no doc yet), [[read_guard_common]] (no doc yet), [[pre-tool-bash-gate-pr-create]] (no doc yet), [[git-pre-push]] (no doc yet), [[pre-tool-bash-databricks-ask]] (no doc yet), [[sql_summary]] (no doc yet).
- The path loader `scripts/core/paths.py`, reached through `TOLLGATE_HOME` in one test: [[paths]] (no doc yet) {src:tests/hooks/test_guard_hooks.py:107}.
- Standard library only: `json`, `os`, `subprocess`, `tempfile`, `unittest`.
- Environment: each call gets the developer's environment plus the values the test sets {src:tests/hooks/test_guard_hooks.py:36}. The tests set `TOLLGATE_STATE_DIR`, `GUARD_REGEX`, `TOLLGATE_CODE_DIR`, `DATABRICKS_HOST` and some `TOLLGATE_*` push variables.

**Used by.** Product code: none. Tests: the unit test step of the hook runner finds it by the pattern `test_*.py` {src:tests/hooks/run.sh:198}, and CI runs the same command {src:.github/workflows/tests.yml:35}. Its own header gives the command `python3 -m unittest tests/hooks/test_guard_hooks.py` {src:tests/hooks/test_guard_hooks.py:13}. Searched 2026-11-20: the whole worktree except `.git`, `docs/`, caches and virtual environments for `test_guard_hooks`; those were the only hits.

## Behavior

**Setup.** `run` starts a hook with the payload on stdin and no time limit {src:tests/hooks/test_guard_hooks.py:34-36}. `payload` builds `tool_name`, `session_id` and `tool_input` {src:tests/hooks/test_guard_hooks.py:39-40}. The exit code that means block is 2 {src:tests/hooks/test_guard_hooks.py:26}.

**ReadBeforeWrite (13 tests).** The pair of hooks logs each guarded file a session reads and blocks a write to a guarded file that was not read. A guarded file is one whose name ends in `-state.md` unless `GUARD_REGEX` says otherwise {src:hooks/read_guard_common.py:23} {src:hooks/read_guard_common.py:30-32}. Setup gives each test its own state folder, an empty guarded file `X-1-state.md` and an empty plain file {src:tests/hooks/test_guard_hooks.py:44-50}.
- A write to an unread guarded file exits 2 with `not been read` on stderr; the `Edit` tool is blocked too {src:tests/hooks/test_guard_hooks.py:61-67} {src:hooks/pre-tool-write-require-read.py:44-56}.
- `MultiEdit` exits 0 because the hook gates only `Write` and `Edit` {src:tests/hooks/test_guard_hooks.py:69-70} {src:hooks/pre-tool-write-require-read.py:24} {src:hooks/pre-tool-write-require-read.py:42-43}.
- After the recorder logs a read, the write is allowed; a read logged under another session id does not count {src:tests/hooks/test_guard_hooks.py:72-78} {src:hooks/post-tool-read-record.py:30-35} {src:hooks/read_guard_common.py:59-62}.
- An unguarded file and a new guarded file that does not exist yet are allowed {src:tests/hooks/test_guard_hooks.py:80-84} {src:hooks/pre-tool-write-require-read.py:45-48}. A custom `GUARD_REGEX` of `notes\.md$` guards `notes.md` and stops guarding the state file {src:tests/hooks/test_guard_hooks.py:86-89}.
- Bad input (`not json`, an empty string, `[]`) exits 2 for the guard and 0 for the recorder {src:tests/hooks/test_guard_hooks.py:91-94} {src:hooks/pre-tool-write-require-read.py:60-65} {src:hooks/post-tool-read-record.py:39-43}. An invalid pattern `(` exits 2 with `fails closed` on stderr {src:tests/hooks/test_guard_hooks.py:96-100} {src:hooks/pre-tool-write-require-read.py:63}.
- With a paths file that holds a `state:` line and `TOLLGATE_HOME` set, the read log goes under that folder and not under `TOLLGATE_STATE_DIR`, and a later write is allowed {src:tests/hooks/test_guard_hooks.py:102-113} {src:hooks/read_guard_common.py:35-47}. The result of the first write in that test is not checked {src:tests/hooks/test_guard_hooks.py:109}. Without the loader, the log goes under `TOLLGATE_STATE_DIR` {src:tests/hooks/test_guard_hooks.py:115-119} {src:hooks/read_guard_common.py:55-56}.
- A session id `../../evil` writes no `evil.log` in the temp folder or above it, because every character outside letters, digits, dot, underscore and hyphen becomes an underscore {src:tests/hooks/test_guard_hooks.py:121-124} {src:hooks/read_guard_common.py:27} {src:hooks/read_guard_common.py:61}.

**PrCreateGate (5 tests).** The command text `gh pr create` is built from two string pieces in the test source {src:tests/hooks/test_guard_hooks.py:28}.
- Eight real invocations exit 2: plain, with flags, after `cd r &&`, with `-R org/repo` before the words, with a full path, inside `bash -c`, inside `eval`, and inside `$( )` {src:tests/hooks/test_guard_hooks.py:131-136} {src:hooks/pre-tool-bash-gate-pr-create.py:77-86}. The hook reads the repo flag and its value as skipped words {src:hooks/pre-tool-bash-gate-pr-create.py:30} {src:hooks/pre-tool-bash-gate-pr-create.py:57-59}.
- Six commands that only mention it, or are other `gh pr` or push commands, exit 0 {src:tests/hooks/test_guard_hooks.py:138-141}.
- The block message contains `wait` and `approval` {src:tests/hooks/test_guard_hooks.py:143-146} {src:hooks/pre-tool-bash-gate-pr-create.py:34-38}.
- A command with an unterminated quote falls back to a text match: the real command still blocks and a quoted mention still passes {src:tests/hooks/test_guard_hooks.py:148-150} {src:hooks/pre-tool-bash-gate-pr-create.py:89-94}.
- Bad input (`not json`, empty, `{}x`, `[]`) exits 2 {src:tests/hooks/test_guard_hooks.py:152-154} {src:hooks/pre-tool-bash-gate-pr-create.py:111-116}.

**GitPrePush (5 tests).** The helper feeds one ref line on stdin and strips every `TOLLGATE_*` variable first {src:tests/hooks/test_guard_hooks.py:158-162}.
- A push to `main` or `master` exits 1; a push to `feat` exits 0 {src:tests/hooks/test_guard_hooks.py:164-169} {src:hooks/git-pre-push:27} {src:hooks/git-pre-push:33-38}.
- `TOLLGATE_ALLOW_PROTECTED_PUSH=1` lets a protected push through {src:tests/hooks/test_guard_hooks.py:171-172} {src:hooks/git-pre-push:29}.
- `TOLLGATE_PROTECTED_BRANCHES=release` blocks `release` and frees `main` {src:tests/hooks/test_guard_hooks.py:174-176} {src:hooks/git-pre-push:27}.
- A `TOLLGATE_PRE_PUSH_CMD` of `false` blocks and `true` allows {src:tests/hooks/test_guard_hooks.py:178-180} {src:hooks/git-pre-push:45-49}.

**CodeDirWriteGuard (8 tests).** Setup makes a `code` folder with a `repo` folder and a separate `dev` folder, and sets `TOLLGATE_CODE_DIR` to `code` {src:tests/hooks/test_guard_hooks.py:190-196}.
- With the variable unset, the write guard exits 0, prints a `systemMessage` saying the variable is not set, prints `NOT active` on stderr and never denies {src:tests/hooks/test_guard_hooks.py:205-212} {src:hooks/pre-tool-write-guard-path.sh:83-91}. In v1 the guard first asks the protected file list about the path, and the test path `/x/y` is not on it, so the warning branch is reached {src:hooks/pre-tool-write-guard-path.sh:57-61}.
- The `Write` tool is denied inside the code folder and passes in the dev folder with empty output {src:tests/hooks/test_guard_hooks.py:214-218} {src:hooks/pre-tool-write-guard-path.sh:105-117}. The deny reason names a read-only search source {src:hooks/pre-tool-write-guard-path.sh:112}.
- The Bash guard denies 16 write shapes into the code folder: `cp`, `cp -t`, `mv`, `sed -i`, `sed -i.bak`, `tee`, `>`, `>>`, `2>&1 >`, `touch`, `rm -rf`, `git -C ... commit`, `cd ... && git pull`, `cd ... && touch`, and the two spellings of the variable `$TOLLGATE_CODE_DIR` and `${TOLLGATE_CODE_DIR}` {src:tests/hooks/test_guard_hooks.py:220-227} {src:hooks/pre-tool-bash-guard-code-dir.py:219-237} {src:hooks/pre-tool-bash-guard-code-dir.py:265}.
- A relative write from a working directory inside the code folder is denied {src:tests/hooks/test_guard_hooks.py:229-230} {src:hooks/pre-tool-bash-guard-code-dir.py:260} {src:hooks/lib/protected_paths.py:89}.
- Ten commands that read from the code folder or write elsewhere give no decision: copy out, `cat` to the dev folder, redirect and `sed -i` in the dev folder, `git status`, `git log`, `cd ... && git diff`, `ls`, `rm` in the dev folder, and a copy into a sibling folder `codebackup` {src:tests/hooks/test_guard_hooks.py:232-238} {src:hooks/pre-tool-bash-guard-code-dir.py:57-58} {src:hooks/lib/protected_paths.py:92}.
- With the variable unset, the Bash guard exits 0 with empty output {src:tests/hooks/test_guard_hooks.py:240-245} {src:hooks/pre-tool-bash-guard-code-dir.py:276}: the hook now has no early exit for an unset variable, it reads the payload and checks the always-on protected Tollgate files list, and a harmless command ends at the final exit 0 {src:hooks/pre-tool-bash-guard-code-dir.py:261}. With the variable set, input that is not JSON, empty or `{}` exits 2 {src:tests/hooks/test_guard_hooks.py:247-249} {src:hooks/pre-tool-bash-guard-code-dir.py:273-275}.
- Known limit: `D=<repo>; touch $D/f` gives no decision {src:tests/hooks/test_guard_hooks.py:251-252} {src:hooks/pre-tool-bash-guard-code-dir.py:24-25} {src:hooks/pre-tool-bash-guard-code-dir.py:268}.

**GateOverrideWriteGuard (7 tests).** A model write to a file named `*-gate-override.md` is denied by the write guard, because the owner makes that file from a terminal {src:hooks/pre-tool-write-guard-path.sh:30-52}.
- `Write`, `Edit` and `MultiEdit` to `T-001-gate-override.md` are denied and the output says `terminal` {src:tests/hooks/test_guard_hooks.py:268-273}. The script never reads the tool name, so the three runs take the same path {src:hooks/pre-tool-write-guard-path.sh:15-23}.
- It is denied with `TOLLGATE_CODE_DIR` unset, because the override check runs first {src:tests/hooks/test_guard_hooks.py:275-280} {src:hooks/pre-tool-write-guard-path.sh:33-52}. A name in other letter case is denied {src:tests/hooks/test_guard_hooks.py:282-284} {src:hooks/pre-tool-write-guard-path.sh:34}.
- A symlink named `innocent.md` that points at the override name is denied, because the real name is checked; the target file does not exist, so the link is dangling {src:tests/hooks/test_guard_hooks.py:286-290} {src:hooks/pre-tool-write-guard-path.sh:35-37}.
- A `NotebookEdit` payload with `notebook_path` is denied {src:tests/hooks/test_guard_hooks.py:292-295} {src:hooks/pre-tool-write-guard-path.sh:23}.
- Four other names give no decision: `T-001-state.md`, `T-001-gate-override.md.bak`, `gate-override.txt` and `T-001-gate-overrides.md` {src:tests/hooks/test_guard_hooks.py:297-300}. A write into the code folder is still denied {src:tests/hooks/test_guard_hooks.py:302-303}.

**DatabricksGateExtended (7 tests).** The hook denies a command that pulls row data from Databricks, with a summary and an approval code that is a hash of the command; a rerun with the code in front gives `ask` {src:hooks/pre-tool-bash-databricks-ask.py:99-131} {src:hooks/pre-tool-bash-databricks-ask.py:250-253}. The class sets `DATABRICKS_HOST` empty so a host on the machine cannot change the result {src:tests/hooks/test_guard_hooks.py:307} {src:hooks/pre-tool-bash-databricks-ask.py:203-206}.
- Eleven command shapes are denied and the reason holds `TOLLGATE_DATA_APPROVED=`: two Python SQL connector imports, a heredoc with the connector, a statement execution call, `spark.sql`, a `uv run` call with `DatabricksSession`, `dbsqlcli`, three `curl` calls to workspace or SQL paths, and a `wget` to an example host with a SQL path {src:tests/hooks/test_guard_hooks.py:315-328} {src:hooks/pre-tool-bash-databricks-ask.py:79-90}. The `wget` case matches on the SQL path alone, not on the host {src:hooks/pre-tool-bash-databricks-ask.py:90} {src:hooks/pre-tool-bash-databricks-ask.py:221}.
- The reason holds the description the caller gave and the SQL text {src:tests/hooks/test_guard_hooks.py:330-333} {src:hooks/pre-tool-bash-databricks-ask.py:233-243}.
- Eight string prefixes times three quote styles, 24 commands in all, show the query text in the reason {src:tests/hooks/test_guard_hooks.py:335-344} {src:hooks/pre-tool-bash-databricks-ask.py:92-93}. The closing quote argument is rewritten only for the double quote case, and that case then builds a different command, so that rewrite does nothing {src:tests/hooks/test_guard_hooks.py:338-341}.
- Spaces around the dot in `spark . sql`, `spark. table` and `spark .read` still deny {src:tests/hooks/test_guard_hooks.py:346-349} {src:hooks/pre-tool-bash-databricks-ask.py:86}.
- The code from the first reply, put in front of the same command, gives `ask`; the same code with ` --x` added gives `deny` {src:tests/hooks/test_guard_hooks.py:351-355} {src:hooks/pre-tool-bash-databricks-ask.py:209-210} {src:hooks/pre-tool-bash-databricks-ask.py:250-253}.
- Six commands that only mention these names give no decision {src:tests/hooks/test_guard_hooks.py:357-360}. The CLI paths `databricks fs cat` and `databricks api post /api/2.0/sql/statements` deny, `databricks clusters list` does not, and the code flow gives `ask` for `fs cat` {src:tests/hooks/test_guard_hooks.py:362-368} {src:hooks/pre-tool-bash-databricks-ask.py:189-200}.

## Diagram

No diagram: each case is one process with one payload and no mock chain.

## Notes

**Tests that look wrong or cannot fail**
- `test_session_id_cannot_escape_state_dir`: the second path checked, `<tmp>/../evil.log`, needs three levels up, while the id has two, so that assertion cannot fail {src:tests/hooks/test_guard_hooks.py:121-124}. The test also never checks that a sanitized log was written, so it passes if nothing is logged.
- `test_bash_guard_silent_when_unset_and_on_bad_input`: the name says bad input, but the body sends a valid JSON payload with the variable unset {src:tests/hooks/test_guard_hooks.py:240-245}. Bad input with the variable unset is not tested; in v1 the hook no longer exits early in that case, it reads stdin and fails closed with exit 2 {src:hooks/pre-tool-bash-guard-code-dir.py:258} {src:hooks/pre-tool-bash-guard-code-dir.py:273-275}.
- `test_write_edit_multiedit_to_override_file_denied_with_terminal_message` varies the tool name, which the script ignores, so only one path is tested three times {src:tests/hooks/test_guard_hooks.py:270} {src:hooks/pre-tool-write-guard-path.sh:15-23}.
- The substitution branch of the PR gate, for a `$( )` inside a quoted word, is not exercised: the unquoted form in the test is split into plain words and found directly (checked by splitting the string with the same lexer settings, 2026-11-20) {src:tests/hooks/test_guard_hooks.py:135} {src:hooks/pre-tool-bash-gate-pr-create.py:32} {src:hooks/pre-tool-bash-gate-pr-create.py:73}.
- The header of the Bash code folder guard still lists "interpreters writing through code (python -c, perl -e)" as not caught {src:hooks/pre-tool-bash-guard-code-dir.py:24-26}; in v1 the code does check `python -c` and `node -e` style bodies that name a protected path and contain a write word {src:hooks/pre-tool-bash-guard-code-dir.py:198-208}. No test in this file covers that; see [test_self_protection](test_self_protection.md). The same header line also lists command substitution as not caught; the code now splits a command at a newline, `$(`, a backtick and `)` {src:hooks/pre-tool-bash-guard-code-dir.py:91-116}, and [test_self_protection](test_self_protection.md) covers that.
- The same PR gate logic exists in two files, the hook and `hooks/gh_pr_create_detect.py`; only the hook copy is tested here {src:hooks/pre-tool-bash-gate-pr-create.py:41-94} {src:hooks/gh_pr_create_detect.py:30-83}.

**Not covered.** The Databricks tests send no bad JSON, trigger no internal error, and do not cover the 600 character SQL cut, `--json @file`, or the PHI and production notes of `sql_summary.py` {src:hooks/pre-tool-bash-databricks-ask.py:63} {src:hooks/pre-tool-bash-databricks-ask.py:178-186} {src:hooks/pre-tool-bash-databricks-ask.py:256-264} (searched this test file, 2026-11-20). `test_hooks` covers part of the Databricks gate, see [test_hooks](test_hooks.md). The PHI hooks are in [test_phi_hook_levels](test_phi_hook_levels.md) and the gate rule functions in [test_gate_rules](test_gate_rules.md).

**Description against code**
- Three hook headers used to say "fails open" while the code blocked; after the cleanup they say fails closed and match the code. `hooks/pre-tool-write-require-read.py` says it fails closed on any internal error {src:hooks/pre-tool-write-require-read.py:14}; the code blocks with exit 2 {src:hooks/pre-tool-write-require-read.py:62-64}, and the test expects the block {src:tests/hooks/test_guard_hooks.py:93}.
- `hooks/pre-tool-bash-gate-pr-create.py` says any other internal error fails closed, exit 2 {src:hooks/pre-tool-bash-gate-pr-create.py:14-15}; the code blocks {src:hooks/pre-tool-bash-gate-pr-create.py:113-115}.
- `hooks/pre-tool-bash-guard-code-dir.py` says it fails closed on unreadable input, a missing helper module or any internal error {src:hooks/pre-tool-bash-guard-code-dir.py:30}; the code exits 2 {src:hooks/pre-tool-bash-guard-code-dir.py:273-275}, and the test expects the block {src:tests/hooks/test_guard_hooks.py:247-249}.
- The databricks hook header says an internal error returns `ask` {src:hooks/pre-tool-bash-databricks-ask.py:24}; that matches the code {src:hooks/pre-tool-bash-databricks-ask.py:282-283}, but no test reaches it.
**Machine and version dependence**
- Each hook is started as an executable, so each needs its execute bit; the write guard is a bash script that calls `python3` {src:hooks/pre-tool-write-guard-path.sh:1} {src:hooks/pre-tool-write-guard-path.sh:15}. The push hook needs `bash` {src:hooks/git-pre-push:1}.
- The Bash code folder guard uses `str.removeprefix`, which needs Python 3.9 or newer {src:hooks/pre-tool-bash-guard-code-dir.py:164}; the 3.12 minimum covers that, so these tests need no extra version. The test file itself needs 3.7 for `capture_output` {src:tests/hooks/test_guard_hooks.py:35}.
- The temp folder is resolved with `realpath` for the code folder tests, which handles macOS temp folder links {src:tests/hooks/test_guard_hooks.py:192-193}. Symlink tests need `os.symlink` {src:tests/hooks/test_guard_hooks.py:289}.
- `GUARD_REGEX` is set empty in the read guard tests so a value in the developer's shell cannot leak in {src:tests/hooks/test_guard_hooks.py:46}. The classes for the pull request gate, the push hook and the Databricks gate do not clear any other variable the hooks might read, so a value in the shell is passed through {src:tests/hooks/test_guard_hooks.py:34-36}; the push helper is the exception and strips every `TOLLGATE_*` name {src:tests/hooks/test_guard_hooks.py:160}.

**Inputs without a check, and shared writes.** The tests write only inside their own temp folders. The Bash guard replaces `$HOME`, `$TOLLGATE_HOME` and `$CLAUDE_DOTFILES` in the command text with the caller's environment values before it decides {src:hooks/lib/protected_paths.py:97-104} {src:hooks/pre-tool-bash-guard-code-dir.py:268}; those values are not checked. `TOLLGATE_PRE_PUSH_CMD` is run as a shell command by the push hook; the test sets only `true` and `false` {src:hooks/git-pre-push:45-49} {src:tests/hooks/test_guard_hooks.py:179-180}.
