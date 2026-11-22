#!/usr/bin/env bash
# module_name: rebuild.sh
# description: Rebuild the search index. Incremental by default, --full re-embeds everything.
# author: Dipen Patel (dipenpatel-dev)
# date:
# version: 1.0.0
# change_log:
#   1.0.0: Ported. Folders come from the path loader. Python: TOLLGATE_PYTHON, else the state folder venv, else python3.
# usage: rebuild.sh [--full] [--source vault|tickets|references] [--embedder hash|local]
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDEX_DIR="$("$SCRIPT_DIR/../core/tg_path" index)" || { echo "not set up" >&2; exit 2; }
STATE_DIR="$("$SCRIPT_DIR/../core/tg_path" state)" || { echo "not set up" >&2; exit 2; }
if [ -n "${TOLLGATE_PYTHON:-}" ]; then PYTHON="$TOLLGATE_PYTHON"
elif [ -x "$STATE_DIR/venv/bin/python3" ]; then PYTHON="$STATE_DIR/venv/bin/python3"
else PYTHON="python3"; echo "rebuild: no venv found at $STATE_DIR/venv, using python3" >&2; fi
mkdir -p "$INDEX_DIR"
if [ ! -w "$INDEX_DIR" ]; then
    echo "Error: index folder is not writable" >&2
    exit 1
fi
exec "$PYTHON" "$SCRIPT_DIR/build_index.py" "$@"
