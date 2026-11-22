---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/core/test_paths.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/core/paths.py, scripts/core/tg_path, scripts/core/session_cost.py]         # source files under test, relative paths from repo root
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

This file tests the path loader, the module that turns logical folder names such as `tickets` or `output` into real folders, and the small command `tg_path` that prints one of them. It covers default folders, overrides from the paths file, the "not set up" errors, the vault layout table, and the helpers that find ticket folders. One test at the end is about the session cost tracker rather than the loader.

## Dependencies

**Depends on.**
- Standard library imports, as written: `os`, `pathlib`, `subprocess`, `sys`, `unittest` {src:tests/scripts/core/test_paths.py:10-14}; and `tempfile`, imported inside `TicketFolders.setUp` {src:tests/scripts/core/test_paths.py:235}.
- `throwaway_home` from the harness {src:tests/scripts/core/test_paths.py:20}: [[throwaway_home]] and [throwaway_home](../../harness/throwaway_home.md).
- `core.paths` {src:tests/scripts/core/test_paths.py:21}: [[paths]] and [paths](../../../scripts/core/paths.md).
- The `tg_path` command, run as a separate process {src:tests/scripts/core/test_paths.py:23} {src:tests/scripts/core/test_paths.py:41}: [[tg_path]] and [tg_path](../../../scripts/core/tg_path.md).
- `core.session_cost`, imported inside one test {src:tests/scripts/core/test_paths.py:227}: [[session_cost]] and [session_cost](../../../scripts/core/session_cost.md).
- `scripts/core/paths.py` run as a command with `dirs` {src:tests/scripts/core/test_paths.py:164}.

**Used by.**
- Product code: none. Searched with `git grep` for `test_paths` outside `docs/` on 2026-11-20. The hits are this file's header, a test method named `test_paths_file_line_renames_a_folder` in this file {src:tests/scripts/core/test_paths.py:149}, and unrelated names in other test files.
- Found at run time by `unittest discover` in the folder runner {src:tests/scripts/core/run.sh:6}, which the end-to-end runner calls {src:tests/system/run.sh:23}.
- Tests: this file is itself a test.

## Behavior

**Helpers.** `with_env(env)` replaces the whole process environment with a given dict and restores the saved one on exit {src:tests/scripts/core/test_paths.py:29-35}. `run_cli` starts `tg_path` with the current Python and `-B` and the given environment {src:tests/scripts/core/test_paths.py:41-42}.

**Class `LoaderDefaults`.**
- `test_defaults_from_knowledge` removes the paths file variable, then checks `vault` equals `TOLLGATE_KNOWLEDGE`, `tickets` is `<vault>/02-tickets`, `output`, `meetings`, `conversations` (`05-conversations`) and `references` sit under the vault, `state` equals `TOLLGATE_STATE_DIR`, `repos` equals `TOLLGATE_CODE_DIR`, and `cache`, `logs` and `index` sit under `<home>/.tollgate` {src:tests/scripts/core/test_paths.py:48-62}. The loader's tables back this {src:scripts/core/paths.py:32-43} {src:scripts/core/paths.py:50} {src:scripts/core/paths.py:103-111}.
- `test_state_default_without_env`: with `TOLLGATE_STATE_DIR` unset, `state` is `<home>/.tollgate/state` {src:tests/scripts/core/test_paths.py:66-69}. The loader builds it from `~`, so the test relies on the throwaway `HOME` {src:scripts/core/paths.py:94} {src:scripts/core/paths.py:105} {src:tests/harness/throwaway_home.py:34}.
- `test_get_all_lists_names`: `get_all()` returns every name in `NAMES` except `standards`, which has no default {src:tests/scripts/core/test_paths.py:74-76} {src:scripts/core/paths.py:113-115}.
- `test_unknown_name`: an unknown name raises `KeyError` {src:tests/scripts/core/test_paths.py:81-82} {src:scripts/core/paths.py:116}.

**Class `LoaderFile`** (the paths file is a list of `name: path` lines {src:scripts/core/paths.py:81-89}).
- `standards` raises `NotSetUp` until the file has a `standards:` line, then returns that folder {src:tests/scripts/core/test_paths.py:89-93}.
- A `references:` line moves that folder out of the vault {src:tests/scripts/core/test_paths.py:97-99}.
- A file with a comment line, a blank line, a quoted value and a trailing ` # note` overrides `tickets` and `output`; a name not in the file falls back to its default {src:tests/scripts/core/test_paths.py:104-111}. The loader skips comments, cuts the trailing note, and removes quotes {src:scripts/core/paths.py:83} {src:scripts/core/paths.py:86} {src:scripts/core/paths.py:87}.
- `~`, `$VAR` and `${VAR}` are expanded in values {src:tests/scripts/core/test_paths.py:116-121} {src:scripts/core/paths.py:59-60}.
- A paths file that does not exist is ignored {src:tests/scripts/core/test_paths.py:125-128} {src:scripts/core/paths.py:77-79}.
- With `TOLLGATE_KNOWLEDGE` unset, a `vault:` line in the file supplies the vault and `tickets` follows it {src:tests/scripts/core/test_paths.py:132-136}.

