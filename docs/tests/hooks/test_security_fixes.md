---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/hooks/test_security_fixes.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers:            # source files under test, relative paths from repo root
  - hooks/git_ask_before_run.py
  - hooks/git_push_guard.sh
  - hooks/git_commit_guard.sh
  - hooks/git_readonly_guard.sh
  - hooks/co_authored_by_check.sh
  - hooks/secret-command-guard.sh
  - hooks/scrub_secrets.py
  - hooks/post-tool-bash-scan-secrets.py
  - hooks/pre-commit-secrets
  - hooks/git-pre-push
  - settings.json
tags: []
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
update_needed: 2026-11-20
---

## Purpose

Regression tests for a batch of security fixes in the hooks: the git push, commit and read-only guards, the shell command parser behind them, extra rules in the secret command guard, the Plane key and JSON member shapes in the secret scanners, hooks that must block when their input cannot be read, and the wiring in `settings.json`. Most tests run a hook as a subprocess with a built payload and check the decision it prints.

## Dependencies

**Depends on.**
- `hooks/git_ask_before_run.py`, imported as a module for two helper functions {src:tests/hooks/test_security_fixes.py:27-29}. Vault copy: [[git_ask_before_run]]. Repo copy: [git_ask_before_run](../../hooks/git_ask_before_run.md).
- Hook scripts run as subprocesses: [[git_push_guard]] ([page](../../hooks/git_push_guard.md)), [[git_commit_guard]] ([page](../../hooks/git_commit_guard.md)), [[git_readonly_guard]] ([page](../../hooks/git_readonly_guard.md)), [[co_authored_by_check]] ([page](../../hooks/co_authored_by_check.md)), [[secret-command-guard]] ([page](../../hooks/secret-command-guard.md)), [[scrub_secrets]] ([page](../../hooks/scrub_secrets.md)), [[post-tool-bash-scan-secrets]] ([page](../../hooks/post-tool-bash-scan-secrets.md)), [[pre-commit-secrets]] ([page](../../hooks/pre-commit-secrets.md)), [[git-pre-push]] ([page](../../hooks/git-pre-push.md)), [[pre-tool-write-guard-path]] ([page](../../hooks/pre-tool-write-guard-path.md)), [[guard_worktree_remove]] ([page](../../hooks/guard_worktree_remove.md)), [[pre-tool-bash-databricks-ask]] ([page](../../hooks/pre-tool-bash-databricks-ask.md)), [[pre-tool-bash-guard-gate-override]] ([page](../../hooks/pre-tool-bash-guard-gate-override.md)), [[pre_tool_write_scan_claims]] ([page](../../hooks/pre_tool_write_scan_claims.md)), [[pre_tool_write_vault_frontmatter]] ([page](../../hooks/pre_tool_write_vault_frontmatter.md)).
- Files read directly: `settings.json` {src:tests/hooks/test_security_fixes.py:213}, `hooks/secret-command-guard.sh` {src:tests/hooks/test_security_fixes.py:294}, `hooks/git-pre-push` {src:tests/hooks/test_security_fixes.py:412}, `docs/hooks.md` {src:tests/hooks/test_security_fixes.py:416}.
- Standard library: `json`, `os`, `subprocess`, `sys`, `tempfile`, `unittest`. Outside programs: `git` (needs `init -b`, so git 2.28 or newer) {src:tests/hooks/test_security_fixes.py:67}, `bash` {src:tests/hooks/test_security_fixes.py:366}.

**Used by.** No product code. Searched with `git grep` outside `docs/` on 2026-11-20.
- Tests: found by `unittest discover` in the hook test runner {src:tests/hooks/run.sh:198} and in CI {src:.github/workflows/tests.yml:35}.

## Behavior

**Harness.** `run()` starts a hook script with a payload on stdin, after removing every `TOLLGATE_` variable from the environment so a developer's own settings cannot change a result {src:tests/hooks/test_security_fixes.py:32-35}. `bash_payload()` builds a Bash tool payload with a command and a `cwd` {src:tests/hooks/test_security_fixes.py:38-39}. `decision()` returns the `permissionDecision` from stdout, or an empty string when stdout is empty {src:tests/hooks/test_security_fixes.py:42-45}. All fake keys are built from pieces at run time {src:tests/hooks/test_security_fixes.py:48-53}. `RepoCase` makes a throwaway git repo on branch `main` with one commit {src:tests/hooks/test_security_fixes.py:62-71}.

