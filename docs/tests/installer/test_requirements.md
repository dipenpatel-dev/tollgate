---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/installer/test_requirements.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/requirements.txt, scripts/requirements-epub.txt, scripts/requirements-extras.txt]         # source files under test, relative paths from repo root
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

Three tests for the Python requirements files in `scripts/`. They check that every listed library has both a lower and an upper version bound, that the AGPL-licensed `ebooklib` sits only in the optional epub file, and that the optional extras file names exactly the two libraries it should. The header gives the same scope {src:tests/installer/test_requirements.py:5}.

## Dependencies

**Depends on.**
- Standard library: `os`, `re`, `unittest` {src:tests/installer/test_requirements.py:13} {src:tests/installer/test_requirements.py:14} {src:tests/installer/test_requirements.py:15}.
- The three files `scripts/requirements.txt`, `scripts/requirements-epub.txt` and `scripts/requirements-extras.txt`, found from the test location {src:tests/installer/test_requirements.py:18} {src:tests/installer/test_requirements.py:23} {src:tests/installer/test_requirements.py:29}.

**Used by.** Run by the installer test runner through `unittest discover` over `tests/installer` {src:tests/installer/run.sh:110}, a step of the CI workflow {src:.github/workflows/tests.yml:38}. Searched `git grep test_requirements` outside `docs/` (2026-11-21): only a vault note and no code. Siblings: [[test_mcp_pins]] and [test_mcp_pins](test_mcp_pins.md), [[test_python_hint]] and [test_python_hint](test_python_hint.md).

## Behavior

Helper `packages(name)` returns the lines of a requirements file with surrounding spaces removed, skipping blank lines and lines that start with `#` {src:tests/installer/test_requirements.py:22-24}. The bound pattern `BOUNDED` accepts only a name, `>=`, a version, a comma, `<` and a version, with nothing else {src:tests/installer/test_requirements.py:19}.

| Test | What it proves |
|---|---|
| `test_every_line_has_a_lower_and_upper_bound` | For each of the three files, there is at least one package line, and every line matches `BOUNDED` {src:tests/installer/test_requirements.py:29-33}. The real files use the form `name>=x,<y`, for example `chromadb>=1.5.9,<2` {src:scripts/requirements.txt:9} {src:scripts/requirements-epub.txt:5} {src:scripts/requirements-extras.txt:4}. |
| `test_ebooklib_is_only_in_the_optional_epub_file` | No line of `requirements.txt` starts with `ebooklib`, and one line of `requirements-epub.txt` does {src:tests/installer/test_requirements.py:36} {src:tests/installer/test_requirements.py:37}. |
| `test_extras_name_the_lazy_imports` | The library names in the extras file, taken as the text before the first `<`, `>` or `=`, are exactly `anthropic` and `aiohttp` {src:tests/installer/test_requirements.py:40} {src:tests/installer/test_requirements.py:41}. |

## Diagram

None needed: each test reads files and compares text.

## Notes

- `test_extras_name_the_lazy_imports` is named for lazy imports but only compares the names in the file with a fixed pair. It does not open any script to see what is imported {src:tests/installer/test_requirements.py:39-41}.
- A line with an environment marker, an extra such as `pkg[extra]`, or a third bound would fail `BOUNDED`, so adding one needs the pattern changed {src:tests/installer/test_requirements.py:19}.
- The test does not check that `beautifulsoup4` in `requirements.txt` is needed there. The file's own comment says it is used for epub text only {src:scripts/requirements.txt:6}, and the code imports it only inside `chunk_epub` {src:scripts/search/build_index.py:193}, yet it is still installed by default.
- The header Date is empty {src:tests/installer/test_requirements.py:4}. Inputs reaching a path, command, network address or outbound text: only the three fixed file names. Writes to shared files: none, the test only reads.
