#!/bin/bash
# Module:      backup_index
# Description: Snapshot the vector index to dated restore points.
#              Two tiers: context_cache.json (30 days) and the full index (7 days).
#              The context cache is the costly part to rebuild, so it has its own
#              backup track. Both folders come from the path loader: the index folder
#              is read, and snapshots are written under the output folder only.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# Usage:
#   backup_index.sh          create a snapshot of the current index
#   backup_index.sh --list   list the available restore points
# ChangeLog:
#   Initial version

set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TG_PATH="$HERE/../core/tg_path"
INDEX_DIR="$("$TG_PATH" index)" || { echo "not set up" >&2; exit 2; }
OUTPUT_DIR="$("$TG_PATH" output)" || { echo "not set up" >&2; exit 2; }
SNAPSHOTS="$OUTPUT_DIR/index-snapshots"
TODAY=$(date '+%Y-%m-%d')
CACHE_BACKUP_DIR="$SNAPSHOTS/cache"
FULL_BACKUP_DIR="$SNAPSHOTS/full"
KEEP_CACHE_DAYS=30
KEEP_FULL_DAYS=7

# ---- Mode: --list ----------------------------------------------------------

if [ "$1" = "--list" ]; then
    echo "=== Index restore points ==="
    echo ""
    echo "Full snapshots (last $KEEP_FULL_DAYS days):"
    found=0
    for d in "$FULL_BACKUP_DIR"/*/; do
        [ -d "$d" ] || continue
        found=1
        echo "  $(basename "$d")  ($(du -sh "$d" 2>/dev/null | cut -f1))"
    done
    [ "$found" = "0" ] && echo "  none"
    echo ""
    echo "Context cache backups (last $KEEP_CACHE_DAYS days):"
    found=0
    for f in "$CACHE_BACKUP_DIR"/*.json; do
        [ -f "$f" ] || continue
        found=1
        echo "  $(basename "$f")"
    done
    [ "$found" = "0" ] && echo "  none"
    echo ""
    echo "To restore: restore_index.sh YYYY-MM-DD"
    exit 0
fi

# ---- Validate the index exists ---------------------------------------------

if [ ! -d "$INDEX_DIR" ] || [ -z "$(find "$INDEX_DIR" -name chroma.sqlite3 2>/dev/null | head -1)" ]; then
    echo "ERROR: no index found, nothing to back up"
    exit 1
fi

mkdir -p "$CACHE_BACKUP_DIR" "$FULL_BACKUP_DIR"

echo "=== Index backup, $TODAY ==="

# ---- Tier 1: context_cache.json (lightweight, 30 day retention) ------------

CACHE_SRC="$INDEX_DIR/context_cache.json"
CACHE_DEST="$CACHE_BACKUP_DIR/$TODAY.json"
if [ -f "$CACHE_SRC" ]; then
    cp "$CACHE_SRC" "$CACHE_DEST"
    entries=$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$CACHE_DEST" 2>/dev/null || echo "?")
    size=$(du -sh "$CACHE_DEST" | cut -f1)
    echo "  OK    context_cache.json saved ($entries entries, $size)"
    find "$CACHE_BACKUP_DIR" -name "*.json" -mtime +$KEEP_CACHE_DAYS -delete
    remaining=$(ls "$CACHE_BACKUP_DIR" | wc -l | tr -d ' ')
    echo "        Retaining $remaining cache backups (${KEEP_CACHE_DAYS} day window)"
else
    echo "  WARN  context_cache.json not found, skipping cache backup"
fi

# ---- Tier 2: full index (heavy, 7 day retention) ---------------------------

FULL_DEST="$FULL_BACKUP_DIR/$TODAY"
if [ -d "$FULL_DEST" ]; then
    echo "  SKIP  Full snapshot for $TODAY already exists"
else
    echo "  Copying full index..."
    cp -R "$INDEX_DIR" "$FULL_DEST"
    size=$(du -sh "$FULL_DEST" | cut -f1)
    echo "  OK    Full snapshot saved ($size)"
    count=$(ls "$FULL_BACKUP_DIR" | wc -l | tr -d ' ')
    if [ "$count" -gt "$KEEP_FULL_DAYS" ]; then
        oldest=$(ls "$FULL_BACKUP_DIR" | sort | head -1)
        rm -rf "${FULL_BACKUP_DIR:?}/$oldest"
        echo "        Pruned oldest snapshot: $oldest ($((count - 1)) remain)"
    fi
fi

echo ""
echo "Restore points available:"
for d in "$FULL_BACKUP_DIR"/*/; do
    [ -d "$d" ] && echo "  $(basename "$d")"
done
exit 0
