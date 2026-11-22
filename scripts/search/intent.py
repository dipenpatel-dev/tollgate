"""
module_name: intent.py
description: Query intent classifier. Picks which collections to tilt: explicit intent, situation map, then equal weight.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the personal vector search. The routing profile layer is left out (no profile is defined in the shipped routing.yaml).
  1.1.0: Removed the keyword heuristic and the interactive question. No command reached them, and the
         question blocked on a terminal. Intent now comes only from --intent, --situation or the skill map.
"""
from __future__ import annotations

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402

logger = logging.getLogger(__name__)

VALID_INTENTS: frozenset[str] = frozenset(["teach", "verify", "build", "decide", "draft"])
FULL_CONFIDENCE: float = 1.0
NO_CONFIDENCE: float = 0.0


def classify_intent(
    query: str,
    explicit_intent: str | None = None,
    situation: str | None = None,
) -> tuple[str, float]:
    """Return (intent, confidence). `ambiguous` means equal weight across collections."""
    if explicit_intent == "ambiguous":
        return ("ambiguous", NO_CONFIDENCE)
    if explicit_intent in VALID_INTENTS:
        return (explicit_intent, FULL_CONFIDENCE)
    if situation is not None:
        mapped = map_situation(situation)
        if mapped is not None:
            return (mapped, FULL_CONFIDENCE)
    return ("ambiguous", NO_CONFIDENCE)


def map_situation(situation: str) -> str | None:
    mapped = config.load_routing().get("situation_map", {}).get(situation)
    if mapped is not None and mapped not in VALID_INTENTS:
        logger.warning("situation_map entry %r maps to unknown intent %r", situation, mapped)
        return None
    return mapped


def map_skill(skill: str) -> str | None:
    """Map a command name such as `x-dev` to an intent through the `skill_map` in routing.yaml."""
    routing = config.load_routing().get("skill_map", {})
    suffix = skill.rsplit("-", 1)[-1].lower()
    mapped = routing.get(suffix)
    return mapped if mapped in VALID_INTENTS else None
