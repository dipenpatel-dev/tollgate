---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tools/port/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "exec /usr/bin/env python3 port.py"    # function or line that executes when the script runs
requires: [bash, dirname, env, python3]       # external commands or tools this script depends on
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

A three-line launcher for the port tool. It lets a person run `tools/port/run.sh SOURCE DEST` from any folder without naming `port.py`. It changes nothing itself; every file the run writes is written by the Python program it starts.

## Dependencies

**Depends on.**
- `bash`, named in the first line {src:tools/port/run.sh:1}.
- `dirname` to find its own folder {src:tools/port/run.sh:4}.
- `/usr/bin/env` and a `python3` on `PATH` {src:tools/port/run.sh:5}.
- `tools/port/port.py` in the same folder {src:tools/port/run.sh:5}. Page: [[port]] / [port](port.md).
- No environment variables of its own. `port.py` reads `TOLLGATE_PORT_MAP` and `TOLLGATE_DENYLIST` {src:tools/port/port.py:379} {src:tools/port/port.py:381}.

**Used by.**
- Product code: none (searched `git grep` for `port/run` and `tools/port`, excluding `docs/`, 2026-11-20).
- Tests: `tools/port/tests/test_port.py` runs it once {src:tools/port/tests/test_port.py:221}. Page: [[test_port]] / [test_port](tests/test_port.md).

## Behavior

1. The shell stops on a command error, an unset variable or a failed step in a pipe {src:tools/port/run.sh:3}.
2. It finds the folder that holds the script, by changing into the script's folder in a sub-shell and printing the path {src:tools/port/run.sh:4}.
3. It replaces itself with `python3 port.py` and passes every argument through unchanged and quoted {src:tools/port/run.sh:5}. The exit code is therefore the Python program's exit code.

Arguments are not read or checked by this script. The program accepts `SOURCE`, `DEST`, `--map`, `--denylist`, `--dry-run` and `--root` {src:tools/port/port.py:377} {src:tools/port/port.py:378} {src:tools/port/port.py:379} {src:tools/port/port.py:381} {src:tools/port/port.py:383} {src:tools/port/port.py:384}.

## Diagram

Skipped: straight-line script with no branches.

## Notes

- The usage comment lists `SOURCE DEST [--dry-run] [--map F] [--denylist F]` {src:tools/port/run.sh:2}. The program also accepts `--root`, which the comment omits {src:tools/port/port.py:384}.
- Needs bash because it reads `BASH_SOURCE` {src:tools/port/run.sh:4}.
- `python3` is whichever the `PATH` finds first, so the Python version is not fixed {src:tools/port/run.sh:5}.
- Every argument reaches the Python program with no check from this script; the program's own checks apply (see the port page).
- No file is written by this script. No network address or other shell command is built from the arguments.
- Safe to run again: it holds no state of its own.
