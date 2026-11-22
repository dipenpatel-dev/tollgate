---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/hooks/test_git_hooks.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers:            # source files under test, relative paths from repo root
  - hooks/git_commit_guard.sh
  - hooks/git_push_guard.sh
  - hooks/git_readonly_guard.sh
  - hooks/git_ask_before_run.py
  - hooks/co_authored_by_check.sh
  - hooks/guard_worktree_remove.sh
  - hooks/gh_pr_create_detect.py
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

This file tests the git and pull request guard hooks: the commit and push guards that ask the owner before a commit or push, the push rule that denies a protected branch, the check that rejects a commit message with an AI attribution line, the guard that stops removal of an unmerged worktree, and the detector for `gh pr create` {src:tests/hooks/test_git_hooks.py:4-6}. Each hook runs as its own process and the tests read the JSON decision it prints. Most cases run against a real throwaway git repository.

## Dependencies

**Depends on.** The commit and push wrappers [[git_commit_guard]] and [git_commit_guard](../../hooks/git_commit_guard.md), [[git_push_guard]] and [git_push_guard](../../hooks/git_push_guard.md), the shared helper they call, [[git_ask_before_run]] and [git_ask_before_run](../../hooks/git_ask_before_run.md) {src:hooks/git_commit_guard.sh:18} {src:hooks/git_push_guard.sh:18}, the read-only guard [[git_readonly_guard]] and [git_readonly_guard](../../hooks/git_readonly_guard.md) {src:tests/hooks/test_git_hooks.py:89-90}, [[co_authored_by_check]] and [co_authored_by_check](../../hooks/co_authored_by_check.md) {src:tests/hooks/test_git_hooks.py:90}, [[guard_worktree_remove]] and [guard_worktree_remove](../../hooks/guard_worktree_remove.md) {src:tests/hooks/test_git_hooks.py:90}, and [[gh_pr_create_detect]] and [gh_pr_create_detect](../../hooks/gh_pr_create_detect.md) {src:tests/hooks/test_git_hooks.py:105}. Standard library: `json`, `os`, `subprocess`, `tempfile`, `unittest`. Outside programs: `git`, `bash`, `python3`.

**Used by.** No product code imports a test file. The folder is run by discovery on `test_*.py` (searched with `git grep -n -E "discover -s"`, 2026-11-20):
- Tests: `tests/hooks/run.sh` {src:tests/hooks/run.sh:198}, the CI workflow {src:.github/workflows/tests.yml:35}, and `tests/system/run.sh` {src:tests/system/run.sh:20}.

## Behavior

**Helpers and fixture.** `run` starts a hook script with the given text on standard input. It first drops every environment variable that starts with `TOLLGATE_`, then adds the ones the case asks for {src:tests/hooks/test_git_hooks.py:28-31}, so a value set on the developer machine cannot leak in. `bash_payload` builds a Bash tool payload with a working folder {src:tests/hooks/test_git_hooks.py:34-35}, and `decision` reads the `hookSpecificOutput` block from the output {src:tests/hooks/test_git_hooks.py:38-39}. The attribution line is joined from two parts so the source file does not hold the phrase whole {src:tests/hooks/test_git_hooks.py:25}. `RepoCase` makes a temp repo with `git init -b main`, one file and one commit, and removes it afterwards {src:tests/hooks/test_git_hooks.py:54-64}.

