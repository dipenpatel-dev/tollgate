# Module:      plane_markdown.py
# Description: A small markdown to HTML renderer with no outside library. Raw HTML and images are never produced.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       headings, paragraphs, lists, fenced code, bold, italics, inline code and http links
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import re

FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
INLINE_CODE = re.compile(r"`([^`\n]+)`")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
ITALIC = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
SAFE_SCHEMES = ("http://", "https://", "mailto:")
PLACEHOLDER = "\x00%d\x00"


def escape(text: str) -> str:
    """Escape the characters that could start HTML."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _link(match: re.Match[str]) -> str:
    target = match.group(2)
    if not target.lower().startswith(SAFE_SCHEMES):
        return match.group(0)
    return f'<a href="{target}">{match.group(1)}</a>'


def _inline(text: str) -> str:
    """Render the inline marks of one escaped line. Code spans are shielded first."""
    spans: list[str] = []

    def shield(match: re.Match[str]) -> str:
        spans.append(f"<code>{match.group(1)}</code>")
        return PLACEHOLDER % (len(spans) - 1)

    out = INLINE_CODE.sub(shield, escape(text))
    out = LINK.sub(_link, out)
    out = BOLD.sub(r"<strong>\1</strong>", out)
    out = ITALIC.sub(r"<em>\1</em>", out)
    for index, span in enumerate(spans):
        out = out.replace(PLACEHOLDER % index, span)
    return out


def _code_block(lines: list[str], language: str) -> str:
    body = escape("\n".join(lines))
    attr = f' class="language-{escape(language)}"' if language else ""
    return f"<pre><code{attr}>{body}\n</code></pre>" if lines else f"<pre><code{attr}></code></pre>"


def _list_html(tag: str, items: list[str]) -> str:
    return f"<{tag}>\n" + "".join(f"<li>{_inline(item)}</li>\n" for item in items) + f"</{tag}>"


def _consume_list(lines: list[str], start: int, pattern: re.Pattern[str], tag: str) -> tuple[str, int]:
    items: list[str] = []
    index = start
    while index < len(lines) and pattern.match(lines[index]):
        items.append(pattern.match(lines[index]).group(1))  # type: ignore[union-attr]
        index += 1
    return _list_html(tag, items), index


def _starts_block(line: str) -> bool:
    return bool(FENCE_OPEN.match(line) or HEADING.match(line) or BULLET.match(line) or NUMBERED.match(line))


def _consume_fence(lines: list[str], start: int) -> tuple[str, int]:
    opener = FENCE_OPEN.match(lines[start])
    assert opener is not None
    marker = opener.group(1)
    body: list[str] = []
    index = start + 1
    while index < len(lines):
        closing = lines[index].strip()
        if closing.startswith(marker[0] * len(marker)) and set(closing) == {marker[0]}:
            index += 1
            break
        body.append(lines[index])
        index += 1
    return _code_block(body, opener.group(2)), index


def _consume_paragraph(lines: list[str], start: int) -> tuple[str, int]:
    index = start
    parts: list[str] = []
    while index < len(lines) and lines[index].strip() and not (index > start and _starts_block(lines[index])):
        parts.append(_inline(lines[index].strip()))
        index += 1
    return "<p>" + "\n".join(parts) + "</p>", index


def markdown_to_html(markdown_text: str) -> str:
    """Render markdown. Raw HTML is shown as text and images are not made, so nothing can make a viewer load anything."""
    lines = markdown_text.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        heading = HEADING.match(line)
        if not line.strip():
            index += 1
        elif FENCE_OPEN.match(line):
            html, index = _consume_fence(lines, index)
            blocks.append(html)
        elif heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            index += 1
        elif BULLET.match(line):
            html, index = _consume_list(lines, index, BULLET, "ul")
            blocks.append(html)
        elif NUMBERED.match(line):
            html, index = _consume_list(lines, index, NUMBERED, "ol")
            blocks.append(html)
        else:
            html, index = _consume_paragraph(lines, index)
            blocks.append(html)
    return "\n".join(blocks) + ("\n" if blocks else "")
