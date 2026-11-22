#!/usr/bin/env python3
"""
module_name: reference_add.py
description: Add a file or folder to the reference store (the `references` collection in the index) with tags you choose.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. Local only, no network.
  1.1.0: Inside a folder, files that are links pointing outside it are skipped. A single file named on the command line is taken as given.
usage: python3 reference_add.py PATH [--tag design --tag security] [--embedder hash|local]
  PATH     a file, or a folder (searched for .md .txt .rst .epub files)
  --tag    a label you choose; repeat for several. Chunks carry the tags. reference_query.py filters on them.
Exit:  0 added, 1 nothing to add or bad path, 2 not set up (no index folder or missing package)
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_index  # noqa: E402
import config  # noqa: E402
import embedder as embedder_mod  # noqa: E402
import refstore  # noqa: E402
from core.paths import NotSetUp  # noqa: E402


def collect(target: pathlib.Path) -> list[tuple[pathlib.Path, str]]:
    """Return (file, key) pairs. Keys start with the folder (or file) name so two sources do not collide."""
    exts = build_index.EXTENSIONS["references"]
    if target.is_file():
        return [(target, target.name)] if target.suffix.lower() in exts else []
    out = []
    skip = config.skip_dirs()
    for path in sorted(target.rglob("*")):
        rel_parts = path.relative_to(target).parts
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        if any(p in skip or p.startswith(".") for p in rel_parts):
            continue
        if path.is_symlink() and not build_index.real_inside(path, target):
            continue
        out.append((path, f"{target.name}/{'/'.join(rel_parts)}"))
    return out


def add(target: pathlib.Path, tags: list[str], emb=None) -> dict:
    pairs = collect(target)
    col = refstore.open_references(create=True)
    emb = emb or embedder_mod.embedder_for_index(config.index_root())
    embedder_mod.write_marker(config.index_root(), emb)
    state_file = config.collection_dir("references") / "add_state.json"
    state = build_index.load_state(state_file)
    records, errors = [], 0
    for fpath, key in pairs:
        try:
            chunks, text = build_index.read_chunks(fpath, key, "references")
        except Exception:
            errors += 1
            continue
        if chunks:
            records.append(build_index.FileRecord(fpath, key, "references", str(fpath.stat().st_mtime), text, chunks))
    meta_tags = refstore.tags_to_meta(tags)
    added = build_index.embed_records(records, col, emb, state, state_file, origin="add", tags=meta_tags)
    return {"files": len(records), "chunks": added, "errors": errors, "tags": refstore.meta_to_tags(meta_tags)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Add documents to the reference store.")
    parser.add_argument("path", help="File or folder to add")
    parser.add_argument("--tag", action="append", default=[], help="Tag to attach (repeatable)")
    parser.add_argument("--embedder", default=None, help="hash or local")
    args = parser.parse_args(argv)
    target = pathlib.Path(args.path).expanduser()
    if not target.exists():
        print(f"path not found: {target}", file=sys.stderr)
        return 1
    try:
        config.index_root()
        emb = embedder_mod.embedder_for_index(config.index_root(), args.embedder)
        summary = add(target, args.tag, emb)
    except (NotSetUp, ImportError) as exc:
        print(f"not set up: {exc}", file=sys.stderr)
        return 2
    if summary["chunks"] == 0:
        print("nothing to add (no readable .md .txt .rst .epub files)")
        return 1
    tag_text = ",".join(summary["tags"]) if summary["tags"] else "none"
    print(f"added {summary['chunks']} chunks from {summary['files']} files, tags: {tag_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
