"""
module_name: context_generator.py
description: Generate a short context description for each chunk. Used by build_index.py at index time only, never at query time. Needs a provider; off unless build_index.py is run with --context.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the personal vector search. The secrets-manager key lookup is a seam now: the Claude provider reads ANTHROPIC_API_KEY from the environment only. The Ollama provider needs TOLLGATE_OLLAMA_URL and TOLLGATE_OLLAMA_MODEL.
"""

import asyncio
import hashlib
import json
import logging
import os
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "You are a precise technical writer. Respond with only the requested description."

_DOC_TEMPLATE = (
    "Here is a document:\n\n"
    "<document>\n{doc_text}\n</document>\n\n"
)

_CHUNK_TEMPLATE = (
    "Here is a chunk from that document:\n\n"
    "<chunk>\n{chunk_text}\n</chunk>\n\n"
    "Write 1-2 sentences describing what this chunk covers and where it fits "
    "in the document. Be specific. Use different words than the chunk itself "
    "where possible. No preamble, no labels, just the description."
)

_USER_TEMPLATE = _DOC_TEMPLATE + _CHUNK_TEMPLATE

_USAGE_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)

CallFn = Callable[[str, str], Awaitable[str]]

# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_key(doc_text: str, chunk_text: str) -> str:
    return hashlib.sha256((doc_text + chunk_text).encode()).hexdigest()


def load_cache() -> dict:
    cache_file = config.context_cache_file()
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    cache_file = config.context_cache_file()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_file.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(cache, f)
    os.replace(tmp_path, cache_file)

# ── Shared runner ─────────────────────────────────────────────────────────────

@dataclass
class _RunState:
    results: list[Optional[str]]
    cache: Optional[dict]
    usage: dict[str, int] = field(default_factory=lambda: dict.fromkeys(_USAGE_FIELDS, 0))
    calls_done: int = 0
    calls_since_flush: int = 0
    failures: int = 0


def _flush(state: _RunState) -> None:
    if state.cache is not None:
        save_cache(state.cache)
    state.calls_since_flush = 0
    logger.info(f"Context progress: {state.calls_done} calls done, tokens {json.dumps(state.usage)}")


def _record_group(
    state: _RunState, doc_text: str, members: list[tuple[int, str]], texts: list[Optional[str]]
) -> None:
    for (idx, chunk_text), text in zip(members, texts):
        if text is None:
            state.failures += 1
            continue
        state.results[idx] = text
        if state.cache is not None and text:
            state.cache[_cache_key(doc_text, chunk_text)] = text
    state.calls_done += len(members)
    state.calls_since_flush += len(members)
    if state.calls_since_flush >= config.CONTEXT_SAVE_EVERY_CALLS:
        _flush(state)


async def _run_doc_group(
    call: CallFn,
    semaphore: asyncio.Semaphore,
    doc_text: str,
    members: list[tuple[int, str]],
) -> list[Optional[str]]:
    """One failed call returns None for that chunk only; the rest of the document is kept."""
    async def _one(chunk_text: str) -> Optional[str]:
        async with semaphore:
            try:
                return await call(doc_text, chunk_text)
            except Exception as exc:
                logger.error(f"Context call failed: {type(exc).__name__}: {str(exc)[:200]}")
                return None

    first = await _one(members[0][1])  # warms the prompt or prefix cache before the parallel calls
    rest = await asyncio.gather(*[_one(chunk_text) for _, chunk_text in members[1:]])
    return [first, *rest]


async def _run_groups(
    groups: dict[str, list[tuple[int, str]]],
    state: _RunState,
    call: CallFn,
    doc_workers: int,
    max_concurrent: int,
) -> None:
    semaphore = asyncio.Semaphore(max_concurrent)
    pending = iter(groups.items())

    async def _worker() -> None:
        for doc_text, members in pending:
            texts = await _run_doc_group(call, semaphore, doc_text, members)
            _record_group(state, doc_text, members, texts)

    try:
        await asyncio.gather(*[_worker() for _ in range(doc_workers)])
    finally:
        _flush(state)
    if state.failures:
        raise RuntimeError(
            f"{state.failures} context calls failed; finished work is saved in the cache. Rerun to retry only those."
        )

# ── Claude provider ───────────────────────────────────────────────────────────

def _add_usage(totals: dict[str, int], usage: Any) -> None:
    for name in _USAGE_FIELDS:
        totals[name] += getattr(usage, name, 0) or 0


