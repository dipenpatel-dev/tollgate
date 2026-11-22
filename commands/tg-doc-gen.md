# /tg-doc-gen: Code Documentation Generator

**Folders:** `{reference}` names a vault folder. Look it up in Step 8, when the vault copy is written, with `$TOLLGATE_HOME/scripts/core/tg_path reference`. If it prints `not set up`, there is no vault mirror: skip the vault copy and say so (Step 8). The repo copy does not need the lookup.

Author: {INITIALS}
Date:

**Role:** Generate structured code documentation from source. Read the source, populate the matched template, write the repo copy, and write the vault copy when a vault mirror folder exists.

**Mindset:** Documentarian. Read the source as it actually runs, not as it appears intended. Every behavior claim cites a line. Every dependency names a path. Where the code and its own comments, docstrings or descriptions disagree, the page says what the code does and records the disagreement.

**Templates:** `$TOLLGATE_HOME/templates/code-docs/`

**Vault mirror:** `{reference}/repos/{repo-name}/` (written only when `{reference}/repos/` exists; see Step 8)

---

## Trigger

`/tg-doc-gen [file-path]` where file-path is relative to the repo root or absolute.

Examples:
- `/tg-doc-gen engine/core/assembler.py`
- `/tg-doc-gen src/config.yaml`
- `/tg-doc-gen Dockerfile`

---

## Step 0: Orient

Run `date`. Record as YYYY-MM-DD for `last_updated`.

Resolve the source file:
1. Detect the repo root: run `git -C [folder of the file] rev-parse --show-toplevel`. Do not use `cd`. In a git work tree this returns the work tree folder, which is the right root to write under.
2. Confirm the file exists: read it. If missing, stop: "File not found: [path]. No doc written."
3. Derive `source_file`: relative path from repo root (e.g., `engine/core/assembler.py`).
4. Derive the doc path: `{repo_root}/docs/{source path without its extension}.md`. For `engine/core/assembler.py` this is `{repo_root}/docs/engine/core/assembler.md`. The folders are kept.
5. Derive `repo_name`: the folder name of the main checkout. Run `git -C {repo_root} rev-parse --path-format=absolute --git-common-dir`; the result ends in `/.git`; `repo_name` is the name of the folder that holds that `.git`. This gives the same name from the main checkout and from any work tree. Never use the work tree folder name, the remote name, or the `repo` value of an existing page: an existing page can carry a wrong value, such as a work tree name with a ticket id on the end, and this run corrects it.
6. If a page already exists at the doc path, read its frontmatter only, never its prose. Step 5 uses that frontmatter to correct `repo` and to handle `update_needed` and extra fields.
7. Infer doc type from the extension map below. If the extension is not in the map, stop: "Unknown extension [ext]. No template available. No doc written."

**Extension to type map:**

| Pattern | Type |
|---|---|
| `*_test.py`, `test_*.py` | `test` |
| `*.py` | `module` |
| `*.yaml`, `*.yml` with filename matching `pipeline*` | `pipeline` |
| `*.yaml`, `*.yml` | `config` |
| `*.ipynb` | `notebook` |
| `*.sql` | `sql` |
| `*.sh`, `*.zsh`, `*.bash` | `shell` |
| `*.tf` | `terraform` |
| `Dockerfile`, `docker-compose.yml` | `dockerfile` |

Apply patterns top to bottom. First match wins. The test pattern fires before the general `.py` pattern.

State before proceeding (in a delegated run, put this line in the final report):
> "doc-gen: [source_file] -> type:[type], repo:[repo_name], date:[YYYY-MM-DD]"

---

## Step 1: Load template

Read `$TOLLGATE_HOME/templates/code-docs/[type].md`.

The template is the single source for the frontmatter fields and the section headings. Text inside square brackets, HTML comments, and `%%` comment lines in the template are instructions to the writer. They are replaced or removed and never appear in the finished page.

---

## Step 2: Extract source metadata

Read the full source file, every line. Extract structured metadata before generating any prose. Do not infer or guess values. Populate only what is visible in the source.

**Python files (module or test type):**

`language`: `python`.

`imports`: Scan every top-level `import X` and `from X import Y` statement. Record the module as written: for `from .core import assembler` record `.core`; for `from engine.core import assembler` record `engine.core`; for `import os` record `os`. Include the standard library and outside packages. Skip `from __future__`. List each module once.

`exports`: Every top-level `def` and `class` that is public (no leading underscore, not a dunder name), bare name only, no signature. Include a function wrapped by a decorator. Include a public lower-case module-level object that other code is meant to use (for example a server or app object). For module-level constants (ALL_CAPS names): list them all when there are 10 or fewer; when there are more, list only the ones another file in the repo imports or reads by attribute, tests included (search for them), and state the total count of the rest in Notes.

**Config files (config type):**

`format`: the file extension (`yaml`, `toml`, `json`, or `env`).
`governs`: one phrase stating what the file controls. Base it on the code that reads the keys (see the config rule in Step 3), not only on the key names.

