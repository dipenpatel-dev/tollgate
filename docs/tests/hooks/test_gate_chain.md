---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/hooks/test_gate_chain.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers:            # source files under test, relative paths from repo root
  - hooks/pre-prompt-expansion-check-gates.py
  - hooks/gate_rules.py
  - hooks/pre-tool-write-guard-path.sh
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

This file tests the gate that stops the `tg-arch`, `tg-dev` and `tg-qa` chain commands until the earlier step has left the right `Status:` line in the ticket files. It runs the real gate hook and the real write guard as separate processes against a throwaway vault, with one fake ticket, `T-001` {src:tests/hooks/test_gate_chain.py:3-7}. Four groups of cases are numbered GAT-01 to GAT-04: the arch gate, the full chain, the owner override file, and the fixed command names {src:tests/hooks/test_gate_chain.py:1} {src:tests/hooks/test_gate_chain.py:11-13}.

## Dependencies

**Depends on.** The gate hook [[pre-prompt-expansion-check-gates]] and [pre-prompt-expansion-check-gates](../../hooks/pre-prompt-expansion-check-gates.md) {src:tests/hooks/test_gate_chain.py:27}, the write guard [[pre-tool-write-guard-path]] and [pre-tool-write-guard-path](../../hooks/pre-tool-write-guard-path.md) {src:tests/hooks/test_gate_chain.py:28}, and, through the hook, the status rules in [[gate_rules]] and [gate_rules](../../hooks/gate_rules.md) {src:hooks/pre-prompt-expansion-check-gates.py:375}. The hook also loads the path loader `scripts/core/paths.py` through `TOLLGATE_HOME` {src:hooks/pre-prompt-expansion-check-gates.py:160-162}, which the test points at the repo root {src:tests/hooks/test_gate_chain.py:76}. Standard library: `datetime`, `json`, `os`, `subprocess`, `tempfile`, `unittest`, `typing`. Outside programs: `python3` on the path, for the write guard {src:hooks/pre-tool-write-guard-path.sh:15}.

**Used by.** No product code imports a test file. The test folder is run by discovery on the pattern `test_*.py` from three places (searched with `git grep -n -E "discover -s"`, 2026-11-20):
- Tests: `tests/hooks/run.sh` {src:tests/hooks/run.sh:198}, the CI workflow {src:.github/workflows/tests.yml:35}, and `tests/system/run.sh` {src:tests/system/run.sh:20}.

## Behavior

**Setup shared by every case.** Each test makes a temp folder with a `home` and a `vault`, and creates `vault/02-tickets/T-001` {src:tests/hooks/test_gate_chain.py:54-61}. `put` writes `T-001-<suffix>.md` into that folder {src:tests/hooks/test_gate_chain.py:64-68}. `set_status` writes a two line file with a `Status:` line {src:tests/hooks/test_gate_chain.py:70-71}. `gate` runs the hook with a JSON payload shaped like a typed slash command (`UserPromptExpansion`) {src:tests/hooks/test_gate_chain.py:39-48}. It copies the environment without `TOLLGATE_SKILL_PREFIX`, then sets `HOME`, `TOLLGATE_KNOWLEDGE`, `TOLLGATE_HOME` and `TOLLGATE_GATE_LOG` to the temp locations {src:tests/hooks/test_gate_chain.py:75-77}. `is_blocked` demands exit code 0, treats empty output as allowed, and otherwise requires the JSON decision to be `block` {src:tests/hooks/test_gate_chain.py:86-91}. The hook prints that shape on a block {src:hooks/pre-prompt-expansion-check-gates.py:453}.

**GAT-01, arch needs an approved spec.**
- With the state file holding the spec-approved value and a spec with no `Status:` line, arch is blocked and the reason names `spec.md` {src:tests/hooks/test_gate_chain.py:96-100}. The rule for arch needs the spec status and the state value {src:hooks/gate_rules.py:187-194}, and the reason names the file {src:hooks/gate_rules.py:164-165}. After the spec gets the `Status` line the rule expects, arch is allowed {src:tests/hooks/test_gate_chain.py:101-102}.
- A missing spec file also blocks {src:tests/hooks/test_gate_chain.py:104-106}, because a missing file reads as not valid text {src:hooks/gate_rules.py:158-159}.
- A spec holding only a dated line in the old style (a line starting with the word for approval, then a date) does not open the gate {src:tests/hooks/test_gate_chain.py:108-111}, since the reader only looks at lines starting `Status:` {src:hooks/gate_rules.py:139-142}.

