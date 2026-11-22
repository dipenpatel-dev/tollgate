#!/bin/bash
# Module:      restore_index
# Description: Restore the vector index from a dated snapshot. With no date it lists the
#              restore points. A full restore overwrites the index folder, so it asks for
#              a yes first (or takes --yes) and keeps a copy of the current index.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# Usage:
#   restore_index.sh                       list available restore points
#   restore_index.sh YYYY-MM-DD [--yes]    restore the full index from that date
#   restore_index.sh cache YYYY-MM-DD      restore only context_cache.json
# ChangeLog:
#   Initial version

set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TG_PATH="$HERE/../core/tg_path"
INDEX_DIR="$("$TG_PATH" index)" || { echo "not set up" >&2; exit 2; }
OUTPUT_DIR="$("$TG_PATH" output)" || { echo "not set up" >&2; exit 2; }
SNAPSHOTS="$OUTPUT_DIR/index-snapshots"
FULL_BACKUP_DIR="$SNAPSHOTS/full"
CACHE_BACKUP_DIR="$SNAPSHOTS/cache"

YES=0
ARGS=()
for a in "$@"; do
    if [ "$a" = "--yes" ]; then YES=1; else ARGS+=("$a"); fi
done
set -- ${ARGS[@]+"${ARGS[@]}"}

# ---- Mode: list ------------------------------------------------------------

if [ -z "$1" ] || [ "$1" = "--list" ]; then
    "$HERE/backup_index.sh" --list
    exit 0
fi

# ---- Mode: restore cache only ----------------------------------------------

if [ "$1" = "cache" ]; then
    DATE="$2"
    if [ -z "$DATE" ]; then
        echo "Usage: restore_index.sh cache YYYY-MM-DD"
        exit 1
    fi
    CACHE_SRC="$CACHE_BACKUP_DIR/$DATE.json"
    if [ ! -f "$CACHE_SRC" ]; then
        echo "ERROR: No cache backup found for $DATE"
        exit 1
    fi
    mkdir -p "$INDEX_DIR"
    cp "$CACHE_SRC" "$INDEX_DIR/context_cache.json"
    echo "OK, context_cache.json restored from $DATE"
    exit 0
fi

# ---- Mode: restore full index ----------------------------------------------

DATE="$1"
SNAPSHOT="$FULL_BACKUP_DIR/$DATE"

if [ ! -d "$SNAPSHOT" ]; then
    echo "ERROR: No full snapshot found for $DATE"
    exit 1
fi

echo "=== Restore index from $DATE ==="
echo "This overwrites the current index folder."

if [ "$YES" != "1" ]; then
    read -r -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 1
    fi
fi

CURRENT_BACKUP="$FULL_BACKUP_DIR/pre-restore-$(date '+%Y-%m-%d-%H%M%S')"
if [ -d "$INDEX_DIR" ]; then
    echo "Keeping a copy of the current index first..."
    cp -R "$INDEX_DIR" "$CURRENT_BACKUP"
    rm -rf "$INDEX_DIR"
fi

echo "Restoring..."
cp -R "$SNAPSHOT" "$INDEX_DIR"

size=$(du -sh "$INDEX_DIR" | cut -f1)
echo "OK, index restored from $DATE ($size)"
exit 0
