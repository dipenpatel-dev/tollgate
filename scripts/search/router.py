"""
module_name: router.py
description: Parallel retrieval over the index collections with a gentle intent tilt, a tier tie-breaker and an optional local re-ranker.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.1.0
change_log:
  1.0.0: Ported from the personal seven-collection router. Three collections, embedder injected, re-ranker optional and local only. Score is similarity times tier weight.
  1.1.0: Candidates are kept per collection (no crowding). Tier is an additive tie-breaker. The size-based collection tilt is gone and the intent tilt is clamped to +/-0.1. The final order is the weighted score; the re-ranker is blended with it, not multiplied. Collections are opened only when active. The knowledge collection written by sweep is queried.
"""
from __future__ import annotations

import logging
import math
import os
import pathlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
import embedder as embedder_mod  # noqa: E402
from intent import classify_intent  # noqa: E402

logger = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9]*-\d+\b")


def _enabled_names() -> set[str]:
    """Collections that are switched on now. A stale index folder of a switched-off one is ignored."""
    names = set(config.COLLECTION_NAMES) | set(config.QUERY_ONLY_COLLECTIONS)
    try:
        import build_index
        names |= set(build_index.active_collections())
    except Exception:
        pass
    return names


def open_collections(index_root: pathlib.Path, names=None) -> dict[str, Any]:
    """Open each enabled collection that exists on disk. Missing and switched-off ones are left out.

    Raises ImportError without chromadb. `names` (tests) opens exactly those, skipping the enabled check.
    """
    opened: dict[str, Any] = {}
    enabled = None if names else _enabled_names()
    for name in names or config.ALL_COLLECTION_NAMES:
        if enabled is not None and name not in enabled:
            continue
        folder = index_root / name
        if not folder.is_dir():
            continue
        client = config.chroma_client(folder)
        opened[name] = client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
    return opened


def _get_reranker():
    if os.environ.get(config.ENV_RERANK) != "1":
        return None
    try:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        embedder_mod._stub_backend()
        from sentence_transformers import CrossEncoder
        return CrossEncoder(config.RERANK_MODEL)
    except Exception:
        return None


def _query_one(name, collection, query_embedding, top_k, emb):
    try:
        count = collection.count()
        if count == 0:
            return (name, [], None)
        res = collection.query(query_embeddings=[query_embedding], n_results=min(top_k, count),
                               include=["documents", "metadatas", "distances"])
        out = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            if 1.0 - dist < emb.min_cosine:
                continue
            out.append({"doc": doc, "meta": meta, "raw_score": round(emb.score_from_distance(dist), 4),
                        "collection": name})
        return (name, out, None)
    except Exception as exc:  # one bad collection must not hide the others
        return (name, [], exc)


def _resolve_weights(resolved: str, routing: dict, names) -> dict[str, float]:
    if resolved == "ambiguous":
        weights = routing.get("equal_weights") or {n: 1.0 for n in names}
    else:
        weights = (routing.get("intents") or {}).get(resolved)
        if weights is None or all(v == 0 for v in weights.values()):
            weights = routing.get("equal_weights") or {n: 1.0 for n in names}
    return dict(weights)


def _tilts(weights: dict[str, float], names, ambiguous: bool) -> dict[str, float]:
    """Collection tilt between 1 - INTENT_TILT and 1 + INTENT_TILT. A weight of 0 switches a collection off (None).

    Ambiguous queries use no tilt. A collection missing from the weights gets the top weight.
    """
    out: dict[str, float | None] = {}
    top = max([v for v in weights.values() if v > 0] or [1.0])
    for name in names:
        w = weights.get(name, top)
        if w <= 0:
            out[name] = None
        elif ambiguous:
            out[name] = 1.0
        else:
            out[name] = 1.0 - config.INTENT_TILT + 2 * config.INTENT_TILT * min(1.0, w / top)
    return out


def _query_ids(query: str) -> set[str]:
    return {m.group(0).lower() for m in ID_PATTERN.finditer(query)}


def _has_id(ticket_id: str, file: str) -> bool:
    """True when the ID appears as a whole token: not after a letter or digit, not before a digit."""
    return re.search(r"(?<![a-z0-9])" + re.escape(ticket_id) + r"(?!\d)", file.lower()) is not None


