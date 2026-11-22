"""
sync_meetings.py
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: Sync meeting notes from a source folder of exported markdown files into the meetings
       folder. The source folder is given with --source (a cloud drive mount, for example);
       the meetings folder comes from the path loader. This is the seam where a meeting
       connector plugs in: any tool that drops exported markdown into a folder works.
Usage: python3 sync_meetings.py --source DIR [--dry-run] [--full]
  --source    Folder that holds the exported notes
  --dry-run   Show what would be synced without writing anything
  --full      Re-sync all files (ignore state, skip only if notes.md already exists)

Rules:
  - Never overwrites an existing notes.md (preserves manually curated files)
  - Strips the CSS header injected by document exports
  - Converts HTML entities (&#39; to ', &amp; to &, and so on)
  - Tracks synced files by source mtime in .sync-state.json inside the meetings folder. A corrupt
    state file is reported and replaced by an empty one; the state write is atomic.
  - Two meetings with the same date and title no longer collide: the second gets the start time
    (and then a number) added to its folder name. The "_targets" entry in the state file records
    which source file owns which folder, so a hand-curated folder is still never overwritten.
  - An empty title slug falls back to "untitled-meeting".
  - Each note is scrubbed of credentials and scanned for PHI before it is written. A PHI hit
    means the note is not written; a short record (file name, reason, no content) is appended to
    .quarantine.log in the meetings folder.
"""

from __future__ import annotations

import re
import sys
import html
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_write_scan  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────

DRIVE_DIR = None
MEETINGS_DIR = None
STATE_FILE = None


def configure(source=None, meetings=None) -> None:
    """Set the source and meetings folders. The meetings folder defaults to the path loader."""
    global DRIVE_DIR, MEETINGS_DIR, STATE_FILE
    DRIVE_DIR = Path(source) if source is not None else None
    MEETINGS_DIR = Path(meetings) if meetings is not None else get_path("meetings")
    STATE_FILE = MEETINGS_DIR / ".sync-state.json"


# Matches: "2026-04-07 - Weekly Sync - 2026 04 07 13:29 PDT - Notes by Gemini.md"
# Also handles duplicates: "Notes by Gemini (1).md"
FILENAME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) - (.+?) - \d{4} \d{2} \d{2} (\d{2}):(\d{2}) \w+ - Notes by Gemini(?: \(\d+\))?\.md$"
)
FALLBACK_SLUG = "untitled-meeting"
TARGETS_KEY = "_targets"

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s[:60].rstrip("-") or FALLBACK_SLUG


def parse_filename(filename: str) -> tuple[str, str] | None:
    """Return (date_str, title) or None if filename doesn't match pattern."""
    m = FILENAME_RE.match(filename)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def filename_time(filename: str) -> str:
    """The HHMM start time from a matching filename, or an empty string."""
    m = FILENAME_RE.match(filename)
    return (m.group(3) + m.group(4)) if m else ""


def pick_folder(date_str: str, slug: str, hhmm: str, ident: str, owner_of, on_disk) -> str:
    """Choose the folder name for a meeting.

    ident names the meeting (its source file name without a " (1)" copy marker). owner_of(name)
    gives the ident that owns a folder, or None. on_disk(name) says whether notes.md exists there.
    A folder owned by this meeting is reused. A free folder is taken. An unowned folder with
    notes.md at the plain name is a hand-curated one and is returned as is (the caller skips it
    and never overwrites). Otherwise the next candidate is tried: the plain name, then the name
    with the start time, then the name with the start time and a number.
    """
    base = f"{date_str}_{slug}"
    candidates = [base] + ([f"{base}_{hhmm}"] if hhmm else []) + [f"{base}_{hhmm or 'x'}_{n}" for n in range(2, 100)]
    for name in candidates:
        who = owner_of(name)
        if who == ident:
            return name
        if who is None and not on_disk(name):
            return name
        if who is None and name == base:
            return name
    return candidates[-1]


