"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: Shared pattern module for citation enforcement in Claude Code PreToolUse hooks.
       Holds STATUS_PATTERN, CITATION_PATTERN, and the line-by-line state machine scanner.
       Not a hook. Imported by pre_tool_write_scan_claims.py through the hooks
       directory.
ChangeLog:
  - Removed the mention of the dropped validate-for-write.py helper.
  - Created. Follows the phi_patterns.py shape.
    Line-by-line state machine handles YAML front matter, fenced code
    blocks (including mermaid), and table header rows.
"""

from __future__ import annotations

import re

# Bare words in assertive prose that state a fact and need a citation marker.
STATUS_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:DONE|SHIPPED|APPROVED|COMPLETE)\b"
)

# Citation marker: "(source: X)" or an "(unverified" prefix. re.IGNORECASE covers
# stylistic variations. No dash character is embedded in the pattern.
CITATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(source:[^)]+\)"
    r"|\(unverified",
    re.IGNORECASE,
)


def strip_to_scannable(text: str) -> list[tuple[int, str]]:
    """
    Return (line_number, line) pairs for lines that should be scanned.

    Suppressed lines: YAML front matter between the first --- pair,
    fenced code blocks (``` or ~~~, including mermaid), and table header
    rows (lines whose only characters are |, -, :, and whitespace).
    """
    result: list[tuple[int, str]] = []
    in_fence: bool = False
    in_yaml: bool = False
    first_line_seen: bool = False

    for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
        stripped = line.strip()

        # YAML front matter: a first line of "---" opens suppression
        if not first_line_seen:
            if stripped == "---":
                in_yaml = True
                first_line_seen = True
                continue
            first_line_seen = True

        if in_yaml:
            if stripped == "---":
                in_yaml = False
            continue  # suppress all YAML lines including the closing ---

        # Fence toggle: ``` or ~~~ at the start of the stripped line
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue  # skip the fence delimiter line itself

        if in_fence:
            continue  # suppress all content inside a fenced block

        # Table header row: only |, -, :, and whitespace characters
        if stripped.count("|") >= 2 and re.fullmatch(r"[\s|:\-]+", stripped):
            continue

        result.append((line_no, line))

    return result


def has_citation(line: str) -> bool:
    """Return True when the line contains a valid citation marker."""
    return bool(CITATION_PATTERN.search(line))


def scan_for_uncited_claims(texts: list[str]) -> list[tuple[int, str]]:
    """
    Return (line_number, matched_word) for status assertions on non-suppressed
    lines that carry no citation marker.
    """
    findings: list[tuple[int, str]] = []
    for text in texts:
        for line_no, line in strip_to_scannable(text):
            m = STATUS_PATTERN.search(line)
            if m and not has_citation(line):
                findings.append((line_no, m.group(0)))
    return findings
