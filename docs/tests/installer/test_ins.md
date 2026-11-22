---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/installer/test_ins.sh    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "top-level body: sources helpers.sh, makes the repo copy, then runs cases INS-00 to INS-11 in order"    # function or line that executes when the script runs
requires:          # external commands or tools this script depends on
  - bash
  - python3
  - grep
  - find
  - ls
  - cmp
  - diff
  - cp
  - tar
  - touch
  - id
  - xargs
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

Installer tests INS-00 to INS-11. They run the real `install.sh` inside throwaway homes and check what it writes: files and folders, answers given by flags or by typed questions, a second run that changes nothing, a config file free of secrets, a settings backup that can be restored, names that must not run as code, the Linux path with no secret tool, the vault folder layout, the rule that Python 3.12 is the minimum, both for the Python that runs the installer and for an existing search environment, and the installer's handling of the installed commands, a repo path with a space, workspace and profile values with special characters, and the meetings folder.

## Dependencies

**Depends on.**
- [[helpers]] ([helpers](helpers.md)), sourced first {src:tests/installer/test_ins.sh:6}; it supplies `new_world`, `run_install`, `snapshot`, `normalise`, `json_equal`, `seed_user_settings` and `user_settings_survive`.
- `check`, `WORK` and `TOLLGATE_DIR` from the runner [[run]] ([run](run.md)) {src:tests/installer/test_ins.sh:2-3}.
- `install.sh`, its Python check {src:install.sh:143-153} and its search environment check {src:install.sh:172-183}, its flags `--non-interactive`, `--name`, `--vault`, `--initials`, `--ticket-prefix`, `--restore-settings` {src:install.sh:73-99}, its refusal of a repo path with whitespace {src:install.sh:160-165}, its rewrite of `$TOLLGATE_HOME/` in the installed commands {src:install.sh:1155}, its meetings folder lookup {src:install.sh:908-909}, and its escaping of the workspace path and the profile values {src:install.sh:1270} {src:install.sh:1525-1534}. Vault copy: [[install]]. Repo copy: [install](../../install.md).
- The real `python3` found on the path when INS-09 starts, which the version shim wraps {src:tests/installer/test_ins.sh:242}.
- `scripts/core/tg_path`, which INS-11 runs in the repo copy to learn the meetings folder {src:tests/installer/test_ins.sh:316}. Repo copy: [tg_path](../../scripts/core/tg_path.md).
- Programs listed in `requires`; `python3 -I` for JSON checks {src:tests/installer/test_ins.sh:37}.

**Used by.** Sourced by the installer runner {src:tests/installer/run.sh:97}, which CI runs {src:.github/workflows/tests.yml:38}. No product code uses it (searched with `git grep` outside `docs/`, 2026-11-20). Tests: this file is itself a test file.

## Behavior

Each case ends with `check DESCRIPTION CONDITION`.

