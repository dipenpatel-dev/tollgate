"""
module_name: refstore.py
description: Shared helpers for the reference store: open the references collection, read the situation to tag file, format passages.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version for reference_add.py, reference_query.py and ground.py.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402

SITUATIONS_FILE = "references.yaml"
ENV_PATHS = "TOLLGATE_PATHS"


def situations_file() -> pathlib.Path | None:
    """references.yaml sits next to the paths file. None when no paths file is named."""
    raw = os.environ.get(ENV_PATHS, "").strip()
    if not raw:
        return None
    return pathlib.Path(os.path.expandvars(os.path.expanduser(raw))).parent / SITUATIONS_FILE


def _split_tags(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [t.strip().strip("\"'") for t in value.split(",") if t.strip().strip("\"'")]


def load_situation_tags(path: pathlib.Path | None = None) -> dict[str, list[str]]:
    """Read `situation: [tag, tag]` lines. Missing or empty file gives {} (meaning: search everything)."""
    path = path or situations_file()
    if path is None:
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    found: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.split(" #")[0].strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        name, _, value = line.partition(":")
        tags = _split_tags(value)
        if name.strip() and tags:
            found[name.strip()] = tags
    return found


def clean_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", tag.strip().lower()).strip("-")


def tags_to_meta(tags: list[str]) -> str:
    cleaned = sorted({clean_tag(t) for t in tags if clean_tag(t)})
    return "|" + "|".join(cleaned) + "|" if cleaned else ""


def meta_to_tags(value: str) -> list[str]:
    return [t for t in (value or "").split("|") if t]


def open_references(create: bool = False):
    """Return the references collection, or None when there is no store. Raises ImportError without chromadb."""
    folder = config.collection_dir("references")
    if not folder.is_dir():
        if not create:
            return None
        folder.mkdir(parents=True, exist_ok=True)
    client = config.chroma_client(folder)
    return client.get_or_create_collection(name="references", metadata={"hnsw:space": "cosine"})