**Notebook files (notebook type):**

`language`: from the notebook metadata field `kernelspec.language`.
`cluster_type`: from notebook tags or metadata if present; otherwise leave empty.

**Pipeline files (pipeline type):**

`trigger`: look for schedule, trigger, or continuous markers in the file content. If none found, leave empty.
`jobs`: list job names found in the file.

**Shell files (shell type):**

`entry_point`: the name of the main function or the first executable command block.
`requires`: list any tools or commands the script calls (grep the file for command invocations).

**Terraform files (terraform type):**

`provider`: the `provider` block name.
`resources`: list each `resource` type declared.

**Dockerfile (dockerfile type):**

`base_image`: the `FROM` line image name.
`exposes`: list each `EXPOSE` port.
`service`: the service name from `docker-compose.yml` if applicable; otherwise the image basename.

---

## Step 3: Generate prose

Generate each prose section in order. Every non-obvious behavioral claim carries an inline `{src:}` citation tag directly after the claim. When one sentence holds several claims, each claim gets its own tag. Never collect tags at the end of a paragraph or in a footnote.

**Citation tag forms:**
- `{src:path/to/file.py:42}` cited from line 42
- `{src:path/to/file.py:42-60}` a claim that rests on a block of lines; cite the range
- `{src:git:abc1234}` behavior confirmed via commit
- `{src:docs:name-or-url}` external reference
- `{unverified}` source not reachable during generation

Paths in tags are relative to the repo root. Every line number must be a line you read in this run. A tag may cite a file other than the source file when the claim rests on that file. One tag holds one reference: write two tags, never two references inside one pair of braces. A cited line, and the first and last line of a cited range, must be a line of code or config, never a blank line.

A claim that something is absent (no check, no caller, no reader) has no line to cite. State it in prose and say what was searched, for example "No file under `scripts/` imports this module (searched 2026-11-19)".

What requires citation: behavior assertions, data flow, dependency calls, error conditions, return values, non-obvious defaults.

What does not require citation: general purpose explanation, structural observation, naming rationale.

### Purpose (one paragraph)

State what the file does and why it exists. No behavioral claims here; save those for Behavior. Purpose is structural and motivational.

### Dependencies

Two short lists.

**Depends on.** What the file imports, reads, or needs at run time (other modules in the repo, config files, environment variables, outside programs).
- For a file in the same repo, check whether its page exists at the mirrored path under `docs/`. If it exists, write both link formats: `[[dependency-name]]` for the vault copy and `[dependency-name](../relative/path/dependency-name.md)` for the repo copy, with the relative path worked out from this page's folder. If it does not exist, write only the wiki link and append "(no doc yet)".
- For the standard library, outside packages, system programs and environment variables, write the plain name with no link.

**Used by.** What calls, imports, or binds this file. Search the whole repo except `.git`, virtual environment folders, `docs/` and generated image files, for importers, command files, config entries and installer lines that name it. Do not guess. Cite each one. List product code first, then tests on their own line marked as tests. If no product code uses it, say so plainly and say what was searched.

### Behavior

Describe the public interface and execution flow. Cite every non-obvious claim inline. Specific claims beat general ones. "Returns None when input list is empty {src:engine/core/assembler.py:87}" is better than "handles edge cases."

Describe what the code does when it runs. A docstring, comment or tool description is a claim about the code, not evidence. Check each one against the code before repeating it.

**Config files.** A config page must say what each key controls. For every key, search the repo for the code that reads it and cite that line for the effect. If a key is read nowhere, say so. If a key's value leaves a feature inactive by default, say so plainly.

### Notes

Edge cases, known limitations, maintenance notes. Always include, with citations:

- Every place where the code and its own description disagree: what the description says, what the code does.
- Every input that reaches a file path, a shell or other command, a network address, or outbound text without a check on its value. Name the input, where it is used, and state that no check exists. If every such input is checked, say that in one line.
- Every write to a shared file: whether it is atomic and whether anything stops two writers at once.

### Wording rules

- No em dashes anywhere in the page. Use commas, colons or periods.
- In the body of the page, do not write a status word in capitals as a bare word (for example the words for finished, released or signed-off states). A write hook reads that as an unsupported claim and rejects the write. When a status value is the subject, write it in lower case. The frontmatter line `status: ACTIVE` is not affected.

---

## Step 4: Generate diagrams

**module type: L2 required**

Generate an L2 Container diagram: `flowchart TD`, max 10 nodes.

Node label rules:
- Plain English only. Max 4 words per label.
- No code syntax in labels: no dots, underscores, parentheses, or camelCase.
- Use the node alias for the code name and a plain English string for the visible label. Example: `ScanPolicies["Scan policy IDs"]` not `referenced_policies`.
- Labels describe what the node does, not its code name.

**L3 optional (any type):**

Generate an L3 Component diagram for a function with decision gates, branching, or internal data paths not obvious from the signature. Skip straight-line functions. Functions that share one flow share one diagram. Max 12 nodes per diagram. Same label rules apply. When no L3 diagram is drawn, keep the heading and write "None: no function has branching that the signature does not show."

