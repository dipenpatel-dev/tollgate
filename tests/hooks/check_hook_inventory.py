#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: fail when hooks/, settings.json and docs/hooks.md disagree about which hooks exist
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Removed validate-for-write.py from the helper list (hook dropped).
  - Check 4 now covers every PreToolUse and UserPromptExpansion entry plus the PostToolUse secret and
    PHI scanners. Added check 5 (no MultiEdit in a matcher, it is not a current tool name) and
    check 6 (a PreToolUse Skill matcher runs the gate hook for model-invoked skills).
  - Check 4 also covers the sensitive path read hook.
  - Added check 4: PHI scan hooks must set onFailure block.
  - Created.

Checks:
  1. every hook file in hooks/ is wired in settings.json (unless allowlisted as a helper)
  2. every hook file in hooks/ is mentioned in docs/hooks.md
  3. every hook file settings.json points at exists
  4. every PreToolUse and UserPromptExpansion hook, and the PostToolUse secret and PHI scanners,
     set "onFailure": "block" in settings.json (a policy hook that cannot run must not fail open)
  5. no matcher in settings.json names MultiEdit
  6. a PreToolUse matcher on Skill runs the gate hook

Run: python3 tests/hooks/check_hook_inventory.py   (exit 0 = consistent, 1 = drift)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO / "hooks"
SETTINGS = REPO / "settings.json"
DOC = REPO / "docs" / "hooks.md"
HELPERS = frozenset({
    "gate_rules.py",
    "phi_patterns.py",
    "read_guard_common.py",
    "sql_summary.py",
    "state_file_io.py",
    "git-pre-push",
    "pre-commit-secrets",
    "git_ask_before_run.py",
    "gh_pr_create_detect.py",
    "claim_patterns.py",
    "scrub_secrets.sh",
    "secret_var_registry.txt",
})
FAIL_CLOSED_EVENTS = ("PreToolUse", "UserPromptExpansion")
POST_POLICY_HOOKS = frozenset({
    "post-tool-bash-scan-secrets.py",
    "post-tool-result-scan-phi.py",
    "scrub_secrets.py",
})
GATE_HOOK = "pre-prompt-expansion-check-gates.py"
HOOK_REF_RE = re.compile(r"hooks/([A-Za-z0-9_.-]+)")


def wired_names(settings: dict) -> set[str]:
    """File names of every hook command in settings.json."""
    names: set[str] = set()
    for groups in settings.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                match = HOOK_REF_RE.search(hook.get("command", ""))
                if match:
                    names.add(match.group(1))
    return names


def hooks_not_blocking(settings: dict) -> list[str]:
    """Policy hook entries that do not set onFailure to block."""
    problems: list[str] = []
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                match = HOOK_REF_RE.search(hook.get("command", ""))
                if not match:
                    continue
                name = match.group(1)
                policy = event in FAIL_CLOSED_EVENTS or (event == "PostToolUse" and name in POST_POLICY_HOOKS)
                if policy and hook.get("onFailure") != "block":
                    problems.append(f"hooks/{name} ({event}) must set onFailure to block in settings.json")
    return problems


def multiedit_matchers(settings: dict) -> list[str]:
    """Matchers that still name MultiEdit."""
    return [
        f"settings.json {event} matcher {group['matcher']!r} names MultiEdit, which is not a current tool"
        for event, groups in settings.get("hooks", {}).items()
        for group in groups
        if "MultiEdit" in group.get("matcher", "")
    ]


def skill_gate_missing(settings: dict) -> list[str]:
    """A PreToolUse matcher on Skill that runs the gate hook must exist."""
    for group in settings.get("hooks", {}).get("PreToolUse", []):
        if group.get("matcher") == "Skill" and any(GATE_HOOK in h.get("command", "") for h in group.get("hooks", [])):
            return []
    return [f"settings.json has no PreToolUse matcher on Skill that runs hooks/{GATE_HOOK}"]


def hook_files() -> set[str]:
    """Hook file names in hooks/, ignoring caches and hidden files."""
    return {p.name for p in HOOKS_DIR.iterdir() if p.is_file() and not p.name.startswith(".")}


def find_problems() -> list[str]:
    """Return one message per inventory mismatch."""
    files = hook_files()
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    wired = wired_names(settings)
    doc = DOC.read_text(encoding="utf-8")
    problems = [f"settings.json references missing file: hooks/{n}" for n in sorted(wired - files)]
    problems += hooks_not_blocking(settings)
    problems += multiedit_matchers(settings)
    problems += skill_gate_missing(settings)
    for name in sorted(files - HELPERS):
        if name not in wired:
            problems.append(f"hooks/{name} is not wired in settings.json")
    for name in sorted(files):
        if name not in doc:
            problems.append(f"hooks/{name} is not mentioned in docs/hooks.md")
    return problems


def main() -> int:
    problems = find_problems()
    for message in problems:
        print(f"FAIL {message}")
    if not problems:
        print("PASS hook inventory: hooks/, settings.json and docs/hooks.md agree")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
