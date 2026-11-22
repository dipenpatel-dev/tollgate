#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: assertions for tests/e2e/run_gate.sh over two Claude Code stream-json outputs
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Created.

Usage: check_gate.py WORK_DIR BARE_REMOTE TICKET_KEY   (exit 0 = all pass)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def load(path: str) -> list[dict]:
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.startswith("{")]


def hook_outputs(events: list[dict], name_part: str) -> list[str]:
    return [(e.get("stdout") or "") + (e.get("output") or "") for e in events
            if e.get("subtype") == "hook_response" and name_part in e.get("hook_name", "")]


def tool_calls(events: list[dict], tool: str) -> list[dict]:
    calls = []
    for event in events:
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == tool:
                    calls.append(block.get("input") or {})
    return calls


def remote_has_commits(remote: str) -> bool:
    out = subprocess.run(["git", "-C", remote, "for-each-ref"], capture_output=True, text=True, check=False)
    return bool(out.stdout.strip())


def main(argv: list[str]) -> int:
    work, remote, ticket = argv[1:4]
    a = load(os.path.join(work, "streamA.jsonl"))
    b = load(os.path.join(work, "streamB.jsonl"))
    gate = hook_outputs(a, "UserPromptExpansion")
    push = hook_outputs(b, "PreToolUse:Bash")
    all_tools_a = [e for e in a if e.get("type") == "assistant"
                   for blk in e.get("message", {}).get("content", [])
                   if isinstance(blk, dict) and blk.get("type") == "tool_use"]
    failed = [e.get("hook_name") for e in a + b
              if e.get("subtype") == "hook_response" and e.get("outcome") not in ("success", None)]
    results = [
        ("gate: hook ran on the slash command", bool(gate), "no UserPromptExpansion hook response"),
        ("gate: decision is block", any('"decision": "block"' in g for g in gate), f"outputs: {gate}"),
        ("gate: reason names the ticket and the missing spec",
         any(ticket in g and "spec" in g.lower() for g in gate), f"outputs: {gate}"),
        ("gate: command did not go on to run tools", not all_tools_a, f"{len(all_tools_a)} tool calls after block"),
        ("push: model attempted git push", any("push" in c.get("command", "") for c in tool_calls(b, "Bash")),
         "no push attempted"),
        ("push: guard denied the protected branch",
         any('"permissionDecision": "deny"' in p and "protected branch" in p for p in push), f"outputs: {push}"),
        ("push: nothing reached the remote", not remote_has_commits(remote), "remote has refs"),
        ("no hook run failed", not failed, f"failed: {failed}"),
    ]
    for name, ok, why in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  ({why})"))
    passed = sum(ok for _, ok, _ in results)
    print(f"\n  {passed}/{len(results)} passed   artifacts: {work}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
