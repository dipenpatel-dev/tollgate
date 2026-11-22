---
doc_type: test
repo: "tollgate"
source_file: "tests/scripts/core/test_tg_ticket_dir.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
covers: [scripts/core/tg_ticket_dir]         # source files under test, relative paths from repo root
tags: []
links: []
---

## Purpose

This file tests the `tg_ticket_dir` command, which prints the folder of one ticket. It runs the command as a separate process in a throwaway home and checks the printed folder and the exit code for a nested ticket, a flat ticket, a missing ticket, a malformed key, a vault that is not set up, and a wrong number of arguments {src:tests/scripts/core/test_tg_ticket_dir.py:36-83}.

## Dependencies

**Depends on.**
- Standard library imports, as written: `os`, `pathlib`, `subprocess`, `sys`, `unittest` {src:tests/scripts/core/test_tg_ticket_dir.py:10-14}.
- `throwaway_home` from the harness {src:tests/scripts/core/test_tg_ticket_dir.py:19}: [[throwaway_home]] and [throwaway_home](../../harness/throwaway_home.md). The harness folder is put on the import path first {src:tests/scripts/core/test_tg_ticket_dir.py:17}.
- The `tg_ticket_dir` command, run as a separate process {src:tests/scripts/core/test_tg_ticket_dir.py:21} {src:tests/scripts/core/test_tg_ticket_dir.py:25}: [[tg_ticket_dir]] and [tg_ticket_dir](../../../scripts/core/tg_ticket_dir.md).

**Used by.**
- Product code: none. Searched with `git grep` for `test_tg_ticket_dir` outside `docs/` on 2026-11-20; the only hit is this file's own header, so nothing else names it.
- Found at run time by `unittest discover` in the folder runner {src:tests/scripts/core/run.sh:6}, which the end-to-end runner calls {src:tests/system/run.sh:23}.
- Tests: this file is itself a test.

## Behavior

**Helpers.** `run_cli(env, *args)` starts the command with the current Python and `-B`, the given environment, and the given arguments, capturing output as text {src:tests/scripts/core/test_tg_ticket_dir.py:25-26}. `tickets_root(env)` builds `<TOLLGATE_KNOWLEDGE>/02-tickets` and creates it {src:tests/scripts/core/test_tg_ticket_dir.py:30-31}. The folder name `02-tickets` is the loader's default for `tickets` {src:scripts/core/paths.py:35}.

**Class `TgTicketDirCli`.** Each test uses a fresh throwaway home {src:tests/scripts/core/test_tg_ticket_dir.py:37}.
- `test_prints_nested_folder`: with `PROJ/PROJ-312` made, `PROJ-312` exits 0, prints that folder, and writes nothing to stderr {src:tests/scripts/core/test_tg_ticket_dir.py:39-44}. The command's nested lookup backs this {src:scripts/core/paths.py:251-261}.
- `test_prints_flat_folder`: with `T-1` made directly under the tickets folder, `T-1` exits 0 and prints it {src:tests/scripts/core/test_tg_ticket_dir.py:49-53} {src:scripts/core/paths.py:248-250}.
- `test_missing_ticket_exits_1_with_not_found`: with no ticket, `PROJ-9` exits 1, stderr holds "not found", stdout is empty {src:tests/scripts/core/test_tg_ticket_dir.py:58-61} {src:scripts/core/tg_ticket_dir:27-29}.
- `test_bad_key_is_not_found`: the key `../etc` exits 1 with "not found" {src:tests/scripts/core/test_tg_ticket_dir.py:66-68}. The finder refuses a key that is not letters, a hyphen and digits {src:scripts/core/paths.py:245-246}.
- `test_not_set_up_exits_1`: with `TOLLGATE_KNOWLEDGE` removed, `PROJ-1` exits 1, stderr holds "not set up", stdout is empty {src:tests/scripts/core/test_tg_ticket_dir.py:72-76} {src:scripts/core/tg_ticket_dir:24-26} {src:scripts/core/paths.py:100}.
- `test_usage_error_with_no_or_extra_arguments`: no argument, and two arguments, both exit 2 with "usage" in stderr {src:tests/scripts/core/test_tg_ticket_dir.py:80-83} {src:scripts/core/tg_ticket_dir:19-21}. Unlike the `tg_path` tests, this covers the extra-argument case.

**Comparing paths.** The two success tests compare real paths of the printed folder and the expected folder {src:tests/scripts/core/test_tg_ticket_dir.py:42-43} {src:tests/scripts/core/test_tg_ticket_dir.py:52-53}. This avoids a failure from the macOS `/var` to `/private/var` link.

**Run as a file.** The `__main__` guard calls `unittest.main()` {src:tests/scripts/core/test_tg_ticket_dir.py:86-87}.

## Diagram

None: the fixtures are one throwaway home per test, with no mock chains.

## Notes

- **Code and description.** The header says the file tests the `tg_ticket_dir` command {src:tests/scripts/core/test_tg_ticket_dir.py:3}. That matches what it runs. The `date:` header line is empty {src:tests/scripts/core/test_tg_ticket_dir.py:5}.
- **Not tested.** Searched the file for these cases on 2026-11-20 and found none: a prefix folder in a different letter case (`ex` for `EX-4`), flat winning over nested when both exist, a symlink that points outside the tickets folder, a key with a trailing newline, and a malformed key while the vault is not set up. The finder behind them is covered in [[test_paths]] / [test_paths](test_paths.md) for the first four {src:tests/scripts/core/test_paths.py:255-256} {src:tests/scripts/core/test_paths.py:250-252} {src:tests/scripts/core/test_paths.py:269-276}; the trailing newline and the last case have no test I found.
- **Weak checks.** Only the nested test asserts that stderr is empty {src:tests/scripts/core/test_tg_ticket_dir.py:44}. The flat test does not.
- **Environment isolation.** Every test passes the throwaway environment to the child process {src:tests/scripts/core/test_tg_ticket_dir.py:26}, which sets its own `TOLLGATE_PATHS` inside the throwaway home {src:tests/harness/throwaway_home.py:41}, so a real paths file does not leak in.
- **Machine and version dependence.** The expected folder name `02-tickets` is written as a literal {src:tests/scripts/core/test_tg_ticket_dir.py:30}, so a layout rename needs an edit here too. No special Python version is needed beyond what `paths.py` already needs.
- **Inputs that reach paths or commands.** The keys come from constants in the test {src:tests/scripts/core/test_tg_ticket_dir.py:40}. `subprocess.run` gets an argument list, so no shell is involved {src:tests/scripts/core/test_tg_ticket_dir.py:25}.
- **Writes to shared files.** Tests create folders only inside the throwaway home {src:tests/scripts/core/test_tg_ticket_dir.py:31} {src:tests/scripts/core/test_tg_ticket_dir.py:39}; each test owns its own home, and the harness removes it on exit {src:tests/harness/throwaway_home.py:59}.