async def _generate_claude(groups: dict[str, list[tuple[int, str]]], state: _RunState) -> None:
    import anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        # Seam: a connector may fetch the key from your own secret store and export it before this runs.
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = anthropic.AsyncAnthropic()

    async def _call(doc_text: str, chunk_text: str) -> str:
        message = await client.messages.create(
            model=config.CLAUDE_CONTEXT_MODEL,
            max_tokens=config.CONTEXT_MAX_OUTPUT_TOKENS,
            output_config={"effort": config.CLAUDE_CONTEXT_EFFORT},
            system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": [
                {
                    "type": "text",
                    "text": _DOC_TEMPLATE.format(doc_text=doc_text),
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": _CHUNK_TEMPLATE.format(chunk_text=chunk_text)},
            ]}],
        )
        _add_usage(state.usage, message.usage)
        text_block = next((b for b in message.content if b.type == "text"), None)
        if text_block is None:
            logger.warning(f"No text block in context reply (stop_reason={message.stop_reason}); using empty context")
            return ""
        return text_block.text.strip()

    await _run_groups(
        groups, state, _call, config.CONTEXT_DOC_WORKERS, config.CONTEXT_MAX_CONCURRENT
    )

# ── Ollama provider ───────────────────────────────────────────────────────────

def _ollama_payload(doc_text: str, chunk_text: str) -> dict[str, Any]:
    return {
        "model": config.OLLAMA_CONTEXT_MODEL,
        "system": _SYSTEM_PROMPT,
        "prompt": _USER_TEMPLATE.format(doc_text=doc_text, chunk_text=chunk_text),
        "stream": False,
        "think": False,
        "keep_alive": config.OLLAMA_KEEP_ALIVE,
        "options": {
            "num_ctx": config.OLLAMA_NUM_CTX,
            "num_predict": config.CONTEXT_MAX_OUTPUT_TOKENS,
            "temperature": 0,
        },
    }


async def _generate_ollama(groups: dict[str, list[tuple[int, str]]], state: _RunState) -> None:
    import aiohttp
    if not config.OLLAMA_BASE_URL or not config.OLLAMA_CONTEXT_MODEL:
        raise RuntimeError("TOLLGATE_OLLAMA_URL and TOLLGATE_OLLAMA_MODEL must both be set")
    timeout = aiohttp.ClientTimeout(total=config.OLLAMA_CALL_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def _call(doc_text: str, chunk_text: str) -> str:
            url = f"{config.OLLAMA_BASE_URL}/api/generate"
            async with session.post(url, json=_ollama_payload(doc_text, chunk_text)) as resp:
                data = await resp.json()
            if "response" not in data:
                raise RuntimeError(f"Ollama returned no response: {str(data)[:300]}")
            state.usage["output_tokens"] += data.get("eval_count", 0)
            state.usage["input_tokens"] += data.get("prompt_eval_count", 0)
            return data["response"].strip()

        await _run_groups(
            groups, state, _call, config.OLLAMA_DOC_WORKERS, config.OLLAMA_MAX_CONCURRENT
        )

# ── Public API ────────────────────────────────────────────────────────────────

def _split_cached(
    pairs: list[tuple[str, str]], cache: Optional[dict], results: list[Optional[str]]
) -> dict[str, list[tuple[int, str]]]:
    """Fill results from cache; return uncached (index, chunk) members grouped by document."""
    groups: dict[str, list[tuple[int, str]]] = {}
    for i, (doc, chunk) in enumerate(pairs):
        key = _cache_key(doc, chunk)
        if cache is not None and key in cache:
            results[i] = cache[key]
        else:
            groups.setdefault(doc, []).append((i, chunk))
    return groups


def batch_generate_context(
    pairs: list[tuple[str, str]],
    cache: Optional[dict] = None,
) -> list[str]:
    """
    Generate context descriptions for a list of (doc_text, chunk_text) pairs.
    Checks cache first. Uncached pairs are grouped by document and generated.
    Results are flushed to the cache file during the run and on failure.
    Returns results in the same order as the input list.
    """
    results: list[Optional[str]] = [None] * len(pairs)
    groups = _split_cached(pairs, cache, results)
    state = _RunState(results=results, cache=cache)
    if groups:
        provider = config.CONTEXT_PROVIDER
        if provider == "claude":
            asyncio.run(_generate_claude(groups, state))
        elif provider == "ollama":
            asyncio.run(_generate_ollama(groups, state))
        else:
            raise ValueError(f"Unknown CONTEXT_PROVIDER: {provider!r}. Use 'claude' or 'ollama'.")
    return results
