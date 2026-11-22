"""
module_name: phi_guard.py
description: Pattern based scrubber for personal identifiers. Drops any record that contains one before it is written to disk.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported. Extra patterns can be added by the caller (scrub extra_patterns argument). Records are dropped whole; matched values are never logged.
"""

from __future__ import annotations

import re
from typing import Any

# Named compiled patterns, one per identifier category.
# Word boundary anchors catch embedded matches inside larger strings (e.g. "MRN 1234567 is due").
# Residual risk: names without a title are not caught by these patterns.
SSN_PATTERN: re.Pattern[str] = re.compile(r"\b\d{3}[\s-]?\d{2}[\s-]?\d{4}\b")
MRN_PATTERN: re.Pattern[str] = re.compile(r"\bMRN[:\s#]?\d{6,10}\b")
PT_ID_PATTERN: re.Pattern[str] = re.compile(r"\bPT[\s#:]?\d{5,10}\b")
DOB_SLASH_PATTERN: re.Pattern[str] = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
DOB_ISO_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:DOB|date of birth|born|d/o/b)(?:\s+is)?[\s:=\-]*\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
TITLED_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|Patient|Pt)\.?\s+[A-Z][a-zA-Z]+\b"
)

PHI_PATTERNS: list[re.Pattern[str]] = [
    SSN_PATTERN,
    MRN_PATTERN,
    PT_ID_PATTERN,
    DOB_SLASH_PATTERN,
    DOB_ISO_PATTERN,
    TITLED_NAME_PATTERN,
]


def _record_strings(node: Any) -> list[str]:
    """Return all string leaf values from a nested dict/list structure."""
    results: list[str] = []
    stack: list[Any] = [node]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            results.append(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return results


def _contains_phi(record: dict[str, Any], patterns: list[re.Pattern[str]] | None = None) -> bool:
    """Return True if any string value in record matches a pattern."""
    for text in _record_strings(record):
        for pattern in patterns if patterns is not None else PHI_PATTERNS:
            if pattern.search(text):
                return True
    return False


def scrub(
    payload: list[dict[str, Any]],
    source: str,  # reserved for source specific pattern settings
    extra_patterns: list[re.Pattern[str]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return (clean_records, reject_count) with PHI-matched records dropped.

    Each record is checked as a whole: any PHI match in any string value drops the
    entire record. Reject counts surface in daily_brief.json; no offending values
    are logged. extra_patterns adds your own compiled patterns to the built in set.
    """
    patterns = PHI_PATTERNS + list(extra_patterns or [])
    clean: list[dict[str, Any]] = []
    rejected = 0
    for record in payload:
        if _contains_phi(record, patterns):
            rejected += 1
        else:
            clean.append(record)
    return clean, rejected
