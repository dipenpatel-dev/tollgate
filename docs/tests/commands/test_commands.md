---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/commands/test_commands.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["commands/", "hooks/gate_rules.py", "docs/variables.md", "docs/gate-lines.md", "tests/leak/scan_leaks.py"]         # source files under test, relative paths from repo root
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

Rule checks on the command files in `commands/`. The command files are plain Markdown instructions that Claude follows, so the tests read them as text. They check that no personal path is left, that repo files they name exist, that variables and brace markers are defined, that the influence command is free of analysis of named people, that the chain commands carry the words the gate expects, that the search call is quote-safe, that every command has the fixed `tg-` prefix, that vault git steps are only printed, never run, and that no command holds an old flat ticket path, an old flat wiki link or an em dash.

## Dependencies

**Depends on.**
- Files read as data: every `commands/*.md` {src:tests/commands/test_commands.py:21} {src:tests/commands/test_commands.py:61}; `docs/variables.md` {src:tests/commands/test_commands.py:121}; `docs/gate-lines.md` {src:tests/commands/test_commands.py:305}; `LICENSE` {src:tests/commands/test_commands.py:197}.
- `hooks/gate_rules.py`, loaded by file path as a module {src:tests/commands/test_commands.py:154} {src:tests/commands/test_commands.py:155} {src:tests/commands/test_commands.py:158}. Page: [[gate_rules]] / [gate_rules](../../hooks/gate_rules.md).
- `tests/leak/scan_leaks.py`, started as a separate process {src:tests/commands/test_commands.py:198} {src:tests/commands/test_commands.py:205}. Page: [[scan_leaks]] / [scan_leaks](../leak/scan_leaks.md).
- `bash`, used to run the grounding snippet {src:tests/commands/test_commands.py:356}.
- Environment variable `TOLLGATE_REQUIRE_SCRIPTS` {src:tests/commands/test_commands.py:224}.
- Standard library: `importlib.util`, `os`, `re`, `shutil`, `subprocess`, `sys`, `tempfile`, `unittest` {src:tests/commands/test_commands.py:11} {src:tests/commands/test_commands.py:18}.
- Overview page: [[commands]] / [commands](../commands.md).

**Used by.**
- Product code: none.
- Started by its launcher `tests/commands/run.sh` {src:tests/commands/run.sh:7}. Page: [[run]] / [run](run.md).
- Searched `git grep` for `test_commands` and `tests/commands`, excluding `docs/` (2026-11-20). No CI workflow names it.

## Behavior

**Which files are checked.** `WAVE2` lists 16 commands {src:tests/commands/test_commands.py:23} {src:tests/commands/test_commands.py:24} {src:tests/commands/test_commands.py:26}. Only those present in `commands/` are checked by the first rule groups {src:tests/commands/test_commands.py:64} {src:tests/commands/test_commands.py:66}. `ALL_COMMANDS` lists all 29 shipped commands {src:tests/commands/test_commands.py:30} {src:tests/commands/test_commands.py:36}.

**Rule 1: personal paths (`TestCmd01`).** Each line is scanned for `/Users/name`, `/home/name` or `/Volumes/name` {src:tests/commands/test_commands.py:45}. A generic name such as `user` or `runner` is allowed, but a `/Volumes/` path always counts because it has no name group {src:tests/commands/test_commands.py:42} {src:tests/commands/test_commands.py:83} {src:tests/commands/test_commands.py:84} {src:tests/commands/test_commands.py:86}. One test checks the pattern matches two sample paths {src:tests/commands/test_commands.py:217} {src:tests/commands/test_commands.py:218} {src:tests/commands/test_commands.py:219}.

