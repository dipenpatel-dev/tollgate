---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/hooks/test_secret_command_guard.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers:            # source files under test, relative paths from repo root
  - hooks/secret-command-guard.sh
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

Unit tests for the Bash command guard, the hook that stops a command from printing a credential or a private key. Each test feeds the hook one command as a hook payload and checks whether the hook blocks it or lets it through. The hook is run as a real subprocess, so the tests exercise the script as Claude Code would.

## Dependencies

**Depends on.**
- `hooks/secret-command-guard.sh`: the script under test. Vault copy: [[secret-command-guard]]. Repo copy: [secret-command-guard](../../hooks/secret-command-guard.md).
- Standard library: `json`, `os`, `subprocess`, `unittest`.
- At run time the hook itself needs `bash`, `python3`, `grep` and `sed` on the path {src:hooks/secret-command-guard.sh:30} {src:hooks/secret-command-guard.sh:55} {src:hooks/secret-command-guard.sh:128}.

**Used by.** No product code. Searched with `git grep` over the worktree outside `docs/` on 2026-11-20.
- The hook test runner finds this file with `unittest discover -p 'test_*.py'` {src:tests/hooks/run.sh:198}.
- The CI workflow runs the same discovery {src:.github/workflows/tests.yml:35}.
- Tests: this file is itself a test. Related test file [[test_security_fixes]] ([test_security_fixes](test_security_fixes.md)) adds more cases for the same hook.

## Behavior

**Harness.** The hook path is built from the test file location, two folders up then `hooks/secret-command-guard.sh` {src:tests/hooks/test_secret_command_guard.py:19}. `run()` wraps a command in a payload with `tool_name` Bash and `tool_input.command`, runs the hook directly with that payload on stdin, and captures text output {src:tests/hooks/test_secret_command_guard.py:22-24}. The hook is run as a program, not through an interpreter, so it needs its executable bit and its shebang line {src:hooks/secret-command-guard.sh:1}.

**Block contract.** A block means exit code 2 and the word BLOCKED on stderr. The hook's `block()` function writes that text and exits 2 {src:hooks/secret-command-guard.sh:47-52}. The helper `assertBlocked` checks both parts {src:tests/hooks/test_secret_command_guard.py:50-53}; `assertAllowed` checks exit 0 {src:tests/hooks/test_secret_command_guard.py:55-56}.

**First class, `SecretCommandGuard` (five cases).**
- `test_HOK_02_block_is_exit_2_with_stderr`: the command is the program name that lists the environment, written in two halves so the literal never sits in the source {src:tests/hooks/test_secret_command_guard.py:29}. It proves exit 2 plus BLOCKED {src:tests/hooks/test_secret_command_guard.py:30-31}, through the hook rule for an environment pipe or that program name {src:hooks/secret-command-guard.sh:74-76}.
- `test_HOK_03_blocks_inline_private_key_header`: a PEM header is assembled from parts and echoed to a file; exit 2 expected {src:tests/hooks/test_secret_command_guard.py:34-35}. The hook rule matches the header text case-insensitively {src:hooks/secret-command-guard.sh:61-63}.
- `test_blocks_key_file_read_but_not_public_key`: reading a private SSH key is blocked and reading the `.pub` file is allowed {src:tests/hooks/test_secret_command_guard.py:38-39}. The hook skips its first rule when `.pub` appears {src:hooks/secret-command-guard.sh:56} and strips `.pub` names before its last rule {src:hooks/secret-command-guard.sh:128}.
- `test_blocks_token_echo`: `echo $MY_API_TOKEN` exits 2 {src:tests/hooks/test_secret_command_guard.py:42}, through the echo rule {src:hooks/secret-command-guard.sh:84-86}.
- `test_allows_normal_command_and_empty`: `ls -la` and an empty command exit 0 {src:tests/hooks/test_secret_command_guard.py:45-46}. An empty command short-circuits to exit 0 {src:hooks/secret-command-guard.sh:43-45}.

