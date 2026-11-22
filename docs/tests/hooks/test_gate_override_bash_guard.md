---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/hooks/test_gate_override_bash_guard.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers:            # source files under test, relative paths from repo root
  - hooks/pre-tool-bash-guard-gate-override.py
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

This file tests the Bash side of the gate override guard. The owner creates a `*-gate-override.md` file from a terminal, and the model must not write one through a shell command. The hook looks at the command text for that file name together with a write verb or an output redirect {src:hooks/pre-tool-bash-guard-gate-override.py:13-19}. The tests feed it command lines and check that writes are denied, reads pass, and a payload it cannot read stops with exit code 2. The v1 hardening of the hook (names built from quotes, variables, globs, command substitution and inline interpreter code) is not tested in this file; those cases are in [test_self_protection](test_self_protection.md).

## Dependencies

**Depends on.** The hook [[pre-tool-bash-guard-gate-override]] and [pre-tool-bash-guard-gate-override](../../hooks/pre-tool-bash-guard-gate-override.md) {src:tests/hooks/test_gate_override_bash_guard.py:21}. Standard library: `json`, `os`, `subprocess`, `unittest`. The hook is started as a program, so it needs `python3` on the path {src:hooks/pre-tool-bash-guard-gate-override.py:1}.

**Used by.** No product code imports a test file. The folder is run by discovery on `test_*.py` (searched with `git grep -n -E "discover -s"`, 2026-11-20):
- Tests: `tests/hooks/run.sh` {src:tests/hooks/run.sh:198}, the CI workflow {src:.github/workflows/tests.yml:35}, and `tests/system/run.sh` {src:tests/system/run.sh:20}.

## Behavior

**Helpers.** `run` starts the hook with the given text on standard input and captures output, with no custom environment {src:tests/hooks/test_gate_override_bash_guard.py:25-26}. `cmd` wraps a command string in a Bash tool payload {src:tests/hooks/test_gate_override_bash_guard.py:29-30}. `denied` is true only when the exit code is 0, output is not empty, and the JSON holds a permission decision of `deny` for the `PreToolUse` event {src:tests/hooks/test_gate_override_bash_guard.py:33-37}. The path `P` used in most cases is a fake override path under `$TOLLGATE_KNOWLEDGE` for ticket `T-001` {src:tests/hooks/test_gate_override_bash_guard.py:22}.

**Write commands are denied (17 cases, each its own sub test).** The list holds echo with `>` and `>>`, `printf` into `tee`, `cp`, `mv`, `dd of=`, `install`, `ln -s`, `touch`, `truncate`, `sed -i`, a `python3 -c` that opens the file for writing, a `cd d && echo hi>name` with no space before the redirect, `cat` with a redirect, `rm`, and two spellings in other letter case {src:tests/hooks/test_gate_override_bash_guard.py:41-63}. Why each is caught:
- The file name match ignores letter case {src:hooks/pre-tool-bash-guard-gate-override.py:37}. The hook looks for the name in the command as typed and again with quotes and backslashes removed, and only then asks whether the command is write shaped {src:hooks/pre-tool-bash-guard-gate-override.py:95-98}.
- Any `>` left after safe redirects are removed counts as a write {src:hooks/pre-tool-bash-guard-gate-override.py:68-70}. This catches the redirect cases, including `cat` with a redirect.
- Otherwise any word of the command that is in the write verb set counts {src:hooks/pre-tool-bash-guard-gate-override.py:71-72}. The set holds `echo`, `printf`, `tee`, `cp`, `mv`, `dd`, `install`, `ln`, `touch`, `truncate`, `sed`, `python3` and `rm` among others {src:hooks/pre-tool-bash-guard-gate-override.py:38-40}.

**Reads are allowed (7 cases).** `cat`, `ls`, `grep`, `head`, `cat` with `2>&1`, `cat` with `2>/dev/null`, and an `ls` of the ticket folder must give exit 0 and empty output {src:tests/hooks/test_gate_override_bash_guard.py:65-79}. The two redirect forms are removed before the `>` test {src:hooks/pre-tool-bash-guard-gate-override.py:41} {src:hooks/pre-tool-bash-guard-gate-override.py:68}. The last case never names the override file, so the write check is not reached; the inline code check then finds no interpreter and returns false {src:hooks/pre-tool-bash-guard-gate-override.py:97-99} {src:hooks/pre-tool-bash-guard-gate-override.py:88-89}.

