#!/usr/bin/env python3
"""
module_name: vault_health.py
description: Vault dead link scanner and index health check. Prints a short report; exits 1 when links are degraded or the index is stale.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the personal vault health script. Folders come from the path loader. Prints `not set up` (exit 2) with no vault.
  1.1.0: Conversation and chat thread folders are both left out, named from the layout.
usage: python3 vault_health.py [--top 5] [--json]
"""
import argparse
import json
import os
import pathlib
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
from core.paths import NotSetUp, get_path  # noqa: E402

VAULT: Path = Path(".")
EXCLUDE_DIRS = {"worktrees", ".git"}
STALE_HOURS = 25
DEAD_LINK_THRESHOLD = 10  # count above which search is considered degraded

# Literal citation shorthand that notes write when reporting past findings, not real link targets.
PLACEHOLDER_TARGETS = {
    "filename", "...", "(.*?)", "wiki links", "relative/path/to/skill-file", "memory_slug",
    "name", "wikilink", "wikilinks", "wiki", "wiki-link", "path/to/file", "module-name",
    "argparse", "json", "subprocess", "pathlib", "urllib", "yaml",
    "learnings", "decisions", "patterns",
}
NON_MD_EXTENSIONS = {"json", "py", "sh", "yaml", "yml", "csv", "txt", "ipynb"}

# Targets that live outside the vault by design.
OUT_OF_VAULT_PREFIXES: tuple = ("memory/",)   # replaced by the layout name in _setup()
MEMORY_SLUG_RE = re.compile(r"^(feedback|project|reference|user)[_-][a-z0-9_-]+$")

# A bare ticket reference resolves when the ID matches the ticket naming pattern.
# The folder does not have to exist, so links to old tickets with pruned folders still resolve.
TICKET_ID_RE = re.compile(r"^(?:[A-Za-z0-9_-]+/)?([A-Za-z]+-\d+)$")
TEMPLATE_RE = re.compile(r"YYYY|YY-MM-DD")


def _setup() -> None:
    """Resolve the vault and the folders to leave out (conversation and chat thread notes are out of scope)."""
    global VAULT, OUT_OF_VAULT_PREFIXES
    VAULT = get_path("vault")
    OUT_OF_VAULT_PREFIXES = (config.folder_name("memory") + "/",)
    for key in ("conversations", "chat_threads"):
        try:
            EXCLUDE_DIRS.add(config.folder_name(key).split("/")[0])
        except (KeyError, NotSetUp, IndexError):
            continue
    EXCLUDE_DIRS.update(config.extra_skip_dirs())


def _collect_vault_files() -> list[Path]:
    files = []
    for f in VAULT.rglob("*.md"):
        parts = set(f.parts)
        if parts & EXCLUDE_DIRS:
            continue
        if any(p.startswith(".") for p in f.parts):
            continue
        files.append(f)
    return files


def _collect_ticket_dirs() -> set[str]:
    dirs = set()
    for d in VAULT.rglob("*"):
        if not d.is_dir() or not re.match(r"^[A-Za-z]+-\d+$", d.name):
            continue
        if set(d.parts) & EXCLUDE_DIRS:
            continue
        dirs.add(d.name.lower())
    return dirs


