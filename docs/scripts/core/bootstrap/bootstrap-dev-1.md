---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "scripts/core/bootstrap/bootstrap-dev-1.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "the exec command on line 11"    # function or line that executes when the script runs
requires: [bash, cd, dirname, pwd, scripts/core/bootstrap/_worker_common.sh]    # external commands or tools this script depends on
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

A one-line wrapper that starts the `dev-1` worker session. It holds only the worker name (`dev-1`) and the worker type (`dev`) and hands them to the shared launcher, which does all the work.

## Dependencies

**Depends on.**
- Repo file `scripts/core/bootstrap/_worker_common.sh`, run with `bash` {src:scripts/core/bootstrap/bootstrap-dev-1.sh:11}. Page: [[_worker_common]] and [_worker_common](_worker_common.md).
- Outside programs: `bash`, `cd`, `dirname` and `pwd` for finding its own folder {src:scripts/core/bootstrap/bootstrap-dev-1.sh:11}.
- Through the launcher: `TOLLGATE_HOME`, and a template named `dev-identity-template.md` {src:scripts/core/bootstrap/_worker_common.sh:30}.

**Used by.**
- Product code: none. No file under `scripts/`, `install.sh` or the hooks names `bootstrap-dev-1` (searched with `git grep`, excluding `docs/`, 2026-11-20). It is meant to be run by hand in a terminal.
- Tests: `tests/scripts/core/test_bootstrap.py`. Line 94 runs this wrapper directly in the unset-home test {src:tests/scripts/core/test_bootstrap.py:94}, and the shared role list used by the other tests includes `dev-1` {src:tests/scripts/core/test_bootstrap.py:26}.

## Behavior

- Strict mode on: `set -euo pipefail` {src:scripts/core/bootstrap/bootstrap-dev-1.sh:9}.
- Works out the folder that holds this script from `BASH_SOURCE[0]` and replaces itself with `bash <that folder>/_worker_common.sh "dev-1" "dev"` {src:scripts/core/bootstrap/bootstrap-dev-1.sh:11}. Command line arguments given to the wrapper are not passed on, because the line forwards no `"$@"` {src:scripts/core/bootstrap/bootstrap-dev-1.sh:11}.
- Because the type is not `dispatch`, the launcher writes a registry record for this worker {src:scripts/core/bootstrap/_worker_common.sh:46}. The exit code is the launcher's, since the wrapper replaces itself with it {src:scripts/core/bootstrap/bootstrap-dev-1.sh:11}.
- The file is marked executable (mode `rwxr-xr-x`, listed 2026-11-20), and a test checks the executable bit {src:tests/scripts/core/test_bootstrap.py:53-57}.

## Diagram

None: the script is one straight line, so a diagram would add nothing.

## Notes

- Code and description: the header says it launches the `dev-1` worker session with its identity prompt injected {src:scripts/core/bootstrap/bootstrap-dev-1.sh:5}. That is true through the launcher {src:scripts/core/bootstrap/_worker_common.sh:67}. The header `Date:` is blank {src:scripts/core/bootstrap/bootstrap-dev-1.sh:4}.
- Inputs that reach a path, command or text without a check: the name and type are fixed text in the file, and the folder comes from the script's own location {src:scripts/core/bootstrap/bootstrap-dev-1.sh:11}. If the wrapper is reached through a symbolic link, `dirname` returns the folder of the link, not of the real file, so the launcher would be looked up beside the link (reasoned from how `BASH_SOURCE` works, not run). Environment variables are checked by the launcher, see [[_worker_common]].
- Writes to shared files: none in this file. The launcher writes the identity file and the registry record; see its page for the atomicity notes.
- `dev-1` and `dev-2` share one template, `dev-identity-template.md`, so both get the same identity text apart from the name {src:scripts/core/bootstrap/_worker_common.sh:30} {src:scripts/core/bootstrap/_worker_common.sh:43}.
- Tests: the wrapper is covered by the role loop in `test_each_role_launches_with_identity` {src:tests/scripts/core/test_bootstrap.py:59-71}, and directly by `test_unset_home_says_not_set_up`, which removes `TOLLGATE_HOME` and expects exit 1 and the text `not set up` {src:tests/scripts/core/test_bootstrap.py:90-96}.
