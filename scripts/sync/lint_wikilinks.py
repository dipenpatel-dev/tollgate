"""
lint_wikilinks.py
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: Convert regular markdown links pointing to vault files into wiki links.
       The vault comes from the path loader. The scan state is kept in the state folder.
ChangeLog:
  Initial implementation
  State load and save use the shared helpers in vault_write_scan (atomic write, corrupt file safe).
Usage:
  python3 lint_wikilinks.py [--dry-run] [--full] [--skip-dir NAME]
  --dry-run  Report what would change, write nothing
  --full     Re-scan all files regardless of prior state
  --skip-dir Folder name to leave alone (repeatable), in addition to the built in list

Converts: [text](relative/path/to/file.md)     -> [[filename|text]]
          [text](relative/path/to/file.md#sec)  -> [[filename#sec|text]]
          [filename](relative/path/to/file.md)  -> [[filename]]       (text == stem)
Skips:    http/https URLs, anchor-only links (#), already-wiki links
"""

from __future__ import annotations

import os
import re
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_write_scan  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────

VAULT_DIR = None
STATE_FILE = None
STATE_NAME = "lint_wikilinks_state.json"

SKIP_DIRS = {".vector-index", ".git", ".obsidian", ".trash", "__pycache__"}


def configure(vault=None, state_dir=None) -> None:
    """Set the vault and the state file. With no arguments both come from the path loader."""
    global VAULT_DIR, STATE_FILE
    VAULT_DIR = Path(vault) if vault is not None else get_path("vault")
    state_root = Path(state_dir) if state_dir is not None else get_path("state")
    STATE_FILE = state_root / STATE_NAME

# ── Regex ─────────────────────────────────────────────────────────────────────

# Matches [text](target), captures text and target separately
# Negative lookbehind for ! to avoid image links
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")

# Already a wiki link, skip anything inside [[ ]]
WIKI_LINK_RE = re.compile(r"\[\[.*?\]\]")

# ── Converters ────────────────────────────────────────────────────────────────

def resolve_target(source_file: Path, raw_target: str) -> tuple[Path | None, str]:
    """
    Resolve a markdown link target relative to its source file.
    Returns (resolved_path_or_None, anchor_string).
    anchor_string is empty if no anchor.
    """
    # Separate anchor
    anchor = ""
    if "#" in raw_target:
        parts = raw_target.split("#", 1)
        raw_target = parts[0]
        anchor = parts[1]

    if not raw_target:
        return None, anchor

    # Skip external links
    if raw_target.startswith(("http://", "https://", "mailto:", "ftp://")):
        return None, anchor

    # Try file-relative resolution first
    resolved = (source_file.parent / raw_target).resolve()
    try:
        resolved.relative_to(VAULT_DIR.resolve())
        if resolved.exists():
            return resolved, anchor
    except ValueError:
        pass

    # Fall back to vault-root-relative (Claude often writes paths from vault root)
    resolved_vault = (VAULT_DIR / raw_target).resolve()
    try:
        resolved_vault.relative_to(VAULT_DIR.resolve())
        if resolved_vault.exists():
            return resolved_vault, anchor
    except ValueError:
        pass

    return None, anchor


def to_wiki_link(text: str, target_path: Path, anchor: str) -> str:
    """
    Build an Obsidian wiki link from text, resolved target path, and anchor.
    Uses just the stem (filename without extension). Obsidian resolves by name.
    """
    stem = target_path.stem  # e.g. 'my_note'
    target_str = f"{stem}#{anchor}" if anchor else stem

    # If display text matches the stem (case-insensitive), omit the alias
    if text.strip().lower() == stem.lower():
        return f"[[{target_str}]]"

    return f"[[{target_str}|{text}]]"


