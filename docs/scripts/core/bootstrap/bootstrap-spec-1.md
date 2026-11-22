---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: scripts/core/bootstrap/bootstrap-spec-1.sh    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "exec bash _worker_common.sh spec-1 spec (line 11)"    # function or line that executes when the script runs
requires: [bash]       # external commands or tools this script depends on
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

A one-line wrapper that starts the first spec worker session. It holds no launch logic of its own: it hands the worker name `spec-1` and the worker type `spec` to the shared launcher, which builds the identity file, records the worker as available and starts Claude.

## Dependencies

**Depends on.**
- `bash`, used to run the shared launcher. {src:scripts/core/bootstrap/bootstrap-spec-1.sh:11}
- [[_worker_common]] (no doc yet): the shared launcher in the same folder, found by the folder of this script. {src:scripts/core/bootstrap/bootstrap-spec-1.sh:11}
- Everything the launcher needs at run time: `TOLLGATE_HOME` {src:scripts/core/bootstrap/_worker_common.sh:19}, an optional `TOLLGATE_WORKER_TEMPLATES` {src:scripts/core/bootstrap/_worker_common.sh:27}, and the `claude` program {src:scripts/core/bootstrap/_worker_common.sh:67}.

**Used by.** No product code calls this script. A repo search for `bootstrap-spec-1` and for `bootstrap/` outside `docs/` (git grep, 2026-11-20) finds only the file's own header comment and the tests. The search found no entry in `settings.json`, `install.sh` or any command file, so a person runs it by hand.
- Tests: `tests/scripts/core/test_bootstrap.py` builds the path as `bootstrap-<role>.sh` for every role, including `spec-1`. {src:tests/scripts/core/test_bootstrap.py:26} {src:tests/scripts/core/test_bootstrap.py:63}

## Behavior

1. The script stops on any error, any unset variable and any failure inside a pipe. {src:scripts/core/bootstrap/bootstrap-spec-1.sh:9}
2. It works out its own folder from `BASH_SOURCE[0]` inside a command substitution, so the `cd` does not move the caller's shell. {src:scripts/core/bootstrap/bootstrap-spec-1.sh:11}
3. It replaces itself (`exec`) with `bash <folder>/_worker_common.sh "spec-1" "spec"`. The script never returns to its own code and its exit status is the launcher's. {src:scripts/core/bootstrap/bootstrap-spec-1.sh:11}

What the launcher then does with those two arguments:
- Takes the first as the worker name and the second as the type, and stops if either is missing. {src:scripts/core/bootstrap/_worker_common.sh:16} {src:scripts/core/bootstrap/_worker_common.sh:17}
- Exits 1 with "not set up" when `TOLLGATE_HOME` is unset. {src:scripts/core/bootstrap/_worker_common.sh:19-22}
- Reads the template `spec-identity-template.md` and exits 1 when it is missing. {src:scripts/core/bootstrap/_worker_common.sh:30} {src:scripts/core/bootstrap/_worker_common.sh:33-36}
- Sets the terminal title and writes `<state>/workers/spec-1-identity.md` with `{{WORKER_NAME}}` replaced. {src:scripts/core/bootstrap/_worker_common.sh:39} {src:scripts/core/bootstrap/_worker_common.sh:43}
- Writes `<state>/worker-registry/spec-1.json` with status `available`, no ticket and an empty worktree path, through a temp file and `mv`. {src:scripts/core/bootstrap/_worker_common.sh:46-62}
- Sets `TOLLGATE_WORKER_ID=spec-1` and runs `claude --append-system-prompt-file <identity file>`. {src:scripts/core/bootstrap/_worker_common.sh:66-67}

The test for this role checks the identity text, the Claude arguments, the registry fields (`worker_name`, `type`, `status`) and that no `.tmp` file is left. {src:tests/scripts/core/test_bootstrap.py:67-71} {src:tests/scripts/core/test_bootstrap.py:76-80} It runs against a fake `claude` and fake templates, so it proves the wiring, not the real identity text. {src:tests/scripts/core/test_bootstrap.py:35-44}

## Diagram

None: the wrapper is a single straight-line command, so a diagram would add nothing.

## Notes

- **Header versus code.** The header says the script launches the session "with its identity prompt injected". {src:scripts/core/bootstrap/bootstrap-spec-1.sh:5} The wrapper itself injects nothing; all of that work is in the launcher. {src:scripts/core/bootstrap/_worker_common.sh:43} {src:scripts/core/bootstrap/_worker_common.sh:67} This is a loose description, not a wrong one. The `Date:` header field is empty. {src:scripts/core/bootstrap/bootstrap-spec-1.sh:4}
- **Missing template in the repo.** The launcher's default template folder is `$TOLLGATE_HOME/templates/workers` {src:scripts/core/bootstrap/_worker_common.sh:27}. That folder does not exist in this checkout (only `templates/code-docs` does; `ls templates`, 2026-11-20), and no file named `*identity-template*` is tracked (git grep, 2026-11-20). Unless `TOLLGATE_WORKER_TEMPLATES` points at templates held elsewhere, this script exits 1 with "identity template not found". The tests avoid the problem by writing their own templates. {src:tests/scripts/core/test_bootstrap.py:40-44}
- **Unchecked inputs.** The wrapper takes no command-line input and passes two fixed strings. {src:scripts/core/bootstrap/bootstrap-spec-1.sh:11} Inputs that reach a path or command inside the launcher without a value check: `TOLLGATE_HOME` builds the path of the program run to find the state folder {src:scripts/core/bootstrap/_worker_common.sh:24} {src:scripts/core/bootstrap/_worker_common.sh:25}; `TOLLGATE_WORKER_TEMPLATES` builds the template path read by `sed` {src:scripts/core/bootstrap/_worker_common.sh:27} {src:scripts/core/bootstrap/_worker_common.sh:43}. No check exists on either. The worker name goes into a `sed` pattern and a JSON text block {src:scripts/core/bootstrap/_worker_common.sh:43} {src:scripts/core/bootstrap/_worker_common.sh:52}; for this wrapper it is the fixed word `spec-1`.
- **Shared-file writes.** The identity file is written with a plain redirect, not through a temp file, and no lock stops two launches writing it at once. {src:scripts/core/bootstrap/_worker_common.sh:43} The registry file is written through a temp file plus `mv`, which is atomic on one filesystem, but nothing locks it, and it is overwritten on every launch. {src:scripts/core/bootstrap/_worker_common.sh:49} {src:scripts/core/bootstrap/_worker_common.sh:62} Starting `spec-1` again therefore resets a record that may already hold a ticket assignment back to `available`. {src:scripts/core/bootstrap/_worker_common.sh:54-55}
- Needs bash (the `BASH_SOURCE` array is a bash feature). {src:scripts/core/bootstrap/bootstrap-spec-1.sh:1}
