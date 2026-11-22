---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_standards.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/__init__.py, scripts/connectors/plane/__main__.py, scripts/connectors/plane/cli.py, scripts/connectors/plane/plane_comment_builder.py, scripts/connectors/plane/plane_drift_checker.py, scripts/connectors/plane/plane_markdown.py, scripts/connectors/plane/plane_sync.py, scripts/connectors/plane/plane_sync_ledger.py, scripts/connectors/plane/plane_sync_settings.py, scripts/connectors/plane/plane_ticket_syncer.py, scripts/connectors/plane/plane_work_item_client.py, scripts/connectors/plane/vault_ticket_creator.py, scripts/connectors/plane/vault_ticket_files.py]         # source files under test, relative paths from repo root
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

This test file holds the house rules for the plane connector package as automated checks. It does not run the connector. It reads the package's source files as text or as syntax trees and fails when a file breaks a rule: a banned import, a print call, an over-long function, a missing type hint, a missing header field, or a host name or person path in the text.

## Dependencies

**Depends on.**
- Standard library: `ast`, `re`, `unittest` {src:tests/scripts/connectors/plane/test_plane_standards.py:11-13}.
- [[plane_sync_test_support]] / [plane_sync_test_support](plane_sync_test_support.md). The test imports it first, only to put the scripts folder on the module path {src:tests/scripts/connectors/plane/test_plane_standards.py:10}, and takes `SCRIPTS` from it {src:tests/scripts/connectors/plane/test_plane_standards.py:15}. That module sets `SCRIPTS` to the `scripts` folder at the repo root {src:tests/scripts/connectors/plane/plane_sync_test_support.py:26-28}.
- The package folder `scripts/connectors/plane`, read through `PACKAGE_DIR` {src:tests/scripts/connectors/plane/test_plane_standards.py:17}. Pages: [[cli]] / [cli](../../../../scripts/connectors/plane/cli.md), [[plane_work_item_client]] / [plane_work_item_client](../../../../scripts/connectors/plane/plane_work_item_client.md). The other package files are read too (see Behavior).
- The test folder itself, in the last check {src:tests/scripts/connectors/plane/test_plane_standards.py:92}.

**Used by.** Searched with `git grep` for the file name, excluding `docs/` (2026-11-20). No product code names it.
- It is picked up by file-name pattern `test_*.py` in the plane runner {src:tests/scripts/connectors/plane/run.sh:6}, which the end-to-end runner calls for the area `connectors/plane` {src:tests/system/run.sh:22-23}. See [[run]] / [run](run.md).
- Tests: no other test imports it.

## Behavior

Shared constants: functions may be at most 40 lines {src:tests/scripts/connectors/plane/test_plane_standards.py:18}; banned import names are `requests`, `urllib.request`, `urllib.error`, `urllib3`, `http`, `socket`, `yaml`, `markdown_it`, `httpx`, `aiohttp` {src:tests/scripts/connectors/plane/test_plane_standards.py:20}; the type-hint check skips `__main__.py`, `plane_sync.py`, `__init__.py` {src:tests/scripts/connectors/plane/test_plane_standards.py:21}. `sources()` is every `*.py` directly in the package folder, sorted {src:tests/scripts/connectors/plane/test_plane_standards.py:24-25}.

Each test case, and what it proves:

