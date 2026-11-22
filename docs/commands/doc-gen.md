# /tg-doc-gen

Writes structured documentation for one source file, to the repo and the vault in the same run, with every behavior claim tied to a source line {src:commands/tg-doc-gen.md:8} {src:commands/tg-doc-gen.md:118}.

The command name is fixed: `/tg-doc-gen [file-path]`, with the path relative to the repo root or absolute {src:commands/tg-doc-gen.md:20}.

## When to use

After you finish or change a file and want a doc that matches what the code does when it runs. Where the code and its own comments disagree, the page says what the code does and records the disagreement {src:commands/tg-doc-gen.md:10} {src:commands/tg-doc-gen.md:161}.

## What it does

1. Finds the repo root and the main-checkout repo name (never the work tree folder name), derives the doc path, and picks the doc type from the extension. It stops if the file is missing or the extension has no template {src:commands/tg-doc-gen.md:34-40}.
2. If a page already exists it reads only its frontmatter, never its prose {src:commands/tg-doc-gen.md:39}.
3. Loads the matching template, extracts metadata from the full source, and writes prose with inline `{src:path:line}` tags {src:commands/tg-doc-gen.md:65} {src:commands/tg-doc-gen.md:73} {src:commands/tg-doc-gen.md:118}.
4. Writes the repo page, re-opens every cited line to confirm each claim, runs the chart check if there is a diagram, writes the vault mirror copy, and updates the repo index {src:commands/tg-doc-gen.md:217} {src:commands/tg-doc-gen.md:228-229} {src:commands/tg-doc-gen.md:238} {src:commands/tg-doc-gen.md:244}.

## What it reads and writes

- Reads: the source file and the matching template in `$TOLLGATE_HOME/templates/code-docs/` {src:commands/tg-doc-gen.md:65}.
- Writes: a page at `{repo_root}/docs/{source path without extension}.md`, overwriting any old one with a full regeneration {src:commands/tg-doc-gen.md:37} {src:commands/tg-doc-gen.md:217}.
- Vault copy: the folder is looked up at run time with `$TOLLGATE_HOME/scripts/core/tg_path reference`, then `/repos` is added. The copy goes to `{reference}/repos/{repo_name}/`. If the lookup prints `not set up` or that folder does not exist, no vault copy is written and the report says `Vault mirror: skipped (no mirror folder)`. The command never creates the root {src:commands/tg-doc-gen.md:3} {src:commands/tg-doc-gen.md:235-238}.
- Index: `{repo_root}/docs/{repo_name}_index.md`, created or appended to, never re-sorted {src:commands/tg-doc-gen.md:244} {src:commands/tg-doc-gen.md:254}.
- Chart check: `$TOLLGATE_HOME/scripts/chart/chart_check --role document-writer {doc path}` on any diagram {src:commands/tg-doc-gen.md:229}.
- Frontmatter: the template's fields, in its order. An `update_needed` field on the old page is dropped; any other extra field is kept and named in the report {src:commands/tg-doc-gen.md:208-209}.

It runs no vault git line and makes no commit. It never uses `cd` {src:commands/tg-doc-gen.md:299}.

## Hooks and gate lines

No gate line applies. The write guards apply. A hook rejects em dashes and capital status words in the body; after three rejections the command stops and reports the hook message {src:commands/tg-doc-gen.md:167-168} {src:commands/tg-doc-gen.md:219}. If the source is in a read-only repo, the command writes docs to a scratch path and says so {src:commands/tg-doc-gen.md:298}. Files with patient data are not documented: it stops and flags before any write {src:commands/tg-doc-gen.md:294}.

## Example

`/tg-doc-gen src/loader.py` writes `docs/src/loader.md`, the vault copy when the mirror folder exists, and adds a line to the repo index {src:commands/tg-doc-gen.md:37} {src:commands/tg-doc-gen.md:238} {src:commands/tg-doc-gen.md:248-251}.