**GAT-02, the whole chain in one test.** The steps run in order {src:tests/hooks/test_gate_chain.py:115-146}:
1. `spec` is never gated {src:tests/hooks/test_gate_chain.py:118}, because only `arch`, `dev` and `qa` are gated {src:hooks/pre-prompt-expansion-check-gates.py:71}.
2. `arch` is blocked at state `ROUTED`, allowed once spec and state are set {src:tests/hooks/test_gate_chain.py:120-123}.
3. `dev` is blocked while the design file holds the design-finished value and allowed once it holds the design-approved value {src:tests/hooks/test_gate_chain.py:125-131}. The rule asks for the approved design status {src:hooks/gate_rules.py:201} and a state in the allowed list {src:hooks/gate_rules.py:39}.
4. State `IN_DEV` still lets `dev` through, and `qa` stays blocked {src:tests/hooks/test_gate_chain.py:133-135}. `qa` needs the state that marks dev as finished {src:hooks/gate_rules.py:213}.
5. With that state set and no validation file, `qa` is still blocked; a validation file with `DOCUMENTED` opens it, and so does the older `VALIDATED` {src:tests/hooks/test_gate_chain.py:137-143} {src:hooks/gate_rules.py:38}.
6. After the state moves on to the qa-passed value, `qa` is blocked again, so a rerun cannot skip dev completion {src:tests/hooks/test_gate_chain.py:145-146}.

**GAT-03, the owner override file.**
- With state `ROUTED`, arch is blocked. Writing `Override: arch <today> owner decision` into `T-001-gate-override.md` opens it and the gate log gets a line containing `override arch T-001` {src:tests/hooks/test_gate_chain.py:161-166}. The hook logs that event on a valid override {src:hooks/pre-prompt-expansion-check-gates.py:378}. The override covers one skill only: `dev` stays blocked {src:tests/hooks/test_gate_chain.py:168}, because the line must name the skill being run {src:hooks/pre-prompt-expansion-check-gates.py:267}.
- A model write to the override file is refused for `Write`, `Edit` and `MultiEdit`: the output has `deny` and the word `terminal` {src:tests/hooks/test_gate_chain.py:170-175}. The guard denies any path whose lower case name ends in `-gate-override.md` {src:hooks/pre-tool-write-guard-path.sh:34-37} with a message that says the owner creates it from a terminal {src:hooks/pre-tool-write-guard-path.sh:44}.
- A refused write leaves the gate shut {src:tests/hooks/test_gate_chain.py:178-182}.
- An override dated yesterday does not count {src:tests/hooks/test_gate_chain.py:184-188}, since the hook compares the line date with today {src:hooks/pre-prompt-expansion-check-gates.py:264-267}.

**GAT-04, fixed `tg-` names.**
- `tg-arch` is gated and its block message tells the user to run `/tg-spec T-001` first {src:tests/hooks/test_gate_chain.py:193-197}. The hook builds that line from the run-first table {src:hooks/pre-prompt-expansion-check-gates.py:72} {src:hooks/pre-prompt-expansion-check-gates.py:299}.
- A leftover `TOLLGATE_SKILL_PREFIX` of `tg`, empty, `my-team` or `tg-` changes nothing, arch stays blocked {src:tests/hooks/test_gate_chain.py:202-206}. The hook has a fixed prefix constant {src:hooks/pre-prompt-expansion-check-gates.py:61} and does not read that variable (searched `hooks/` for `SKILL_PREFIX`, 2026-11-20: only two comment lines).
- Names that are not `tg-arch`, `tg-dev` or `tg-qa` produce no output: `zz-arch`, `arch`, `dev`, `qa`, `my-team-arch`, `close`, `tg-spec`, `tg-architect` {src:tests/hooks/test_gate_chain.py:208-212}. The hook needs the `tg-` start and a name from the chain list {src:hooks/pre-prompt-expansion-check-gates.py:136-139}, and then only gates the three skills {src:hooks/pre-prompt-expansion-check-gates.py:341}. The state is `ROUTED` in this case, so a gated name would have blocked {src:tests/hooks/test_gate_chain.py:209}.

