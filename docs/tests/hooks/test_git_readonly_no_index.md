---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/test_git_readonly_no_index.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["hooks/git_readonly_guard.sh", "hooks/git_ask_before_run.py"]         # source files under test, relative paths from repo root
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

This file tests the read-only git guard against one hole: `git diff` can print any file on disk when it is told to compare two paths without a repository, either with the `--no-index` flag or by being given two paths outside the repo. The tests check that both forms are denied and that ordinary `git diff` forms still pass {src:tests/hooks/test_git_readonly_no_index.py:5-6}. The guard runs as a separate process with a JSON payload on stdin. It has 5 tests in 1 class. It was not run while this page was written, so each claim says what a test asserts.

## Dependencies

**Depends on.**
- The wrapper `hooks/git_readonly_guard.sh`, started as an executable {src:tests/hooks/test_git_readonly_no_index.py:28}: [[git_readonly_guard]] and [git_readonly_guard](../../hooks/git_readonly_guard.md). The wrapper replaces itself with `python3 git_ask_before_run.py readonly` {src:hooks/git_readonly_guard.sh:20}.
- The decision code in `hooks/git_ask_before_run.py`: [[git_ask_before_run]] and [git_ask_before_run](../../hooks/git_ask_before_run.md).
- The `git` program: one test class makes a throwaway repo with `git init` {src:tests/hooks/test_git_readonly_no_index.py:49}, and the hook itself runs `git rev-parse --show-toplevel` {src:hooks/git_ask_before_run.py:396}.
- Standard library only: `json`, `os`, `subprocess`, `tempfile`, `unittest` {src:tests/hooks/test_git_readonly_no_index.py:16-20}.

**Used by.** Product code: none. Tests: the unit test step of the hook runner finds it by the pattern `test_*.py` {src:tests/hooks/run.sh:198}, and CI runs the same command {src:.github/workflows/tests.yml:35}. Its header gives the command `python3 -m unittest tests/hooks/test_git_readonly_no_index.py` {src:tests/hooks/test_git_readonly_no_index.py:11}. Searched 2026-11-21: the whole worktree except `.git`, `docs/`, caches and virtual environments for `test_git_readonly_no_index`; no other file names it.

## Behavior

**Setup.** `run_guard` builds a payload with `tool_name`, `cwd` and the command, starts the wrapper with that payload and runs it in the folder given {src:tests/hooks/test_git_readonly_no_index.py:26-29}. `verdict` turns the result into a word: `exitN` for a non-zero exit, an empty string for no output, otherwise the `permissionDecision` {src:tests/hooks/test_git_readonly_no_index.py:32-38}. Class setup makes a temp folder with a `repo` folder (initialised, with `a.txt`) and an `outside` folder holding `note.txt` {src:tests/hooks/test_git_readonly_no_index.py:44-54}. The hook takes its base folder from the payload `cwd`, or from the process folder when `cwd` is absent {src:hooks/git_ask_before_run.py:427}.

**Flag form (1 test, 8 commands).** Every command must give `deny` when run from the repo {src:tests/hooks/test_git_readonly_no_index.py:60-69}.
- The spellings are `--no-index`, `--no-index=1`, and the shortened `--no-in` and `--no-inde`; the flag after `--stat`; the flag after `git -C <repo>`; the command inside `sh -c`; and the command after `echo hi &&` {src:tests/hooks/test_git_readonly_no_index.py:61-68}.
- The hook accepts a token as the flag when, with anything after `=` removed, it is at least 7 characters long and is a start of `--no-index` {src:hooks/git_ask_before_run.py:366} {src:hooks/git_ask_before_run.py:371-372}. A diff with such a token is denied with a reason that says it prints any file on disk {src:hooks/git_ask_before_run.py:407-409}.
- The `git -C` option, the `sh -c` body and the `&&` chain are found by the shared command parser, not by code in this check {src:hooks/git_ask_before_run.py:174-176} {src:hooks/git_ask_before_run.py:204-208} {src:hooks/git_ask_before_run.py:196}.

**Two paths outside the repo (1 test, 5 commands).** Without the flag, git compares two files by itself when both paths are outside the repo. The five commands are a diff of `/dev/null` and a file outside, the same outside file twice, two paths under `~/.ssh`, `$HOME/.env` with `/dev/null`, and the same pair after `--`; each must give `deny` {src:tests/hooks/test_git_readonly_no_index.py:71-77}.
- The hook takes the non-flag words of the diff, dropping a bare `--`, and does nothing when fewer than two remain {src:hooks/git_ask_before_run.py:392-394}. It asks git for the repo top level and denies when both of the first two words are outside it {src:hooks/git_ask_before_run.py:395-398} {src:hooks/git_ask_before_run.py:410-411}.
- A word is outside when it contains `$` or starts with a backtick, which is why `$HOME/.env` counts without being expanded {src:hooks/git_ask_before_run.py:377-378}. Otherwise `~` is expanded, the path is joined to the base folder, symlinks are resolved, and the result is compared with the top level {src:hooks/git_ask_before_run.py:379} {src:hooks/git_ask_before_run.py:382-383}. An unknown top level counts as outside {src:hooks/git_ask_before_run.py:380-381}.

