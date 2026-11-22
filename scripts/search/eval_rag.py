#!/usr/bin/env python3
"""
module_name: eval_rag.py
description: Measure search quality against a file of known questions. Run before and after index changes.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the personal eval. The question list is a file you give (the original list was tied to one vault). Retrieval is injectable. Hit@1, hit@N, reciprocal rank, critical misses.
usage: python3 eval_rag.py --golden QUESTIONS.json [--top-k 3] [--min-hit-rate 0.8] [--json]
question fields: id, question, expected (list of file keys), optional must_outrank (a file that must not rank above the expected one),
                 critical (true: a miss is flagged HALLUCINATION_RISK), expect_none (true: nothing should be returned)
Exit: 0 when the hit rate meets --min-hit-rate and no critical question missed, 1 otherwise, 2 not set up
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
from core.paths import NotSetUp  # noqa: E402

ENV_CASES = "TOLLGATE_EVAL_CASES"
RETURN_LIMIT = 5

Retrieve = Callable[[str], list[str]]


def default_retrieve(question: str) -> list[str]:
    """Ranked file keys from the real index, applying the search score floor."""
    import embedder as embedder_mod
    import router
    root = config.index_root()
    emb = embedder_mod.embedder_for_index(root)
    found = router.query_all(question, intent="ambiguous", top=RETURN_LIMIT, index_root=root, embedder=emb)
    return [r["file"] for r in found if r["score"] >= emb.base_floor]


def first_rank(results: list[str], expected: list[str]) -> int | None:
    for pos, source in enumerate(results, 1):
        if source in expected:
            return pos
    return None


def outranks(results: list[str], expected: list[str], distractor: str | None) -> bool:
    if distractor is None or distractor not in results:
        return True
    best = first_rank(results, expected)
    return best is not None and best < results.index(distractor) + 1


def verdict(row: dict, top_k: int) -> str:
    if row["expect_none"]:
        ok = row["returned"] == 0
    else:
        ok = row["rank"] is not None and row["rank"] <= top_k
    if ok and row["outranked_ok"]:
        return "PASS"
    return "HALLUCINATION_RISK" if row["critical"] else "MISS"


def evaluate(cases: list[dict], retrieve: Retrieve | None = None, top_k: int = 3) -> list[dict]:
    retrieve = retrieve or default_retrieve
    rows = []
    for case in cases:
        results = retrieve(case["question"])
        row = {
            "id": case["id"],
            "rank": first_rank(results, case.get("expected", [])),
            "outranked_ok": outranks(results, case.get("expected", []), case.get("must_outrank")),
            "critical": bool(case.get("critical", False)),
            "expect_none": bool(case.get("expect_none", False)),
            "returned": len(results),
        }
        row["verdict"] = verdict(row, top_k)
        rows.append(row)
    return rows


def summarize(rows: list[dict], top_k: int) -> dict:
    total = len(rows)
    ranked = [r for r in rows if not r["expect_none"]]
    passes = sum(1 for r in rows if r["verdict"] == "PASS")
    found = sum(1 for r in rows if (r["returned"] == 0 if r["expect_none"] else (r["rank"] is not None and r["rank"] <= top_k)))
    return {
        "total": total,
        "hit_rate": found / total if total else 0.0,
        "hit_at_1": sum(1 for r in ranked if r["rank"] == 1) / max(1, len(ranked)),
        "mrr": sum(1 / r["rank"] for r in ranked if r["rank"]) / max(1, len(ranked)),
        "passes": passes,
        "critical_misses": sum(1 for r in rows if r["verdict"] == "HALLUCINATION_RISK"),
        "outrank_failures": sum(1 for r in rows if not r["outranked_ok"]),
    }


def print_report(rows: list[dict], top_k: int) -> dict:
    for r in rows:
        print(f"{r['verdict']:<19} {r['id']:<40} rank={r['rank']} returned={r['returned']} outranks_ok={r['outranked_ok']}")
    s = summarize(rows, top_k)
    print(f"\nhit@{top_k} = {s['hit_rate']:.2f}  hit@1 = {s['hit_at_1']:.2f}  mrr = {s['mrr']:.2f}  "
          f"critical misses = {s['critical_misses']}  outrank failures = {s['outrank_failures']}")
    return s


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Score search against known questions.")
    parser.add_argument("--golden", default=os.environ.get(ENV_CASES), help="Questions file (JSON list)")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-hit-rate", type=float, default=0.8)
    parser.add_argument("--json", action="store_true", help="Print rows as JSON")
    args = parser.parse_args(argv)
    if not args.golden:
        print("no question file: pass --golden FILE or set " + ENV_CASES, file=sys.stderr)
        return 2
    cases = json.loads(pathlib.Path(args.golden).read_text(encoding="utf-8"))
    try:
        rows = evaluate(cases, top_k=args.top_k)
    except (NotSetUp, ImportError):
        print("not set up")
        return 2
    if args.json:
        print(json.dumps(rows, indent=2))
        s = summarize(rows, args.top_k)
    else:
        s = print_report(rows, args.top_k)
    ok = s["hit_rate"] >= args.min_hit_rate and s["critical_misses"] == 0 and s["outrank_failures"] == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