**Write verbs on other files are allowed.** `echo hello > /tmp/x.txt`, `cp a b`, `python3 -c 'print(1)'` and `git status` give empty output {src:tests/hooks/test_gate_override_bash_guard.py:81-84}, because none names the override file {src:hooks/pre-tool-bash-guard-gate-override.py:97-99}. The `python3 -c` case does reach the inline code check, and passes because its text has neither `gate` nor `override` {src:hooks/pre-tool-bash-guard-gate-override.py:90-91}.

**Unreadable payload fails closed.** Empty input, `not json` and `[]` must exit with code 2 and say `fails closed` on standard error {src:tests/hooks/test_gate_override_bash_guard.py:86-91}. The first two fail at the JSON read, the third at the object check, and the handler prints the message and exits 2 {src:hooks/pre-tool-bash-guard-gate-override.py:104-106} {src:hooks/pre-tool-bash-guard-gate-override.py:113-115}.

**A readable payload with no usable command is allowed.** `{"tool_input": null}`, a numeric `command` and `{}` give exit 0 and empty output {src:tests/hooks/test_gate_override_bash_guard.py:93-99}. The code treats a missing tool input as an empty one and ignores a command that is not a string {src:hooks/pre-tool-bash-guard-gate-override.py:107-109}.

**Deny shape.** The output has exactly one key, `hookSpecificOutput`, holding exactly `hookEventName`, `permissionDecision` and `permissionDecisionReason` {src:tests/hooks/test_gate_override_bash_guard.py:101-105} {src:hooks/pre-tool-bash-guard-gate-override.py:57-58}.

## Diagram

None: the test starts one script with a JSON payload and reads its output, so there is no fixture chain.

## Notes

- **Hook header now matches the code.** The hook header says it "fails closed on unreadable input or an internal error" {src:hooks/pre-tool-bash-guard-gate-override.py:26}. The code exits 2, which blocks {src:hooks/pre-tool-bash-guard-gate-override.py:113-115}, and the test checks the blocking behavior {src:tests/hooks/test_gate_override_bash_guard.py:90}.
- **Code and description disagree, verb list.** The header lists `cat` with a redirect as a write verb {src:hooks/pre-tool-bash-guard-gate-override.py:16-19}. `cat` is not in the verb set {src:hooks/pre-tool-bash-guard-gate-override.py:38-40}; the redirect test catches it instead {src:hooks/pre-tool-bash-guard-gate-override.py:69-70}. The set also holds `rsync`, `curl` and `wget`, which the header does not list {src:hooks/pre-tool-bash-guard-gate-override.py:40}.
- **Not tested.** Verbs in the set that no case uses: `awk`, `perl`, `ruby`, `node`, `python`, `sh`, `bash`, `zsh`, `rsync`, `curl`, `wget`. None of the "not caught" limits in the header (a glob that hides the `gate-` part, scripts that write the file inside, encoded names, names built by code in a script file) {src:hooks/pre-tool-bash-guard-gate-override.py:24-25} has a case here, and a hard link made earlier under another name is not seen either, because the check reads only the names typed in the command {src:hooks/pre-tool-bash-guard-gate-override.py:94-99}, so a change that closes or widens them would not be noticed.
- **Broad match, by reading the code.** Because every word of the command counts, a read such as `grep install <override path>` would also be denied, since `install` is in the verb set {src:hooks/pre-tool-bash-guard-gate-override.py:71-72}. The tests only use four read commands without extra words.
- **Weak assertions.** The two allow lists check empty output only, not the exit code {src:tests/hooks/test_gate_override_bash_guard.py:84}. A hook that crashed with an error exit and no output would pass those cases.
- **Machine and version dependence.** The hook is run directly {src:tests/hooks/test_gate_override_bash_guard.py:26}, so it needs the execute bit. The test passes the full current environment and no working folder, and nothing in the cases uses a machine path: the override path is a text string that is never opened.
- **Inputs without a check.** The hook never runs or opens the command text it is given, it only scans it {src:hooks/pre-tool-bash-guard-gate-override.py:94-99}. In the test every command is a constant.
- **Shared file writes.** None, in the test or in the hook.