- **INS-00.** The fake user name differs from `id -un` {src:tests/installer/test_ins.sh:12-13}.
- **INS-01, fresh install, non-interactive.** Exit 0 {src:tests/installer/test_ins.sh:18-19}; eight named files exist plus `tg-ticket.md`, and five vault folders and a workspace file under `Developer/` {src:tests/installer/test_ins.sh:21-32}; the paths file has exactly two lines (`references:` and `vault_git:`) and the connectors file is empty {src:tests/installer/test_ins.sh:33-36}; the settings `env` block holds the five `TOLLGATE_` values {src:tests/installer/test_ins.sh:37-47}; the shell profile exports initials, ticket prefix and paths {src:tests/installer/test_ins.sh:48-50}; hook commands point into the repo copy {src:tests/installer/test_ins.sh:51-52}; installed commands call `tg-search` by absolute path and the matching allow rule exists {src:tests/installer/test_ins.sh:55-58}; the stub keychain log is absent {src:tests/installer/test_ins.sh:59-60}.
- **INS-02, flags equal answers.** One home answers the questions from a file, another gives the same answers as flags {src:tests/installer/test_ins.sh:66-70}. Four files must match after replacing the home path, and both homes must hold the same set of files {src:tests/installer/test_ins.sh:73-80}. Initials with a digit exit 2 with nothing written {src:tests/installer/test_ins.sh:81-84}; a ticket prefix with a dash exits 2 {src:tests/installer/test_ins.sh:85-86}. `install.sh` rejects non-letters with exit 2 {src:install.sh:107-112}. A bad typed answer is asked again and the next one accepted {src:tests/installer/test_ins.sh:88-93}.
- **INS-03, second run changes nothing.** User settings are seeded {src:tests/installer/test_ins.sh:97}; the first run keeps them {src:tests/installer/test_ins.sh:100-102}; a snapshot before and after the second run must be identical {src:tests/installer/test_ins.sh:103-109}; exactly one Tollgate block in the profile {src:tests/installer/test_ins.sh:110-111}; each hook entry appears once {src:tests/installer/test_ins.sh:112-120}; exactly one settings backup exists {src:tests/installer/test_ins.sh:121-122}.
- **INS-04, config holds answers and no secret.** Fake secrets are built at run time and exported {src:tests/installer/test_ins.sh:128-131}. The config must hold the vault, initials and ticket prefix {src:tests/installer/test_ins.sh:135-138}, none of five files may contain a fake value {src:tests/installer/test_ins.sh:139-143}, every config line must be `NAME="value"` {src:tests/installer/test_ins.sh:144-145}, no key-like words {src:tests/installer/test_ins.sh:146-147}, and the file is not world writable {src:tests/installer/test_ins.sh:148-149}.
- **INS-05, settings backup and restore.** A backup equal to the original exists {src:tests/installer/test_ins.sh:154-160}; the merged file differs from it {src:tests/installer/test_ins.sh:161-162}; `--restore-settings` restores it byte for byte and keeps a `before-restore` copy {src:tests/installer/test_ins.sh:163-168}; a settings file that is not valid JSON is backed up unchanged and the install still exits 0 {src:tests/installer/test_ins.sh:170-175}.
- **INS-06, odd names are never run as code.** Six names, including `$(...)`, backticks, a quote and a semicolon, and a backslash, are saved by run one and read by run two {src:tests/installer/test_ins.sh:181-187}. A marker file must not appear, and the saved name read back by sourcing the config must equal the input {src:tests/installer/test_ins.sh:188-190}.
- **INS-07, Linux without `secret-tool`.** A stub `uname` reports Linux {src:tests/installer/test_ins.sh:198}. The install must exit 0, print the `sudo apt install libsecret-tools` hint, create no `.secrets` file, and write the fake token to no file {src:tests/installer/test_ins.sh:202-210}. `install.sh` prints that hint and skips storing {src:install.sh:266-267}.
- **INS-08, vault layout and references.** The vault must hold exactly a fixed list of 19 folders {src:tests/installer/test_ins.sh:216-218}; three old folders and `meetings` are not created {src:tests/installer/test_ins.sh:219-221}; a `*-library` folder exists and the paths file points at it {src:tests/installer/test_ins.sh:222-225}; the profile meetings path is `<vault>/meetings`, which is also what the path loader prints when the paths file has no `meetings:` line {src:tests/installer/test_ins.sh:226-227}; a second run neither overwrites nor reorders an existing paths file {src:tests/installer/test_ins.sh:229-232}; a missing `references:` line is added once after existing lines {src:tests/installer/test_ins.sh:234-238}.

- **INS-09, minimum Python is 3.12.** A `python3` shim is written that runs the real Python but, for `-c` checks only, makes `sys.version_info` report the version in `FAKE_PY_MAJOR` and `FAKE_PY_MINOR` {src:tests/installer/test_ins.sh:241-252}. The runner is pointed at it through `RUN_PATH` {src:tests/installer/test_ins.sh:255}. With minor 11 the install exits 1 and prints `Tollgate needs Python 3.12 or newer, found 3.11` {src:tests/installer/test_ins.sh:255-257}; the installer prints that line and exits 1 {src:install.sh:148-152}. A refused run must leave no vault folder and no `settings.json` {src:tests/installer/test_ins.sh:258-259}. With minor 12 the install exits 0 and the message is absent {src:tests/installer/test_ins.sh:262-264}.
- **INS-10, an existing search environment must also be 3.12 or newer.** `_make_old_venv` writes a stub `venv/bin/python3` in the throwaway home that reports the given minor version for `-c` checks {src:tests/installer/test_ins.sh:268-274}. With minor 11 and `--non-interactive` the install exits 1 with `existing search environment uses 3.11: delete <home>/.tollgate/state/venv and re-run` {src:tests/installer/test_ins.sh:276-280}. The refused run must leave no vault, no `settings.json`, no paths file, and the stub venv still in place {src:tests/installer/test_ins.sh:281-282}. With minor 12 the install exits 0 without that message {src:tests/installer/test_ins.sh:284-288}. A third case drives the menu from a typed-answers file (Enter, Enter, `f`, which is the clean start in simple mode) with a `marker.txt` in `~/.claude` {src:tests/installer/test_ins.sh:290-297}. It expects exit 1 and the same message {src:tests/installer/test_ins.sh:298-299}, then checks that the marker is intact, no `.claude.backup.*` folder exists and no vault was made {src:tests/installer/test_ins.sh:300-301}. That matches the installer calling the check before any backup or wipe {src:install.sh:633-634}. The check also runs again once the vault path is final {src:install.sh:914}.
- **INS-11, installed commands, a repo path with a space, escapes, profile quoting and the meetings folder.** Four small scenarios, each in its own home. (1) A normal install exits 0 and no installed command file still holds the text `$TOLLGATE_HOME/` {src:tests/installer/test_ins.sh:304-308}; `tg-start.md` calls `tg_path` by the absolute repo path {src:tests/installer/test_ins.sh:309-310}; the installed `settings.json` allows `tg_path` and `tg_ticket_dir` by absolute path, so a command's first lookup does not stop at a permission prompt {src:tests/installer/test_ins.sh:311-312}; the `tg-search` call in `tg-retrieve.md` is the absolute path, not wrapped in quotes {src:tests/installer/test_ins.sh:313-314}; and the profile line `export TOLLGATE_MEETINGS=` holds exactly what `tg_path meetings` prints for the new vault {src:tests/installer/test_ins.sh:316-318}. (2) The repo is copied to a folder whose name has a space and run from there: exit 1, the line `Move the repo to a path without spaces`, and no vault, no `settings.json` and no profile written {src:tests/installer/test_ins.sh:321-329}. The installer prints that line and exits 1 {src:install.sh:163-164}. (3) A name of `A&B|C` makes a base folder with `&` and `|` in its path; the workspace file path must appear unchanged in `CLAUDE.md` {src:tests/installer/test_ins.sh:332-336}, which depends on the escaped substitution {src:install.sh:1270}. (4) A vault path holding a `$` and a double quote gives a profile that passes `bash -n` and, when sourced, gives back the same path in `TOLLGATE_KNOWLEDGE` {src:tests/installer/test_ins.sh:339-344}, which depends on the `_dq` escaping {src:install.sh:1527}.

