---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/test_read_path_hook.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["hooks/pre-tool-read-ask-sensitive-path.py"]         # source files under test, relative paths from repo root
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

This file tests the hook that makes Claude Code ask before it reads a file whose path is on a sensitive list: `.env` files, `*.pem`, `*.key` and anything under an `.ssh` folder, plus extra patterns from an environment variable. It uses fake paths, because the hook looks at path text only {src:tests/hooks/test_read_path_hook.py:10}. It has 25 tests in 5 classes. It was not run while this page was written, so each claim says what a test asserts, not that it passes.

## Dependencies

**Depends on.**
- The hook under test, `hooks/pre-tool-read-ask-sensitive-path.py`: [[pre-tool-read-ask-sensitive-path]] and [pre-tool-read-ask-sensitive-path](../../hooks/pre-tool-read-ask-sensitive-path.md). The test starts it as an executable file with a JSON payload on stdin {src:tests/hooks/test_read_path_hook.py:24} {src:tests/hooks/test_read_path_hook.py:35}.
- The environment variable `TOLLGATE_SENSITIVE_PATHS`. The test helper removes it from the child environment and sets it only when a test passes a value {src:tests/hooks/test_read_path_hook.py:25} {src:tests/hooks/test_read_path_hook.py:30-32}. One test sets `PYTHONPATH` for the child {src:tests/hooks/test_read_path_hook.py:33-34}.
- Standard library only: `json`, `os`, `subprocess`, `tempfile`, `unittest`.

**Used by.** Product code: none. Tests: the unit test step of the hook runner finds it by the pattern `test_*.py` {src:tests/hooks/run.sh:198}, and the CI workflow runs the same command {src:.github/workflows/tests.yml:35}. Searched 2026-11-20: the whole worktree except `.git`, `docs/`, caches and virtual environments for `test_read_path_hook`; the only hit outside the file was its own `Run:` line {src:tests/hooks/test_read_path_hook.py:12}.

## Behavior

**Setup.** `run` removes `TOLLGATE_SENSITIVE_PATHS` from the inherited environment, adds it back when a test gives a value, and runs the hook with no time limit {src:tests/hooks/test_read_path_hook.py:29-35}. `decision` reads the `permissionDecision` field of the hook output and treats empty output as no decision {src:tests/hooks/test_read_path_hook.py:42-45}. The hook has four default patterns {src:hooks/pre-tool-read-ask-sensitive-path.py:36}, adds the extra ones split on commas {src:hooks/pre-tool-read-ask-sensitive-path.py:51-56}, and checks both the typed path and the symlink resolved path {src:hooks/pre-tool-read-ask-sensitive-path.py:59-63}.

**DefaultList (8 tests).** These prove the built in list asks, and nothing else does.
- `.env`, `server.pem`, `server.key` and a file inside `.ssh` (also nested) each give `ask` {src:tests/hooks/test_read_path_hook.py:52-63} {src:hooks/pre-tool-read-ask-sensitive-path.py:66-72}.
- Upper case `SERVER.PEM` and `.ENV` still ask, because the hook lowers both the patterns and the path {src:tests/hooks/test_read_path_hook.py:65-67} {src:hooks/pre-tool-read-ask-sensitive-path.py:56} {src:hooks/pre-tool-read-ask-sensitive-path.py:63}.
- `src/main.py`, `README.md` and `notes/keys.md` exit 0 with no output {src:tests/hooks/test_read_path_hook.py:69-72}.
- Look alike names give no decision: `environment.md`, `env.md`, `pem.txt`, `monkey.txt`, a folder named `ssh` without the dot, and `my.ssh.notes` {src:tests/hooks/test_read_path_hook.py:74-78}. The name `monkey.txt` holds the letters `key` but not as the file extension, so it tests the `*.key` pattern {src:hooks/pre-tool-read-ask-sensitive-path.py:36}.
- The reason text holds `pattern: .env` and the event name is `PreToolUse` {src:tests/hooks/test_read_path_hook.py:80-84} {src:hooks/pre-tool-read-ask-sensitive-path.py:97-98}. The test name adds "never the content", but the path is fake and no file exists, so that part cannot fail; the hook itself never opens the file {src:hooks/pre-tool-read-ask-sensitive-path.py:75-81}.

**ExtraList (7 tests).** These prove the variable adds patterns and never removes one.
- A bare name `secrets.json` asks {src:tests/hooks/test_read_path_hook.py:91-92}. A folder pattern `exports/` asks at any depth {src:tests/hooks/test_read_path_hook.py:94-96} {src:hooks/pre-tool-read-ask-sensitive-path.py:68-70}.
- An absolute folder `/fake/data/exports/` asks there and gives no decision for `/fake/other/exports/` {src:tests/hooks/test_read_path_hook.py:98-100}.
- A glob with a slash is matched against the whole path: `/fake/data/raw/*` asks for `raw/a.csv` and not for `clean/a.csv` {src:tests/hooks/test_read_path_hook.py:102-104} {src:hooks/pre-tool-read-ask-sensitive-path.py:71-72}.
- A value of ` , ,` adds nothing, and spaces around a real entry are trimmed {src:tests/hooks/test_read_path_hook.py:106-108} {src:hooks/pre-tool-read-ask-sensitive-path.py:54} {src:hooks/pre-tool-read-ask-sensitive-path.py:56}.
- `.env` still asks when the variable is empty or set to something else {src:tests/hooks/test_read_path_hook.py:110-112}. The entry `!*.pem` does not stop `a.pem` from asking {src:tests/hooks/test_read_path_hook.py:114-115}. The hook has no negation syntax; `!*.pem` is just one more pattern {src:hooks/pre-tool-read-ask-sensitive-path.py:54-56}.

