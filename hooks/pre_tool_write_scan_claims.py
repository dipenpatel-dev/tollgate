#!/usr/bin/env python3
"""
Trigger: PreToolUse -- Write|Edit|NotebookEdit (.md files only)
Scope: markdown content only; the .md path filter runs before the scan
Action: scan for uncited status assertions (DONE, SHIPPED, APPROVED, COMPLETE)
On result: permissionDecision deny JSON + exit 0 blocks; exit 0 allows
Fails closed: an internal error exits 2, so a broken citation gate blocks the write
Returns the line number and the word only, never the surrounding text.

Author: Dipen Patel (dipenpatel-dev)
Date:
ChangeLog:
  - Created. Follows the phi_patterns.py shape.
  - Reads the path from file_path as Claude Code sends it, and still accepts path.
"""

from __future__ import annotations

import json
import os
import sys

HOOK_EVENT = "PreToolUse"


def deny(reason: str) -> None:
    """Emit a structured deny response and exit 0 (the JSON carries the block decision)."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def extract_content(payload: dict) -> list[tuple[str | None, str]]:
    """
    Return (file_path, content) pairs for .md files only, so the scanner never reads
    Python, shell, YAML or JSON files where status words are legitimate identifiers.
    """
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    path = inp.get("file_path") or inp.get("path")

    if tool == "Write":
        pairs: list[tuple[str | None, str | None]] = [(path, inp.get("content"))]
    elif tool == "Edit":
        pairs = [(path, inp.get("new_string"))]
    elif tool == "MultiEdit":  # not a current tool name; kept so an old payload parses harmlessly
        pairs = [(path, e.get("new_string")) for e in (inp.get("edits") or [])]
    elif tool == "NotebookEdit":
        pairs = [(inp.get("notebook_path"), inp.get("new_source"))]
    else:
        pairs = []

    return [
        (p, t)
        for p, t in pairs
        if isinstance(t, str) and t
        and isinstance(p, str) and p.endswith(".md")
    ]


def main() -> None:
    payload = json.loads(sys.stdin.read())
    pairs = extract_content(payload)
    if not pairs:
        sys.exit(0)

    findings = scan_for_uncited_claims([t for _, t in pairs])
    if findings:
        line_no, word = findings[0]
        deny(
            "Uncited status assertion '{}' on line {}. "
            "Add (source: <tool or document>) or the marker (unverified: confirm before "
            "relying on this) to the same line, or use lowercase or "
            "paraphrase the word if it is not a factual claim.".format(word, line_no)
        )
    sys.exit(0)


# Import claim_patterns from the same hooks directory, then run main().
# Fails closed: any import or runtime error exits 2 (blocks the write).
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from claim_patterns import scan_for_uncited_claims  # noqa: E402
    main()
except SystemExit:
    raise
except Exception as exc:
    sys.stderr.write("pre_tool_write_scan_claims: %s; blocking (fails closed).\n" % type(exc).__name__)
    sys.exit(2)