## Diagram

Skipped: each case is a sequence of install runs and checks with no branching.

## Notes

- **Code versus description.** The header says INS-00 to INS-11 {src:tests/installer/test_ins.sh:2}, which matches the cases from INS-00 {src:tests/installer/test_ins.sh:13} to INS-11 {src:tests/installer/test_ins.sh:303}, and the runner comment above the line that sources this file says the same {src:tests/installer/run.sh:95}. The comment on the question order lists Jira, Notion, Slack and vault search {src:tests/installer/test_ins.sh:64-65}; the answer list also holds one answer for the vault git question and one for the `git init` question, which the comment does not name {src:tests/installer/test_ins.sh:68} {src:install.sh:971} {src:install.sh:991}.
- **Tests that cannot fail in practice.** INS-00 would fail only if `id -un` returned the fake name {src:tests/installer/test_ins.sh:13}. The INS-06 `touch` marker checks only see an absolute marker path, because the test rewrites `MARK` to an absolute path {src:tests/installer/test_ins.sh:185} {src:tests/installer/test_ins.sh:190}. INS-11 passes its meetings check with or without the new helper call, because no test writes a `meetings:` line in the paths file, so the helper and the fallback both give `<vault>/meetings` {src:tests/installer/test_ins.sh:316-318} {src:install.sh:909}. The profile quoting case checks only the profile, not the VS Code workspace file the same install writes, and that file holds the vault path unescaped inside JSON text {src:tests/installer/test_ins.sh:339-344} {src:install.sh:1737}; from reading the code, a double quote in the vault path makes that file invalid JSON (not run).
- **Machine and version dependence.** INS-07 hard-codes `/usr/bin/uname` in the stub and asserts that `secret-tool` is not on `$H/bin:/usr/bin:/bin` {src:tests/installer/test_ins.sh:198} {src:tests/installer/test_ins.sh:203}. CI also runs on Ubuntu {src:.github/workflows/tests.yml:17}; whether that image carries `secret-tool` is [uncertain], and if it does this check fails. INS-08 pins the full folder list, so adding a vault folder needs this test updated {src:tests/installer/test_ins.sh:217}. INS-09 and INS-10 take the real `python3` from the path {src:tests/installer/test_ins.sh:242}, so the shim only changes what version `-c` checks report; the `FAKE_PY_MINOR` default of 9 is never used because every case sets it {src:tests/installer/test_ins.sh:248} {src:tests/installer/test_ins.sh:255}. INS-01 expects the workspace file at `$H/Developer/*/*.code-workspace` {src:tests/installer/test_ins.sh:31}. INS-11 copies the whole repo a second time into a folder with a space, so it needs `tar` and extra disk space under `$WORK` {src:tests/installer/test_ins.sh:321-323}.
- **Inputs reaching a path, command, network address or outbound text without a check.** INS-06 passes hostile text to `--name` on purpose {src:tests/installer/test_ins.sh:181} {src:tests/installer/test_ins.sh:186}. INS-11 does the same with `&` and `|` in the name and `$` and a double quote in the vault path {src:tests/installer/test_ins.sh:333} {src:tests/installer/test_ins.sh:339}; its profile case sources the installer's profile in a `bash -c` shell {src:tests/installer/test_ins.sh:342}. The test then runs `source` on the config the installer wrote, in a `bash -c` shell {src:tests/installer/test_ins.sh:188}; INS-04 also sources it directly in the test shell {src:tests/installer/test_ins.sh:136}. If the installer's quoting failed, that code would run on the machine running the tests, with the marker path inside `$WORK`. No test input reaches a network address: INS-07 uses an `example.invalid` address {src:tests/installer/test_ins.sh:201}.
- **Writes to shared files.** Everything is written under `$WORK` through `run_install`. INS-08 overwrites the paths file with `printf` while no install runs {src:tests/installer/test_ins.sh:229} {src:tests/installer/test_ins.sh:234}; none of the writes is atomic and nothing locks, since the cases run in sequence.