def _resolve_wikilink(base: str, file_set: set[str], basename_map: dict[str, str], ticket_dirs: set[str]) -> bool:
    """Return True if the wikilink target resolves to a real vault file."""
    # Strip heading anchors and display aliases
    base = re.sub(r"[|#].*", "", base).strip()
    if not base:
        return True  # empty, ignore

    # Links into directories this checker deliberately does not index are out
    # of scan scope, not missing.
    if any(base == d or base.startswith(f"{d}/") for d in EXCLUDE_DIRS):
        return True

    if base.lower() in PLACEHOLDER_TARGETS:
        return True

    # Bash `[[ $VAR -eq 0 ]]` test syntax in indented shell examples, not a
    # wikilink. Real Obsidian targets never contain "$".
    if "$" in base:
        return True

    # Mermaid diagram node labels: quoted strings, multi-line or HTML content.
    # These appear inside [[...]] when Mermaid flow nodes use the same brackets.
    if base.startswith('"') or "\\n" in base or "<br/>" in base:
        return True

    # Directory references (trailing slash), not a file link.
    if base.endswith("/"):
        return True

    # Shell flags or options (starts with dash), not a vault path.
    if base.startswith("-"):
        return True

    # Spaces in a path are not valid Obsidian wikilink targets.
    if " " in base:
        return True

    # Template text containing un-substituted placeholders.
    if TEMPLATE_RE.search(base):
        return True

    if base.startswith(OUT_OF_VAULT_PREFIXES) or base.startswith("/"):
        return True

    if MEMORY_SLUG_RE.match(base.lower()):
        return True

    # Bare ticket ID pattern: accept any well-formed ID regardless of whether
    # the ticket directory currently exists, so historical refs to shipped or
    # cancelled tickets with pruned folders do not show as dead links.
    if TICKET_ID_RE.match(base):
        return True

    name = Path(base).name
    if "." in name and name.rsplit(".", 1)[-1].lower() in NON_MD_EXTENSIONS:
        return True  # out of scope: this checker only validates markdown cross-references

    # Full path match relative to vault root. Target may already carry its
    # own extension (a stray ".md" typed inside the brackets); try as-is
    # before assuming a bare basename that needs ".md" appended.
    if str(VAULT / base) in file_set:
        return True
    candidate = VAULT / (base + ".md")
    if str(candidate) in file_set:
        return True

    # Basename match (Obsidian short-form: [[filename]] resolves anywhere in vault).
    # Obsidian also accepts [[file.md]] with the extension present in the brackets;
    # strip .md so the stem lookup still finds the file.
    bn = name.lower()
    if bn in basename_map:
        return True
    if bn.endswith(".md"):
        if bn[:-3] in basename_map:
            return True

    return False


def check_dead_links(top_n: int = 10) -> dict:
    files = _collect_vault_files()
    file_set = {str(f) for f in files}
    basename_map = {f.stem.lower(): str(f) for f in files}
    ticket_dirs = _collect_ticket_dirs()

    dead: dict[str, int] = {}
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for link in re.findall(r"\[\[([^\]]+)\]\]", content):
            if not _resolve_wikilink(link, file_set, basename_map, ticket_dirs):
                base = re.sub(r"[|#].*", "", link).strip()
                dead[base] = dead.get(base, 0) + 1

    top = sorted(dead.items(), key=lambda x: -x[1])[:top_n]
    return {
        "total_missing": len(dead),
        "degraded": len(dead) > DEAD_LINK_THRESHOLD,
        "top_dead_links": [{"target": t, "ref_count": c} for t, c in top],
    }


def check_index_health() -> dict:
    result: dict = {}
    vault_col_dir = config.collection_dir("vault")
    build_state = vault_col_dir / "build_state.json"
    chroma_file = vault_col_dir / "chroma.sqlite3"
    result["index_dir_exists"] = vault_col_dir.exists()
    result["chroma_exists"] = chroma_file.exists()
    ref_file = build_state if build_state.exists() else (chroma_file if chroma_file.exists() else None)
    if ref_file:
        ts = ref_file.stat().st_mtime
        result["last_run"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        age_hours = (datetime.now().timestamp() - ts) / 3600
        result["index_age_hours"] = round(age_hours, 1)
        result["index_stale"] = age_hours > STALE_HOURS
    else:
        result["last_run"] = "unknown"
        result["index_stale"] = True
    return result


def format_text(dead: dict, index: dict) -> str:
    lines = ["VAULT HEALTH"]
    flag = " [DEGRADED]" if dead["degraded"] else ""
    lines.append(f"  Dead links: {dead['total_missing']} missing targets{flag}")
    for item in dead["top_dead_links"]:
        lines.append(f"    {item['ref_count']}x  [[{item['target']}]]")
    lines.append(f"  Index last run: {index.get('last_run', 'unknown')}")
    if index.get("index_stale"):
        lines.append("  Index: STALE, the index job may have failed")
    if not index.get("chroma_exists"):
        lines.append("  Index store: NOT FOUND, search unavailable")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Vault health check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--top", type=int, default=5, help="Top N dead links to show")
    args = parser.parse_args(argv)
    try:
        _setup()
    except NotSetUp:
        print("not set up")
        return 2
    if not VAULT.is_dir():
        print("not set up")
        return 2
    dead = check_dead_links(top_n=args.top)
    index = check_index_health()
    if args.json:
        print(json.dumps({"dead_links": dead, "index": index}, indent=2))
    else:
        print(format_text(dead, index))
    return 1 if (dead["degraded"] or index.get("index_stale") or not index.get("chroma_exists")) else 0


if __name__ == "__main__":
    sys.exit(main())
