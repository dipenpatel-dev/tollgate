#!/usr/bin/env bash
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: PreToolUse Bash. Asks for approval before any git commit, showing the
#        command, the staged files and the draft message.
# Ticket: none (Tollgate is not Jira tracked)
# ChangeLog:
#   - Created. Ported from the dotfiles version; asks in every repo (the dotfiles
#     version limited it to one employer folder, which is not portable).
#
# Trigger: PreToolUse, Bash
# Action: prints an ask decision as JSON; exit 2 on unreadable input.
# The helper ignores commands that are not git commit.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/git_ask_before_run.py" commit
