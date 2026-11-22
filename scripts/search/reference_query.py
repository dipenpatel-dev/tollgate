#!/usr/bin/env python3
"""
module_name: reference_query.py
description: Search the reference store and print passages with source and tag. Local only, no network.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. Situations map to tags in references.yaml next to the paths file (empty by default).
usage: python3 reference_query.py --situation spec_define --stakes medium --skill NAME --query "words" --top 3
  --situation  a name the calling command gives (spec_define, arch_design, dev_implement, qa_review ...).
               references.yaml maps it to your tags: `spec_define: [framing, bias]`. No entry or no file: search all.
  --stakes     low, medium or high. Higher stakes accept weaker matches.
  --skill      the calling command name (recorded in the header line only)
  --query      the words to search for
  --top        number of passages (default 3)
Output: one block per passage: `[n] source | heading | tag: a,b | score`, then the excerpt.
        `not set up` (exit 2) when there is no store. `no match` (exit 0) when nothing matches.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
import refstore  # noqa: E402
from core.paths import NotSetUp  # noqa: E402


def search(query: str, situation: str | None, stakes: str, top: int, emb=None, index_root=None) -> list[dict] | None:
    """Return passages, or None when there is no store."""
    import embedder as embedder_mod
    import router
    try:
        col = refstore.open_references()
    except ImportError:
        return None
    if col is None or col.count() == 0:
        return None
    root = index_root or config.index_root()
    emb = emb or embedder_mod.embedder_for_index(root)
    tags = refstore.load_situation_tags().get(situation or "", [])
    floor = max(0.0, emb.base_floor + config.STAKES_FLOOR_SHIFT.get(stakes, 0.0))
    found = router.query_all(query, intent="ambiguous", top=max(top * 4, 12), index_root=root, embedder=emb,
                             collections={"references": col}, where_tags=tags or None)
    return [r for r in found if r["score"] >= floor][:top]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Search the reference store.")
    parser.add_argument("--situation", default=None)
    parser.add_argument("--stakes", default="medium", choices=list(config.STAKES))
    parser.add_argument("--skill", default=None)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        results = search(args.query, args.situation, args.stakes, args.top)
    except (NotSetUp, ImportError):
        print("not set up")
        return 2
    except Exception as exc:
        print(f"not set up ({type(exc).__name__})")
        return 2
    if results is None:
        print("not set up")
        return 2
    if not results:
        print("no match")
        return 0
    for n, r in enumerate(results, 1):
        tag = ",".join(refstore.meta_to_tags(r.get("tags", ""))) or "none"
        print(f"[{n}] source: {r['file']} | {r['heading']} | tag: {tag} | score {r['score']}")
        print(r["excerpt"])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