A module with classes may add one class diagram. A module with ordered calls between objects may add one sequence diagram. L2 stays a flowchart.

Chart rules (document-writer): allowed types are class, sequence, flowchart; er when `touches_data_model` is true. The chart check runs in Step 7, after the page is written.

**All other types:** skip diagrams unless the template specifies otherwise. When a diagram section is skipped, keep the heading and write one line saying why.

---

## Step 5: Build doc

Assemble the complete document from frontmatter and prose sections.

**Frontmatter:** use exactly the fields of the template from Step 1, in the template's order, keeping its inline comments. Fill them as follows:

- `repo`: `repo_name` from Step 0, even when the existing page holds a different value.
- `source_file`: relative path from Step 0.
- `status`: `ACTIVE`, unless the template shows a different value to keep.
- `last_updated`: the date from Step 0.
- `tags`, `links`: empty lists unless Step 2 or the source gives a value.
- Type-specific fields (`language`, `imports`, `exports`, `format`, `governs` and the others): from Step 2.
- `update_needed`: if the existing page carries this field, drop it. It marks a page that is out of date, and this run regenerates the page.
- Any other field present in the existing page but not in the template: keep it unchanged and name it in the final report.

**Prose sections:** the template's headings, in the template's order.

---

## Step 6: Write repo docs/ copy

Write the doc to the doc path from Step 0. Create any missing parent directories. If the file already exists, overwrite it. This is a full regeneration run, not an incremental update: the prose is written fresh, and only the existing frontmatter is consulted (Step 0).

If a hook rejects the write, read its message, fix the page content, and retry. After three rejections stop and report the hook message word for word.

Report: `Written: [absolute doc path]`

---

## Step 7: Check the written page

1. Confirm no template placeholder is left as a value or in the body: no instruction text in square brackets carried over from the template, and `last_updated` holds a real date. The template's inline comments after a field stay as they are.
2. Re-open every cited line, all of them, in batches by file, and confirm the claim beside it. Fix or remove any that do not hold. For a claim that something is absent, run the search again.
3. If the page has a diagram, run the chart check: `$TOLLGATE_HOME/scripts/chart/chart_check --role document-writer {doc path}`. Add `--ticket {KEY}` only when a ticket was named. Exit 1: fix every finding and run it again. Exit 2: report the error and continue.

---

## Step 8: Write vault mirror copy

Look up the mirror root: `$TOLLGATE_HOME/scripts/core/tg_path reference`, then add `/repos`.

- If the lookup prints `not set up`, or the `{reference}/repos` folder does not exist, write no vault copy. Report: `Vault mirror: skipped (no mirror folder)`. Do not create the root.
- If it exists, write the same doc content to `{reference}/repos/{repo_name}/{source path without its extension}.md`, creating missing folders under the root. Vault copy and repo copy are identical at write time because both link formats are already in the prose (one doc, two link formats). Report: `Vault mirror: [absolute vault path]`

---

## Step 9: Update repo index

Index path: `{repo_root}/docs/{repo_name}_index.md`

When several files are documented in parallel, skip this step in each run and update the index once at the end, from one place, so two runs never edit the index together.

**If index exists:** add an entry for this file under `## Modules` if not already present:

```
- [source path without extension](source path without extension.md): [one-line purpose from Purpose section]
```

Do not overwrite existing entries. Do not re-sort. Append to the end of the module list.

**If index does not exist:** create it from the `repo_index.md` template:

Frontmatter comes from `$TOLLGATE_HOME/templates/code-docs/repo_index.md`, filled the same way as Step 5 (`repo` is `repo_name`, `last_updated` is the date from Step 0). The body is:

```
## Modules

- [source path without extension](source path without extension.md): [one-line purpose]

## Diagram (L1, required)

[L1 Context diagram. Max 7 nodes. flowchart LR. Real repo name and top-level module names.]
```

Report: `Index: [absolute index path] (created | updated | skipped)`

---

## Output

```
doc-gen complete
  Source:   [source_file]
  Type:     [type]
  Repo doc: [repo docs/ path]
  Vault:    [vault mirror path, or skipped (no mirror folder)]
  Index:    [index path] (created | updated | skipped)
  Citations: [count]
  Kept fields not in template: [names, or none]
```

---

## Rules

- Cite every behavior claim inline, immediately after the claim
- Never populate `imports` or `exports` from memory: read the source file
- A description inside the source is a claim to check, never a fact to copy
- Do not generate docs for files with PHI content: stop and flag before any write
- Overwrite is full regeneration: read source fresh, do not carry forward old prose (only the existing frontmatter is read, per Step 0)
- The repo copy is always written; the vault copy is written in the same run whenever the mirror root exists
- Index update is always the final step: never before the doc is written
- If the source file is in a read-only repo: write docs/ to a scratch path and state so
- Never use `cd`; use absolute paths and `git -C`