**Rule 2: named repo files exist (`TestCmd02`).** Paths under the repo areas (`hooks`, `docs`, `scripts` and so on) are pulled out of each command {src:tests/commands/test_commands.py:43} {src:tests/commands/test_commands.py:46} {src:tests/commands/test_commands.py:94}. A path with a brace, wildcard or bracket, a trailing slash, or no dot in its last part is skipped {src:tests/commands/test_commands.py:96} {src:tests/commands/test_commands.py:97} {src:tests/commands/test_commands.py:98} {src:tests/commands/test_commands.py:99}. Paths beginning `scripts/` are held apart {src:tests/commands/test_commands.py:100} {src:tests/commands/test_commands.py:101}. The others must exist in the repo {src:tests/commands/test_commands.py:110} {src:tests/commands/test_commands.py:111}. Script paths must exist only when `TOLLGATE_REQUIRE_SCRIPTS` is `1` {src:tests/commands/test_commands.py:113} {src:tests/commands/test_commands.py:114} {src:tests/commands/test_commands.py:224}. A second test only prints the script paths to standard error and asserts nothing {src:tests/commands/test_commands.py:228} {src:tests/commands/test_commands.py:234} {src:tests/commands/test_commands.py:236}.

**Rule 3: variables and markers (`TestCmd03`).** Every `$TOLLGATE_*` or `$CLAUDE_DOTFILES` reference must appear in `docs/variables.md` {src:tests/commands/test_commands.py:49} {src:tests/commands/test_commands.py:122} {src:tests/commands/test_commands.py:123} {src:tests/commands/test_commands.py:143} {src:tests/commands/test_commands.py:144}. A brace marker such as `{KEY}` passes if defined there, if it is lower case, digits and underscores, or if it is `N`, `NN` or `TOTAL` {src:tests/commands/test_commands.py:128} {src:tests/commands/test_commands.py:129} {src:tests/commands/test_commands.py:134}. Small tests prove lower-case markers pass and `PREFIX_UPPER`, `NAME`, `MRN` and `Block` fail {src:tests/commands/test_commands.py:248} {src:tests/commands/test_commands.py:255}. One test proves `docs/variables.md` names four variables and two markers {src:tests/commands/test_commands.py:258} {src:tests/commands/test_commands.py:260} {src:tests/commands/test_commands.py:262}.

**Rule 4: no analysis of named people (`TestCmd04`).** The influence command is copied to a temporary folder as `influence.md` with `LICENSE` and scanned by the leak scanner with an empty deny list; the scan must exit 0 {src:tests/commands/test_commands.py:196} {src:tests/commands/test_commands.py:197} {src:tests/commands/test_commands.py:205} {src:tests/commands/test_commands.py:271} {src:tests/commands/test_commands.py:274}. It is skipped if the command file is absent {src:tests/commands/test_commands.py:268} {src:tests/commands/test_commands.py:269}. A second test scans made-up bad text and expects exit 1 and the rule code `CMD-04` in the output {src:tests/commands/test_commands.py:277} {src:tests/commands/test_commands.py:283} {src:tests/commands/test_commands.py:284}. The rule itself lives in the scanner {src:tests/leak/scan_leaks.py:279} {src:tests/leak/scan_leaks.py:289}. The scanner applies it to files named `influence.md` and, since the cleanup, also `tg-influence.md` {src:tests/leak/scan_leaks.py:208}. This test still copies the real command to a file named `influence.md`, so it exercises the first name only.

**Rule 5: gate words (`TestCmd05`).** The test loads the gate's constants {src:tests/commands/test_commands.py:153}. For the spec, design, dev and qa commands it requires that at least one accepted word of each group sits on a line that also mentions "status" or "state" {src:tests/commands/test_commands.py:162} {src:tests/commands/test_commands.py:165} {src:tests/commands/test_commands.py:166} {src:tests/commands/test_commands.py:176} {src:tests/commands/test_commands.py:180} {src:tests/commands/test_commands.py:189}. The words come from the gate file {src:hooks/gate_rules.py:32} {src:hooks/gate_rules.py:33} {src:hooks/gate_rules.py:34} {src:hooks/gate_rules.py:35} {src:hooks/gate_rules.py:36} {src:hooks/gate_rules.py:37} {src:hooks/gate_rules.py:38}. The design drafting word is hard-coded in the test, not taken from the gate {src:tests/commands/test_commands.py:167}, and `docs/gate-lines.md` is checked to document it {src:tests/commands/test_commands.py:304} {src:tests/commands/test_commands.py:305} {src:docs/gate-lines.md:31}. Another test requires every constant to be upper case and underscores {src:tests/commands/test_commands.py:299} {src:tests/commands/test_commands.py:302}.