**`PushParserTests` (7 cases).** A list of 26 command shapes that all hide a `git push`: extra `-c`, `-C`, `--git-dir`, an absolute path to git, `env` prefixes, a subshell, `sh -c`, `eval`, `$(...)`, `sudo`, `time`, `nohup`, and four `env` split-string forms (`env -S "..."`, `env --split-string="..."`, `env -S '...'` and `env -i -S '...'`) {src:tests/hooks/test_security_fixes.py:80-107} {src:tests/hooks/test_security_fixes.py:103-106}.
- Every shape is denied when it targets `main` {src:tests/hooks/test_security_fixes.py:112-115}. The hook denies a protected branch when `TOLLGATE_ALLOW_PROTECTED_PUSH` is not 1 {src:hooks/git_ask_before_run.py:444-451}, using the default protected list `main master` {src:hooks/git_ask_before_run.py:40}.
- Every shape asks when it targets `feature/x` {src:tests/hooks/test_security_fixes.py:117-120}; the hook returns `ask` after the protected check {src:hooks/git_ask_before_run.py:452}.
- Non-pushes (`git status`, `echo git push`, a quoted push, `cat push`, `gitpush`) print nothing {src:tests/hooks/test_security_fixes.py:122-125}. The parser needs the first word to be `git` by base name {src:hooks/git_ask_before_run.py:164}.
- The four split-string shapes are new in the cleanup. `-S` is no longer in the list of `env` flags that take one value {src:hooks/git_ask_before_run.py:54}; instead `strip_prefixes` spots a split-string option after `env` {src:hooks/git_ask_before_run.py:146}, splits its string into words with `shlex` (falling back to blanks when quotes are unbalanced) {src:hooks/git_ask_before_run.py:112-117}, puts those words back in place of the option {src:hooks/git_ask_before_run.py:147-149}, and carries on, so the hidden `git push` is found. The helper recognises `-S STRING`, `-SSTRING`, `--split-string STRING` and `--split-string=STRING` {src:hooks/git_ask_before_run.py:120-130}.
- An unbalanced quote still finds the push, because the lexer falls back to a crude split that over-detects {src:tests/hooks/test_security_fixes.py:127-128} {src:hooks/git_ask_before_run.py:93-98}.
- `git -c a=b -C <repo> push origin x` is parsed into verb `push`, repo path and config list {src:tests/hooks/test_security_fixes.py:130-132} {src:hooks/git_ask_before_run.py:171-176}.
- The commit guard asks for six of the same shapes {src:tests/hooks/test_security_fixes.py:134-138}.
- The Co-Authored-By check denies four shapes of a commit that carries that line {src:tests/hooks/test_security_fixes.py:140-145}. Its filter is any `git` word followed later by `commit` {src:hooks/co_authored_by_check.sh:36}.

**`ReadonlyGuardTests` (5 cases).**
- 21 commands that could run a program or write a file through an auto-approved git read verb are denied: `--output`, `--ext-diff`, `-c`, `--config-env`, and `git config` writes of keys that name a program {src:tests/hooks/test_security_fixes.py:154-178}. The hook checks the verb list {src:hooks/git_ask_before_run.py:324} {src:hooks/git_ask_before_run.py:401-422} and a pattern of dangerous keys {src:hooks/git_ask_before_run.py:329-335}.
- 19 harmless forms print nothing, including `git config user.email 'me@example.invalid'` {src:tests/hooks/test_security_fixes.py:180-189}. That last form is allowed because `user.email` is not in the dangerous key pattern {src:hooks/git_ask_before_run.py:329-335}, so the hook does let a git config write through for non-listed keys.
- 17 more `git config` keys that name a program or a program path are denied: the `cmd` and `path` forms of `difftool`, `mergetool`, `browser` and `man`, `web.browser`, `interactive.diffFilter`, the `cmd` and `command` forms of `trailer`, `core.alternateRefsCommand`, `sequence.editor`, `core.editor`, `gpg.program` and `gpg.x.program` {src:tests/hooks/test_security_fixes.py:191-197}. The first thirteen of those are new patterns in the cleanup {src:hooks/git_ask_before_run.py:334-335}; the last four were already in the pattern {src:hooks/git_ask_before_run.py:330} {src:hooks/git_ask_before_run.py:332}.
- `config_write_key()` returns `None` for reads and the key for writes, including the new `set` word form and a `--file` value that must be skipped {src:tests/hooks/test_security_fixes.py:199-205} {src:hooks/git_ask_before_run.py:340-362}.
- An unreadable payload exits 2 {src:tests/hooks/test_security_fixes.py:207-208} {src:hooks/git_ask_before_run.py:462-464}.

