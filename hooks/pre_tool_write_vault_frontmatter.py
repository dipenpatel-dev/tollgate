#!/usr/bin/env python3
"""
Trigger: PreToolUse -- Write|Edit on markdown files inside the vault (TOLLGATE_KNOWLEDGE)
Scope: .md files under the vault folder only; the path filter runs before any scan.
       With TOLLGATE_KNOWLEDGE unset the hook allows everything.
Action: block writes with invalid frontmatter (status case, type separator, empty string value)
On result: permissionDecision deny JSON + exit 0 blocks; exit 0 allows
Fails closed: an internal error exits 2 and blocks the write (an unset TOLLGATE_KNOWLEDGE still allows)

Author: Dipen Patel (dipenpatel-dev)
Date:
ChangeLog:
  - Created. Replaces the after-the-fact frontmatter reminder with a check before the write.
  - The vault folder comes from TOLLGATE_KNOWLEDGE instead of a fixed folder name.
"""

from __future__ import annotations

import json
import os
import re
import sys

HOOK_EVENT = "PreToolUse"


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def vault_root() -> str:
    """Resolved vault folder with a trailing slash, or empty when TOLLGATE_KNOWLEDGE is unset."""
    raw = os.environ.get("TOLLGATE_KNOWLEDGE", "").strip()
    if not raw:
        return ""
    return os.path.realpath(os.path.expanduser(raw)).rstrip("/") + "/"


def in_vault(path: str, root: str) -> bool:
    return bool(root) and os.path.realpath(path).startswith(root)


def extract_frontmatter(content: str) -> dict[str, str] | None:
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        kv = re.match(r"^(\w+):\s*(.*)", line)
        if kv:
            fields[kv.group(1)] = kv.group(2).strip()
    return fields


def get_content_pairs(payload: dict, root: str) -> list[tuple[str, str]]:
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    if tool == "Write":
        pairs = [(inp.get("file_path"), inp.get("content"))]
    elif tool == "Edit":
        pairs = [(inp.get("file_path"), inp.get("new_string"))]
    elif tool == "MultiEdit":  # not a current tool name; kept so an old payload parses harmlessly
        pairs = [(inp.get("file_path"), e.get("new_string")) for e in (inp.get("edits") or [])]
    else:
        pairs = []
    return [
        (p, t)
        for p, t in pairs
        if isinstance(p, str) and p.endswith(".md") and in_vault(p, root)
        and isinstance(t, str) and t
    ]


def check_frontmatter(fields: dict[str, str], file_path: str) -> str | None:
    status = fields.get("status")
    if status and status not in ("null", "") and not re.match(r"^[A-Z][A-Z0-9_]*$", status):
        return (
            "Frontmatter status '{}' in {} must be ALL_CAPS (e.g. ACTIVE, LOCKED, DRAFT). "
            "Fix the status field and retry.".format(status, file_path)
        )

    type_val = fields.get("type")
    if type_val and type_val not in ("null", "") and "-" in type_val:
        return (
            "Frontmatter type '{}' in {} must use underscore not hyphen (e.g. ticket_spec). "
            "Fix the type field and retry.".format(type_val, file_path)
        )

    for key, val in fields.items():
        if val == '""' or val == "''":
            return (
                "Frontmatter field '{}' in {} is an empty string. "
                "Use null for absent optional fields, not an empty string.".format(key, file_path)
            )

    return None


def main() -> None:
    payload = json.loads(sys.stdin.read())
    root = vault_root()
    if not root:
        sys.exit(0)
    for file_path, content in get_content_pairs(payload, root):
        fields = extract_frontmatter(content)
        if fields is None:
            continue
        violation = check_frontmatter(fields, file_path)
        if violation:
            deny(violation)
    sys.exit(0)


try:
    main()
except SystemExit:
    raise
except Exception as exc:
    sys.stderr.write("pre_tool_write_vault_frontmatter: %s; blocking (fails closed).\n" % type(exc).__name__)
    sys.exit(2)
