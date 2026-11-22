#!/usr/bin/env python3
"""
module_name: check_index_health.py
description: Index health check. Confirms each probe query returns a passage from the expected file at or above the score floor.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from a check tied to three named documents. Probes are now your own: index_health.json next to the paths file. With none, the check only confirms the index has chunks.
usage: python3 check_index_health.py [--checks FILE] [--no-report]
probe file (JSON list): [{"label": "x", "file_contains": "part of a file name", "query": "words", "collection": "vault"}]
Exit: 0 healthy, 1 a probe failed or the index is empty, 2 not set up
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
import embedder as embedder_mod  # noqa: E402
import refstore  # noqa: E402
from core.paths import NotSetUp, get_path  # noqa: E402

TOP_K: int = 60  # wide window: the check filters by file after the global top-K, so a healthy passage must not fall outside it
PROBE_FILE = "index_health.json"


def load_checks(path: pathlib.Path | None = None) -> list[dict]:
    if path is None:
        sit = refstore.situations_file()
        path = sit.parent / PROBE_FILE if sit else None
    if path is None:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [c for c in data if isinstance(c, dict) and c.get("query") and c.get("file_contains")] if isinstance(data, list) else []


def _query_file(query: str, file_contains: str, emb, cols: dict) -> list[dict]:
    vec = emb.encode_query([query], normalize_embeddings=config.NORMALIZE_EMBEDDINGS)[0]
    results = []
    for col in cols.values():
        n = min(TOP_K, col.count())
        if n == 0:
            continue
        raw = col.query(query_embeddings=[vec], n_results=n, include=["documents", "metadatas", "distances"])
        for doc, meta, dist in zip(raw["documents"][0], raw["metadatas"][0], raw["distances"][0]):
            if file_contains.lower() in meta.get("file", "").lower():
                results.append({"file": meta.get("file", ""), "score": round(emb.score_from_distance(dist), 3),
                                "excerpt": doc[:200].strip()})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def run_checks(checks: list[dict] | None = None, emb=None, index_root=None) -> dict:
    import router
    root = index_root or config.index_root()
    report: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "checks": [], "passed": True}
    if not root.is_dir():
        report.update(passed=False, error=f"index not found: {root.name}")
        return report
    try:
        emb = emb or embedder_mod.embedder_for_index(root)
        cols = router.open_collections(root)
    except Exception as exc:
        report.update(passed=False, error=f"index unavailable: {type(exc).__name__}")
        return report
    report["threshold"] = emb.base_floor
    counts = {n: c.count() for n, c in cols.items()}
    report["counts"] = counts
    if sum(counts.values()) == 0:
        report.update(passed=False, error="index has no chunks")
        return report
    for check in checks if checks is not None else load_checks():
        scope = {check["collection"]: cols[check["collection"]]} if check.get("collection") in cols else cols
        found = _query_file(check["query"], check["file_contains"], emb, scope)
        top = found[0]["score"] if found else 0.0
        ok = bool(found) and top >= emb.base_floor
        report["checks"].append({"label": check.get("label", check["file_contains"]), "query": check["query"],
                                 "top_score": top, "result_count": len(found),
                                 "threshold": emb.base_floor, "passed": ok})
        report["passed"] = report["passed"] and ok
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Index health check")
    parser.add_argument("--checks", default=None, help="Probe file (default: index_health.json next to the paths file)")
    parser.add_argument("--no-report", action="store_true", help="Do not write the dated report file")
    args = parser.parse_args(argv)
    try:
        checks = load_checks(pathlib.Path(args.checks)) if args.checks else None
        report = run_checks(checks)
        logs = get_path("logs")
    except (NotSetUp, ImportError):
        print("not set up")
        return 2
    if not args.no_report:
        try:
            logs.mkdir(parents=True, exist_ok=True)
            out = logs / f"index-health-{date.today().isoformat()}.json"
            out.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Health report written to: {out}")
        except OSError as exc:
            print(f"Warning: could not write health report: {exc}", file=sys.stderr)
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        failed = [c["label"] for c in report["checks"] if not c["passed"]]
        print("\nFAIL: " + (report.get("error") or "probes below threshold: " + ", ".join(failed)), file=sys.stderr)
        return 1
    print("\nPASS: index healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