**`SettingsTests` (5 cases)** read the repo `settings.json`.
- No blanket `git config` allow rule exists, and every `git config` rule names a read flag {src:tests/hooks/test_security_fixes.py:216-221}; the file holds five narrow rules {src:settings.json:263-267}.
- Every hook under `PreToolUse` and `UserPromptExpansion` sets `onFailure` to `block` {src:tests/hooks/test_security_fixes.py:223-227}.
- No matcher names the dropped tool `MultiEdit` {src:tests/hooks/test_security_fixes.py:229-232}.
- Exactly one `Skill` matcher exists and it runs the gate script with `onFailure` block {src:tests/hooks/test_security_fixes.py:234-239} {src:settings.json:118-125}.
- The read-only guard is wired {src:tests/hooks/test_security_fixes.py:241-243} {src:settings.json:151-155}.

**`SecretCommandGuardTests` (5 cases).** 19 new block shapes exit 2 {src:tests/hooks/test_security_fixes.py:250-273}: keychain `-g` and `-wa` forms, `dump-keychain`, reads of the AWS credentials file, `.netrc` and Databricks config, `/proc/self/environ`, a Python one-liner that opens the credentials file, and the full-path forms of the environment dumps {src:hooks/secret-command-guard.sh:79-82} {src:hooks/secret-command-guard.sh:89-96} {src:hooks/secret-command-guard.sh:117-118}. Nine near-misses exit 0, such as `ls -la ~/.netrc` and `/usr/bin/env python3 x.py` {src:tests/hooks/test_security_fixes.py:275-281}. Payloads `not json`, an empty string and `[]` exit 2 with the words "could not read" {src:tests/hooks/test_security_fixes.py:283-287} {src:hooks/secret-command-guard.sh:30-41}. A readable payload without a command exits 0 {src:tests/hooks/test_security_fixes.py:289-291} {src:hooks/secret-command-guard.sh:43-45}. One case reads the hook source and asserts the words SPEED BUMP are present {src:tests/hooks/test_security_fixes.py:293-295} {src:hooks/secret-command-guard.sh:7}.

**`ShellHooksFailClosed` (3 cases).** Four shell hooks exit 2 for each of three bad payloads {src:tests/hooks/test_security_fixes.py:299-304}: `pre-tool-write-guard-path.sh` {src:hooks/pre-tool-write-guard-path.sh:27}, `co_authored_by_check.sh` {src:hooks/co_authored_by_check.sh:30}, `guard_worktree_remove.sh` {src:hooks/guard_worktree_remove.sh:29} and `secret-command-guard.sh`. The write guard still allows a readable payload without a path, with an invented code folder set, and prints nothing {src:tests/hooks/test_security_fixes.py:306-310} {src:hooks/pre-tool-write-guard-path.sh:94}. Four Python hooks exit 2 on `not json` {src:tests/hooks/test_security_fixes.py:312-316} {src:hooks/pre-tool-bash-guard-gate-override.py:113-115} {src:hooks/pre-tool-bash-databricks-ask.py:259-261} {src:hooks/pre_tool_write_scan_claims.py:91-94} {src:hooks/pre_tool_write_vault_frontmatter.py:125-127}.