def _score_candidates(candidates, tilts, query):
    """Weighted score for each candidate, then the best TOP_K_RERANK of EACH collection."""
    rules = config.tier_rules()
    ids = _query_ids(query)
    per: dict[str, list[dict]] = {}
    for c in candidates:
        tilt = tilts.get(c["collection"])
        if tilt is None:
            continue
        file = c["meta"].get("file") or c["meta"].get("source_ref") or ""
        tier, label = config.tier_for(file, c["collection"], rules)
        base = c["raw_score"] + (config.ID_MATCH_BONUS if ids and any(_has_id(i, file) for i in ids) else 0.0)
        c = {**c, "file": file, "tier": tier, "tier_label": label,
             "weighted_score": round(base * tilt + config.TIER_ADJUST[tier], 4)}
        per.setdefault(c["collection"], []).append(c)
    kept: list[dict] = []
    for group in per.values():
        group.sort(key=lambda x: x["weighted_score"], reverse=True)
        kept.extend(group[: config.TOP_K_RERANK])
    kept.sort(key=lambda x: x["weighted_score"], reverse=True)
    return kept


def _unit(score: float) -> float:
    """Bring a re-ranker score into 0..1. Scores already in range are kept; raw logits go through a sigmoid."""
    if 0.0 <= score <= 1.0:
        return score
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, score))))


def _finish(query, weighted, reranker):
    if reranker is not None and len(weighted) > 1:
        scores = reranker.predict([(query, c["doc"]) for c in weighted]).tolist()
        for c, s in zip(weighted, scores):
            c["rerank_score"] = round(float(s), 4)
            c["score"] = round(config.RERANK_BLEND * _unit(float(s))
                               + (1 - config.RERANK_BLEND) * c["weighted_score"], 4)
    else:
        for c in weighted:
            c["rerank_score"] = None
            c["score"] = c["weighted_score"]
    weighted.sort(key=lambda c: c["score"], reverse=True)
    return [{
        "file": c["file"],
        "heading": c["meta"].get("heading") or c["meta"].get("summary", ""),
        "excerpt": c["doc"][: config.EXCERPT_CHARS].strip(),
        "score": c["score"],
        "tier": c["tier"],
        "tier_label": c["tier_label"],
        "rerank_score": c["rerank_score"],
        "collection": c["collection"],
        "tags": c["meta"].get("tags", ""),
    } for c in weighted]


def _enforce_collection_distribution(results, n_collections, total):
    """Cap one collection's share of the final list; fill the rest from overflow."""
    cap = max(2, -(-total // max(1, n_collections)))
    counts: dict[str, int] = {}
    kept, overflow = [], []
    for r in results:
        if counts.get(r["collection"], 0) < cap:
            kept.append(r)
            counts[r["collection"]] = counts.get(r["collection"], 0) + 1
        else:
            overflow.append(r)
    for r in overflow:
        if len(kept) >= total:
            break
        kept.append(r)
    kept.sort(key=lambda r: r["score"], reverse=True)
    return kept[:total]


def query_all(
    query: str,
    intent: str | None = None,
    top: int = config.TOP_K_RETURN,
    situation: str | None = None,
    *,
    failed: list[str] | None = None,
    queried: dict[str, int] | None = None,
    index_root: pathlib.Path | None = None,
    embedder: Any = None,
    collections: dict[str, Any] | None = None,
    names: tuple[str, ...] | None = None,
    where_tags: list[str] | None = None,
) -> list[dict]:
    """Query the collections in parallel and return weighted, optionally re-ranked results.

    failed gets the names of collections whose query raised. queried gets {name: chunk count}.
    where_tags keeps only chunks carrying at least one of the tags.
    """
    root = index_root or config.index_root()
    routing = config.load_routing()
    resolved, _conf = classify_intent(query, intent, situation=situation)
    emb = embedder or embedder_mod.embedder_for_index(root)
    cols = collections if collections is not None else open_collections(root, names)
    if queried is not None:
        queried.update({n: c.count() for n, c in cols.items()})
    if not cols:
        return []
    vec = emb.encode_query([query], normalize_embeddings=config.NORMALIZE_EMBEDDINGS)[0]
    with ThreadPoolExecutor(max_workers=len(cols)) as pool:
        futures = [pool.submit(_query_one, n, c, vec, config.TOP_K_RETRIEVE, emb) for n, c in cols.items()]
        raw: list[dict] = []
        for fut in futures:
            name, found, exc = fut.result()
            if exc is not None:
                logger.warning("Collection %r query failed: %s", name, exc)
                if failed is not None:
                    failed.append(name)
            else:
                raw.extend(found)
    if where_tags:
        wanted = {t.lower() for t in where_tags}
        raw = [c for c in raw
               if wanted & {t for t in c["meta"].get("tags", "").lower().split("|") if t}]
    weights = _resolve_weights(resolved, routing, list(cols))
    tilts = _tilts(weights, list(cols), resolved == "ambiguous")
    weighted = _score_candidates(raw, tilts, query)
    ranked = _finish(query, weighted, _get_reranker())
    if resolved == "ambiguous":
        return _enforce_collection_distribution(ranked, len({r["collection"] for r in ranked}), top)
    return ranked[:top]
