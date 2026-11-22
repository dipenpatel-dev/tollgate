#!/usr/bin/env python3
"""
module_name: mermaid_block.py
description: Extract a fenced mermaid block from a markdown file and copy it to the clipboard,
             without the fence markers, ready to paste into a diagram editor. Lists the blocks
             when no number is given. Falls back to standard output when no clipboard tool exists.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial. List mode and extract-to-clipboard mode. Clipboard tool is found at run time.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

FENCE_PATTERN = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
HEADING_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)
CLIPBOARD_TOOLS = (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"])


def read_blocks(path: Path) -> tuple[list[str], list[str]]:
    """Return (mermaid blocks, level-two headings) for a markdown file."""
    text = path.read_text(encoding="utf-8")
    return FENCE_PATTERN.findall(text), HEADING_PATTERN.findall(text)


def label_for(headings: list[str], index: int) -> str:
    """Heading that precedes block `index` (1-based), or a placeholder."""
    return headings[index - 1] if index - 1 < len(headings) else "(no heading)"


def list_blocks(blocks: list[str], headings: list[str]) -> None:
    for number, block in enumerate(blocks, start=1):
        flag = " [has subgraph]" if "subgraph" in block else ""
        line_count = len(block.strip().splitlines())
        print(f"{number}. {label_for(headings, number)}  ({line_count} lines){flag}")


def clipboard_command():
    """First clipboard tool found on this machine, or None."""
    for command in CLIPBOARD_TOOLS:
        if shutil.which(command[0]):
            return command
    return None


def copy_to_clipboard(payload: str) -> bool:
    """Send payload to the system clipboard. Returns False if no tool is available."""
    command = clipboard_command()
    if command is None:
        return False
    try:
        subprocess.run(command, input=payload, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extract a mermaid block for pasting into a diagram editor.")
    parser.add_argument("file", type=Path, help="Markdown file containing mermaid fences.")
    parser.add_argument("block", nargs="?", type=int, help="Block number to extract. Omit to list all blocks.")
    parser.add_argument("--stdout", action="store_true", help="Print the block instead of copying it.")
    args = parser.parse_args(argv)

    if not args.file.is_file():
        print(f"No such file: {args.file}", file=sys.stderr)
        return 1

    blocks, headings = read_blocks(args.file)
    if not blocks:
        print(f"No mermaid blocks found in {args.file}", file=sys.stderr)
        return 1

    if args.block is None:
        list_blocks(blocks, headings)
        return 0

    if not 1 <= args.block <= len(blocks):
        print(f"Block {args.block} out of range: 1 to {len(blocks)}", file=sys.stderr)
        return 1

    payload = blocks[args.block - 1].strip()
    if args.stdout:
        print(payload)
        return 0

    if not copy_to_clipboard(payload):
        print("Clipboard unavailable, falling back to stdout:", file=sys.stderr)
        print(payload)
        return 0

    print(f"Copied block {args.block}: {label_for(headings, args.block)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
