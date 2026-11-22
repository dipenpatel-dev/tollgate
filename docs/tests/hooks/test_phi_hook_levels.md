---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/test_phi_hook_levels.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["hooks/pre-tool-bash-scan-phi.py", "hooks/pre-tool-write-scan-phi.py", "hooks/post-tool-result-scan-phi.py", "hooks/pre-submit-vault-inject.sh", "hooks/phi_patterns.py"]         # source files under test, relative paths from repo root
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

This file tests what each PHI hook prints at each finding level (deny, ask, warn), and that the Bash hook also scans the script files a command names {src:tests/hooks/test_phi_hook_levels.py:1-5}. Every sample value comes from `fake_phi.py` and is joined from parts at run time; script files are written into a temp folder and never run {src:tests/hooks/test_phi_hook_levels.py:7-8}. It has 28 test methods in 6 test classes. Five of them sit in a shared mixin that two classes inherit, so 33 tests run in all {src:tests/hooks/test_phi_hook_levels.py:58-59} {src:tests/hooks/test_phi_hook_levels.py:102} {src:tests/hooks/test_phi_hook_levels.py:113}. It was not run while this page was written, so each claim says what a test asserts.

## Dependencies

**Depends on.**
- The value builders `tests/hooks/fake_phi.py`: [[fake_phi]] (no doc yet) {src:tests/hooks/test_phi_hook_levels.py:22}.
- The Bash hook: [[pre-tool-bash-scan-phi]] and [pre-tool-bash-scan-phi](../../hooks/pre-tool-bash-scan-phi.md). The shared pattern module: [[phi_patterns]] and [phi_patterns](../../hooks/phi_patterns.md). Both are started or imported through the hooks, not by this file {src:tests/hooks/test_phi_hook_levels.py:26-29}.
- No page yet: [[pre-tool-write-scan-phi]] (no doc yet), [[post-tool-result-scan-phi]] (no doc yet), [[pre-submit-vault-inject]] (no doc yet).
- Standard library only: `json`, `os`, `shutil`, `subprocess`, `tempfile`, `unittest`.
- Environment: each hook call gets the developer's environment {src:tests/hooks/test_phi_hook_levels.py:35-38}. The vault inject test adds `TOLLGATE_KNOWLEDGE` {src:tests/hooks/test_phi_hook_levels.py:183}.

**Used by.** Product code: none. Tests: `tests/hooks/test_phi_qa_regressions.py` imports `BASH_HOOK`, `POST_HOOK`, `WRITE_HOOK`, `bash_payload` and `run_hook` from this file {src:tests/hooks/test_phi_qa_regressions.py:27}. The unit test step of the hook runner and the CI workflow find it by the pattern `test_*.py` {src:tests/hooks/run.sh:198} {src:.github/workflows/tests.yml:35}. Searched 2026-11-20: the whole worktree except `.git`, `docs/`, caches and virtual environments for `test_phi_hook_levels`; those were the only hits.

## Behavior

**Setup.** `run_hook` starts a hook file with the payload on stdin and returns its JSON output, or `None` when the output is empty; it has no time limit {src:tests/hooks/test_phi_hook_levels.py:35-39}. `level_texts` gives one fake text per level: a name label for deny, a labeled phone for ask, an age and sex phrase for warn {src:tests/hooks/test_phi_hook_levels.py:42-48}. The hooks map labels to levels through one table: `NAME` is deny, `PHONE` is ask, `CONTEXT_CLUE` is warn {src:hooks/phi_patterns.py:203-212}.

**PreToolSchemaMixin (5 tests, run for the write hook and the Bash hook).** The Write class sends the text as file content and the Bash class sends `echo '<text>'` {src:tests/hooks/test_phi_hook_levels.py:105-106} {src:tests/hooks/test_phi_hook_levels.py:116-117}.
- Deny: the output has event name `PreToolUse`, decision `deny`, and a reason that names `NAME` {src:tests/hooks/test_phi_hook_levels.py:71-75} {src:hooks/phi_patterns.py:549-555}.
- Ask: decision `ask` and a reason that names `PHONE` {src:tests/hooks/test_phi_hook_levels.py:77-81} {src:hooks/phi_patterns.py:549-551}.
- Warn: no `permissionDecision`, a string `additionalContext`, and a `systemMessage` that names `CONTEXT_CLUE` {src:tests/hooks/test_phi_hook_levels.py:83-90} {src:hooks/phi_patterns.py:545-548}.
- No output at any level holds the fake last name, the fake phone or the age number `58` {src:tests/hooks/test_phi_hook_levels.py:92-96} {src:hooks/phi_patterns.py:524-526}. The age check is a plain substring test, so any other `58` in the output would fail it.
- Clean text prints nothing {src:tests/hooks/test_phi_hook_levels.py:98-99}.