**SymlinkResolution (3 tests).** These use a real temp folder resolved with `realpath` {src:tests/hooks/test_read_path_hook.py:119-122}.
- A link named `notes.txt` that points at `server.pem` asks. Only the resolved path matches, so this test does prove the resolution step {src:tests/hooks/test_read_path_hook.py:124-129} {src:hooks/pre-tool-read-ask-sensitive-path.py:62}.
- A file inside a link named `.ssh` asks {src:tests/hooks/test_read_path_hook.py:131-137}. The typed path already contains `/.ssh/`, so it would ask even if the resolved form were dropped; the name `plain_folder` of the real target is never needed. This test cannot fail on the resolution step {src:hooks/pre-tool-read-ask-sensitive-path.py:70}.
- A link to an unlisted file gives no decision {src:tests/hooks/test_read_path_hook.py:139-144}.

**FailureModes (6 tests).** These prove the hook denies when it cannot decide.
- The inputs `not json`, an empty string, `[]` and `null` give `deny` {src:tests/hooks/test_read_path_hook.py:148-150} {src:hooks/pre-tool-read-ask-sensitive-path.py:84-90}. A `tool_input` that is a string gives `deny` too {src:tests/hooks/test_read_path_hook.py:152-153}.
- An error inside matching gives `deny` and the output holds the word `internally`. The test plants a `fnmatch.py` whose `fnmatchcase` raises, in a temp folder given as `PYTHONPATH` {src:tests/hooks/test_read_path_hook.py:155-161} {src:hooks/pre-tool-read-ask-sensitive-path.py:102-107}.
- A payload with no `tool_input`, an empty one, or an empty path exits 0 with no output {src:tests/hooks/test_read_path_hook.py:163-167} {src:hooks/pre-tool-read-ask-sensitive-path.py:92-93}.
- A `Grep` call on `.env` is not checked {src:tests/hooks/test_read_path_hook.py:169-171} {src:hooks/pre-tool-read-ask-sensitive-path.py:92}.
- Both `deny` and `ask` exit with code 0 {src:tests/hooks/test_read_path_hook.py:173-175} {src:hooks/pre-tool-read-ask-sensitive-path.py:48}.

**KnownLimits (1 test).** A `Bash` command `cat .../.env` produces no output, so Bash reads are not covered {src:tests/hooks/test_read_path_hook.py:179-181} {src:hooks/pre-tool-read-ask-sensitive-path.py:92}. The test pins today's limit: if the hook ever starts covering Bash it will fail and need an edit.

## Diagram

No diagram: every case is one child process with one payload.

## Notes

**Tests that look wrong or cannot fail.** `test_file_inside_symlinked_ssh_folder_asks` does not prove symlink resolution, and `test_reason_names_pattern_and_never_the_content` does not prove the absence of file content (see above) {src:tests/hooks/test_read_path_hook.py:131-137} {src:tests/hooks/test_read_path_hook.py:80-84}.

**Description against code.** The hook header says it does not cover Bash, Grep and Glob {src:hooks/pre-tool-read-ask-sensitive-path.py:22}. The tests pin Bash and Grep only. No test sends `Glob` or the `NotebookEdit` tool, and no test uses a `~` entry, which the hook expands {src:hooks/pre-tool-read-ask-sensitive-path.py:55} (searched `tests/hooks/test_read_path_hook.py` for `Glob` and `~`, 2026-11-20).

**Machine and version dependence.**
- The fake paths `/fake/project`, `/fake/home/user` and `/fake/data` must not exist as real folders or links on the machine, because the hook resolves them with `realpath` {src:tests/hooks/test_read_path_hook.py:26} {src:hooks/pre-tool-read-ask-sensitive-path.py:62}.
- The hook runs as a direct executable, so it needs its execute bit and `python3` on the path {src:hooks/pre-tool-read-ask-sensitive-path.py:1}. The symlink tests need `os.symlink` {src:tests/hooks/test_read_path_hook.py:128}.
- `test_internal_error_in_matching_denies` works because `PYTHONPATH` entries are searched before the standard library, and only if nothing imports `fnmatch` before the hook does. That depends on the Python build {src:tests/hooks/test_read_path_hook.py:157-159} {src:hooks/pre-tool-read-ask-sensitive-path.py:27}.
- Python 3.7 or newer is needed for `capture_output` {src:tests/hooks/test_read_path_hook.py:35}. The hook uses `X | None` and `tuple[str, ...]` only in annotations, which the future import keeps from being evaluated {src:hooks/pre-tool-read-ask-sensitive-path.py:25} {src:hooks/pre-tool-read-ask-sensitive-path.py:36}. The import was kept from when the minimum was 3.9; it is not needed on 3.12.
- `run` has no time limit, so a hung hook would hang the whole suite {src:tests/hooks/test_read_path_hook.py:35}.

**Inputs without a check, and shared writes.** The tests write only to their own temp folder {src:tests/hooks/test_read_path_hook.py:120-122}. No shared file is written.
