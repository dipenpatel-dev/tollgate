# /tg-pull-notes

**It copies new exported meeting notes from a folder you name into the local meetings folder.** Use it after you export notes from your meeting tool. It makes no outside calls and writes nothing to the vault {src:commands/tg-pull-notes.md:3} {src:commands/tg-pull-notes.md:86}.

The command name is fixed: `/tg-pull-notes {source_folder}`. Add `full` to ignore the state file and re-check everything; it still never overwrites an existing `notes.md` {src:commands/tg-pull-notes.md:13-14}.

## What it does

1. Asks "Which folder holds the exported notes?" if you gave none. It does not guess a folder {src:commands/tg-pull-notes.md:16}.
2. Runs a dry run to list what is new {src:commands/tg-pull-notes.md:34}. It stops if the dry run exits 1 or prints `not set up`, if the source folder is not found, or if nothing is new {src:commands/tg-pull-notes.md:39-41}.
3. Reads each new file and checks for personal identifiers. If it finds one it stops and tells you the type, never the value. Remove that file from the source folder and run again; the puller cannot skip a single file {src:commands/tg-pull-notes.md:47-52}.
4. Runs the real pull and reports how many notes were pulled and skipped, then tells you the notes are local only {src:commands/tg-pull-notes.md:59} {src:commands/tg-pull-notes.md:70-72} {src:commands/tg-pull-notes.md:78}.

Only files named like `2026-04-07 - Weekly Sync - 2026 04 07 13:29 PDT - Notes by Gemini.md` (and copies ending `(1)`) are picked up. Others are skipped without a message. If the folder has files but none match, it says so and stops {src:commands/tg-pull-notes.md:18}. An existing `notes.md` is never overwritten {src:commands/tg-pull-notes.md:62}.

## What it reads and writes

- Reads: the source folder you name {src:commands/tg-pull-notes.md:5}.
- Writes: `YYYY/MM/{date}_{title-slug}/notes.md` in the meetings folder (taken from the path loader), and a hidden `.sync-state.json` there. No vault changes. It does not commit {src:commands/tg-pull-notes.md:7} {src:commands/tg-pull-notes.md:86} {src:commands/tg-pull-notes.md:88}.
- Script: `python3 $TOLLGATE_HOME/scripts/sync/sync_meetings.py --source {source_folder}`, with `--dry-run` for the first pass and `--full` for the full mode {src:commands/tg-pull-notes.md:34} {src:commands/tg-pull-notes.md:59} {src:commands/tg-pull-notes.md:62}.
- It uses no `tg_path` folder lookup, no search and no vault git line.

Tollgate has no mail or drive connector; the export is the seam. A mail or drive pull would need a connector that is off until first use and prints `not set up` {src:commands/tg-pull-notes.md:5} {src:commands/tg-pull-notes.md:84}.

## Hooks and gate lines

None apply. It writes outside the vault and touches no gate line {src:commands/tg-pull-notes.md:86}.

## Example

```
/tg-pull-notes ~/Downloads/meeting-exports
```

Reports "Pulled 2 new, skipped 5" and lists the two new notes. For ticket T-001 work, the notes stay local until you process them {src:commands/tg-pull-notes.md:70-72} {src:commands/tg-pull-notes.md:78}.
