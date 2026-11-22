#!/usr/bin/env python3
# Module:      vault_staleness.py
# Description: Nightly vault staleness scan. Flags stale docs, open TODOs, broken wikilinks
#              and stale blocked items. Reads the vault, writes one report into the output
#              folder. Both folders come from the path loader.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Vault health report
# Version:     1.0
# ChangeLog:
#   Initial version
# Usage:       vault_staleness.py [--report-only]
#   --report-only  exit 0 even when issues are found (exit 2 means issues were found)

from __future__ import annotations

import logging
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp, folder_name, LAYOUT_SUBDIRS  # noqa: E402

SYSTEM_MAP_DIR = folder_name("system_map")
REFERENCE_DIR = folder_name("reference")
TICKETS_DIR = folder_name("tickets")
KNOWLEDGE_DIR = folder_name("knowledge")
EDUCATION_DIR = folder_name("education")
CONVERSATIONS_DIR_NAME = folder_name("conversations")
THREADS_DIR_NAME = folder_name("chat_threads")


VAULT = None
REPORT_PATH = None
REPORT_NAME = "vault-health-report.md"


def configure(vault=None, output=None) -> None:
    """Set the vault and the report path. With no arguments both come from the path loader."""
    global VAULT, REPORT_PATH
    VAULT = Path(vault) if vault is not None else get_path("vault")
    REPORT_PATH = (Path(output) if output is not None else get_path("output")) / REPORT_NAME

# Per-folder staleness thresholds (days since last git commit). The subfolders come from the layout
# table in core.paths; a subfolder not listed in SUBDIR_THRESHOLDS gets DEFAULT_THRESHOLD.
# Folders not in the layout are skipped. Tickets and memory are intentionally excluded.
DEFAULT_THRESHOLD = {"days": 60, "label": "Vault docs"}
SUBDIR_THRESHOLDS: dict[str, dict] = {
    "clients":          {"days": 45, "label": "Client profiles"},
    "pipelines":        {"days": 45, "label": "Pipeline docs"},
    "architecture":     {"days": 60, "label": "Architecture docs"},
    "data-model":       {"days": 90, "label": "Data model docs"},
    "platform-learning": {"days": 90, "label": "Learning notes"},
}
STALENESS_RULES: dict[str, dict] = {}
for _key, _subs in LAYOUT_SUBDIRS:
    if _key != "system_map":
        continue
    for _sub in _subs:
        STALENESS_RULES[SYSTEM_MAP_DIR + "/" + _sub] = SUBDIR_THRESHOLDS.get(_sub, DEFAULT_THRESHOLD)
STALENESS_RULES[EDUCATION_DIR] = {"days": 90, "label": "Education modules"}

# All vault folders scanned for TODOs and broken wikilinks (broader net)
CONTENT_SCAN_FOLDERS: list[str] = [
    SYSTEM_MAP_DIR,
    EDUCATION_DIR,
]

TODO_PATTERN = re.compile(r"^\s*-\s*\[\s*\]|TODO:|FIXME:", re.MULTILINE)
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#\n]+?)(?:[|#][^\]]*?)?\]\]")

# Folders skipped on purpose. Both are top level layout folders, matched by path segment.
MEMORY_DIR = folder_name("memory")
WIKILINK_SKIP_DIRS = (MEMORY_DIR,)


def under_folder(rel: str, folder: str) -> bool:
    """True when the vault relative path rel is the folder or sits inside it (whole path segments)."""
    rel_parts = Path(rel).parts
    folder_parts = Path(folder).parts
    return rel_parts[:len(folder_parts)] == folder_parts