**Class `LoaderLayout`.**
- `folder_name` returns the layout table value for every key and `meetings` for `meetings`; an unknown key raises `KeyError` {src:tests/scripts/core/test_paths.py:143-147} {src:scripts/core/paths.py:191-192}.
- A `tickets:` line pointing at `<vault>/work-items` makes `folder_name("tickets")` return `work-items`, leaves `system_map` unchanged, and shows up in `layout_dirs()` {src:tests/scripts/core/test_paths.py:152-156} {src:scripts/core/paths.py:194-197}.
- `get_path("tickets", env)` uses the dict given instead of the process environment {src:tests/scripts/core/test_paths.py:160-161} {src:scripts/core/paths.py:124}.
- `test_layout_cli_lists_dirs` runs `paths.py dirs` and expects the tickets folder name and `<knowledge>/decisions` in the output {src:tests/scripts/core/test_paths.py:164-167}. The `dirs` command prints `layout_dirs()` {src:scripts/core/paths.py:321-322}. This test passes no `env` to the child process (see Notes).

**Class `LoaderNotSetUp`.**
- With `TOLLGATE_KNOWLEDGE` unset, `vault`, `tickets`, `output` and `meetings` all raise `NotSetUp` {src:tests/scripts/core/test_paths.py:173-177} {src:scripts/core/paths.py:100-102}.
- With `TOLLGATE_CODE_DIR` unset, `repos` raises `NotSetUp` {src:tests/scripts/core/test_paths.py:181-184} {src:scripts/core/paths.py:112}.
- `get_all()` leaves out `vault` when it cannot resolve but keeps `cache` {src:tests/scripts/core/test_paths.py:190-192} {src:scripts/core/paths.py:179-181}.

**Class `TgPathCli`.**
- A known name prints the path, exits 0, and prints nothing on stderr {src:tests/scripts/core/test_paths.py:198-202} {src:scripts/core/tg_path:23}.
- A name that cannot resolve exits 1 with "not set up" on stderr and nothing on stdout {src:tests/scripts/core/test_paths.py:206-210} {src:scripts/core/tg_path:24-26}.
- An unknown name also exits 1 with "not set up" {src:tests/scripts/core/test_paths.py:214-216}. That is the `KeyError` branch, which writes "not set up: unknown name" {src:scripts/core/tg_path:27-29}.
- No argument exits 2 with "usage" {src:tests/scripts/core/test_paths.py:220-222} {src:scripts/core/tg_path:19-21}.

**Class `SessionCostSlug`.** `derive_project_slug` turns `/a.b/c_d e` into `-a-b-c-d-e`, so every character that is not a letter or digit becomes a dash {src:tests/scripts/core/test_paths.py:228} {src:scripts/core/session_cost.py:55}.

**Class `TicketFolders`** (helpers in `paths.py` that find a ticket folder, flat as `<tickets>/KEY` or by prefix as `<tickets>/PREFIX/KEY`). `setUp` makes a temp `tickets` folder with its real path resolved {src:tests/scripts/core/test_paths.py:236-239}.
- Flat ticket found {src:tests/scripts/core/test_paths.py:242-243}; nested ticket found {src:tests/scripts/core/test_paths.py:246-247}; when both exist, flat wins {src:tests/scripts/core/test_paths.py:250-252} {src:scripts/core/paths.py:248-250}.
- A lower-case prefix folder `ex` matches key `EX-4` {src:tests/scripts/core/test_paths.py:255-256} {src:scripts/core/paths.py:257}.
- A missing ticket, or a missing root folder, gives `None` {src:tests/scripts/core/test_paths.py:259-260} {src:scripts/core/paths.py:253-255}.
- Eleven bad keys, including `"../x"`, `"PROJ-1/.."`, `"PROJ-1 "`, `"PROJ-1-2"` and `None`, give `None`, even with folders `x` and `S` present {src:tests/scripts/core/test_paths.py:263-266}. The key must be letters, a hyphen and digits {src:scripts/core/paths.py:203} {src:scripts/core/paths.py:245-246}.
- A flat ticket that is a symlink to a folder outside the tickets root is refused, and `iter_ticket_folders` yields nothing when both a symlinked ticket and a symlinked prefix folder point outside {src:tests/scripts/core/test_paths.py:269-276}. The check compares real paths {src:scripts/core/paths.py:207-214} {src:scripts/core/paths.py:278}. The test sets up the case `Q-1` under the symlinked prefix `Q` {src:tests/scripts/core/test_paths.py:273-275} but never asks `ticket_folder("Q-1")` directly.
- A symlink that stays inside the root is allowed, and the returned path keeps the symlink name {src:tests/scripts/core/test_paths.py:279-281}.
- `iter_ticket_folders` yields exactly `PROJ/PROJ-3`, `PROJ/PROJ-4`, `T-1`, `T-2` and `ex/EX-9` from a tree that also holds `notes`, `sprints`, `PROJ/archive`, `PROJ/T-5`, `PROJ/readme` and a plain file `PROJ-6` {src:tests/scripts/core/test_paths.py:284-288} {src:scripts/core/paths.py:276-291}. On a missing folder it yields nothing {src:tests/scripts/core/test_paths.py:291} {src:scripts/core/paths.py:273-275}.
- With no root given, the root is the loader's `tickets` path, and a `tickets:` line in the paths file is followed {src:tests/scripts/core/test_paths.py:296-299} {src:tests/scripts/core/test_paths.py:304-307} {src:scripts/core/paths.py:218}.
- `ticket_prefix_depth` returns 1 for `("PROJ","PROJ-312","PROJ-312-state.md")` and `("ex","EX-1","x.md")` and 0 for four other shapes {src:tests/scripts/core/test_paths.py:310-315} {src:scripts/core/paths.py:228-234}.
- `subdir_prefixes` keeps only names the layout lists: `clients` is kept and `products` dropped; `decisions` is kept {src:tests/scripts/core/test_paths.py:318-319} {src:scripts/core/paths.py:300-305}.
- `file_value("sessions")` returns the paths file line even though `sessions` is not a loader name, and `file_value("nothing")` returns `None` {src:tests/scripts/core/test_paths.py:323-326} {src:scripts/core/paths.py:140-141}.