**WriteHookLevels and BashHookLevels (1 test each).** Text that is not JSON gives a `deny` {src:tests/hooks/test_phi_hook_levels.py:108-110} {src:tests/hooks/test_phi_hook_levels.py:119-121} {src:hooks/pre-tool-write-scan-phi.py:53-55} {src:hooks/pre-tool-bash-scan-phi.py:340-346}. The tests check the decision field only, not the exit code.

**PostHookLevels (5 tests).** The after tool hook gets a Bash style `tool_response` {src:tests/hooks/test_phi_hook_levels.py:125-130}.
- Each level shows in the context as `NAME (deny)`, `PHONE (ask)` or `CONTEXT_CLUE (warn)` {src:tests/hooks/test_phi_hook_levels.py:132-135} {src:hooks/phi_patterns.py:524-526}.
- Deny and ask keep the firm wording `PHI DETECTED` and `Do not process` {src:tests/hooks/test_phi_hook_levels.py:137-141} {src:hooks/post-tool-result-scan-phi.py:39-43}.
- Warn uses the soft wording: no firm phrases, but `Weak PHI signal` and `false alarm` {src:tests/hooks/test_phi_hook_levels.py:143-148} {src:hooks/post-tool-result-scan-phi.py:33-38}.
- A deny finding plus a warn finding in one text gives the firm wording and still lists `CONTEXT_CLUE (warn)` {src:tests/hooks/test_phi_hook_levels.py:150-154} {src:hooks/phi_patterns.py:514-518}. The name label is not a pairing clue, so the age phrase stays a lone warn {src:hooks/phi_patterns.py:489-490}.
- A clean result prints nothing {src:tests/hooks/test_phi_hook_levels.py:156-158}.

**VaultInjectLevels (3 tests).** The prompt injection hook runs a search script and injects matching excerpts. The test copies the hook and `phi_patterns.py` into a temp folder and puts a stub `query_index.py` in the place the hook expects; the stub records its arguments and stdin and returns one excerpt {src:tests/hooks/test_phi_hook_levels.py:164-178} {src:hooks/pre-submit-vault-inject.sh:14-17}.
- An excerpt holding a finding of any of the three levels is replaced by the text `excerpt withheld` and the original text is not in the output {src:tests/hooks/test_phi_hook_levels.py:187-191} {src:hooks/pre-submit-vault-inject.sh:101-103}.
- A clean excerpt is injected {src:tests/hooks/test_phi_hook_levels.py:193-195} {src:hooks/pre-submit-vault-inject.sh:104-108}.
- A prompt that starts with `--top 99` reaches the stub on stdin, and is not in its arguments; the arguments hold `--stdin` and no `--index` {src:tests/hooks/test_phi_hook_levels.py:197-204} {src:hooks/pre-submit-vault-inject.sh:55-57}.

**ScriptFileScan (13 tests).** The Bash hook reads the script a command names and scans its text with the same rules; the file is only read {src:hooks/pre-tool-bash-scan-phi.py:279-311}. The class writes scripts into a temp folder and sends that folder as the working directory {src:tests/hooks/test_phi_hook_levels.py:210-225} {src:hooks/pre-tool-bash-scan-phi.py:323-326}.
- `p18`: an address inside a here document is denied. This one scans the command text only; no script file is involved {src:tests/hooks/test_phi_hook_levels.py:227-229} {src:hooks/pre-tool-bash-scan-phi.py:322}.
- `p19` Python: `python3 run.py` where `run.py` holds an address is denied; the reason names `script file run.py` and the `ADDRESS` label and not the street text {src:tests/hooks/test_phi_hook_levels.py:231-237} {src:hooks/pre-tool-bash-scan-phi.py:326}.
- `p19` other forms: `bash`, `sh`, `zsh`, `source`, `python3 -u` on a `.sh` file after `cd`, an env assignment prefix, `sudo` after `true;`, `node`, `bash -e`, and the file path alone after `chmod 700`, are all denied {src:tests/hooks/test_phi_hook_levels.py:239-247} {src:hooks/pre-tool-bash-scan-phi.py:196-233}. The `cd` in that command goes to the folder that is already the working directory, so the test cannot show whether `cd` is followed {src:tests/hooks/test_phi_hook_levels.py:242}.
- `p19` ask: a labeled phone in a script gives `ask` {src:tests/hooks/test_phi_hook_levels.py:249-251}.
- A script that would create a marker file is denied for the address in its comment and the marker is never created, so the hook did not run it {src:tests/hooks/test_phi_hook_levels.py:253-258} {src:hooks/pre-tool-bash-scan-phi.py:285-295}.
- `p20`: a missing script gives no decision {src:tests/hooks/test_phi_hook_levels.py:260-261} {src:hooks/pre-tool-bash-scan-phi.py:303-311}. An unreadable script (mode 0) gives none, and the test skips itself when the user can still read it {src:tests/hooks/test_phi_hook_levels.py:263-269}. A folder, a binary file with a null byte, and a command with an unclosed quote give none {src:tests/hooks/test_phi_hook_levels.py:271-275} {src:hooks/pre-tool-bash-scan-phi.py:286-287} {src:hooks/pre-tool-bash-scan-phi.py:304-305}.
- Inline code and stdin are not files: `python3 -c ... run.py`, `python3 - run.py` and `bash -lc ... run.py` give none even though `run.py` holds an address {src:tests/hooks/test_phi_hook_levels.py:277-280} {src:hooks/pre-tool-bash-scan-phi.py:170-183}.
- `p21`: a script larger than 256 KB gives the same verdict as a small one with the same last line, and that verdict is deny {src:tests/hooks/test_phi_hook_levels.py:282-289} {src:hooks/pre-tool-bash-scan-phi.py:58} {src:hooks/pre-tool-bash-scan-phi.py:279-295}. An address that straddles the 256 KB block edge is still found because each block starts with the last 1024 bytes of the one before {src:tests/hooks/test_phi_hook_levels.py:291-296} {src:hooks/pre-tool-bash-scan-phi.py:59} {src:hooks/pre-tool-bash-scan-phi.py:294-295}.
- Known limits: a value built from pieces inside the script gives no decision (`f06`), and a command whose script is missing gives none (`f07`) {src:tests/hooks/test_phi_hook_levels.py:298-303} {src:tests/hooks/test_phi_hook_levels.py:305-306}. The first of these says to update `docs/hooks.md` if it ever fails {src:tests/hooks/test_phi_hook_levels.py:299-300}.