def git_last_modified(path: Path) -> datetime | None:
    rel = str(path.relative_to(VAULT))
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ai", "--", rel],
        cwd=VAULT,
        capture_output=True,
        text=True,
    )
    ds = result.stdout.strip()
    if not ds:
        # Fall back to filesystem mtime for untracked files
        try:
            mtime = path.stat().st_mtime
            return datetime.fromtimestamp(mtime, tz=timezone.utc)
        except OSError:
            return None
    try:
        return datetime.fromisoformat(ds[:19]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def age_days(dt: datetime, today: datetime) -> int:
    return (today - dt).days


def collect_all_wikilink_targets() -> set[str]:
    """Build a lowercase stem → path map for every .md file in the vault."""
    targets: set[str] = set()
    for md in VAULT.rglob("*.md"):
        targets.add(md.stem.lower())
        targets.add(md.name.lower())         # with .md extension
    return targets


def scan_staleness(today: datetime) -> list[dict]:
    findings: list[dict] = []
    for folder_rel, rule in STALENESS_RULES.items():
        folder = VAULT / folder_rel
        if not folder.exists():
            continue
        for md in sorted(folder.rglob("*.md")):
            dt = git_last_modified(md)
            if dt is None:
                continue
            days = age_days(dt, today)
            if days >= rule["days"]:
                findings.append({
                    "type": "stale",
                    "label": rule["label"],
                    "path": str(md.relative_to(VAULT)),
                    "days": days,
                    "last_updated": dt.strftime("%Y-%m-%d"),
                    "threshold": rule["days"],
                })
    return findings


def scan_todos() -> list[dict]:
    findings: list[dict] = []
    for folder_rel in CONTENT_SCAN_FOLDERS:
        folder = VAULT / folder_rel
        if not folder.exists():
            continue
        for md in sorted(folder.rglob("*.md")):
            try:
                content = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if TODO_PATTERN.search(content):
                findings.append({
                    "type": "todo",
                    "path": str(md.relative_to(VAULT)),
                })
    return findings


def scan_broken_wikilinks(all_targets: set[str]) -> list[dict]:
    findings: list[dict] = []
    for folder_rel in CONTENT_SCAN_FOLDERS:
        folder = VAULT / folder_rel
        if not folder.exists():
            continue
        for md in sorted(folder.rglob("*.md")):
            # Skip known-intentional dirs
            rel = str(md.relative_to(VAULT))
            if any(under_folder(rel, skip) for skip in WIKILINK_SKIP_DIRS):
                continue
            try:
                content = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in WIKILINK_PATTERN.finditer(content):
                target = match.group(1).strip()
                target_stem = Path(target).stem.lower()
                target_name = Path(target).name.lower()
                if target_stem not in all_targets and target_name not in all_targets:
                    findings.append({
                        "type": "broken_wikilink",
                        "path": rel,
                        "target": target,
                    })
    return findings


def scan_stale_blocked(today: datetime) -> list[dict]:
    """Flag docs with status/blocked tag not touched in > 30 days."""
    findings: list[dict] = []
    blocked_pattern = re.compile(r"status/blocked", re.IGNORECASE)
    for md in VAULT.rglob("*.md"):
        rel = str(md.relative_to(VAULT))
        if under_folder(rel, TICKETS_DIR) or under_folder(rel, MEMORY_DIR):
            continue
        try:
            first_lines = md.read_text(encoding="utf-8", errors="ignore")[:500]
        except OSError:
            continue
        if not blocked_pattern.search(first_lines):
            continue
        dt = git_last_modified(md)
        if dt and age_days(dt, today) > 30:
            findings.append({
                "type": "stale_blocked",
                "path": rel,
                "days": age_days(dt, today),
                "last_updated": dt.strftime("%Y-%m-%d"),
            })
    return findings


def render_report(
    today: datetime,
    stale: list[dict],
    todos: list[dict],
    broken: list[dict],
    blocked: list[dict],
) -> str:
    ts = today.strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.append(f"# Vault Health Report")
    lines.append(f"Generated: {ts}\n")

    total_issues = len(stale) + len(todos) + len(broken) + len(blocked)
    lines.append("## Summary")
    lines.append(f"- Stale documents: {len(stale)}")
    lines.append(f"- Open TODOs: {len(todos)}")
    lines.append(f"- Broken wikilinks: {len(broken)}")
    lines.append(f"- Stale blocked items: {len(blocked)}")
    lines.append(f"- **Total issues: {total_issues}**\n")

    if stale:
        lines.append("## Stale Documents")
        by_label: dict[str, list[dict]] = defaultdict(list)
        for item in stale:
            by_label[item["label"]].append(item)
        for label, items in sorted(by_label.items()):
            threshold = items[0]["threshold"]
            lines.append(f"\n### {label} (threshold: {threshold} days)")
            lines.append("| File | Last Updated | Days Old |")
            lines.append("|---|---|---|")
            for item in sorted(items, key=lambda x: -x["days"]):
                lines.append(f"| {item['path']} | {item['last_updated']} | {item['days']} |")

    if todos:
        lines.append("\n## Open TODOs")
        lines.append("Files containing unchecked checkboxes or TODO/FIXME markers:\n")
        for item in todos:
            lines.append(f"- {item['path']}")

    if broken:
        lines.append("\n## Broken Wikilinks")
        lines.append("Wikilinks pointing to files that do not exist in the vault:\n")
        by_file: dict[str, list[str]] = defaultdict(list)
        for item in broken:
            by_file[item["path"]].append(item["target"])
        for path, targets in sorted(by_file.items()):
            unique = sorted(set(targets))
            lines.append(f"- **{path}**: {', '.join(f'`[[{t}]]`' for t in unique)}")

    if blocked:
        lines.append("\n## Stale Blocked Items")
        lines.append("Documents tagged `status/blocked` not updated in > 30 days:\n")
        lines.append("| File | Last Updated | Days Old |")
        lines.append("|---|---|---|")
        for item in sorted(blocked, key=lambda x: -x["days"]):
            lines.append(f"| {item['path']} | {item['last_updated']} | {item['days']} |")

    if total_issues == 0:
        lines.append("\n_No issues found. Vault is healthy._")

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        configure()
    except NotSetUp:
        print("not set up", file=sys.stderr)
        return 2
    if not VAULT.exists():
        log.error("vault folder not found")
        return 1

    today = datetime.now(tz=timezone.utc)

    all_targets = collect_all_wikilink_targets()

    stale = scan_staleness(today)
    todos = scan_todos()
    broken = scan_broken_wikilinks(all_targets)
    blocked = scan_stale_blocked(today)

    report = render_report(today, stale, todos, broken, blocked)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    total = len(stale) + len(todos) + len(broken) + len(blocked)
    print(f"vault_staleness: {total} issue(s), report at {REPORT_PATH}")

    return 0 if (total == 0 or "--report-only" in argv) else 2


if __name__ == "__main__":
    sys.exit(main())