## Diagram

None: the fixtures are one throwaway home or one temp folder per test, with no mock chains.

## Notes

- **Code and description.** The header says the file tests "the path loader and the tg_path command" {src:tests/scripts/core/test_paths.py:3}. One class tests `session_cost.derive_project_slug` {src:tests/scripts/core/test_paths.py:225-228}, which is outside that description. The test name says the slug "matches the rule claude code uses" {src:tests/scripts/core/test_paths.py:226}, but it only compares our function with a hand-written answer. It cannot show what Claude Code does; that claim is only a comment in the code {src:scripts/core/session_cost.py:54}.
- **Description vs behavior in `tg_path`.** The command says it exits 1 with "not set up" when it "cannot resolve" {src:scripts/core/tg_path:4}. A mistyped name also gets "not set up: unknown name" {src:scripts/core/tg_path:28}, and the test pins that wording {src:tests/scripts/core/test_paths.py:216}. A typo and a missing setup look the same to a caller.
- **Tests that depend on the real environment.** Two tests do not isolate the environment. `test_layout_cli_lists_dirs` runs the child with no `env` argument {src:tests/scripts/core/test_paths.py:164-165}, and `test_subdir_prefixes_only_name_layout_folders` has no `with_env` {src:tests/scripts/core/test_paths.py:317-319}. Both reach `folder_name`, which reads the paths file named by the real `TOLLGATE_PATHS` {src:scripts/core/paths.py:72} {src:scripts/core/paths.py:193}. A real paths file that renames `system_map` or `tickets` could fail them. The README claim that tests never touch real files {src:scripts/README.md:31} is true for writes but not for these reads.
- **Weak or missing checks.**
  - The bad-key test has no key with a trailing newline. The key pattern ends with `$` {src:scripts/core/paths.py:203}, which in Python also matches before a final newline; I read this and did not run it.
  - The `Q-1` symlink case sets up data but asserts only through `iter_ticket_folders` {src:tests/scripts/core/test_paths.py:276}.
  - The `layout` command of `paths.py` is not run; only `dirs` is {src:tests/scripts/core/test_paths.py:164} {src:scripts/core/paths.py:318-320}.
  - Expected values such as `02-tickets`, `05-conversations` and `01-system-map/clients/` are written as literals {src:tests/scripts/core/test_paths.py:52} {src:tests/scripts/core/test_paths.py:55} {src:tests/scripts/core/test_paths.py:318}, so a layout rename needs edits here too.
- **Machine and version dependence.** The state default and the `~` test depend on `HOME` pointing at the throwaway home {src:tests/harness/throwaway_home.py:34}. The macOS `/var` to `/private/var` link is handled by resolving the temp folder {src:tests/scripts/core/test_paths.py:238}. No special Python version is needed beyond what `paths.py` already needs.
- **Inputs that reach paths or commands.** Values written to the paths file come from a temp home or constants {src:tests/scripts/core/test_paths.py:91} {src:tests/scripts/core/test_paths.py:133}. In the loader, paths-file values and `TOLLGATE_*` variables become folder paths after expansion only, with no check on where they point {src:scripts/core/paths.py:59-60} {src:scripts/core/paths.py:126-127}. The ticket helpers do check keys and symlinks {src:scripts/core/paths.py:245-246} {src:scripts/core/paths.py:249}. No shell command is built from input in this file; `subprocess.run` gets argument lists {src:tests/scripts/core/test_paths.py:41-42}.
- **Writes to shared files.** Tests write only inside temp folders or throwaway homes (paths files, folders, symlinks) {src:tests/scripts/core/test_paths.py:105} {src:tests/scripts/core/test_paths.py:271} {src:tests/scripts/core/test_paths.py:280}. The paths-file writes are plain `write_text`, not atomic, and nothing prevents two writers, but each test owns its own file.
- **Header.** The `date:` field of the header is empty {src:tests/scripts/core/test_paths.py:5}.
