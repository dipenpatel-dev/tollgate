# Module:      plane_comment_builder.py
# Description: Builds Plane comment text from vault files: markdown to HTML, secret scan, length cut, session and extras text.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       plane sync comment text only; reads vault files, writes nothing
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Mapping

from connectors.plane.plane_markdown import markdown_to_html
from connectors.plane.vault_ticket_files import session_log_files

COMMENT_KEY_LENGTH = 12
SECTION_PREFIX = "## "
FRONTMATTER_FENCE = "---"
MERMAID_FENCE_OPEN = "```mermaid"
FENCE_CLOSE = "```"
SESSION_HEADING = "### "
SPEC_SECTIONS = ("Requirements", "Acceptance Criteria")
DESIGN_PLAN_HEADING = "Implementation Plan"
DIAGRAM_HEADING = "### Final diagram"


def find_secret_pattern(text: str, patterns: Mapping[str, str]) -> str | None:
    """Return the name of the first pattern that matches the text, or None."""
    for name, pattern in patterns.items():
        if re.search(pattern, text):
            return name
    return None


def cut_to_limit(text: str, limit: int, pointer_line: str) -> str:
    """Return the text unchanged when it fits, else a cut text that ends with the pointer line."""
    if len(text) <= limit:
        return text
    keep = max(0, limit - len(pointer_line) - 1)
    return text[:keep] + "\n" + pointer_line


def read_new_session_text(
    folder: Path, ticket_id: str, offsets: Mapping[str, int]
) -> tuple[str, dict[str, int]]:
    """Return the text after each file's offset, and the new offsets (the length of every file)."""
    parts: list[str] = []
    new_offsets: dict[str, int] = {}
    for path in session_log_files(folder, ticket_id):
        text = path.read_text(encoding="utf-8")
        new_offsets[path.name] = len(text)
        fresh = text[offsets.get(path.name, 0):]
        if fresh.strip():
            parts.append(f"{SESSION_HEADING}{path.name}\n{fresh}")
    return "\n\n".join(parts), new_offsets


def extract_markdown_section(text: str, heading: str) -> str:
    """Return the lines from the `## heading` line up to the next `## ` line, or an empty string."""
    collected: list[str] = []
    inside = False
    for line in text.splitlines():
        if inside and line.startswith(SECTION_PREFIX):
            break
        if line.rstrip() == f"{SECTION_PREFIX}{heading}":
            inside = True
        if inside:
            collected.append(line)
    return "\n".join(collected).strip("\n")


def _heading_index(lines: list[str], heading: str) -> int | None:
    wanted = (f"## {heading}", f"### {heading}")
    for index, line in enumerate(lines):
        if line.rstrip() in wanted:
            return index
    return None


def extract_first_mermaid_block(text: str, after_heading: str) -> str:
    """Return the first mermaid fenced block after the heading, with both fence lines, or an empty string."""
    lines = text.splitlines()
    start = _heading_index(lines, after_heading)
    if start is None:
        return ""
    block: list[str] = []
    for line in lines[start + 1:]:
        if not block and line.strip() == MERMAID_FENCE_OPEN:
            block.append(line)
        elif block:
            block.append(line)
            if line.strip() == FENCE_CLOSE:
                return "\n".join(block)
    return ""


def build_spec_extras(spec_text: str, design_text: str) -> str:
    """Join the spec requirements, the acceptance criteria and the design diagram; name any part that is missing."""
    parts: list[str] = []
    for heading in SPEC_SECTIONS:
        section = extract_markdown_section(spec_text, heading)
        parts.append(section if section else f"(extras: section {heading} not found in the spec)")
    diagram = extract_first_mermaid_block(design_text, DESIGN_PLAN_HEADING)
    if diagram:
        parts.append(f"{DIAGRAM_HEADING}\n\n{diagram}")
    else:
        parts.append(f"(extras: diagram under {DESIGN_PLAN_HEADING} not found in the design)")
    return "\n\n".join(parts)


def build_dev_extras(validation_text: str) -> str:
    """Return the validation text without its frontmatter."""
    lines = validation_text.splitlines()
    if lines and lines[0].rstrip() == FRONTMATTER_FENCE:
        for index, line in enumerate(lines[1:], start=1):
            if line.rstrip() == FRONTMATTER_FENCE:
                return "\n".join(lines[index + 1:]).strip("\n")
    return validation_text.strip("\n")


def comment_key(text: str) -> str:
    """Return the first 12 hex characters of the SHA-256 of the text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:COMMENT_KEY_LENGTH]