**Outside any repo (1 test).** From the `outside` folder, `git diff a b` is denied {src:tests/hooks/test_git_readonly_no_index.py:79-80}. Git gives no top level there, so the hook treats both words as outside {src:hooks/git_ask_before_run.py:396} {src:hooks/git_ask_before_run.py:380-381}.

**Ordinary forms stay allowed (1 test, 15 commands).** Each gives an empty verdict from the repo {src:tests/hooks/test_git_readonly_no_index.py:82-88}.
- Thirteen are `git diff` forms, one is `git log` and one is `git status`: `git diff`, `--stat`, `HEAD~1`, `--cached --name-only`, `HEAD~1 HEAD`, `main..feature`, `-- a.txt`, `HEAD -- a.txt`, `a.txt a.txt`, `--no-color`, `--no-prefix`, `--no-renames`, a diff of one outside file, `git log --no-merges` and `git status` {src:tests/hooks/test_git_readonly_no_index.py:83-87}.
- The three flags that start with `--no-` are not prefixes of `--no-index`, so they pass the flag check {src:hooks/git_ask_before_run.py:371-372}. A diff with one path word is never treated as the two-path form {src:hooks/git_ask_before_run.py:393-394}. Two words that resolve inside the repo are not outside {src:hooks/git_ask_before_run.py:383}. The no-index check applies only to the verb `diff`, so `git log --no-merges` skips it {src:hooks/git_ask_before_run.py:407}.

**Unreadable payload (1 test).** The input `not json` exits 2 {src:tests/hooks/test_git_readonly_no_index.py:90-93}. The hook blocks on JSON that cannot be read {src:hooks/git_ask_before_run.py:462-464}.

## Diagram

No diagram: each case is one process with one payload against one temp folder, and there are no mocks.

## Notes

**Cases not tested.**
- A `--no-index` spelling of 6 characters or fewer is not tried, and the hook does not treat one as the flag {src:hooks/git_ask_before_run.py:366} {src:hooks/git_ask_before_run.py:372}.
- The flag check reads every argument, including words after a bare `--`, so a file literally named `--no-index` after `--` would also be denied {src:hooks/git_ask_before_run.py:408}. No test uses such a name (searched the test file for `-- --no`, 2026-11-21).
- Only the first two non-flag words are looked at, and a word that is the value of an option counts as a word {src:hooks/git_ask_before_run.py:392} {src:hooks/git_ask_before_run.py:397}. No test puts an option with a separate value before the paths.
- A path inside the repo that is a symlink to a place outside is resolved and counts as outside {src:hooks/git_ask_before_run.py:379} {src:hooks/git_ask_before_run.py:383}. No test makes such a link.
- The wrapper's own `-c` and `--output` denials are covered in [test_security_fixes](test_security_fixes.md), not here.

**Description against code.** The scope text at the top of `hooks/git_ask_before_run.py` says the readonly mode denies `--no-index` and a diff of two paths outside the repo {src:hooks/git_ask_before_run.py:9-11}; the code does that for the verb `diff` only {src:hooks/git_ask_before_run.py:407}. The wrapper header at `hooks/git_readonly_guard.sh` does not list the new denials {src:hooks/git_readonly_guard.sh:4-7}; the code behind it does deny them. No test checks the header text.

**Inputs without a check.** The repo path taken from `git -C <path>` and each path word of a diff are handed to `os.path.realpath` and, for the repo path, to `git -C <path> rev-parse --show-toplevel` with no check on their value {src:hooks/git_ask_before_run.py:175} {src:hooks/git_ask_before_run.py:379} {src:hooks/git_ask_before_run.py:396}. The git call is a list, not a shell {src:hooks/git_ask_before_run.py:220}, and has a 5 second limit {src:hooks/git_ask_before_run.py:42} {src:hooks/git_ask_before_run.py:221}. Whether git can run code from a hostile repo's config during that read is [uncertain] and not tested. In the test file the only values used as paths are paths made by `tempfile` and a few fixed strings.

**Shared writes.** The tests write only inside their own temp folder, removed in class teardown {src:tests/hooks/test_git_readonly_no_index.py:56-58}. Nothing is written to a shared file.

**Machine dependence.** The tests need `git` on the path and the execute bit on the wrapper {src:tests/hooks/test_git_readonly_no_index.py:28}. `~/.ssh/id_x` in the test is only a text argument; the hook never opens it, and denial does not depend on the file existing {src:tests/hooks/test_git_readonly_no_index.py:74}.