## Diagram

None: the fixtures are one temp vault and two scripts run as processes, with no mock chain.

## Notes

- **Cannot fail, file existence.** `assertFalse(os.path.exists(target))` after the three model writes {src:tests/hooks/test_gate_chain.py:176} holds whatever the guard does: the test never creates that file and the guard only prints a decision {src:hooks/pre-tool-write-guard-path.sh:38-49}.
- **Weak check, refused write keeps gate shut.** The second assertion in the refused write case {src:tests/hooks/test_gate_chain.py:182} is true with or without a working guard, because no override file exists at that point. Only the `deny` assertion before it {src:tests/hooks/test_gate_chain.py:181} tests the guard.
- **Weak check, three tool names.** The `Write`, `Edit` and `MultiEdit` loop {src:tests/hooks/test_gate_chain.py:172} cannot tell the tools apart, because the guard reads only `file_path` or `notebook_path` and never the tool name {src:hooks/pre-tool-write-guard-path.sh:23}.
- **Time dependence.** `TODAY` is read once when the module loads {src:tests/hooks/test_gate_chain.py:31} while the hook reads the date when it runs {src:hooks/pre-prompt-expansion-check-gates.py:433}. A run that crosses midnight can fail the override cases.
- **Machine and version dependence.** The hook and write guard are started directly as programs {src:tests/hooks/test_gate_chain.py:79} {src:tests/hooks/test_gate_chain.py:157}, so both need the execute bit and `python3` on the path {src:hooks/pre-prompt-expansion-check-gates.py:1}. `capture_output` and `text` need Python 3.7 or later {src:tests/hooks/test_gate_chain.py:79}. The `cwd` in the payload is the fake `/tmp/example` and the hook never reads it {src:tests/hooks/test_gate_chain.py:44}; no machine path is needed.
- **Code and description (hook, not this file).** No disagreement found now. The hook header says the fixed names `tg-arch`, `tg-dev` and `tg-qa` are gated and the prefix variable is no longer read {src:hooks/pre-prompt-expansion-check-gates.py:8-9}. A later line records the old behaviour, an empty `TOLLGATE_SKILL_PREFIX` gating the bare commands and an unset one allowing, as "Earlier" and replaced {src:hooks/pre-prompt-expansion-check-gates.py:21-23}. The test confirms bare `arch`, `dev` and `qa` are not gated, even with a prefix value set {src:tests/hooks/test_gate_chain.py:210} {src:tests/hooks/test_gate_chain.py:211}.
- **Not covered here.** The `Skill` tool path through `normalize_payload` {src:hooks/pre-prompt-expansion-check-gates.py:388-401}, exit code 2 on an unreadable payload {src:hooks/pre-prompt-expansion-check-gates.py:427-430}, the symlink refusal for the override file {src:hooks/pre-prompt-expansion-check-gates.py:251-260}, and the warning printed when `TOLLGATE_KNOWLEDGE` is unset {src:hooks/pre-prompt-expansion-check-gates.py:344-350}. `tests/hooks/test_gate_hook.py` and others in this folder test some of these.
- **Inputs without a check.** In this test file every path, command and payload is built from constants or the temp folder. The environment of the caller is copied into the child process {src:tests/hooks/test_gate_chain.py:75}, so any `TOLLGATE_*` value already set (other than the prefix) reaches the hook unchecked.
- **Shared file writes.** All writes go under the temp folder, removed after each test {src:tests/hooks/test_gate_chain.py:56}. The hook appends to the gate log with a plain append open, not atomic and not locked {src:hooks/pre-prompt-expansion-check-gates.py:123-124}; the test gives each case its own log file {src:tests/hooks/test_gate_chain.py:62}, so two writers never meet.
