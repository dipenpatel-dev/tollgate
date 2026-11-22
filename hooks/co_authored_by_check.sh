#!/usr/bin/env bash
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: PreToolUse Bash. Blocks a git commit whose command text holds a
#        Co-Authored-By line, so no AI attribution reaches a commit.
# Ticket: none (Tollgate is not Jira tracked)
# ChangeLog:
#   - Fails closed (exit 2) when the payload cannot be parsed.
#   - Created. Ported from the dotfiles version; now returns a JSON deny on
#     stdout with exit 0, and the match ignores letter case.
#
# Trigger: PreToolUse, Bash
# Action: deny when a git commit command contains Co-Authored-By; allow otherwise.
# On result: the model removes the line and retries.

set -uo pipefail

input=$(cat)

cmd=$(python3 -c "
import sys, json
d = json.load(sys.stdin)
if not isinstance(d, dict):
    raise ValueError('payload is not an object')
ti = d.get('tool_input') or {}
c = ti.get('command') if isinstance(ti, dict) else None
print(c if isinstance(c, str) else '')
" <<< "$input" 2>/dev/null) || {
    printf '\nBLOCKED: co_authored_by_check could not read the tool payload, so the command is blocked.\n\n' >&2
    exit 2
}

# Only examine git commit commands
# (any `git` word followed later by `commit`, so -c options, env prefixes, sh -c strings and a path
# to git do not hide it)
if ! printf '%s' "$cmd" | grep -qE '(^|[^A-Za-z0-9_-])git([[:space:]]|$).*commit'; then
    exit 0
fi

if printf '%s' "$cmd" | grep -qi 'Co-Authored-By'; then
    printf '\nBLOCKED: Remove Co-Authored-By before committing.\nRule: no AI attribution in any repo.\n\n' >&2
    python3 -c "
import json
print(json.dumps({'hookSpecificOutput': {
    'hookEventName': 'PreToolUse',
    'permissionDecision': 'deny',
    'permissionDecisionReason': 'Remove the Co-Authored-By line from the commit message and retry. Rule: no AI attribution in any repo.'
}}))
"
    exit 0
fi

exit 0
