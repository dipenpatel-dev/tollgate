#!/usr/bin/env bash
# File: _worker_common.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Shared launcher for worker sessions. Called by the bootstrap-* wrappers.
# ChangeLog:
#   Initial port.

set -euo pipefail

# Usage: _worker_common.sh <worker-name> <worker-type>
# Needs TOLLGATE_HOME. Identity templates come from TOLLGATE_WORKER_TEMPLATES
# when set, else from the templates folder inside TOLLGATE_HOME.
# Writes the identity file and the registry record under the state path.

WORKER_NAME="${1:?worker name required}"
WORKER_TYPE="${2:?worker type required}"

if [ -z "${TOLLGATE_HOME:-}" ]; then
    echo "not set up: TOLLGATE_HOME is not set" >&2
    exit 1
fi

TG_PATH="${TOLLGATE_HOME}/scripts/core/tg_path"
STATE_DIR="$("$TG_PATH" state)" || { echo "not set up" >&2; exit 1; }

TEMPLATE_DIR="${TOLLGATE_WORKER_TEMPLATES:-${TOLLGATE_HOME}/templates/workers}"
IDENTITY_DIR="${STATE_DIR}/workers"
REGISTRY_DIR="${STATE_DIR}/worker-registry"
TEMPLATE="${TEMPLATE_DIR}/${WORKER_TYPE}-identity-template.md"
IDENTITY_FILE="${IDENTITY_DIR}/${WORKER_NAME}-identity.md"

if [ ! -f "$TEMPLATE" ]; then
    echo "identity template not found for worker type: ${WORKER_TYPE}" >&2
    exit 1
fi

# 1. Terminal title
printf '\033]0;%s\007' "${WORKER_NAME}"

# 2. Generate the identity file from the type template
mkdir -p "${IDENTITY_DIR}"
sed "s/{{WORKER_NAME}}/${WORKER_NAME}/g" "${TEMPLATE}" > "${IDENTITY_FILE}"

# 3. Initial registry record (the dispatch operator keeps none)
if [ "${WORKER_TYPE}" != "dispatch" ]; then
    mkdir -p "${REGISTRY_DIR}"
    REGISTRY_FILE="${REGISTRY_DIR}/${WORKER_NAME}.json"
    TMP_FILE="${REGISTRY_FILE}.tmp"
    cat > "${TMP_FILE}" << REC
{
  "worker_name": "${WORKER_NAME}",
  "type": "${WORKER_TYPE}",
  "status": "available",
  "current_ticket": null,
  "worktree_path": "",
  "last_updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "assigned_at": null,
  "session_id": ""
}
REC
    mv "${TMP_FILE}" "${REGISTRY_FILE}"
fi

# 4. Launch Claude with the appended identity
export TOLLGATE_WORKER_ID="${WORKER_NAME}"
exec claude --append-system-prompt-file "${IDENTITY_FILE}"
