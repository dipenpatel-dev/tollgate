"""
module_name: config.py
description: Central settings for the search scripts. Folders come from the path loader, never from literals.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the personal vector search. Three collections (vault, tickets, references).
         Paths resolved lazily through core.paths. Embedding and re-ranking are optional and local only.
  1.1.0: Tier is a small additive tie-breaker, not a multiplier. Tier is matched on layout folders and whole
         path tokens, not word substrings. Skip folders come from the layout. The knowledge collection
         (written by sweep) is queried.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core.paths import NotSetUp, folder_name, get_path  # noqa: E402,F401

HERE: pathlib.Path = pathlib.Path(__file__).resolve().parent
ROUTING_FILE: pathlib.Path = HERE / "routing.yaml"

# ── Collections ───────────────────────────────────────────────────────────────

COLLECTION_NAMES: tuple[str, ...] = ("vault", "tickets", "references")
# Optional collections. Each is off until its folder is configured: `code` follows the `repos`
# path (TOLLGATE_CODE_DIR), `standards` follows the `standards` line in the paths file.
OPTIONAL_COLLECTIONS: tuple[str, ...] = ("code", "standards")
# Written by sweep, never by build_index. Queried when its folder exists, never rebuilt or pruned here.
QUERY_ONLY_COLLECTIONS: tuple[str, ...] = ("knowledge",)
BUILT_COLLECTION_NAMES: tuple[str, ...] = COLLECTION_NAMES + OPTIONAL_COLLECTIONS
ALL_COLLECTION_NAMES: tuple[str, ...] = BUILT_COLLECTION_NAMES + QUERY_ONLY_COLLECTIONS
DEFAULT_SKIP_DIRS: frozenset[str] = frozenset(
    {".git", ".obsidian", ".trash", "__pycache__", "node_modules", ".venv", ".mypy_cache"}
)
# Folders left out of the vault walk only. These match the TOP LEVEL of the vault by path, never a
# folder of the same name deeper down (a ticket may keep its own `work` folder and stay indexed).
VAULT_SKIP_TOP_NAMES: frozenset[str] = frozenset({"archive", "work", "history"})
# Layout keys whose folders are also left out of the vault walk (raw landing notes, generated output).
VAULT_SKIP_LAYOUT_KEYS: tuple[str, ...] = ("landing", "output")
# Folders left out of the optional collections, on top of the defaults above.
CODE_SKIP_DIRS: frozenset[str] = frozenset(
    {"__pycache__", ".git", ".venv", "node_modules", ".mypy_cache", ".terraform", "site-packages",
     ".venv-inventory", ".venv-smart", ".venv-photos", ".pytest_cache", ".ruff_cache"}
)
STANDARDS_SKIP_DIRS: frozenset[str] = frozenset({".git", "__pycache__", "commands"})
# Extra folder names to leave out of the vault walk, comma separated.
ENV_EXTRA_SKIP = "TOLLGATE_INDEX_SKIP"

# ── Embedding ─────────────────────────────────────────────────────────────────

MODEL_NAME: str = os.environ.get("TOLLGATE_EMBED_MODEL", "all-MiniLM-L6-v2")
RERANK_MODEL: str = os.environ.get("TOLLGATE_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
NORMALIZE_EMBEDDINGS: bool = True
ENV_EMBEDDER = "TOLLGATE_EMBEDDER"   # hash | local | auto (default auto)
# Name of the model's own prompt for search questions (for example `query` for the Snowflake
# Arctic models). Empty means questions are embedded as plain text.
ENV_QUERY_PROMPT = "TOLLGATE_EMBED_QUERY_PROMPT"
# 1 lets the model run the code that ships with it. Some models need it. Off by default.
ENV_TRUST_REMOTE_CODE = "TOLLGATE_EMBED_TRUST_REMOTE_CODE"
ENV_RERANK = "TOLLGATE_RERANK"       # 1 turns the optional local re-ranker on

# ── Chunking ──────────────────────────────────────────────────────────────────

MIN_CHUNK_CHARS: int = 80
MAX_CHUNK_CHARS: int = 2000
OVERLAP_CHARS: int = 200

# ── Retrieval ─────────────────────────────────────────────────────────────────

TOP_K_RETRIEVE: int = 60
TOP_K_RERANK: int = 20
TOP_K_RETURN: int = 5
MIN_SCORE: float = 0.3
EXCERPT_CHARS: int = 300

# How results are ordered. The final order is always the `score` field of each result.
#   1. Every collection is searched on its own and keeps its own best TOP_K_RERANK candidates, so a
#      large collection cannot crowd a small one out before ranking.
#   2. score = (similarity + ID_MATCH_BONUS when the query names an ID found in the path)
#              * collection tilt (named intents only, between 1 - INTENT_TILT and 1 + INTENT_TILT)
#              + tier adjustment: OBSERVED (tier 3) sinks by 0.05; VERIFIED stays level, because on the
#                golden questions any bonus for it pushed on-point notes out of the top three.
#   3. With the optional re-ranker on, score = RERANK_BLEND * re-ranker + (1 - RERANK_BLEND) * step 2.
TIER_ADJUST: dict[int, float] = {1: 0.0, 2: 0.0, 3: -0.05}
INTENT_TILT: float = 0.1
ID_MATCH_BONUS: float = 0.1
RERANK_BLEND: float = 0.5
TIER_LABELS: dict[int, str] = {1: "VERIFIED", 2: "DOCUMENTED", 3: "OBSERVED"}
# Tiers come from the vault layout folders first (conversations, chat threads, meetings and landing
# are OBSERVED; decisions and patterns are VERIFIED), then from whole words in a path segment.
# A word never matches inside another word ("threadpool" is not "thread"). The lists can be
# replaced in routing.yaml under `tiers`.
DEFAULT_TIER_WORDS: dict[int, list[str]] = {
    1: ["rca", "decision", "pattern"],
    3: ["meeting", "conversation", "landing", "slack", "chat", "thread"],
}
TIER_FOLDER_KEYS: dict[int, tuple[str, ...]] = {3: ("conversations", "chat_threads", "meetings", "landing")}
# Sub folders of the knowledge folder that are VERIFIED, and plain folder names that are VERIFIED anywhere.
TIER1_KNOWLEDGE_SUBDIRS: tuple[str, ...] = ("decisions", "patterns")
TIER1_SEGMENT_NAMES: frozenset[str] = frozenset({"rca", "rcas", "decisions", "patterns"})
DEFAULT_TIER: int = 2

# ── Optional context generation (index time only, off by default) ─────────────

CONTEXT_PROVIDER: str = os.environ.get("TOLLGATE_CONTEXT_PROVIDER", "claude")  # claude | ollama
CLAUDE_CONTEXT_MODEL: str = os.environ.get("TOLLGATE_CONTEXT_MODEL", "claude-haiku-5-5")
CLAUDE_CONTEXT_EFFORT: str = "low"
OLLAMA_CONTEXT_MODEL: str = os.environ.get("TOLLGATE_OLLAMA_MODEL", "")
OLLAMA_BASE_URL: str = os.environ.get("TOLLGATE_OLLAMA_URL", "")
OLLAMA_NUM_CTX: int = 32768
OLLAMA_DOC_WORKERS: int = 4
OLLAMA_MAX_CONCURRENT: int = 4
OLLAMA_KEEP_ALIVE: str = "60m"
OLLAMA_CALL_TIMEOUT_SECONDS: int = 600
CONTEXT_DOC_WORKERS: int = 8
CONTEXT_SAVE_EVERY_CALLS: int = 20
CONTEXT_MAX_OUTPUT_TOKENS: int = 250
CONTEXT_MAX_CONCURRENT: int = 10
CONTEXT_MAX_DOC_CHARS: int = 8000
CONTEXT_CACHE_NAME: str = "context_cache.json"

# ── Stakes (reference_query) ──────────────────────────────────────────────────

STAKES = ("low", "medium", "high")
STAKES_FLOOR_SHIFT: dict[str, float] = {"low": 0.1, "medium": 0.0, "high": -0.05}


# ── Path helpers (lazy so an import never fails when nothing is set up) ───────

def index_root() -> pathlib.Path:
    return get_path("index")


def collection_dir(name: str) -> pathlib.Path:
    return index_root() / name


def context_cache_file() -> pathlib.Path:
    return index_root() / CONTEXT_CACHE_NAME


def extra_skip_dirs() -> frozenset[str]:
    raw = os.environ.get(ENV_EXTRA_SKIP, "")
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def skip_dirs() -> frozenset[str]:
    return DEFAULT_SKIP_DIRS | extra_skip_dirs()


def load_routing() -> dict:
    """Load routing.yaml. Returns {} when the file or PyYAML is missing."""
    if not ROUTING_FILE.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    data = yaml.safe_load(ROUTING_FILE.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def tier_words() -> dict[int, list[str]]:
    words = {k: list(v) for k, v in DEFAULT_TIER_WORDS.items()}
    custom = load_routing().get("tiers")
    if isinstance(custom, dict):
        for key, value in custom.items():
            try:
                words[int(key)] = [str(w).lower() for w in value]
            except (TypeError, ValueError):
                continue
    return words


def _segments(value: str) -> list[str]:
    return [p for p in value.lower().replace("\\", "/").split("/") if p]


def vault_skip_paths() -> frozenset[str]:
    """Vault-relative folders left out of the vault walk: the fixed top-level names plus the layout folders."""
    out = set(VAULT_SKIP_TOP_NAMES)
    for key in VAULT_SKIP_LAYOUT_KEYS:
        try:
            out.add("/".join(_segments(folder_name(key))))
        except (KeyError, NotSetUp):
            continue
    return frozenset(out)


def tier_rules() -> dict:
    """Everything tier_for needs, read once so a query does not re-read the layout per result."""
    tier3_folders = []
    for key in TIER_FOLDER_KEYS[3]:
        try:
            tier3_folders.append(_segments(folder_name(key)))
        except (KeyError, NotSetUp):
            continue
    tier1_folders = []
    try:
        base = _segments(folder_name("knowledge"))
        tier1_folders = [base + [sub] for sub in TIER1_KNOWLEDGE_SUBDIRS]
    except (KeyError, NotSetUp):
        pass
    return {"tier3_folders": [f for f in tier3_folders if f], "tier1_folders": tier1_folders,
            "words": tier_words()}


def _starts_with(segments: list[str], prefix: list[str]) -> bool:
    return bool(prefix) and segments[: len(prefix)] == prefix


def _has_word(tokens: set[str], words: list[str]) -> bool:
    return any(w in tokens or w + "s" in tokens for w in words)


def tier_for(file_path: str, collection: str = "vault", rules: dict | None = None) -> tuple[int, str]:
    """Confidence tier of a file. Order: OBSERVED layout folders, VERIFIED folders, OBSERVED words,
    VERIFIED words, default. Words match whole tokens of a path segment only."""
    rules = rules or tier_rules()
    segments = _segments(file_path)
    tokens = {t for seg in segments for t in re.split(r"[^a-z0-9]+", seg) if t}
    if any(_starts_with(segments, f) for f in rules["tier3_folders"]):
        return 3, TIER_LABELS[3]
    if any(_starts_with(segments, f) for f in rules["tier1_folders"]) or \
            any(seg in TIER1_SEGMENT_NAMES for seg in segments[:-1]):
        return 1, TIER_LABELS[1]
    words = rules["words"]
    for tier in (3, 1):
        if _has_word(tokens, words.get(tier, [])):
            return tier, TIER_LABELS[tier]
    return DEFAULT_TIER, TIER_LABELS[DEFAULT_TIER]


def chroma_client(path):
    """A local ChromaDB client with telemetry off, so nothing leaves the machine."""
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