**Known gaps (`TestKnownGaps`).** Commands outside `WAVE2` get rules 1 to 3 too (script paths not required) {src:tests/commands/test_commands.py:313}. A failing command fails the run unless it is in `KNOWN_GAPS`, which is empty {src:tests/commands/test_commands.py:40} {src:tests/commands/test_commands.py:317}.

**Quote-safe search call (`TestGroundingQuoteSafe`).** The grounding step in the dev and qa commands passes the query through a quoted here-document {src:commands/tg-dev.md:118} {src:commands/tg-qa.md:88}. The first test extracts that code block and checks it has no single-quoted query, uses `<<'TG_QUERY'`, and calls the search with `'{skill}' -` {src:tests/commands/test_commands.py:328} {src:tests/commands/test_commands.py:330} {src:tests/commands/test_commands.py:337} {src:tests/commands/test_commands.py:338} {src:tests/commands/test_commands.py:339}. The second builds a fake `tg-search` script that records its arguments and input, fills in three hostile queries (quotes, `$(...)`, backticks, a `; touch` attempt), runs the block with `bash -c`, and proves no marker file appears and the query arrives as one unchanged piece {src:tests/commands/test_commands.py:325} {src:tests/commands/test_commands.py:350} {src:tests/commands/test_commands.py:352} {src:tests/commands/test_commands.py:356} {src:tests/commands/test_commands.py:359} {src:tests/commands/test_commands.py:362}.

**Fixed prefix (`TestFixedPrefix`).** The command files must be exactly the 29 listed {src:tests/commands/test_commands.py:369} {src:tests/commands/test_commands.py:370}; none may hold the old `{prefix}` markers {src:tests/commands/test_commands.py:376}; every `/tg-name` mentioned must be a real command {src:tests/commands/test_commands.py:384} {src:tests/commands/test_commands.py:385}; none may call search through an interpreter and script path {src:tests/commands/test_commands.py:393}; and the close command may not run `git add`, `commit` or `push` inside a `bash` block and must name `session_cost.py` {src:tests/commands/test_commands.py:406} {src:tests/commands/test_commands.py:410} {src:commands/tg-close.md:71}.

**Vault git step (`TestVaultGitStep`).** For close, dev and qa: each names the vault-mode lookup {src:tests/commands/test_commands.py:437} {src:commands/tg-dev.md:468} {src:commands/tg-qa.md:691}; each describes the three modes with fixed phrases {src:tests/commands/test_commands.py:442} {src:tests/commands/test_commands.py:443}; no runnable block (`bash`, `sh`, `shell`, `zsh`, `console`) holds a vault git command {src:tests/commands/test_commands.py:416} {src:tests/commands/test_commands.py:418} {src:tests/commands/test_commands.py:450}; vault git lines appear only in blocks of kind `text` {src:tests/commands/test_commands.py:457} {src:tests/commands/test_commands.py:458}. Dev and qa must not contain three named old phrases {src:tests/commands/test_commands.py:464} {src:tests/commands/test_commands.py:465} {src:tests/commands/test_commands.py:466}. Dev must keep three code-repo git steps {src:tests/commands/test_commands.py:470} {src:tests/commands/test_commands.py:471} {src:tests/commands/test_commands.py:472}. Close must scan the files it wrote, not the vault history {src:tests/commands/test_commands.py:477} {src:tests/commands/test_commands.py:478} {src:commands/tg-close.md:267}.

**Clean text (`TestCmdCleanText`, new in the cleanup).** The class covers every shipped command except `tg-doc-gen` {src:tests/commands/test_commands.py:488} {src:tests/commands/test_commands.py:489}. Four tests:
- No command holds a flat ticket path, meaning `{tickets}/` followed by a bracket or `{KEY}` {src:tests/commands/test_commands.py:484} {src:tests/commands/test_commands.py:497}.
- No command holds the flat wiki link start `[[02-tickets/{KEY}/` {src:tests/commands/test_commands.py:485} {src:tests/commands/test_commands.py:501}.
- No command holds an em dash character {src:tests/commands/test_commands.py:486} {src:tests/commands/test_commands.py:505}.
- The spec and design commands name the vault git lookup and no longer say the owner commits {src:tests/commands/test_commands.py:509} {src:tests/commands/test_commands.py:510}. The lookup line is present in both commands {src:commands/tg-spec.md:484} {src:commands/tg-arch.md:550}.

