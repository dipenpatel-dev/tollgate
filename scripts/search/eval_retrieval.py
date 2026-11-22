#!/usr/bin/env python3
"""
module_name: eval_retrieval.py
description: End to end retrieval eval. Builds a throwaway index from a folder of notes, asks every question in a file, and scores the answers.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the adapter that scored a second index. Now self contained: it builds its own temporary index so your real index is never touched.
usage: python3 eval_retrieval.py --corpus FOLDER --golden QUESTIONS.json [--embedder hash|local] [--top-k 3] [--min-hit-rate 0.8]
Exit: same as eval_rag.py
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import eval_rag  # noqa: E402


def run(corpus: pathlib.Path, golden: pathlib.Path, embedder: str | None, top_k: int, min_hit_rate: float) -> int:
    cases = json.loads(golden.read_text(encoding="utf-8"))
    saved = {k: os.environ.get(k) for k in ("TOLLGATE_PATHS", "TOLLGATE_KNOWLEDGE", "TOLLGATE_EMBEDDER")}
    with tempfile.TemporaryDirectory() as tmp:
        paths_file = pathlib.Path(tmp) / "paths.yaml"
        paths_file.write_text(f"vault: {corpus}\nindex: {pathlib.Path(tmp) / 'index'}\n", encoding="utf-8")
        os.environ["TOLLGATE_PATHS"] = str(paths_file)
        os.environ.pop("TOLLGATE_KNOWLEDGE", None)
        if embedder:
            os.environ["TOLLGATE_EMBEDDER"] = embedder
        try:
            import build_index
            build_index.build(full=True, embedder_name=embedder)
            rows = eval_rag.evaluate(cases, top_k=top_k)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    summary = eval_rag.print_report(rows, top_k)
    ok = summary["hit_rate"] >= min_hit_rate and summary["critical_misses"] == 0 and summary["outrank_failures"] == 0
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build a throwaway index and score it.")
    parser.add_argument("--corpus", required=True, type=pathlib.Path)
    parser.add_argument("--golden", required=True, type=pathlib.Path)
    parser.add_argument("--embedder", default=None)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-hit-rate", type=float, default=0.8)
    args = parser.parse_args(argv)
    return run(args.corpus.expanduser().resolve(), args.golden, args.embedder, args.top_k, args.min_hit_rate)


if __name__ == "__main__":
    sys.exit(main())
