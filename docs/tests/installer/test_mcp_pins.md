---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/installer/test_mcp_pins.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [install.sh]         # source files under test, relative paths from repo root
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

Two tests that check every MCP server `install.sh` starts through `npx` is registered with an exact version number, not a bare package name. An unpinned name would run whatever was published last, with the stored keys in its environment, so the pin is the safety. The header gives the same scope {src:tests/installer/test_mcp_pins.py:5}.

## Dependencies

**Depends on.**
- Standard library: `os`, `re`, `subprocess`, `tempfile`, `unittest` {src:tests/installer/test_mcp_pins.py:13} {src:tests/installer/test_mcp_pins.py:14} {src:tests/installer/test_mcp_pins.py:15} {src:tests/installer/test_mcp_pins.py:16} {src:tests/installer/test_mcp_pins.py:17}. `from __future__ import annotations` is also present {src:tests/installer/test_mcp_pins.py:11}.
- `install.sh` at the repo root, read as text {src:tests/installer/test_mcp_pins.py:20}. [[install]] / [install](../../install.md).
- `bash`, run with a stub `claude` and a stub `npx` in a temp folder {src:tests/installer/test_mcp_pins.py:33} {src:tests/installer/test_mcp_pins.py:45}.

**Used by.** No product code imports it. The installer test runner calls `unittest discover` over `tests/installer` with `test_*.py` {src:tests/installer/run.sh:110}, and that runner is a step of the CI workflow {src:.github/workflows/tests.yml:38}. Searched `git grep test_mcp_pins` outside `docs/` (2026-11-21): nothing else names it. Siblings: [[test_python_hint]] and [test_python_hint](test_python_hint.md), [[test_requirements]] and [test_requirements](test_requirements.md).

## Behavior

Helper `registered_commands` reads `install.sh` and cuts out the text from the line that sets `ATLASSIAN_MCP_URL` up to the line that prints `Service connections saved` {src:tests/installer/test_mcp_pins.py:27} {src:tests/installer/test_mcp_pins.py:29} {src:tests/installer/test_mcp_pins.py:30}. It writes two stub programs into a temp folder: `claude` appends its arguments to a log file, and `npx` does nothing {src:tests/installer/test_mcp_pins.py:33} {src:tests/installer/test_mcp_pins.py:36}. It then runs a `bash -c` script that defines empty `ok` and `note` functions, sets the Atlassian, Notion and Slack methods all to `api`, pastes the cut block, and closes it with a `fi` {src:tests/installer/test_mcp_pins.py:39-43}. The script runs with a minimal environment: the temp folder first on `PATH`, `LOGFILE` and `HOME` pointing into the temp folder {src:tests/installer/test_mcp_pins.py:44} {src:tests/installer/test_mcp_pins.py:45}. It returns the log lines that start with `mcp add` {src:tests/installer/test_mcp_pins.py:48}.

| Test | What it proves |
|---|---|
| `test_three_npx_servers_are_registered` | Exactly three `mcp add` commands were logged {src:tests/installer/test_mcp_pins.py:52-54}. The code registers one command each for the Atlassian, Notion and Slack API options {src:install.sh:1497} {src:install.sh:1501} {src:install.sh:1503}. |
| `test_every_npx_package_is_pinned` | Each logged command holds `exec npx -y <package>`, and the package matches an optional `@scope/`, a name, then `@` and a version of two to four number groups {src:tests/installer/test_mcp_pins.py:22} {src:tests/installer/test_mcp_pins.py:56-60}. The code builds that command from the variables `MCP_REMOTE_PKG`, `NOTION_MCP_PKG` and `SLACK_MCP_PKG` {src:install.sh:1488} {src:install.sh:1468} {src:install.sh:1469} {src:install.sh:1470}. |

## Diagram

None needed: the helper builds one temp folder and runs one shell script; the two tests share its result.

## Notes

- The test cuts `install.sh` by two fixed text markers {src:tests/installer/test_mcp_pins.py:29} {src:tests/installer/test_mcp_pins.py:30}. If either line is reworded, `str.index` raises `ValueError` and both tests error, so a rewording is caught as a failure, not skipped.
- It checks that a version is present, not that it is a real or old enough release, and not that the Atlassian URL follows the package: the regex takes the first word after `npx -y` only {src:tests/installer/test_mcp_pins.py:58}.
- A fourth `npx` server added to the installer would make the count test fail until the count is updated {src:tests/installer/test_mcp_pins.py:54}.
- The pasted block ends inside the `else` branch of the `claude` check, so the script appends `fi` to close it {src:tests/installer/test_mcp_pins.py:42}; the `claude` stub must be found on `PATH` for that branch to run {src:install.sh:1491}.
- The header Date is empty {src:tests/installer/test_mcp_pins.py:4}.
- Inputs reaching a path, command, network address or outbound text: none from outside the test. The stub `claude` only writes to a log in the temp folder, and `npx` is a stub, so no package is downloaded and nothing goes over the network. Writes to shared files: none outside the temp folder, which is removed when the `with` block ends {src:tests/installer/test_mcp_pins.py:32}.
