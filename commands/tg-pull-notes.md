# /tg-pull-notes: Meeting Notes Puller

**Role:** Bring new exported meeting notes into the local meetings folder. It does not process notes into the vault and does not call any outside service.

**Source:** a folder of exported notes that the user names (a cloud drive mount, a download folder, any folder). Any meeting tool works as long as it drops markdown files there. Tollgate has no mail or drive connector, so the export is the seam.

**Destination:** the meetings folder from the path loader. Each note lands at `YYYY/MM/{date}_{title-slug}/notes.md` inside it. A hidden `.sync-state.json` in that folder remembers what was already pulled.

---

## Trigger

`/tg-pull-notes {source_folder}` pulls from the named folder.
`/tg-pull-notes {source_folder} full` ignores the state file and re-checks everything. It still never overwrites an existing `notes.md`.

With no folder given, ask once: "Which folder holds the exported notes?" Do not guess a folder.

**File names:** the puller only picks up files named like `2026-04-07 - Weekly Sync - 2026 04 07 13:29 PDT - Notes by Gemini.md`, plus copies ending `(1)`. Other files are skipped without a message. If a folder has files but none match, say so and stop.

---

## Step 0: State the plan

Say:
> "Pulling exported meeting notes from {source_folder}. I will check what is new with a dry run, scan the new files for personal identifiers, then copy them into the meetings folder."

No confirmation needed: this command makes no vault changes.

---

## Step 1: Dry run

```bash
python3 $TOLLGATE_HOME/scripts/sync/sync_meetings.py --source {source_folder} --dry-run
```

It lists each note it would create and prints a summary line (would sync, curated skips, unchanged skips, duplicates, errors). Add `--full` only for the full mode.

- Exit 1 or the text `not set up` means the meetings folder or the source is not set up: report it in one line and stop.
- `Source folder not found`: report it and stop.
- If it would sync 0 notes: report "No new notes. The meetings folder is up to date." and stop.

---

## Step 2: Personal identifier check (must pass before the real run)

Read each source file the dry run named. Scan for patient or personal identifiers: names, record numbers, birth dates, social security numbers, diagnoses, addresses, or any string that looks like a medical record ID.

If any file has one:
> "Personal identifiers found in {title}: {describe the type, never the value}. Nothing was written. Remove or move that file out of the source folder, or tell me to stop."

Then stop. The puller cannot skip a single file, so do not run Step 3 until the flagged file is out of the source folder and the dry run is repeated.

---

## Step 3: Pull

```bash
python3 $TOLLGATE_HOME/scripts/sync/sync_meetings.py --source {source_folder}
```

Add `--full` for the full mode. The script strips the export's style header, converts HTML entities, never overwrites an existing `notes.md` (so hand-edited notes stay safe) and records each source file by modified time. A read error on one file is counted and the run continues.

---

## Step 4: Report

```
MEETING NOTES PULL: {timestamp}
  Pulled:   {N} new
  Skipped:  {N} already there or unchanged
  Errors:   {N} (list file names or "none")

NEW NOTES
  {date}  "{title}"  ->  {YYYY/MM/folder}
```

Tell the user the notes are local only and are not yet in the vault. Processing them into vault notes is a separate step.

---

## Rules

- Never call an outside service. A mail or drive pull needs a connector the user sets up on first use; until then it prints `not set up`.
- The identifier check always runs before the real pull. No exceptions.
- Never write to the vault. Pull only.
- Never overwrite an existing `notes.md`.
- Never commit. Committing is a separate, explicit step.
