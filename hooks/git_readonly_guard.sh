#!/usr/bin/env bash
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: PreToolUse Bash. Denies the ways an auto-approved git status, log, diff, show or
#        config command can run a program or overwrite a file: git -c or --config-env,
#        git diff or log with --output or --ext-diff, and git config writes of keys that name
#        a program (core.fsmonitor, core.pager, core.sshCommand, diff.external, textconv, alias).
# Ticket: none (Tollgate is not Jira tracked)
# ChangeLog:
#   - Created. The allow list in settings.json now auto-approves only git status, log, diff and
#     read-only git config forms; this hook closes the option-based holes in those.
#
# Trigger: PreToolUse, Bash
# Action: prints a deny decision as JSON and exits 0; exits 2 when the payload cannot be read.
# Speed bump, not a sandbox: it reads the command text, so a script that runs git elsewhere is not seen.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/git_ask_before_run.py" readonly
