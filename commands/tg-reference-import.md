# /tg-reference-import

Author: {INITIALS}
Date:

Add reference material to the owner's reference library: documents, notes, papers, standards, anything the owner wants the other commands to draw on. The command copies the files into the library folder, writes a short README for them, updates the library index, tells the commands which situations the material helps with, and adds the files to the search index with the owner's tags. After this, `/tg-spec`, `/tg-arch`, `/tg-dev`, `/tg-qa`, `/tg-start` and `/tg-whiteboard` find the material by themselves.

Usage: `/tg-reference-import <path to a file or a folder> [tags]`

**Folders:** `{references}` names the library folder. Look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path references`. If it prints `not set up`, stop and tell the user to run setup.

The reference library is the owner's own and is optional. Tollgate ships none. This command never blocks any other command.

## How the pieces fit

Say this in two sentences the first time the command runs, and no more:

1. A tag is a label the owner chooses, such as `design` or `security`. Every piece of the material carries its tags.
2. A situation is what a command is doing, such as writing a spec. A line in `references.yaml` says which tags to search in that situation. A situation with no line searches everything.

## Rules

- Write only inside `{references}` and to `references.yaml`. Never write to the vault, the code folders or any other place.
- Never overwrite a file. If a name already exists in the target folder, stop and ask.
- Never show or copy passages of the material into the chat or into any other file. File names, sizes and the first heading are enough.
- PHI or PII: the library must hold none. If a file name or a first heading looks like patient or personal data, stop, flag it, and do not copy it.
- One gate: the owner sees the full plan in Step 4 and says yes once before anything is written.
- The search index is shared live state. It is touched only in Step 6, after the yes.

## Steps

### Step 1: Look at what was given

1. Look up `{references}`. Confirm the path in the argument exists. If it does not, say so and stop.
2. List the files below the path. Count them by extension.
3. Supported types are `.md`, `.txt`, `.rst` and `.epub`. Every other type is not searchable and is left out. Name the left out types and counts in one line. For `.pdf` say: "PDF files cannot be searched yet. Export them to text or markdown and run this command again."
4. If no supported file is left, say so and stop.
5. For each supported file, read only its first heading or first line, so the README can describe it. Read nothing else.

### Step 2: Ask for tags and a name

Ask these together, with a pick and a reason for each:

1. **Folder name.** The name of the folder inside `{references}` that holds this material, lower case with underscores, for example `design_notes`. Suggest one from the source folder name.
2. **Tags.** One to four labels. Suggest them from the folder name and the headings. Tags are saved in lower case, with any character other than letters, digits, dots, underscores and hyphens turned into a hyphen.
3. **One line.** What the material is and what it is good for, in the owner's words.

### Step 3: Map situations

1. Read `references.yaml`. It sits in the same folder as the paths file, which is `~/.claude/tollgate/` after a normal install. If it does not exist yet, it is created in Step 5.
2. Show the situations a command can ask for, with what each one is:

   | Situation | Asked by | When |
   |---|---|---|
   | `spec_define` | `/tg-spec` | framing the problem for a spec |
   | `arch_design` | `/tg-arch` | designing the solution |
   | `dev_implement` | `/tg-dev` | writing the code |
   | `qa_review` | `/tg-qa` | reviewing the work |
   | `session_start` | `/tg-start` | opening a work session |
   | `whiteboard` | `/tg-whiteboard` | checking a new idea |

3. Ask which situations this material helps with. Suggest from the tags, and give the reason.
4. Warn once, plainly: once a situation has a line in `references.yaml`, searches in that situation look only at material that carries one of the listed tags. Material with other tags is not searched there. The line for a situation must therefore list every tag the owner wants searched in it. A situation with no line searches everything.
5. When a chosen situation already has a line, keep its existing tags and add the new ones. Never remove a tag the owner did not name.

### Step 4: Show the plan and wait

State in one block, then ask for a yes:

1. Files to copy: count, and the target folder `{references}/<folder name>/`.
2. Files left out, with the reason.
3. Files that would be written: the README in the new folder, the library index `{references}/README.md`, and `references.yaml` (each shown as created or updated, with the exact new line for `references.yaml`).
4. Index change: the search index gains the copied files with the chosen tags. Adding the same files again later replaces them, never doubles them.
5. What it does not do: nothing is deleted, nothing is overwritten, nothing outside `{references}` and `references.yaml` is touched.

Wait for an explicit yes. A change to the plan means showing the plan again.

### Step 5: Copy and write

1. Check that the target folder has none of the incoming names. On any clash, stop and ask the owner for another folder name.
2. Create the folder and copy the supported files into it, keeping the subfolders below the source. Copy only supported types.
3. Write `{references}/<folder name>/README.md`: the one line from Step 2, the tags, the situations, the date, the list of files with their first heading, and the line "Edits to these files reach the search index only when this command adds them again."
4. Write the library index `{references}/README.md`. If it does not exist, create it with a one line purpose and a table with the columns Folder, What it is, Tags, Situations, Added. If it exists, add one row for this folder and change no other row.
5. Write `references.yaml`. If it does not exist, create it with a first comment line saying what the file is. Each line has the form `situation: [tag, tag]`. Change only the lines for the chosen situations.

### Step 6: Add to the search index

Run the add through the one search command:

```bash
$TOLLGATE_HOME/scripts/search/tg-search add {references}/{folder} --tag {tag one} --tag {tag two} 2>/dev/null
```

Repeat `--tag` once per tag. Replace the words between braces with the real folder and tags.

Handle the outcomes:

- Exit 0, the line `added N chunks from M files, tags: ...`: report it as is.
- Exit 1, `nothing to add`: say the files were copied but gave no searchable text, and name the likely cause (empty files or an unreadable `.epub`).
- Exit 2, `not set up`: say the files and the README are in place but the search is not set up. Tell the owner to set up search (`bash $TOLLGATE_HOME/scripts/search/rebuild.sh`) and then run this command again with the same path. Adding again is safe.
- Any other result: say the add failed in one line, without the error text, and stop. The copied files stay.

### Step 7: Test it once

1. For the first chosen situation, search with words from the first heading of one copied file:

   ```bash
   $TOLLGATE_HOME/scripts/search/tg-search reference --situation {situation} --stakes low --query "{words from a heading}" --top 3 2>/dev/null
   ```

2. Show the passages as source and tag lines only. Do not paste passage text.
3. `no match` is a valid outcome. Say so honestly. The cause may be a weak local embedder or a heading with few words. Do not claim the material is findable when the test found nothing.

### Step 8: Report

Report in this order:

1. Copied: count, target folder.
2. Left out: types and counts, and the PDF note when PDFs were present.
3. Indexed: chunks and files, tags.
4. Situations now mapped, with the full tag list of each.
5. Files written: the two READMEs and `references.yaml`.
6. Two limits, said once: edits to a file reach the search only when the file is added again by running this command, and this command does not remove material. A file deleted from the library keeps its passages in the search, and no command removes them yet.

End with the one action for the owner, usually "Open a spec or design and the material is used."