def convert_line(line: str, source_file: Path) -> tuple[str, int]:
    """
    Convert all eligible markdown links in a line to wiki links.
    Returns (converted_line, count_of_changes).
    """
    changes = 0

    # Track positions already inside [[...]] to avoid double-processing
    protected = set()
    for m in WIKI_LINK_RE.finditer(line):
        for i in range(m.start(), m.end()):
            protected.add(i)

    result = []
    pos = 0

    for m in MD_LINK_RE.finditer(line):
        # Skip if match overlaps a wiki link
        if any(i in protected for i in range(m.start(), m.end())):
            result.append(line[pos:m.end()])
            pos = m.end()
            continue

        text = m.group(1)
        raw_target = m.group(2).strip()

        resolved, anchor = resolve_target(source_file, raw_target)

        if resolved is None:
            # Cannot resolve or external link, keep as-is
            result.append(line[pos:m.end()])
            pos = m.end()
            continue

        wiki = to_wiki_link(text, resolved, anchor)
        result.append(line[pos:m.start()])
        result.append(wiki)
        pos = m.end()
        changes += 1

    result.append(line[pos:])
    return "".join(result), changes


# ── File scanner ──────────────────────────────────────────────────────────────

def convert_file(path: Path, dry_run: bool) -> int:
    """
    Convert all markdown links in a file to wiki links.
    Returns count of changes made (or that would be made in dry_run).
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(keepends=True)

    new_lines = []
    total_changes = 0

    for line in lines:
        new_line, changes = convert_line(line, path)
        new_lines.append(new_line)
        total_changes += changes

    if total_changes > 0 and not dry_run:
        path.write_text("".join(new_lines), encoding="utf-8")

    return total_changes


def find_vault_files() -> list[Path]:
    """Walk vault, return all .md files outside skip dirs."""
    results = []
    for dirpath, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f.endswith(".md") and not f.startswith("."):
                results.append(Path(dirpath) / f)
    return results


# ── State management ──────────────────────────────────────────────────────────

def load_state() -> dict:
    return vault_write_scan.load_json_state(STATE_FILE)


def save_state(state: dict) -> None:
    vault_write_scan.write_json_atomic(STATE_FILE, state)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--full", action="store_true", help="Re-scan all files")
    parser.add_argument("--skip-dir", action="append", default=[], help="Folder name to skip (repeatable)")
    args = parser.parse_args()
    try:
        configure()
    except NotSetUp:
        print("not set up", file=sys.stderr)
        sys.exit(2)
    SKIP_DIRS.update(args.skip_dir)

    state = {} if args.full else load_state()
    vault_files = find_vault_files()

    # Warn on duplicate stems, same filename in multiple vault locations causes
    # Obsidian to resolve wikilinks ambiguously (picks first alphabetical match).
    stem_map: dict[str, list[Path]] = {}
    for vf in vault_files:
        stem_map.setdefault(vf.stem, []).append(vf)
    for stem, paths in sorted(stem_map.items()):
        if len(paths) > 1:
            print(f"  Warning: duplicate stem '{stem}', wikilinks may resolve to wrong file:")
            for p in sorted(paths):
                print(f"    {p.relative_to(VAULT_DIR)}")

    total_files_changed = 0
    total_links_converted = 0
    skipped = 0
    errors = 0
    t_start = time.time()

    for path in vault_files:
        file_key = str(path.relative_to(VAULT_DIR))
        mtime = str(path.stat().st_mtime)

        if not args.full and not args.dry_run and state.get(file_key) == mtime:
            skipped += 1
            continue

        try:
            changes = convert_file(path, dry_run=args.dry_run)
        except Exception as e:
            print(f"  ERROR {file_key}: {e}")
            errors += 1
            continue

        if changes > 0:
            label = "would convert" if args.dry_run else "converted"
            print(f"  {label} {changes} link(s): {file_key}")
            total_files_changed += 1
            total_links_converted += changes

        if not args.dry_run:
            # Re-stat after potential write so next run skips unchanged files
            state[file_key] = str(path.stat().st_mtime)

    if not args.dry_run:
        save_state(state)

    elapsed = round(time.time() - t_start, 1)
    mode = "DRY RUN, " if args.dry_run else ""
    print(f"\n{mode}Done in {elapsed}s")
    print(f"  Files changed  : {total_files_changed}")
    print(f"  Links converted: {total_links_converted}")
    print(f"  Files skipped  : {skipped} (unchanged)")
    print(f"  Errors         : {errors}")


if __name__ == "__main__":
    main()
