---
name: tg-pr-review
description: Inbound PR review brief. Fetch diff, resolve scope, run review rules, draft up to three comments. Posts nothing.
model: sonnet
argument-hint: "[PR-NUMBER] [--repo OWNER/REPO] [--nits]"
---

# /tg-pr-review: Inbound PR Review Brief

**Folders:** `{vault}`, `{tickets}`, `{output}` name vault folders. Look each one up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_path <name>` (for example `$TOLLGATE_HOME/scripts/core/tg_path tickets`). If it prints `not set up`, stop and tell the user to run setup. `{ticket}` means the folder of one ticket: look it up when the command runs with `$TOLLGATE_HOME/scripts/core/tg_ticket_dir <KEY>` (it prints the folder, flat or under its prefix folder). If it exits 1 with `not found`, that ticket has no folder: say so and stop, unless this command's own steps create the ticket folder.

Author: {INITIALS}
Date:

**HARD RULE: Do not call the Skill tool at any point during this run.**

**Role:** Reviewer. You are reading someone else's code. You cannot block a merge. Your output is a brief and up to three draft comments. Nothing is sent automatically. The user reviews and posts every comment themselves. This command never posts, comments on, approves, requests changes on or edits a pull request, and never calls a write endpoint of the code host.

---

## Trigger

```
/tg-pr-review N
/tg-pr-review N --repo owner/repo
/tg-pr-review N --nits
```

`N` is the PR number. The repo comes from the current folder's git remote unless `--repo` is given. `--nits` turns style rules on; they are off by default because leaving type-hint notes on someone else's PR spends credibility on nothing.

---

## Step 0: Parse and fetch

Run `date` via Bash. Only read commands of `gh` are allowed in this run (`pr view`, `pr diff`, `api` with GET).

Parse the arguments: PR number (required), `--repo` (optional), `--nits` flag.

**Repo detection.** If `--repo` is not passed:
1. Run `git remote get-url origin` via Bash in the current working directory.
2. Parse `owner/repo` from the URL. Both SSH (`git@host:owner/repo.git`) and HTTPS (`https://host/owner/repo.git`) forms work. Strip protocol, host, and `.git` suffix.
3. If the result is the vault repo (the repo under `{vault}`), or if the command fails, stop and ask: "Which repo is this PR in? (e.g. owner/repo)"
4. Otherwise use the detected repo.

Fetch in parallel:

```bash
gh pr view N --repo REPO --json title,body,author,headRefName,baseRefName,additions,deletions,changedFiles,state,url
gh pr diff N --repo REPO
gh pr view N --repo REPO --json reviews,comments
```

From the PR body and branch name, extract the ticket key. Branch naming convention is `{KEY}/description` or `{KEY}-description`. Also scan the PR body for "closes", "fixes", or bare ticket references.

---

## Step 2: Scope resolution

**Read the ticket chain before producing any findings.** A finding whose severity depends on scope cannot be emitted until the chain is read.

Order:

1. Vault first: `{ticket}/` with the state, spec and design files
2. The ticket tracker connector, only if the vault folder is missing or a stub (under ~20 lines with no real content). The connector is off until first use; with no setup it prints `not set up`. Then continue with the vault copy and say the tracker was not read.
3. Parent ticket: if the spec or the tracker names a parent, read it
4. Any ticket named in "closes" or "resolves" in the PR body or description

A ticket title is routinely narrower than the requirement behind it. Read the parent chain before deciding whether a gap is in scope.

If no ticket is found: proceed, mark `intent` as NOT EVALUATED, note in the brief.

**Cite from the tracker, understand from the vault.** The vault answers what the change was supposed to do. Any name, status, date, or dependency that appears in output must come from a live tracker read with a ticket citation, never from the vault copy. If the tracker is not set up, tag such a value `(unverified: confirm before relying on this)`.

---

## Step 3: Run review rules

Review stage rules only. Evaluate each against **added lines only** (lines in `+` hunks). Never report a finding on a line you did not see added in this diff.

Fetch changed files at the PR head ref using `gh api` or the diff. Never read from a local checkout for the content you quote.

### Active rules at review stage

| Rule | Level | What fires |
|---|---|---|
| `secret` | RED | hardcoded credential, API key, token, private key in an added line |
| `phi-log` | RED | PHI field name interpolated inside a log/print call: `logger.info(f"mrn={mrn}")`: field name beside an interpolation inside a logging call. Silent on column references or prose mentioning the field name. |
| `phi-doc` | RED | Value shaped like a patient identifier in a doc file: nine-digit sequence in identifier shape, DOB beside a personal name, identifier column with real-looking values. Silent on schema definitions and column name prose. |
| `dyn-exec` | RED | `eval()`, `exec()`, `subprocess` with shell=True in an added line |
| `breaking` | RED | A key added to a required fields list where at least one existing config defines it and at least one sibling does not. Needs both a positive and a negative example; stay silent without both. |
| `coverage` | YELLOW | A new or signature-changed public function with no mention of its name in any changed test file |
| `impact` | YELLOW | An entity changed here that is referenced by files outside this PR's diff. Use `grep -r` across the repo to check. |
| `intent` | YELLOW | Diff scope diverges from ticket scope: the branch contains changes not described by the ticket chain. Report scope divergence, never code quality. |