**Schema cases (SchemaTests).**
- A `git commit -m "msg"` gets an ask decision for the `PreToolUse` event, and the reason holds `draft message: msg` {src:tests/hooks/test_git_hooks.py:68-74}. The helper reads the first `-m` value and prints it as the draft {src:hooks/git_ask_before_run.py:228-237} {src:hooks/git_ask_before_run.py:300}.
- A push of a feature branch also gets an ask decision {src:tests/hooks/test_git_hooks.py:76-81}.
- `git status` makes both guards print nothing and exit 0 {src:tests/hooks/test_git_hooks.py:83-86}, because the helper looks only for the verb it was started for {src:hooks/git_ask_before_run.py:440-442} and returns 0 with no output {src:hooks/git_ask_before_run.py:469-470}.
- Fail closed: five scripts (commit guard, push guard, read-only guard, attribution check, worktree guard) are each fed `not json`, empty input and `[]`. Each must exit 2 with nothing on standard output and some text on standard error {src:tests/hooks/test_git_hooks.py:88-94}. In the helper, bad JSON and a non-object payload return 2 with a warning {src:hooks/git_ask_before_run.py:461-467}; the attribution check and the worktree guard print a `BLOCKED` line and exit 2 {src:hooks/co_authored_by_check.sh:28-31} {src:hooks/guard_worktree_remove.sh:27-30}.
- A commit message with the attribution line gets a deny decision {src:tests/hooks/test_git_hooks.py:96-101} {src:hooks/co_authored_by_check.sh:42-50}.
- `gh pr create` detection: a plain call and one inside `bash -c` print `yes`; the same words inside a commit message, and `gh pr list`, print `no` {src:tests/hooks/test_git_hooks.py:103-109}. The detector finds a `gh` word followed by `pr create` {src:hooks/gh_pr_create_detect.py:70}, looks inside a string passed to a shell with `-c` {src:hooks/gh_pr_create_detect.py:59-61} {src:hooks/gh_pr_create_detect.py:72-74}, and a commit message is one token that no shell flag precedes, so it is not opened.

**Push guard cases (PushGuardTests).**
- Six pushes to `main` are denied and each reason mentions a pull request: `git push origin main`, `origin HEAD:main`, `origin feature:refs/heads/main`, `-u origin main`, a bare `git push` on the main branch, and `--all origin` {src:tests/hooks/test_git_hooks.py:116-122}. The helper strips a leading `+` and keeps the part after the last colon {src:hooks/git_ask_before_run.py:272}, removes a `refs/heads/` start {src:hooks/git_ask_before_run.py:273}, maps `HEAD` to the current branch {src:hooks/git_ask_before_run.py:274}, uses the current branch when no refspec is given {src:hooks/git_ask_before_run.py:275-276}, and treats `--all` and `--mirror` as the whole repo {src:hooks/git_ask_before_run.py:258} {src:hooks/git_ask_before_run.py:284-285}. The deny text says to open a pull request {src:hooks/git_ask_before_run.py:450}.
- A push of `feature/x` asks {src:tests/hooks/test_git_hooks.py:124-126}.
- The protected list comes from `TOLLGATE_PROTECTED_BRANCHES`: with `release trunk`, `trunk` is denied and `main` only asks {src:tests/hooks/test_git_hooks.py:128-131} {src:hooks/git_ask_before_run.py:250-253}.
- `TOLLGATE_ALLOW_PROTECTED_PUSH=1` turns the deny for `main` into an ask {src:tests/hooks/test_git_hooks.py:133-135} {src:hooks/git_ask_before_run.py:444}.
- `--force` adds a `FORCE PUSH FLAG` line to the ask text {src:tests/hooks/test_git_hooks.py:137-139} {src:hooks/git_ask_before_run.py:312-313}.
- In `git push origin feature/x && echo main` the word after `&&` is ignored: the result is an ask, not a deny {src:tests/hooks/test_git_hooks.py:141-143}. The helper cuts a command into segments at control operators {src:hooks/git_ask_before_run.py:101-109}. Had `main` been read as a refspec, the result would be a deny.

**Commit guard cases (CommitGuardTests).** With `b.txt` staged, the ask text lists `b.txt` {src:tests/hooks/test_git_hooks.py:147-152} {src:hooks/git_ask_before_run.py:295}. With `git -C <repo> commit` and a working folder of `/`, the ask text names the repo from `-C` {src:tests/hooks/test_git_hooks.py:154-156} {src:hooks/git_ask_before_run.py:174-176} {src:hooks/git_ask_before_run.py:443}.

**Attribution cases (CoAuthorTests).** The attribution line is denied in a plain commit and, in lower case, in a `git -C /r commit` {src:tests/hooks/test_git_hooks.py:163-165}; the hook matches ignoring case {src:hooks/co_authored_by_check.sh:40}. A clean commit is allowed with no output {src:tests/hooks/test_git_hooks.py:167-169}. An `echo` of the phrase is allowed, because only a command with `git` then `commit` is examined {src:tests/hooks/test_git_hooks.py:171-173} {src:hooks/co_authored_by_check.sh:36}.

