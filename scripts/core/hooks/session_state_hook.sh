#!/usr/bin/env bash
# File: session_state_hook.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: PreCompact helper. Calls the session state writer named by TOLLGATE_SESSION_STATE_WRITER.
#        Always exits 0. Errors go to the log, never to the session.
# Not wired into settings.json by this package; a hook entry may call it.
# ChangeLog:
#   Initial port. The writer is now a setting, not a fixed path.

if [ -z "${TOLLGATE_HOME:-}" ]; then
    exit 0
fi

LOG_DIR="$("${TOLLGATE_HOME}/scripts/core/tg_path" logs 2>/dev/null)" || exit 0
mkdir -p "${LOG_DIR}" 2>/dev/null || exit 0

WRITER="${TOLLGATE_SESSION_STATE_WRITER:-}"
if [ -z "$WRITER" ] || [ ! -f "$WRITER" ]; then
    echo "session state writer not configured" >> "${LOG_DIR}/session_state_hook.log" 2>&1
    exit 0
fi

"${TOLLGATE_PYTHON:-python3}" "$WRITER" >> "${LOG_DIR}/session_state_hook.log" 2>&1

exit 0
