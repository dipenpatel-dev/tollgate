#!/usr/bin/env python3
# Author:    Dipen Patel (dipenpatel-dev)
# Date:
# Scope:     Nightly drift patrol, find code docs with update_needed marker and refresh metadata.
#            The vault mirror folder comes from the path loader.
# ChangeLog:
#   HIGH-3: write_frontmatter lstrips leading newline before reconstruction to prevent blank line accumulation
#   HIGH-4: TimeoutExpired caught in get_changed_files and resolve_repo_root; returns safe default on timeout
#   HIGH-1: write_frontmatter uses line-level replacement; no yaml.dump round-trip
#   HIGH-2: get_changed_files removes check=True; returncode guard; timeout=30 on both subprocess calls
#   Initial implementation

import argparse
import logging
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import get_path, NotSetUp, folder_name  # noqa: E402


SYSTEM_MAP_DIR = folder_name("system_map")
REFERENCE_DIR = folder_name("reference")
TICKETS_DIR = folder_name("tickets")
KNOWLEDGE_DIR = folder_name("knowledge")
EDUCATION_DIR = folder_name("education")
CONVERSATIONS_DIR_NAME = folder_name("conversations")
THREADS_DIR_NAME = folder_name("chat_threads")

MIRROR_SUBPATH = (REFERENCE_DIR + "/repos")
DOC_SUFFIX = ".md"
DOCS_SUBDIR = "docs"


def get_changed_files(repo_root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "log", "--since=24 hours ago", "--name-only", "--pretty=format:"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        logging.error("git log timed out after 30s in %s", repo_root)
        return []
    if result.returncode != 0:
        logging.error("git log failed (exit %d): %s", result.returncode, result.stderr.strip())
        return []
    seen: set[Path] = set()
    for raw in result.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        candidate = (repo_root / raw).resolve()
        if candidate.is_file():
            seen.add(candidate)
    return list(seen)


def doc_path_for(source_file: Path, repo_root: Path) -> Path:
    rel = source_file.relative_to(repo_root)
    return repo_root / DOCS_SUBDIR / rel.with_suffix(DOC_SUFFIX)


def parse_frontmatter(doc_path: Path) -> tuple[dict, str, str]:
    """Returns (fm_dict, body_text, raw_fm_text). raw_fm_text is empty when no frontmatter."""
    text = doc_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text, ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text, ""
    fm = yaml.safe_load(parts[1]) or {}
    return fm, parts[2], parts[1]


def write_frontmatter(
    doc_path: Path, raw_fm: str, body: str, updates: dict[str, Optional[str]]
) -> None:
    result_lines: list[str] = []
    for line in raw_fm.splitlines(keepends=True):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            result_lines.append(line)
            continue
        colon_pos = stripped.find(":")
        key = stripped[:colon_pos].strip() if colon_pos != -1 else None
        if key in updates:
            value = updates[key]
            if value is None:
                continue
            indent = line[: len(line) - len(line.lstrip())]
            result_lines.append(f"{indent}{key}: {value}\n")
        else:
            result_lines.append(line)
    doc_path.write_text("---\n" + "".join(result_lines).lstrip("\n") + "---" + body, encoding="utf-8")


def refresh_doc(doc_path: Path) -> bool:
    fm, body, raw_fm = parse_frontmatter(doc_path)
    if not fm.get("update_needed"):
        return False
    write_frontmatter(
        doc_path,
        raw_fm,
        body,
        updates={"last_updated": str(date.today()), "update_needed": None},
    )
    return True


def sync_docs_to_vault(docs_dir: Path, repo_name: str) -> None:
    mirror = get_path("vault") / MIRROR_SUBPATH / repo_name
    mirror.mkdir(parents=True, exist_ok=True)
    for src in sorted(docs_dir.rglob("*.md")):
        rel = src.relative_to(docs_dir)
        dest = mirror / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    logging.info("vault mirror synced: %s", mirror)


def patrol(repo_root: Path) -> int:
    repo_name = repo_root.name
    docs_dir = repo_root / DOCS_SUBDIR
    changed = get_changed_files(repo_root)
    logging.info("repo=%s  changed files (last 24h)=%d", repo_name, len(changed))

    updated = 0
    for src in changed:
        doc = doc_path_for(src, repo_root)
        if not doc.exists():
            logging.debug("no doc for %s", src.relative_to(repo_root))
            continue
        if refresh_doc(doc):
            logging.info(
                "refreshed  %s  (prose regen deferred, /doc-gen not yet available)",
                doc.relative_to(repo_root),
            )
            updated += 1
        else:
            logging.debug("no update_needed marker on %s", doc.relative_to(repo_root))

    logging.info("docs refreshed=%d", updated)
    if updated > 0 and docs_dir.exists():
        sync_docs_to_vault(docs_dir, repo_name)
    return updated


def resolve_repo_root(repo_path: Path) -> Optional[Path]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        logging.error("git rev-parse timed out after 30s in %s", repo_path)
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly code-doc drift patrol")
    parser.add_argument(
        "--repo-path", type=Path, default=Path("."), help="Path inside a git repo"
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format="%(levelname)s  %(message)s")

    repo_path = args.repo_path.resolve()
    if not repo_path.exists():
        logging.error("path does not exist: %s", repo_path)
        sys.exit(1)

    repo_root = resolve_repo_root(repo_path)
    if repo_root is None:
        logging.error("not inside a git repo: %s", repo_path)
        sys.exit(1)

    try:
        patrol(repo_root)
    except NotSetUp:
        logging.error("not set up")
        sys.exit(2)


if __name__ == "__main__":
    main()
