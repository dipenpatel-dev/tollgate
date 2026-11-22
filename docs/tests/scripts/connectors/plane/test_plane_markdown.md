---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_markdown.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/plane_markdown.py]         # source files under test, relative paths from repo root
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

Unit tests for the small markdown to HTML renderer that the Plane connector uses for card descriptions and comments. They check that raw HTML is shown as text, that headings, paragraphs and lists come out in the expected shape, that a closing run of `#` is cut from a heading only after a space, that code is kept whole, that images never become image tags, that unsafe links are not made into links, and that empty text gives empty output.

## Dependencies

**Depends on.**
- `markdown_to_html` from [[plane_markdown]] ([plane_markdown](../../../../scripts/connectors/plane/plane_markdown.md)), the only code under test {src:tests/scripts/connectors/plane/test_plane_markdown.py:13} {src:scripts/connectors/plane/plane_markdown.py:104}.
- `plane_sync_test_support` from [[plane_sync_test_support]] ([plane_sync_test_support](plane_sync_test_support.md)), imported only for its side effect of putting the scripts folder on the module path {src:tests/scripts/connectors/plane/test_plane_markdown.py:10} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:29-31}.
- Standard library: `unittest` {src:tests/scripts/connectors/plane/test_plane_markdown.py:11}.

**Used by.**
- Product code: none. Tests are not imported by product code (searched with `git grep` for the file name outside `docs/`, 2026-11-20).
- Tests (runner): `tests/scripts/connectors/plane/run.sh` finds it with the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}.

## Behavior

Each test calls `markdown_to_html` with a short string and checks the output text. No server, folder or file is involved.

- **Raw HTML is escaped.** Input with a `script` tag gives output without the tag and with `&lt;script&gt;`, and bold markdown becomes a `strong` tag {src:tests/scripts/connectors/plane/test_plane_markdown.py:17-21}.
- **Structure.** A `##` heading gives an `h2`; two lines in a block become one paragraph joined by a newline; dash items become a `ul` with `li` items; numbered items become an `ol` {src:tests/scripts/connectors/plane/test_plane_markdown.py:23-28}.
- **Heading hash marks.** `## Using C#` keeps its `#` and gives `<h2>Using C#</h2>`, while `## Title ##` and `## Title #` both give `<h2>Title</h2>` {src:tests/scripts/connectors/plane/test_plane_markdown.py:30-33}. The pattern drops a closing run of `#` only when white space comes before it {src:scripts/connectors/plane/plane_markdown.py:15}.
- **Fenced block.** A fenced block comes out as `pre` and `code`, the arrow `-->` is escaped to `--&gt;`, and no paragraph tag appears {src:tests/scripts/connectors/plane/test_plane_markdown.py:35-39}.
- **Inline code.** Bold markers inside backticks stay as typed inside a `code` tag {src:tests/scripts/connectors/plane/test_plane_markdown.py:41-43}.
- **Images and links.** An image gives no `img` tag, while a normal `https` link becomes an anchor {src:tests/scripts/connectors/plane/test_plane_markdown.py:45-48}.
- **Unsafe link.** A `javascript:` link gives no anchor tag {src:tests/scripts/connectors/plane/test_plane_markdown.py:50-52}.
- **Empty text.** Empty input gives the empty string {src:tests/scripts/connectors/plane/test_plane_markdown.py:54-55}.
- **Underscores.** A status line with a word that has an underscore keeps that word in the output {src:tests/scripts/connectors/plane/test_plane_markdown.py:57-58}.

## Diagram

None: these are plain unit tests with no fixtures or mocks.

## Notes

- **Description versus code.** The header says "escaping, structure, links, no images" {src:tests/scripts/connectors/plane/test_plane_markdown.py:2}, which matches the tests. The Scope line says real HTTP goes to the local stub on `127.0.0.1` {src:tests/scripts/connectors/plane/test_plane_markdown.py:5}; this file makes no HTTP call and starts no stub, so that line does not describe it {src:tests/scripts/connectors/plane/test_plane_markdown.py:16-58}.
- **A test that cannot catch the bug it is named for.** `test_a_status_line_with_underscores_is_left_alone` uses a line with one underscore word only {src:tests/scripts/connectors/plane/test_plane_markdown.py:58}. A renderer that turns text between a pair of underscores into italics needs an opening and a closing underscore, and the input holds a single one, so the test would also pass with italic handling on. It fails only if the renderer drops the word.
- **Loose assertions.** The link test checks `assertNotIn("<a ", html)` for the `javascript:` case {src:tests/scripts/connectors/plane/test_plane_markdown.py:52}; it does not check what the text becomes, so any output without an anchor passes. The list test relies on exact newlines between tags {src:tests/scripts/connectors/plane/test_plane_markdown.py:27-28}, so a change to spacing breaks it.
- **No test for** nested lists, tables, links with a `data:` address or a `file:` address, or long input; the file holds nine tests, all listed above {src:tests/scripts/connectors/plane/test_plane_markdown.py:17-58}. The heading test does not cover a heading made only of `#` marks or a closing run with no text before it (searched this file, 2026-11-20).
- **Machine and version dependence.** None found; the file has no paths and no newer syntax. It does need the support module import to put `scripts` on `sys.path` {src:tests/scripts/connectors/plane/plane_sync_test_support.py:26-31}.
- **Unchecked inputs.** All inputs are fixed strings in the file. No input reaches a file path, shell command or network address.
- **Shared file writes.** None; the file writes nothing.
- The same image and link check also appears in `test_plane_fixes` through the comment builder import, so it is covered twice {src:tests/scripts/connectors/plane/test_plane_fixes.py:310-313}; see [[test_plane_fixes]] ([test_plane_fixes](test_plane_fixes.md)).
