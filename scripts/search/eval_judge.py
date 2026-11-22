#!/usr/bin/env python3
"""
module_name: eval_judge.py
description: Relevance judge over search results. Scores each returned passage against its question and reports how many are relevant.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the tiered LLM judge. The judge is a function you can swap. Default is a word overlap judge (no model, no network). A local model judge runs only on explicit request.
usage: python3 eval_judge.py --golden QUESTIONS.json [--judge lexical|ollama] [--threshold 0.3] [--top-k 3]
  --judge ollama   posts to TOLLGATE_OLLAMA_URL with TOLLGATE_OLLAMA_MODEL (a local service you run). Never used unless named.
Exit: 0 when relevance precision meets --min-precision, 1 otherwise, 2 not set up
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
from core.paths import NotSetUp  # noqa: E402

Judge = Callable[[str, str], float]
_WORD = re.compile(r"[a-z0-9]+")


def lexical_judge(question: str, passage: str) -> float:
    """Share of question words (length 4 or more) that appear in the passage."""
    q = {w for w in _WORD.findall(question.lower()) if len(w) >= 4}
    if not q:
        return 0.0
    p = set(_WORD.findall(passage.lower()))
    return len(q & p) / len(q)


def ollama_judge(question: str, passage: str) -> float:
    import urllib.request
    if not config.OLLAMA_BASE_URL or not config.OLLAMA_CONTEXT_MODEL:
        raise RuntimeError("TOLLGATE_OLLAMA_URL and TOLLGATE_OLLAMA_MODEL must both be set")
    prompt = (f"Question: {question}\n\nPassage: {passage}\n\n"
              "Rate from 0 to 1 how well the passage helps answer the question. Reply with the number only.")
    body = json.dumps({"model": config.OLLAMA_CONTEXT_MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(config.OLLAMA_BASE_URL.rstrip("/") + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=config.OLLAMA_CALL_TIMEOUT_SECONDS) as resp:
        text = json.loads(resp.read())["response"]
    m = re.search(r"\d*\.?\d+", text)
    return min(1.0, float(m.group(0))) if m else 0.0


def evaluate(cases: list[dict], search, judge: Judge, threshold: float, top_k: int) -> list[dict]:
    """search(question) returns a list of {file, excerpt}. One row per question."""
    rows = []
    for case in cases:
        passages = search(case["question"])[:top_k]
        scores = [judge(case["question"], p["excerpt"]) for p in passages]
        relevant = sum(1 for s in scores if s >= threshold)
        rows.append({"id": case["id"], "returned": len(passages), "relevant": relevant,
                     "expect_none": bool(case.get("expect_none"))})
    return rows


def precision(rows: list[dict]) -> float:
    asked = [r for r in rows if not r["expect_none"] and r["returned"]]
    if not asked:
        return 0.0
    return sum(r["relevant"] / r["returned"] for r in asked) / len(asked)


def _real_search(question: str) -> list[dict]:
    import embedder as embedder_mod
    import router
    root = config.index_root()
    emb = embedder_mod.embedder_for_index(root)
    found = router.query_all(question, intent="ambiguous", top=10, index_root=root, embedder=emb)
    return [r for r in found if r["score"] >= emb.base_floor]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Judge result relevance.")
    parser.add_argument("--golden", required=True, type=pathlib.Path)
    parser.add_argument("--judge", choices=["lexical", "ollama"], default="lexical")
    parser.add_argument("--threshold", type=float, default=0.3)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-precision", type=float, default=0.5)
    args = parser.parse_args(argv)
    cases = json.loads(args.golden.read_text(encoding="utf-8"))
    judge = ollama_judge if args.judge == "ollama" else lexical_judge
    try:
        rows = evaluate(cases, _real_search, judge, args.threshold, args.top_k)
    except (NotSetUp, ImportError):
        print("not set up")
        return 2
    p = precision(rows)
    for r in rows:
        print(f"{r['id']:<40} returned={r['returned']} relevant={r['relevant']}")
    print(f"\nrelevance precision@{args.top_k} = {p:.2f} (judge: {args.judge}, threshold {args.threshold})")
    return 0 if p >= args.min_precision else 1


if __name__ == "__main__":
    sys.exit(main())