**`PlaneKeyShapeTests` (10 cases).**
- `scrub_secrets.py` in its before-tool mode denies a Plane key in a command and in a write, naming the label `PLANE_KEY` and never echoing the key {src:tests/hooks/test_security_fixes.py:325-333} {src:hooks/scrub_secrets.py:60} {src:hooks/scrub_secrets.py:185-196} {src:hooks/scrub_secrets.py:214-223}.
- It denies four spellings of a JSON member holding a long value, labelled `JSON_CREDENTIAL` {src:tests/hooks/test_security_fixes.py:335-337} {src:hooks/scrub_secrets.py:43-46}.
- Short values, a placeholder in angle brackets, a non-credential member name and code that reads the key from the environment are not flagged {src:tests/hooks/test_security_fixes.py:339-342}. The pattern needs 20 or more characters from a fixed set {src:hooks/scrub_secrets.py:45}.
- In after-tool mode the same two shapes are redacted into `[REDACTED:...]` text {src:tests/hooks/test_security_fixes.py:344-350} {src:hooks/scrub_secrets.py:226-253}.
- `post-tool-bash-scan-secrets.py` redacts both with the labels `PLANE_KEY` and `JSON_CREDENTIAL` {src:tests/hooks/test_security_fixes.py:352-357} {src:hooks/post-tool-bash-scan-secrets.py:48-53}.
- `pre-commit-secrets` exits 1 on staged text with either shape, in a fresh repo per case {src:tests/hooks/test_security_fixes.py:359-368} {src:hooks/pre-commit-secrets:18-19} {src:hooks/pre-commit-secrets:53-55}.
- It also exits 1 when the staged line begins with two plus signs followed by a key, which diff output shows as three plus signs. The hook now skips only each file's header block, from `diff --git` to the first `@@`, and keeps every added line after that {src:tests/hooks/test_security_fixes.py:370-378} {src:hooks/pre-commit-secrets:38}. The old filter dropped every line that began with three plus signs, so such a line passed unseen.
- A shared helper `_staged_hook_exit` stages one line in a fresh repo, runs the hook and returns the result {src:tests/hooks/test_security_fixes.py:380-387}. Two cases use it. `test_pre_commit_secrets_blocks_a_private_key_header` stages a private key header, built from pieces, and expects exit 1; this proves the private key pattern now runs, since the hook passes the pattern with `grep -E -e` {src:tests/hooks/test_security_fixes.py:389-393} {src:hooks/pre-commit-secrets:21} {src:hooks/pre-commit-secrets:38}. `test_pre_commit_secrets_blocks_an_added_line_that_looks_like_a_file_header` stages a line starting `++ b/` followed by a key and expects exit 1 {src:tests/hooks/test_security_fixes.py:395-397}.
- It exits 0 when the staged file is a copy of the hook itself {src:tests/hooks/test_security_fixes.py:399-407}.

**`PrePushRiskDocumented` (1 case).** Reads the header of `git-pre-push` up to its `set -uo pipefail` line and checks it contains the words RISK and `bash -c`; checks `docs/hooks.md` mentions `TOLLGATE_PRE_PUSH_CMD` {src:tests/hooks/test_security_fixes.py:411-417} {src:hooks/git-pre-push:16} {src:hooks/git-pre-push:46} {src:docs/hooks.md:597}.

## Diagram

Skipped: fixtures are flat. Each case builds one payload and runs one subprocess, apart from `RepoCase`, which makes one throwaway repo.

## Notes