1. `test_the_package_has_every_expected_file`: nine named files exist in the package folder, including `cli.py`, `plane_sync.py`, the template `plane_ticket_state_template.md` and the settings example {src:tests/scripts/connectors/plane/test_plane_standards.py:29-34}. The name set is built from the `*.py` list joined with every entry of the folder {src:tests/scripts/connectors/plane/test_plane_standards.py:30}; the first part is already inside the second, so only the folder listing matters. All nine exist today (listed 2026-11-20).
2. `test_no_request_library_or_outside_package_is_imported`: for each package file, walks the syntax tree, collects the names of `import X` and `from X import` statements {src:tests/scripts/connectors/plane/test_plane_standards.py:39-44}, and fails when a name equals a banned name or starts with it plus a dot {src:tests/scripts/connectors/plane/test_plane_standards.py:46-47}. Because `http` is on the list, `http.client` is banned too.
3. `test_the_framework_is_the_only_way_out`: checks the text `self._http.request(` is in the work item client {src:tests/scripts/connectors/plane/test_plane_standards.py:50-51} and that `cli.py` contains `registry.register(CONNECTOR_NAME` and `registry.ensure(CONNECTOR_NAME` {src:tests/scripts/connectors/plane/test_plane_standards.py:53-54}. Those strings are there: {src:scripts/connectors/plane/plane_work_item_client.py:160} {src:scripts/connectors/plane/cli.py:73} {src:scripts/connectors/plane/cli.py:171}.
4. `test_no_print_calls_no_todo_no_em_dash`: fails on a call to a bare name `print` {src:tests/scripts/connectors/plane/test_plane_standards.py:60-61}, on the text `TODO` {src:tests/scripts/connectors/plane/test_plane_standards.py:62}, and on the em dash character, built from its code number so this file holds none itself {src:tests/scripts/connectors/plane/test_plane_standards.py:19} {src:tests/scripts/connectors/plane/test_plane_standards.py:63}.
5. `test_functions_are_forty_lines_or_fewer`: every function or async function, including methods and nested ones, measured as last line minus first line plus one {src:tests/scripts/connectors/plane/test_plane_standards.py:67-70}. No file is skipped.
6. `test_every_function_has_type_hints`: for every plain function (not async) outside the skip list, a return annotation must exist and every argument other than `self` and `cls` must have an annotation {src:tests/scripts/connectors/plane/test_plane_standards.py:74-81}.
7. `test_every_file_has_the_header_fields`: the first 14 lines of each file must contain four strings: the author line, `Date:`, `Scope:`, `ChangeLog:` {src:tests/scripts/connectors/plane/test_plane_standards.py:85-87}, and must not match `Ticket:` or any date like 2026-11-20 {src:tests/scripts/connectors/plane/test_plane_standards.py:88}. An empty `Date:` field satisfies the check, as in the sibling source file {src:scripts/connectors/plane/vault_ticket_files.py:4}.
8. `test_no_company_host_or_person_words_in_the_connector_or_its_tests`: for the package folder and the plane test folder, every file directly inside (not subfolders) except this file is searched for a web address ending in `.us`, `.lan`, `.local`, `.internal` or `.home`, for `/Users/`, and for `infisical`, ignoring case {src:tests/scripts/connectors/plane/test_plane_standards.py:91-95}. This file is exempt because its own pattern contains those words {src:tests/scripts/connectors/plane/test_plane_standards.py:94}.

## Diagram

None: the cases are independent reads of source files with no fixture chain or mock.

## Notes

- **Code and description.** The header says it checks "headers, no print, short typed functions, no request library, no outside imports" {src:tests/scripts/connectors/plane/test_plane_standards.py:2}. Headers, print and function size are checked as stated. "No outside imports" is checked only against a fixed list of ten names {src:tests/scripts/connectors/plane/test_plane_standards.py:20}, not against all non-standard packages. The case name `test_the_framework_is_the_only_way_out` {src:tests/scripts/connectors/plane/test_plane_standards.py:49} proves only that three strings are present {src:tests/scripts/connectors/plane/test_plane_standards.py:51-54}; it cannot show that no other network path exists. The constant `SKIP_HINTS` {src:tests/scripts/connectors/plane/test_plane_standards.py:21} is used only to skip files in the type-hint check, so the name is misleading.
- **Gaps in the import check.** `from urllib import request` gives the module name `urllib`, which is not on the banned list, so it passes {src:tests/scripts/connectors/plane/test_plane_standards.py:41-42} {src:tests/scripts/connectors/plane/test_plane_standards.py:46}. A call such as `__import__("urllib.request")` is not an import statement and is not seen {src:tests/scripts/connectors/plane/test_plane_standards.py:39-44}; the framework registry uses that form for a base class {src:scripts/connectors/registry.py:68}.
- **Gaps in the type-hint check.** Async functions, `*args`, `**kwargs` and positional-only arguments are not checked {src:tests/scripts/connectors/plane/test_plane_standards.py:77-81}.
- **Gap in the host-word check.** Subfolders and `__pycache__` are not read because only direct files are scanned {src:tests/scripts/connectors/plane/test_plane_standards.py:93-95}. A file that is not valid UTF-8 would raise an error rather than a clean failure {src:tests/scripts/connectors/plane/test_plane_standards.py:95}.
- **Python version.** The length check uses `end_lineno`, which exists from Python 3.8 {src:tests/scripts/connectors/plane/test_plane_standards.py:70}. No machine path is written in the file; the package folder comes from the support module {src:tests/scripts/connectors/plane/plane_sync_test_support.py:26-28}.
- **Import side effect.** The support module imports the whole connector and the stub server at load time {src:tests/scripts/connectors/plane/plane_sync_test_support.py:33-40}, so a broken import anywhere in the package fails this file at load, before any rule runs.
- **Unchecked inputs.** None reach a file path, command, network address or outbound text: the folders are constants built from the repo location {src:tests/scripts/connectors/plane/test_plane_standards.py:17} {src:tests/scripts/connectors/plane/test_plane_standards.py:92}.
- **Writes to shared files.** None. The file only reads.
- Cases that cannot fail: none found. Every case asserts on real file content.
