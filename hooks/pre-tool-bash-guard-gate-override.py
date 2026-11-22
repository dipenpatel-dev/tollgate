#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: Bash side of the gate override file guard
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Also catches names built from quotes, variables, command substitution, braces and globs, and
    python -c / node -e / perl -e bodies that mention the name and write.
  - Created.

Trigger: PreToolUse, Bash
Action: deny a Bash command whose text names a file matching *-gate-override.md (any letter
        case) together with a write verb or an output redirect. The owner creates those files
        from a terminal; the model must not. Reading one (cat, ls, grep, head) stays allowed.
Method: pattern check on the command text, not a sandbox. Write verbs: echo, printf, tee, cp, mv,
        dd, install, ln, touch, truncate, sed, awk, perl, ruby, node, python, python3, sh, bash,
        zsh, rm, cat with a redirect. Any `>` that is not a descriptor copy (2>&1) or a write to
        /dev/null counts as a redirect.
        A word that holds `gate-` and then a variable, command substitution, brace, or a glob that
        could match `override.md`, or quotes that join to the name (a-gate-"override".md), counts
        as the name when the command is write shaped. An inline interpreter body (python -c,
        node -e, perl -e, a heredoc) that mentions gate or override and writes is denied.
Limits (not caught): a glob that hides the `gate-` part (a-g*te-override.md), scripts that write
        the file internally, encoded names (base64, hex), names built by code in a script file.
Fails closed on unreadable input or an internal error: exit 2 blocks the command.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys

HOOK_EVENT = "PreToolUse"
NAME_RE = re.compile(r"-gate-override\.md", re.IGNORECASE)
WRITE_VERBS = {"echo", "printf", "tee", "cp", "mv", "dd", "install", "ln", "touch", "truncate",
               "sed", "awk", "perl", "ruby", "node", "python", "python3", "sh", "bash", "zsh",
               "rm", "rsync", "curl", "wget"}
SAFE_REDIRECTS_RE = re.compile(r"\d*>&\d+|&>\s*/dev/null|\d*>>?\s*/dev/null")
WORD_RE = re.compile(r"[A-Za-z0-9_]+")
GATE_WORD_RE = re.compile(r"[^\s;|&<>()]*gate-[^\s;|&<>()]*", re.IGNORECASE)
EXPANSION_CHARS = "$`{"
GLOB_CHARS = "*?["
TAIL_TARGET = "override.md"
INTERPRETER_RE = re.compile(r"\b(python[0-9.]*|node|nodejs|perl|ruby|php)\b", re.IGNORECASE)
INLINE_RE = re.compile(r"(?:^|\s)(?:-c|-e|-E|-p|-r|--eval)\b|<<")
INLINE_WRITE_RE = re.compile(
    r"open\s*\(|write|append|unlink|remove|rename|replace|shutil|copy|symlink|link|\bfs\b|touch|"
    r"truncate|rmtree|system|popen|subprocess|exec", re.IGNORECASE)
REASON = ("Bash write blocked: gate override files are created by the owner from a terminal, "
          "not by the model.")


def deny() -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": HOOK_EVENT, "permissionDecision": "deny",
                                             "permissionDecisionReason": REASON}}))
    sys.exit(0)


def dequote(text: str) -> str:
    """Drop quotes and backslashes the way the shell does when it joins a quoted word."""
    return re.sub(r"[\"'\\]", "", text)


def write_shaped(command: str) -> bool:
    stripped = SAFE_REDIRECTS_RE.sub(" ", command)
    if ">" in stripped:
        return True
    words = {w.lower() for w in WORD_RE.findall(stripped)}
    return bool(words & WRITE_VERBS)


def could_be_override_name(command: str) -> bool:
    """A word with `gate-` whose tail is a variable, substitution, brace or a glob matching override.md."""
    for word in GATE_WORD_RE.findall(command):
        tail = word.lower().split("gate-", 1)[1]
        if any(c in tail for c in EXPANSION_CHARS):
            return True
        if any(c in tail for c in GLOB_CHARS) and fnmatch.fnmatchcase(TAIL_TARGET, tail):
            return True
    return False


def inline_code_hits(command: str) -> bool:
    """An interpreter with inline code that mentions gate or override and writes."""
    if not (INTERPRETER_RE.search(command) and INLINE_RE.search(command)):
        return False
    lowered = command.lower()
    return ("gate" in lowered or "override" in lowered) and bool(INLINE_WRITE_RE.search(command))


def violates(command: str) -> bool:
    plain = dequote(command)
    named = bool(NAME_RE.search(command) or NAME_RE.search(plain))
    if named or could_be_override_name(command) or could_be_override_name(plain):
        return write_shaped(command)
    return inline_code_hits(command)


def main() -> None:
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("payload is not an object")
        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        if isinstance(command, str) and violates(command):
            deny()
    except SystemExit:
        raise
    except Exception as exc:  # fail closed: a hook that cannot decide must not let the command through
        sys.stderr.write("pre-tool-bash-guard-gate-override: %s; blocking (fails closed).\n" % type(exc).__name__)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