## Diagram

Skipped: the tests share only a few helper functions; the one multi-step setup (the fake search script) is described in Behavior.

## Notes

**Code and description disagree.**
- The first line says the file holds "CMD-01 to CMD-05" tests {src:tests/commands/test_commands.py:1}. It also holds quoting, prefix, vault git and clean text test classes with no CMD number {src:tests/commands/test_commands.py:320} {src:tests/commands/test_commands.py:365} {src:tests/commands/test_commands.py:413} {src:tests/commands/test_commands.py:481}.
- The header says `TOLLGATE_REQUIRE_SCRIPTS=1` makes "every `$TOLLGATE_HOME/scripts/...` path" required {src:tests/commands/test_commands.py:4} {src:tests/commands/test_commands.py:5}. The code matches any `scripts/...` path with or without the variable prefix {src:tests/commands/test_commands.py:47} {src:tests/commands/test_commands.py:100}.
- Two close-command tests use different rules for what counts as a runnable block: only `bash` in one {src:tests/commands/test_commands.py:406}, five kinds in the other {src:tests/commands/test_commands.py:418}.
- The `TestCmdCleanText` docstring says it covers "any command" with `tg-doc-gen` owned elsewhere {src:tests/commands/test_commands.py:482}; the code skips `tg-doc-gen` for all four tests {src:tests/commands/test_commands.py:489}.

**Tests that cannot fail or are weak.**
- `test_script_paths_reported` has no assertion {src:tests/commands/test_commands.py:228} {src:tests/commands/test_commands.py:236}.
- `test_detector_flags_personal_path` and `test_detector_finds_paths` test the patterns against sample strings, not any command file {src:tests/commands/test_commands.py:217} {src:tests/commands/test_commands.py:238}.
- `test_exactly_the_shipped_commands` compares the folder to a list kept in the same file, and asserts the list length is 29, so adding a command means editing the test {src:tests/commands/test_commands.py:369} {src:tests/commands/test_commands.py:370}.
- Several tests loop only over files that exist and pass with no files {src:tests/commands/test_commands.py:66} {src:tests/commands/test_commands.py:295}.
- The gate-word test passes when the word is on any line that mentions "status" or "state", not necessarily the line that writes the status {src:tests/commands/test_commands.py:180}.
- A rule 2 path with no dot in its last part is never checked, so folder references are not verified {src:tests/commands/test_commands.py:98} {src:tests/commands/test_commands.py:99}.
- The flat ticket path test only matches `{tickets}/` followed by `[` or `{KEY}`; other flat shapes pass {src:tests/commands/test_commands.py:484}.

**Machine and version dependence.**
- The fake search script starts with `#!` plus the running interpreter's path {src:tests/commands/test_commands.py:352}, so an interpreter path with a space can break it.
- Needs `bash` on `PATH` {src:tests/commands/test_commands.py:356}.
- The loop opens a result file without closing it {src:tests/commands/test_commands.py:361}.
- Needs a `LICENSE` file at the repo root {src:tests/commands/test_commands.py:197}.
- `capture_output` and `text=` need Python 3.7 or newer {src:tests/commands/test_commands.py:205}.
- No personal path is used.

**Inputs with no check.** The test builds the hostile queries itself {src:tests/commands/test_commands.py:325}. The one outside input, `TOLLGATE_REQUIRE_SCRIPTS`, is compared to the text `1` {src:tests/commands/test_commands.py:224}. The command run in `bash -c` is text taken from the command files {src:tests/commands/test_commands.py:354} {src:tests/commands/test_commands.py:356}, so a changed command file changes what the test runs, with no check on it beyond the earlier regex.

**Writes to shared files.** None. The tests write only to temporary folders and a temporary deny-list file that is removed afterwards {src:tests/commands/test_commands.py:201} {src:tests/commands/test_commands.py:208}. The scanner test copies `LICENSE` into a temporary folder {src:tests/commands/test_commands.py:197}. The fake search script is written in a temporary folder per query {src:tests/commands/test_commands.py:344} {src:tests/commands/test_commands.py:351}.
