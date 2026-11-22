"""
module_name: embedder.py
description: Injectable embedders. A deterministic hashing embedder (no model, no network) and an optional local model that loads only when it is already on disk.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. Index remembers which embedder built it so queries use the same one.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import re
import sys
import types
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402

EMBEDDER_FILE = "embedder.json"
_STOP = frozenset(
    "a an and are as at be by do does did for from how i in is it of on or our that the "
    "their there this to was we what when where which who why with you your can could should "
    "would not no but if so than then them they these those us has have had been being".split()
)
_WORD = re.compile(r"[a-z0-9]+")


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


class HashEmbedder:
    """Bag of words and character trigrams hashed into a fixed vector. Same text, same vector, every run."""

    name = "hash-v1"
    dim = 2048
    base_floor = 0.1

    def __init__(self) -> None:
        self.min_cosine = 0.12

    def _features(self, text: str) -> dict[int, float]:
        feats: dict[int, float] = {}
        words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
        for raw in words:
            word = _stem(raw)
            slot = zlib.crc32(("w:" + word).encode()) % self.dim
            feats[slot] = feats.get(slot, 0.0) + 1.0
            padded = f"^{word}$"
            for i in range(len(padded) - 2):
                tri = zlib.crc32(("t:" + padded[i:i + 3]).encode()) % self.dim
                feats[tri] = feats.get(tri, 0.0) + 0.25
        return feats

    def encode(self, texts, normalize_embeddings: bool = True, **_kw) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for slot, weight in self._features(text).items():
                vec[slot] = weight
            norm = math.sqrt(sum(v * v for v in vec))
            if norm and normalize_embeddings:
                vec = [v / norm for v in vec]
            out.append(vec)
        return out

    def encode_query(self, texts, normalize_embeddings: bool = True, **kw) -> list[list[float]]:
        """Search questions are embedded the same way as documents for the hash embedder."""
        return self.encode(texts, normalize_embeddings=normalize_embeddings, **kw)

    def score_from_distance(self, distance: float) -> float:
        """Cosine similarity (0 for unrelated text)."""
        return max(0.0, 1.0 - distance)


class LocalModelEmbedder:
    """A sentence-transformers model that must already be on disk. Never downloads."""

    name = "local-model"
    base_floor = 0.3
    min_cosine = -1.0

    def __init__(self, model_name: str | None = None) -> None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        _stub_backend()
        from sentence_transformers import SentenceTransformer  # noqa: WPS433
        self.model_name = model_name or config.MODEL_NAME
        trust = os.environ.get(config.ENV_TRUST_REMOTE_CODE, "").strip() == "1"
        self._model = SentenceTransformer(self.model_name, local_files_only=True,
                                          trust_remote_code=trust)
        self.name = f"local:{self.model_name}"
        self.query_prompt = os.environ.get(config.ENV_QUERY_PROMPT, "").strip() or None
        known = getattr(self._model, "prompts", None) or {}
        if self.query_prompt and self.query_prompt not in known:
            raise ValueError(
                f"{config.ENV_QUERY_PROMPT}={self.query_prompt!r}: the model has no prompt with "
                f"that name (it has: {', '.join(sorted(known)) or 'none'})")

    def encode_query(self, texts, normalize_embeddings: bool = True, **kw) -> list[list[float]]:
        """Embed search questions. Uses the model's own query prompt when one is set."""
        if self.query_prompt:
            kw["prompt_name"] = self.query_prompt
        return self.encode(texts, normalize_embeddings=normalize_embeddings, **kw)

    def encode(self, texts, normalize_embeddings: bool = True, **kw) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]
        arr = self._model.encode(list(texts), normalize_embeddings=normalize_embeddings,
                                 show_progress_bar=False, **kw)
        return arr.tolist()

    def score_from_distance(self, distance: float) -> float:
        return max(0.0, 1.0 - distance / 2.0)


def _stub_backend() -> None:
    """Some platforms lack the optional ONNX backends that sentence-transformers imports. Stub them."""
    if "sentence_transformers.backend" in sys.modules:
        return
    stub = types.ModuleType("sentence_transformers.backend")
    for name in ("export_dynamic_quantized_onnx_model", "export_optimized_onnx_model",
                 "export_static_quantized_openvino_model", "load_onnx_model", "load_openvino_model"):
        setattr(stub, name, None)
    sys.modules["sentence_transformers.backend"] = stub


def get_embedder(name: str | None = None):
    """Return an embedder. name: hash, local, auto (default). `auto` uses a local model if present, else hash."""
    choice = (name or os.environ.get(config.ENV_EMBEDDER, "auto")).strip().lower()
    if choice in ("hash", "fake"):
        return HashEmbedder()
    if choice.startswith("local"):
        return LocalModelEmbedder()
    try:
        return LocalModelEmbedder()
    except Exception:
        return HashEmbedder()


def write_marker(index_root: pathlib.Path, embedder) -> None:
    index_root.mkdir(parents=True, exist_ok=True)
    (index_root / EMBEDDER_FILE).write_text(json.dumps({"name": embedder.name}), encoding="utf-8")


def read_marker(index_root: pathlib.Path) -> str | None:
    try:
        return json.loads((index_root / EMBEDDER_FILE).read_text(encoding="utf-8")).get("name")
    except (OSError, ValueError):
        return None


def embedder_for_index(index_root: pathlib.Path, override: str | None = None):
    """The embedder that built this index. Falls back to the default choice when there is no marker."""
    if override or os.environ.get(config.ENV_EMBEDDER):
        return get_embedder(override)
    marker = read_marker(index_root)
    if marker == HashEmbedder.name:
        return HashEmbedder()
    if marker and marker.startswith("local"):
        # Questions must use the model that built the index, not whatever the setting says now.
        _head, _sep, model = marker.partition(":")
        return LocalModelEmbedder(model or None)
    return get_embedder()


def check_marker(index_root: pathlib.Path, embedder) -> None:
    """Refuse to mix vectors from two models in one index.

    Raises ValueError when the index was built by a different embedder than `embedder`.
    A full rebuild (`--full`) is the way to switch models, so the caller skips this check then.
    """
    marker = read_marker(index_root)
    if marker and marker != embedder.name:
        raise ValueError(
            f"this index was built with {marker}, but the embedder is now {embedder.name}. "
            "Mixing them would give wrong results. Run the build again with --full to switch.")