**Worktree removal cases (WorktreeRemoveTests).** `make_worktree` adds a worktree on a new branch `feat`, and adds one commit there when it should be unmerged {src:tests/hooks/test_git_hooks.py:177-184}.
- Removing an unmerged worktree is denied with `not merged to main` {src:tests/hooks/test_git_hooks.py:186-191}. The guard checks with `merge-base --is-ancestor` {src:hooks/guard_worktree_remove.sh:68} and builds that message {src:hooks/guard_worktree_remove.sh:77}.
- Removing a merged worktree is allowed with no output {src:tests/hooks/test_git_hooks.py:193-196} {src:hooks/guard_worktree_remove.sh:68-70}.
- With `TOLLGATE_PROTECTED_BRANCHES=trunk` and a `trunk` branch, the message says `not merged to trunk` {src:tests/hooks/test_git_hooks.py:198-203}. The base branch is the first name in that list that exists {src:hooks/guard_worktree_remove.sh:53-61}.

## Diagram

None: each case starts one script and reads one JSON answer; the only fixture is a temp repo.

## Notes

- **Wrapper headers now match the code.** `git_commit_guard.sh` and `git_push_guard.sh` both say "exit 2 on unreadable input" {src:hooks/git_commit_guard.sh:12} {src:hooks/git_push_guard.sh:12}. They hand over to the helper, which returns 2 on bad input or an unexpected error {src:hooks/git_ask_before_run.py:459-464} {src:hooks/git_ask_before_run.py:483-486}, and this test expects exit 2 {src:tests/hooks/test_git_hooks.py:93}.
- **Code and description disagree, callers.** The helper header says it is called by the commit and push wrappers {src:hooks/git_ask_before_run.py:23}. The read-only wrapper calls it too {src:hooks/git_readonly_guard.sh:20}.
- **Header of this file.** It lists six hooks {src:tests/hooks/test_git_hooks.py:5-6}. The read-only guard is also run, but only in the fail closed loop {src:tests/hooks/test_git_hooks.py:89-90}. Its deny rules are not tested here (the rule tests live in `tests/hooks/test_security_fixes.py`, found by search 2026-11-20).
- **Machine and version dependence.** `git init -b main` needs git 2.28 or later {src:tests/hooks/test_git_hooks.py:58}. The first commit runs with the user's own git configuration plus fake author names {src:tests/hooks/test_git_hooks.py:47-50}, so a global setting such as forced commit signing could break the fixture {src:tests/hooks/test_git_hooks.py:61}. The code under test uses `str.removeprefix`, which needs Python 3.9 {src:hooks/git_ask_before_run.py:273}; the 3.12 minimum covers that. The test file itself uses `dict | None` only in annotations {src:tests/hooks/test_git_hooks.py:28}. The future import {src:tests/hooks/test_git_hooks.py:15} was kept from when the minimum was 3.9 and made that safe then; it is not needed on 3.12. The scripts are started directly, so they need the execute bit.
- **Cases that cannot fail for one reason.** `test_HOK_02_guards_silent_on_other_commands` checks silence for `git status` only {src:tests/hooks/test_git_hooks.py:85}; a guard that was silent for every command would pass it, and the ask cases elsewhere cover the other side.
- **Not tested here.** The `readonly` rules, shell wrappers such as `env`, `sudo` or `eval` hiding a push {src:hooks/git_ask_before_run.py:133-159}, and an unbalanced quote fallback {src:hooks/git_ask_before_run.py:93-98}.
- **Inputs without a check (hooks).** The repo folder, taken from a `-C` value or the payload folder, goes to `git -C` with no check {src:hooks/git_ask_before_run.py:443} {src:hooks/git_ask_before_run.py:220}. The worktree guard takes the last path-like word of the command and runs `git -C` on it with no check {src:hooks/guard_worktree_remove.sh:38} {src:hooks/guard_worktree_remove.sh:45}. The raw command text is copied into the text shown to the owner {src:hooks/git_ask_before_run.py:321}. In this test file all of these values are constants or the temp folder.
- **Shared file writes.** The tests write only inside the temp folder (`a.txt`, `b.txt`, `n.txt`, the worktree) {src:tests/hooks/test_git_hooks.py:59} {src:tests/hooks/test_git_hooks.py:148} {src:tests/hooks/test_git_hooks.py:181}, removed in `tearDown` {src:tests/hooks/test_git_hooks.py:63-64}. No hook under test writes a shared file.