**Second class, `SecretCommandGuardPatterns` (one case per rule family).**
- OS secret store: `security find-*-password ... -w` and `secret-tool lookup` are blocked, including inside `$(...)` {src:tests/hooks/test_secret_command_guard.py:59-62}. The same commands without the value flag, and `security list-keychains`, are allowed {src:tests/hooks/test_secret_command_guard.py:65-66}. The hook needs a flag cluster containing `w` or `g` {src:hooks/secret-command-guard.sh:89-92}; this file only exercises `-w`.
- `gh auth token` is blocked bare and inside `export T=$(...)`; `gh auth status` is allowed {src:tests/hooks/test_secret_command_guard.py:69-71} {src:hooks/secret-command-guard.sh:102-104}.
- Variable prints: quoted, braced and unquoted forms with names containing KEY, TOKEN, SECRET, PASSWORD or PASSWD are blocked, for `echo`, `printf`, `print` and `cat` {src:tests/hooks/test_secret_command_guard.py:74-80} {src:hooks/secret-command-guard.sh:107-109}. `$HOME`, `$PATH` and `${USER}` are allowed {src:tests/hooks/test_secret_command_guard.py:83-85}.
- Bare environment dumps: `env`, `env | sort`, `set`, `export -p`, `declare -p`, a dump after `&&`, and `set | less` are blocked {src:tests/hooks/test_secret_command_guard.py:88-94} {src:hooks/secret-command-guard.sh:117-118}. Allowed: `env FOO=1 python3 x.py`, `env -i bash -c true`, `set -euo pipefail`, `export FOO=bar` and a names-only dump `env | cut -d= -f1` {src:tests/hooks/test_secret_command_guard.py:97-101} {src:hooks/secret-command-guard.sh:113-116}.
- `.env` files: reading `.env`, `./app/.env`, `.env.local` and a quoted `config/.env` is blocked; `.env.example`, `ls -la .env` and `environment.md` are allowed {src:tests/hooks/test_secret_command_guard.py:104-110} {src:hooks/secret-command-guard.sh:122-126}.
- Private key files by name: a key path stored in a variable then read, `deploy.pem`, `server.key` and a bare `id_ed25519` path are blocked; a `.pub` file and `ls ~/.ssh` are allowed {src:tests/hooks/test_secret_command_guard.py:113-118} {src:hooks/secret-command-guard.sh:128-132}.
- Ten ordinary commands (`ls -la`, `git status`, `set -x`, `pwd` and others) all exit 0 {src:tests/hooks/test_secret_command_guard.py:121-123}.

## Diagram

Skipped: each test is one subprocess call with a literal payload; there are no mocks or fixture chains.

## Notes

- **Code versus description.** No disagreement found between the test names and what the hook does for the cases listed. The hook header calls itself a speed bump, not a security boundary {src:hooks/secret-command-guard.sh:7}, which matches the pattern-only tests here.
- **Untested hook rules in this file.** `ssh-keygen -y` {src:hooks/secret-command-guard.sh:65-67}, `databricks configure` {src:hooks/secret-command-guard.sh:70-72}, `security -g`, `dump-keychain` and the credential-file rule {src:hooks/secret-command-guard.sh:79-82} have no case here. The last three are covered in `tests/hooks/test_security_fixes.py` {src:tests/hooks/test_security_fixes.py:252-264}; the first two have no case anywhere (searched `tests/` with `git grep` for `ssh-keygen` and for `databricks` followed by `configure` on 2026-11-20, no hit).
- **Possible bypass, untested.** The names-only exemption is computed over the whole command text, and when it matches the environment-dump rule is skipped {src:hooks/secret-command-guard.sh:113-117}. By reading the code, a command that holds a bare `env` plus a separate `cut -d= -f1` anywhere would not be blocked by that rule. The only test for the exemption is the single pipeline at line 101 {src:tests/hooks/test_secret_command_guard.py:101}.
- **Can any test not fail?** Every assertion compares an exit code or a substring and would fail if the hook changed behavior. Weakest spot: the `.pub` allow case passes on exit 0 alone {src:tests/hooks/test_secret_command_guard.py:39}.
- **Machine and version dependence.** No machine paths: the hook path comes from `__file__` {src:tests/hooks/test_secret_command_guard.py:19}. `capture_output` needs Python 3.7 or newer {src:tests/hooks/test_secret_command_guard.py:24}. Needs `bash`, `python3` and `grep -E` on the path.
- **Inputs reaching paths, commands, network or outbound text.** None unchecked: command strings such as `cat ~/.ssh/...` are only text sent to the hook, which inspects them and never runs them {src:hooks/secret-command-guard.sh:55}. The only value used as a path is the hook location derived from the test file {src:tests/hooks/test_secret_command_guard.py:19}.
- **Writes to shared files.** None. The tests create no files and write nothing outside the subprocess pipes.
