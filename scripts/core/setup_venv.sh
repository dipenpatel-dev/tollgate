#!/usr/bin/env bash
# File: setup_venv.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Create a Python venv for the scripts and install requirements.txt.
# Usage: setup_venv.sh [--force] [--venv DIR]
#   --force    delete and recreate the venv
#   --venv DIR where to make it (default: the venv folder inside the state path)
#   TOLLGATE_BASE_PYTHON picks the interpreter (default python3). It must be 3.12 or newer.
# ChangeLog:
#   Initial port. Version pin and personal interpreter path removed.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ="$(cd "$HERE/.." && pwd)/requirements.txt"
BASE_PY="${TOLLGATE_BASE_PYTHON:-python3}"
FORCE=0
VENV=""

while [ $# -gt 0 ]; do
    case "$1" in
        --force) FORCE=1 ;;
        --venv) shift; VENV="${1:?--venv needs a folder}" ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ -z "$VENV" ]; then
    STATE="$("$HERE/tg_path" state)" || { echo "not set up" >&2; exit 1; }
    VENV="${STATE}/venv"
fi

if ! command -v "$BASE_PY" >/dev/null 2>&1; then
    echo "python not found: $BASE_PY" >&2
    exit 1
fi

if ! "$BASE_PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
    _found="$("$BASE_PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)" || _found=""
    echo "Tollgate needs Python 3.12 or newer, found ${_found:-no working python} in $BASE_PY" >&2
    exit 1
fi

if [ "$FORCE" = "1" ]; then
    rm -rf "$VENV"
fi

if [ ! -d "$VENV" ]; then
    echo "creating venv"
    "$BASE_PY" -m venv "$VENV"
fi

echo "installing requirements"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$REQ"

echo "venv ready"
"$VENV/bin/python3" --version
