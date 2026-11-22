# /tg-reference-import

Copies reference material into the owner's reference library, writes a README and an index for it, tells the other commands which situations it helps with, and adds it to the search index with the owner's tags {src:commands/tg-reference-import.md:6}.

The command name is fixed: `/tg-reference-import <path to a file or a folder> [tags]` {src:commands/tg-reference-import.md:8}.

## When to use

When you have documents, notes, papers or standards that `/tg-spec`, `/tg-arch`, `/tg-dev`, `/tg-qa`, `/tg-start` and `/tg-whiteboard` should draw on {src:commands/tg-reference-import.md:6}. Tollgate ships no reference material; the library is yours and optional {src:commands/tg-reference-import.md:12}.

## What it does

1. Looks up the library folder with `$TOLLGATE_HOME/scripts/core/tg_path references` and lists the files under your path by type {src:commands/tg-reference-import.md:10} {src:commands/tg-reference-import.md:34}. Only `.md`, `.txt`, `.rst` and `.epub` are searchable. Other types are left out and named. PDF files get a plain note: export them to text or markdown and run the command again {src:commands/tg-reference-import.md:36}. It reads only the first heading of each supported file {src:commands/tg-reference-import.md:38}.
2. Asks for a folder name, one to four tags and a one line description, with a suggested answer for each {src:commands/tg-reference-import.md:42-46}.
3. Reads `references.yaml` and asks which situations the material helps with: `spec_define`, `arch_design`, `dev_implement`, `qa_review`, `session_start` or `whiteboard`. Tags already on a situation are kept and the new ones are added {src:commands/tg-reference-import.md:50} {src:commands/tg-reference-import.md:64}. It warns once that a situation with a line searches only the listed tags {src:commands/tg-reference-import.md:63}.
4. Shows the whole plan and waits for one explicit yes before writing anything {src:commands/tg-reference-import.md:72} {src:commands/tg-reference-import.md:76}.
5. Copies the files, writes a README in the new folder, adds a row to the library index README, and writes `references.yaml` {src:commands/tg-reference-import.md:80-84}. On any name clash it stops and asks {src:commands/tg-reference-import.md:80}.
6. Adds the folder to the search index with `$TOLLGATE_HOME/scripts/search/tg-search add`, one `--tag` per tag {src:commands/tg-reference-import.md:91}. Exit 1 means nothing searchable was found, exit 2 means search is not set up (the files stay, and running the command again is safe), and any other failure is reported in one line {src:commands/tg-reference-import.md:99-101}.
7. Runs one test search for a mapped situation and shows source and tag lines only. No match is reported honestly, never as success {src:commands/tg-reference-import.md:108} {src:commands/tg-reference-import.md:112}.
8. Reports what was copied, left out, indexed and mapped, and states two limits {src:commands/tg-reference-import.md:123}.

## What it reads and writes

- Reads: the files under the path you give (names, sizes and the first heading only) and `references.yaml` {src:commands/tg-reference-import.md:38} {src:commands/tg-reference-import.md:50}.
- Writes: only inside the library folder, plus `references.yaml`. It never writes to the vault or any other place {src:commands/tg-reference-import.md:23}. It never overwrites a file {src:commands/tg-reference-import.md:24}. It never shows or copies passages of the material {src:commands/tg-reference-import.md:25}.
- The search index is shared live state. It is touched only in the add step, after your yes {src:commands/tg-reference-import.md:28}.
- It runs no vault git line and makes no commit. The library folder sits outside the vault.

## Limits

- Edits to a file reach the search only when you add it again by running the command {src:commands/tg-reference-import.md:123}. The rebuild leaves added files alone.
- It does not remove material. A file deleted from the library keeps its passages in the search {src:commands/tg-reference-import.md:123}.
- PDF is not supported {src:commands/tg-reference-import.md:36}.

## Hooks and gate lines

No gate line applies. It is not part of the spec, arch, dev, qa chain. If a file name or first heading looks like patient or personal data, the command stops and flags it before copying {src:commands/tg-reference-import.md:26}.

## Example

`/tg-reference-import ~/Downloads/design_notes` with the tag `design` and the situation `arch_design` copies the notes into the library, then `/tg-arch` searches only material tagged `design` when it designs {src:commands/tg-reference-import.md:63}.