def strip_css_and_clean(text: str) -> str:
    """Remove Google Docs CSS header and convert HTML entities."""
    lines = text.splitlines()

    # Find first markdown heading, everything before is CSS/preamble
    heading_start = None
    for i, line in enumerate(lines):
        if re.match(r"^#{1,3} ", line):
            heading_start = i
            break

    if heading_start is not None:
        text = "\n".join(lines[heading_start:])
    elif len(lines) > 1:
        # No heading found, skip line 1 (the CSS blob) and take the rest
        text = "\n".join(lines[1:]).lstrip("\n")

    # Convert HTML entities
    text = html.unescape(text)
    return text.strip()

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=None, help="Folder that holds the exported notes")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without writing")
    parser.add_argument("--full", action="store_true", help="Re-sync all (ignore state)")
    args = parser.parse_args()
    if args.source is None:
        print("not set up: pass --source with the folder of exported notes", file=sys.stderr)
        sys.exit(1)
    try:
        configure(source=args.source)
    except NotSetUp:
        print("not set up", file=sys.stderr)
        sys.exit(2)

    if not DRIVE_DIR.exists():
        print("Source folder not found")
        return

    loaded = vault_write_scan.load_json_state(STATE_FILE)
    targets: dict = loaded.get(TARGETS_KEY) if isinstance(loaded.get(TARGETS_KEY), dict) else {}
    state: dict = {} if args.full else {k: v for k, v in loaded.items() if k != TARGETS_KEY}
    quarantine_log = MEETINGS_DIR / ".quarantine.log"
    quarantined = 0
    owner: dict = {}
    for source_name, rel in targets.items():
        owner[str(rel)] = source_name

    drive_files = sorted(f for f in DRIVE_DIR.iterdir() if f.name.endswith(".md"))

    synced = 0
    skipped_unchanged = 0
    skipped_exists = 0
    skipped_duplicate = 0
    errors = 0
    synced_this_run: set[str] = set()  # tracks targets created in current run (for dry-run dedup)

    for f in drive_files:
        parsed = parse_filename(f.name)
        if not parsed:
            # Silently skip files that don't match the Gemini naming convention
            continue

        date_str, title = parsed
        slug = slugify(title)
        year, month = date_str[:4], date_str[5:7]
        month_dir = MEETINGS_DIR / year / month
        ident = re.sub(r" \(\d+\)\.md$", ".md", f.name)
        folder_name = pick_folder(
            date_str, slug, filename_time(f.name), ident,
            lambda name: owner.get(f"{year}/{month}/{name}"),
            lambda name: (month_dir / name / "notes.md").exists(),
        )
        target_dir  = month_dir / folder_name
        target_file = target_dir / "notes.md"

        mtime = str(f.stat().st_mtime)

        # Duplicate (e.g. "Notes by Gemini (1).md"), skip if primary already in state
        base_name = re.sub(r" \(\d+\)\.md$", ".md", f.name)
        if base_name != f.name and base_name in state:
            skipped_duplicate += 1
            continue

        # Never overwrite an existing notes.md (preserves manually curated files)
        if target_file.exists() or str(target_file) in synced_this_run:
            state[f.name] = mtime
            skipped_exists += 1
            continue

        # Skip if mtime unchanged
        if not args.full and state.get(f.name) == mtime:
            skipped_unchanged += 1
            continue

        if args.dry_run:
            print(f"  Would create: {target_dir.relative_to(MEETINGS_DIR)}/notes.md")
            synced += 1
            synced_this_run.add(str(target_file))
            owner[f"{year}/{month}/{folder_name}"] = ident
            continue

        try:
            raw = f.read_text(encoding="utf-8", errors="ignore")
            content = strip_css_and_clean(raw)
        except Exception as e:
            print(f"  Error reading {f.name}: {e}")
            errors += 1
            continue

        scan = vault_write_scan.scan_or_none(content)
        if scan is None:
            print(f"  Error scanning {f.name}: scan could not run, not written")
            errors += 1
            continue
        if scan.quarantine:
            vault_write_scan.record_quarantine(quarantine_log, f.name, scan.reason())
            print(f"  Quarantined {f.name}: {scan.reason()}")
            quarantined += 1
            state[f.name] = mtime
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(scan.text, encoding="utf-8")
        state[f.name] = mtime
        targets[ident] = f"{year}/{month}/{folder_name}"
        owner[f"{year}/{month}/{folder_name}"] = ident
        synced += 1
        synced_this_run.add(str(target_file))
        print(f"  Synced: {folder_name}")

    if not args.dry_run:
        vault_write_scan.write_json_atomic(STATE_FILE, {**state, TARGETS_KEY: targets})

    label = "Would sync" if args.dry_run else "Synced"
    print(f"\n{label}: {synced}  |  Curated skip (file exists): {skipped_exists}  |  Mtime skip (source unchanged): {skipped_unchanged}  |  Duplicates skipped: {skipped_duplicate}  |  Errors: {errors}  |  Quarantined (PHI): {quarantined}")


if __name__ == "__main__":
    main()
