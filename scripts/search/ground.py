#!/usr/bin/env python3
"""
module_name: ground.py
description: Grounding lookup for a command. Prints a state line, a collections line, an optional detail line, then passages.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.1.0
change_log:
  1.1.0: A query argument of `-` is read from standard input (a quoted heredoc), so any character in the
         query is safe. Used by the dev and qa commands.
  1.0.0: Initial version. Read only. No network. Always exits 0 so a caller never breaks on it.
usage: python3 ground.py 'SKILL' 'QUERY'   (or QUERY as - to read it from standard input)
output:
  STATE: ok|partial|empty|unavailable
  COLLECTIONS: vault=12 tickets=3 references=none
  DETAIL: <reason>        (only when the state is not ok)
  then passages: `[n] file | heading | collection | score`, followed by the excerpt
states: ok = passages found and every collection answered. partial = passages found but a collection failed.
        empty = the index answered with no passage. unavailable = no index, missing package, or every collection failed.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402

TOP = 5


def ground(skill: str, query: str, top: int = TOP, emb=None, index_root=None) -> tuple[str, str, str, list[dict]]:
    """Return (state, collections line, detail, passages)."""
    try:
        import embedder as embedder_mod
        import router
        root = index_root or config.index_root()
    except Exception as exc:
        return "unavailable", "none", f"not set up ({type(exc).__name__})", []
    if not root.is_dir() or not any((root / n).is_dir() for n in config.ALL_COLLECTION_NAMES):
        return "unavailable", "none", "not set up (no index)", []
    try:
        emb = emb or embedder_mod.embedder_for_index(root)
        failed: list[str] = []
        queried: dict[str, int] = {}
        from intent import map_skill
        results = router.query_all(query, intent=map_skill(skill) or "ambiguous", top=top, failed=failed,
                                   queried=queried, index_root=root, embedder=emb)
    except Exception as exc:
        return "unavailable", "none", f"index error ({type(exc).__name__})", []
    line = " ".join(f"{n}={queried.get(n, 'none')}" for n in config.ALL_COLLECTION_NAMES
                    if n in config.COLLECTION_NAMES or n in queried)
    results = [r for r in results if r["score"] >= emb.base_floor]
    if queried and len(failed) >= len(queried):
        return "unavailable", line, "every collection failed", []
    if not results:
        return "empty", line, "no passage above the score floor" if queried else "index has no chunks", []
    if failed:
        return "partial", line, "collection failed: " + ",".join(sorted(failed)), results
    return "ok", line, "", results


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("STATE: unavailable")
        print("COLLECTIONS: none")
        print("DETAIL: usage: ground.py 'SKILL' 'QUERY'")
        return 0
    query = " ".join(sys.stdin.read().split()) if argv[1] == "-" else argv[1]
    state, line, detail, results = ground(argv[0], query)
    print(f"STATE: {state}")
    print(f"COLLECTIONS: {line}")
    if detail:
        print(f"DETAIL: {detail}")
    for n, r in enumerate(results, 1):
        print(f"[{n}] {r['file']} | {r['heading']} | {r['collection']} | {r['score']}")
        print(r["excerpt"])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
