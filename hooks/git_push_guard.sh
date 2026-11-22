#!/usr/bin/env bash
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: PreToolUse Bash. Asks for approval before any git push, and denies a push
#        to a protected branch (TOLLGATE_PROTECTED_BRANCHES) unless
#        TOLLGATE_ALLOW_PROTECTED_PUSH is 1.
# Ticket: none (Tollgate is not Jira tracked)
# ChangeLog:
#   - Created. Ported from the dotfiles version; added the protected branch deny.
#
# Trigger: PreToolUse, Bash
# Action: prints an ask or deny decision as JSON; exit 2 on unreadable input.
# The helper ignores commands that are not git push.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/git_ask_before_run.py" push