- **Code versus description.** No disagreement is left for the hooks this file tests. The headers of `git_push_guard.sh` and `git_commit_guard.sh` now say "exit 2 on unreadable input" {src:hooks/git_push_guard.sh:12} {src:hooks/git_commit_guard.sh:12}, which matches the Python helper they run {src:hooks/git_push_guard.sh:18} {src:hooks/git_commit_guard.sh:18} {src:hooks/git_ask_before_run.py:462-467} {src:hooks/git_ask_before_run.py:483-486}. The docstrings of `pre_tool_write_scan_claims.py` and `pre_tool_write_vault_frontmatter.py` now say they fail closed, which matches the code {src:hooks/pre_tool_write_scan_claims.py:7} {src:hooks/pre_tool_write_scan_claims.py:91-94} {src:hooks/pre_tool_write_vault_frontmatter.py:8} {src:hooks/pre_tool_write_vault_frontmatter.py:125-127}. The readonly guard header was already correct {src:hooks/git_readonly_guard.sh:14}. The tests here check the code behavior (exit 2) {src:tests/hooks/test_security_fixes.py:312-316}.
- **Gap: no test for the attached split-string form.** The helper also accepts `-SSTRING` with no space {src:hooks/git_ask_before_run.py:128-129}, but none of the four test shapes uses it {src:tests/hooks/test_security_fixes.py:103-106}.
- **Gap: no test for unreadable input on the push or commit guard.** Only the read-only guard is tested for exit 2 {src:tests/hooks/test_security_fixes.py:207-208}; the fail-closed loop does not list `git_push_guard.sh` or `git_commit_guard.sh` {src:tests/hooks/test_security_fixes.py:300-301}.
- **Tests that cannot tell an allow from a crash.** `decision()` returns an empty string whenever stdout is empty, whatever the exit code {src:tests/hooks/test_security_fixes.py:43-44}. The allowed-form checks assert an empty verdict {src:tests/hooks/test_security_fixes.py:189} and the not-a-push and placeholder checks assert empty stdout {src:tests/hooks/test_security_fixes.py:125} {src:tests/hooks/test_security_fixes.py:342}, so a hook that crashed with exit 1 and printed only to stderr would pass them. The two cases that also check the exit code are the write guard {src:tests/hooks/test_security_fixes.py:309} and the secret guard {src:tests/hooks/test_security_fixes.py:281}.
- **Tests that read source text.** `test_documented_as_a_speed_bump` and `PrePushRiskDocumented` fail only if a comment or a docs sentence is removed {src:tests/hooks/test_security_fixes.py:294-295} {src:tests/hooks/test_security_fixes.py:414-417}; they do not test behavior.
- **Not covered here: `git diff --no-index`.** v1 also denies that flag, its abbreviations and a diff of two paths outside the repo {src:hooks/git_ask_before_run.py:407-411}; none of the 21 denied commands above uses them, and the cases are in [test_git_readonly_no_index](test_git_readonly_no_index.md).
- **Allowed config write.** The test file treats a `git config user.email` write as allowed {src:tests/hooks/test_security_fixes.py:186}; the read-only guard only blocks keys that match the dangerous pattern {src:hooks/git_ask_before_run.py:420}.
- **Version and machine dependence.** `git_ask_before_run.py` uses `str.removeprefix`, which needs Python 3.9 or newer {src:hooks/git_ask_before_run.py:273}; the 3.12 minimum covers that. The test imports that module at load {src:tests/hooks/test_security_fixes.py:29}, so on a Python older than 3.9 (below the minimum) the whole file would fail to import. `git init -b main` needs git 2.28 or newer {src:tests/hooks/test_security_fixes.py:67}. The registry file next to `scrub_secrets.py` or an exported `SCRUB_REGISTRY_PATH` can add patterns {src:hooks/scrub_secrets.py:120-124}; `run()` only strips `TOLLGATE_` variables {src:tests/hooks/test_security_fixes.py:33}, so a caller's `SCRUB_REGISTRY_PATH` would reach these tests.
- **Three lists of secret patterns, two of them partly shared.** The pattern lists live in `scrub_secrets.py` {src:hooks/scrub_secrets.py:50-77}, `post-tool-bash-scan-secrets.py` {src:hooks/post-tool-bash-scan-secrets.py:37-68} and `pre-commit-secrets` {src:hooks/pre-commit-secrets:9-33}. In v1 the output scanner imports twelve of the newer shapes from `scrub_secrets.py` and puts them first {src:hooks/post-tool-bash-scan-secrets.py:20} {src:hooks/post-tool-bash-scan-secrets.py:72-77}, but the shell hook keeps its own copy, and the label for the Atlassian shape still differs between the first two ({src:hooks/scrub_secrets.py:53} versus {src:hooks/post-tool-bash-scan-secrets.py:40}). Only the Plane and JSON shapes are checked across all three here.
- **Inputs reaching paths, commands, network or outbound text without a check.** In the code under test, the repo path read from the command text (`git -C <path>`) is handed to `git -C` for `rev-parse`, `diff --cached` and `log` with no check on the value {src:hooks/git_ask_before_run.py:175} {src:hooks/git_ask_before_run.py:446} {src:hooks/git_ask_before_run.py:220}; the call uses a list, not a shell. Whether git can run code from a hostile repo config through those read commands is [uncertain] and was not tested. In the test file, the only values used as paths or commands are the throwaway repo paths made by `tempfile` {src:tests/hooks/test_security_fixes.py:64-66} and the hook paths {src:tests/hooks/test_security_fixes.py:34}.
- **Writes to shared files.** Importing the hook module with `sys.path` set to `hooks/` makes Python write `hooks/__pycache__` in the repo {src:tests/hooks/test_security_fixes.py:27-29}; that write is not atomic and nothing stops two parallel runs from writing it at once. All other files live in temporary folders removed by `cleanup` {src:tests/hooks/test_security_fixes.py:73-74}.
