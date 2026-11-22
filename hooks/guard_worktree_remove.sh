#!/usr/bin/env bash
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: PreToolUse Bash. Blocks `git worktree remove` when the branch checked out
#        in that worktree is not merged into a base branch.
# Ticket: none (Tollgate is not Jira tracked)
# ChangeLog:
#   - Fails closed (exit 2) when the payload cannot be parsed.
#   - Created. Ported from the dotfiles version; the base branch is the first
#     existing name in TOLLGATE_PROTECTED_BRANCHES (default "main master").
#
# Trigger: PreToolUse, Bash
# Action: JSON permissionDecision deny on stdout, exit 0, to block; no output to allow.

set -uo pipefail

input=$(cat)

command=$(printf '%s' "$input" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if not isinstance(d, dict):
    raise ValueError('payload is not an object')
ti = d.get('tool_input') or {}
c = ti.get('command') if isinstance(ti, dict) else None
print(c if isinstance(c, str) else '')
" 2>/dev/null) || {
    printf '\nBLOCKED: guard_worktree_remove could not read the tool payload, so the command is blocked.\n\n' >&2
    exit 2
}

# Only act on git worktree remove commands
if ! printf '%s' "$command" | grep -qE 'git[[:space:]].*worktree[[:space:]]+remove'; then
    exit 0
fi

# Worktree path: last token that starts with / or ~
worktree_path=$(printf '%s' "$command" | grep -oE '(~|/)[^[:space:]]+' | tail -1)
[ -z "$worktree_path" ] && exit 0
worktree_path="${worktree_path/#\~/$HOME}"

# Path missing: allow, git will report its own error
[ -d "$worktree_path" ] || exit 0

branch=$(git -C "$worktree_path" branch --show-current 2>/dev/null || true)
# Detached HEAD: no branch to protect
[ -z "$branch" ] && exit 0

repo_root=$(git -C "$worktree_path" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's|/\.git$||' || true)
[ -z "$repo_root" ] && repo_root="$worktree_path"

# Base branch: first existing name in the protected list
bases="${TOLLGATE_PROTECTED_BRANCHES:-main master}"
bases="${bases//,/ }"
base=""
for candidate in $bases; do
    if git -C "$repo_root" rev-parse --verify --quiet "refs/heads/$candidate" >/dev/null 2>&1; then
        base="$candidate"
        break
    fi
done
# No base branch found: nothing to compare against, allow
[ -z "$base" ] && exit 0

# The base branch itself is never "unmerged"
[ "$branch" = "$base" ] && exit 0

if git -C "$repo_root" merge-base --is-ancestor "$branch" "$base" 2>/dev/null; then
    exit 0
fi

printf '\nBLOCKED: worktree remove prevented.\nBranch "%s" in "%s" has not been merged to %s.\nVerify the merge commit exists on %s before removing the worktree.\n\n' \
    "$branch" "$worktree_path" "$base" "$base" >&2

python3 -c "
import json, sys
msg = 'Branch {} not merged to {} in {}'.format(sys.argv[1], sys.argv[2], sys.argv[3])
print(json.dumps({'hookSpecificOutput': {
    'hookEventName': 'PreToolUse',
    'permissionDecision': 'deny',
    'permissionDecisionReason': msg
}}))
" "$branch" "$base" "$worktree_path"
exit 0