**Style rules (`--nits` only):** T201 (print), E722 (bare except), B006 (mutable default), ANN001/ANN201 (type hints), D103 (missing docstring), ERA001 (commented-out code), S101 (assert outside tests), FIX002 (TODO/FIXME), PLR2004 (magic numbers), PLR0915 (functions over 40 statements), `hdr` (new file missing header).

If `--nits` is not set, skip all style rules entirely. Do not note them under "noted, not commented."

---

## Step 4: Output gates

Run these on every word of generated output before writing anything.

**`line-ref`: hard block.** No line number appears anywhere in the output. Anchor on the symbol name: the function, the config key, the table, the view. A line number is stale the moment anyone rebases. If the reader needs a location, GitHub provides it via inline comments.

**`citation`: hard block.** Every proper noun (function name, table name, config key, file name) that appears in a finding must be verified individually. A claim naming N artifacts requires N verifications. Below full coverage, downgrade from statement to question. No unverified assertion leaves as a statement.

**`stale-ref`: warn.** A cited ticket open and untouched past 14 days: note it as stale in the brief.

**PHI redaction.** If a diff snippet contains a value shaped like a patient identifier, do not quote it. Report the location (file name and symbol name) and the rule name only. The review file lands in the vault. PHI never enters the vault.

**No names, only roles.** Never name a person in the output. Use "the author", "the reviewer", "the author of ABC-123". A ticket number survives a reorg; a name does not.

---

## Step 5: Rank findings and draft comments

**Does the finding earn a comment at all?** One test: does it change the code, or change whether this merges? If neither, it goes to "noted, not commented" and nowhere else.

| Finding | Destination |
|---|---|
| Changes the code or the merge decision | draft comment |
| Changes a downstream decision but not this PR | one line in the approval note |
| Changes nothing actionable | "noted, not commented" only |

**Three comments maximum.** Rank by: severity first, then whether the finding is a deterministic fact. Draft at most three. List the rest under "NOTED, NOT COMMENTED."

**Comment form by evidence strength:**

| Evidence | Level | Form |
|---|---|---|
| Deterministic fact: grep found or did not find a literal | RED | Statement |
| Inference from a pattern | YELLOW | Question, with the conclusion marked as yours ("I'd guess", "reading that") |
| Preference | GREEN | Offer, explicitly non-blocking |

The finding is always about the change, never the person. No "you", no "why did you". The diff is the subject of every sentence.

Build each comment on the five-step model: share the facts, say what you concluded, ask for their version, phrase the conclusion tentatively, make it safe to disagree.

Statement example:
```
tenant_b.yml doesn't define source_key, and this change adds it to the
required list in _validate_config. tenant_b will raise on the next load.

Two options: add the key to tenant_b.yml, or make it required only when
the legacy path is absent, so existing configs keep loading.

Happy to take the first one if you'd rather keep this PR tight.
```

Question example:
```
_validate_config changed behaviour and test_validate.py isn't in the diff.
Reading that, I'd guess the required-key path isn't covered, but I may be
looking in the wrong place. Is it covered somewhere I missed?

Happy to add a case if it's useful.
```

---

## Step 6: Write the review brief

Write to `{output}/reviews/YYYY/YYYY-MM-DD-pr-N.md`. Create the year directory if needed. This is a file on this machine; it is not posted anywhere.

Format:

```
PR #N   REPO   author: [role or redacted per no-names rule]
branch -> base    +X/-Y, Z files

WHAT CHANGED
[Two to four sentences. Answer first. What the diff does, not what the ticket says it should do.]

TICKET CHAIN
[Ticket key and title. Parent if read. Any resolved tickets.]

PRIOR COVERAGE
[What automated review has run on this PR, if anything. "No automated review on this PR." if none.]

FINDINGS
  RED     [rule]   [symbol or file name, no line number]   [one line]
  YELLOW  [rule]   [symbol or file name]                   [one line]
  ...

NOTED, NOT COMMENTED
  [rule]   [location]   [one line reason not commented]

DRAFT COMMENTS   N of 3
  voice: internal · type: PR comment · stakes: [low/medium/high]

  [1] [file: symbol]   [LEVEL]
  [comment text]

  [2] ...

  [3] ...

ASK THE AUTHOR
[One question the diff cannot answer. Omit if there is nothing genuinely unclear.]

written to: {output}/reviews/YYYY/YYYY-MM-DD-pr-N.md
reviewed at: [head SHA from gh pr view]
```

---

## Step 7: Present to the user

Print the review brief to the terminal.

State:
- How many draft comments were produced and which need posting
- The path of the review file
- Any output gates that fired (redaction, downgrade from statement to question)

The user reviews the drafts and posts them, or does not. You do not post comments directly, by any route.
