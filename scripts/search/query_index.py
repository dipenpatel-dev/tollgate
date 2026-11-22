#!/usr/bin/env python3
"""
module_name: query_index.py
description: Query the search index and print relevant chunks as JSON. Prints `not set up` (exit 2) when there is no index.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the personal vector search. Delegates to router.query_all. Adds --situation and --embedder.
  1.1.0: The query can come from standard input (`--stdin`, or `-` as the query), so a prompt never shows in the
         process list and may start with dashes. The index folder comes from the path loader (there is no --index).
usage: python3 query_index.py "your query" [--top 5] [--min-score 0.3] [--intent teach] [--situation spec_define]
       printf '%s' "$PROMPT" | python3 query_index.py --stdin [--top 3]
output: JSON array of {file, heading, excerpt, score, tier, tier_label, collection}
tiers: 1 VERIFIED (decisions, root causes), 2 DOCUMENTED (tickets, system notes), 3 OBSERVED (meetings, chat, scratch)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
from core.paths import NotSetUp  # noqa: E402


MAX_QUERY_CHARS = 4000


def get_tier(file_path: str) -> tuple[int, str]:
    """Kept for callers that import it. Tier comes from words in the path."""
    return config.tier_for(file_path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default=None, help="Query string, or - to read it from standard input")
    parser.add_argument("--stdin", action="store_true", help="Read the query from standard input")
    parser.add_argument("--top", type=int, default=config.TOP_K_RETURN, help="Number of results")
    parser.add_argument("--min-score", type=float, default=None, help="Minimum score (0-1)")
    parser.add_argument("--intent", default=None, help="teach, verify, build, decide or draft. Omit for equal weight.")
    parser.add_argument("--situation", default=None, help="A situation name from routing.yaml")
    parser.add_argument("--embedder", default=None, help="hash or local (default: the one that built the index)")
    args = parser.parse_args(argv)
    if args.stdin or args.query == "-":
        args.query = " ".join(sys.stdin.read().split())[:MAX_QUERY_CHARS]
    if not args.query:
        parser.error("give a query, or --stdin with the query on standard input")

    try:
        root = config.index_root()
        if not root.is_dir() or not any((root / n).is_dir() for n in config.ALL_COLLECTION_NAMES):
            print("not set up")
            return 2
        import embedder as embedder_mod
        import router
        emb = embedder_mod.embedder_for_index(root, args.embedder)
        floor = args.min_score if args.min_score is not None else emb.base_floor
        results = router.query_all(args.query, intent=args.intent or (None if args.situation else "ambiguous"), top=args.top,
                                   situation=args.situation, index_root=root, embedder=emb)
    except (NotSetUp, ImportError):
        print("not set up")
        return 2
    except Exception as exc:
        print(json.dumps({"error": f"Query failed: {exc}"}))
        return 1

    output = [{k: r[k] for k in ("file", "heading", "excerpt", "score", "tier", "tier_label", "collection")}
              for r in results if r.get("score", 0) >= floor]
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
