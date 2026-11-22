"""
module_name: chart_rules.py
description: Loads chart_rules.json and answers which chart types a role may use.
             Pure lookups; no document text is read here.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial loader with validation, role lookup and ticket widening.
"""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass

DEFAULT_RULES = pathlib.Path(__file__).resolve().parent / "chart_rules.json"
SLUG = re.compile(r"^[a-z][a-z0-9_]*$")


class ChartRulesError(ValueError):
    """The rules file is missing, unreadable or holds a bad entry."""


@dataclass(frozen=True)
class ChartRules:
    types: dict            # slug -> frozenset of keywords
    roles: dict            # role -> frozenset of slugs
    widen: dict            # ticket flag -> frozenset of slugs
    max_flowchart_nodes: int
    forbidden_shapes: tuple


def load_rules(path=None) -> ChartRules:
    """Read and check the rules file. Raises ChartRulesError on any problem."""
    location = pathlib.Path(path) if path else DEFAULT_RULES
    try:
        raw = json.loads(location.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ChartRulesError("rules file unreadable: " + type(exc).__name__) from None
    if not isinstance(raw, dict):
        raise ChartRulesError("rules file must hold an object")
    types: dict = {}
    owner: dict = {}
    for slug, entry in (raw.get("types") or {}).items():
        words = entry.get("keywords") if isinstance(entry, dict) else None
        if not SLUG.match(slug) or not isinstance(words, list) or not words:
            raise ChartRulesError("bad type entry: " + str(slug))
        for word in words:
            if word in owner:
                raise ChartRulesError("keyword shared by " + owner[word] + " and " + slug)
            owner[word] = slug
        types[slug] = frozenset(words)
    if not types:
        raise ChartRulesError("rules file has no types")
    roles = {}
    for role, items in (raw.get("roles") or {}).items():
        if not isinstance(items, list) or any(i not in types for i in items):
            raise ChartRulesError("role lists an unknown type: " + str(role))
        roles[role] = frozenset(items)
    widen = {}
    for flag, items in (raw.get("ticket_widen") or {}).items():
        if not isinstance(items, list) or any(i not in types for i in items):
            raise ChartRulesError("widen list has an unknown type: " + str(flag))
        widen[flag] = frozenset(items)
    return ChartRules(
        types=types,
        roles=roles,
        widen=widen,
        max_flowchart_nodes=int(raw.get("max_flowchart_nodes", 12)),
        forbidden_shapes=tuple(raw.get("forbidden_flowchart_shapes", [])),
    )


def allowed_for_role(rules: ChartRules, role: str, widened=frozenset()) -> frozenset:
    """Types a role may use, plus any types a ticket flag widened. Raises on an unknown role."""
    if role not in rules.roles:
        raise ChartRulesError("unknown role: " + role)
    return rules.roles[role] | frozenset(widened)


def widened_types(rules: ChartRules, flags: dict) -> frozenset:
    """Types widened by ticket flags. Only a real true counts; the text 'true' is read by the caller."""
    out = set()
    for flag, slugs in rules.widen.items():
        if flags.get(flag) is True:
            out |= slugs
    return frozenset(out)