## Diagram

No diagram: the only setup chain is the vault inject test, which copies two files and writes one stub script {src:tests/hooks/test_phi_hook_levels.py:164-178}.

## Notes

**Tests that look wrong or cannot fail**
- The `cd` case of `p19` cannot show that `cd` is followed, as noted above {src:tests/hooks/test_phi_hook_levels.py:242}. The hook does not track `cd` at all; it lists that as a known limit {src:hooks/pre-tool-bash-scan-phi.py:35-39}.
- The `p20` case for an unclosed quote passes for a different reason than its header says. The hook header says an unparseable command is skipped {src:hooks/pre-tool-bash-scan-phi.py:26-28}, but the code splits such a line on spaces and looks for a script among the pieces {src:hooks/pre-tool-bash-scan-phi.py:116-134}. The result, no decision, is the same because no such file exists.
- `test_p21_*` use their own copy of the 256 KB cap {src:tests/hooks/test_phi_hook_levels.py:30}. If `MAX_SCRIPT_BYTES` changes {src:hooks/pre-tool-bash-scan-phi.py:58}, the large file may stop crossing a block edge and the two tests would still pass.
- The vault inject tests never test an excerpt longer than 200 characters; the hook cuts the excerpt to 200 characters before it scans it {src:hooks/pre-submit-vault-inject.sh:100-101}.
- The post hook's exit 2 for bad input is not tested in this file {src:hooks/post-tool-result-scan-phi.py:56-63}. The Write and Bash hooks have one bad input test each {src:tests/hooks/test_phi_hook_levels.py:108-110} {src:tests/hooks/test_phi_hook_levels.py:119-121}.
- The test names carry design case numbers (`P18` to `P21`, `F06`, `F07`) from a design that is not linked here {src:tests/hooks/test_phi_hook_levels.py:208}.

**Machine and version dependence**
- `import fake_phi` works only when `tests/hooks` is on the module path, as it is with the `discover -s tests/hooks` command in the header {src:tests/hooks/test_phi_hook_levels.py:10} {src:tests/hooks/test_phi_hook_levels.py:22}. Running the file by path from the repo root would not find it.
- The hooks run as executables, so each needs its execute bit; the inject hook is a bash script that calls `python3`, `grep` and `head` {src:hooks/pre-submit-vault-inject.sh:1} {src:hooks/pre-submit-vault-inject.sh:50}. A `TOLLGATE_PYTHON` in the developer's shell is used in place of `python3` for the stub {src:hooks/pre-submit-vault-inject.sh:18}.
- The Write payload uses the text path `/tmp/x`, which is never opened {src:tests/hooks/test_phi_hook_levels.py:106}. The unreadable script test and the executable path case use `chmod`, so they are not portable to Windows {src:tests/hooks/test_phi_hook_levels.py:246} {src:tests/hooks/test_phi_hook_levels.py:265}.
- Python 3.7 or newer is needed for `capture_output`; the `X | None` annotations are not evaluated because of the future import {src:tests/hooks/test_phi_hook_levels.py:13} {src:tests/hooks/test_phi_hook_levels.py:37}, which was kept from when the minimum was 3.9 and is not needed on 3.12.

**Inputs without a check, and shared writes.** The script tests write only inside their own temp folders. The vault inject test opens its record file without closing it explicitly {src:tests/hooks/test_phi_hook_levels.py:184}. Speed and crash handling are covered in [test_phi_safety_speed](test_phi_safety_speed.md).
