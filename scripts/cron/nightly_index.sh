#!/bin/bash
# Module:      nightly_index
# Description: Nightly vault maintenance: repo mirror, meeting sync, conversation sync,
#              wiki link lint, index snapshot, incremental index rebuild, dated index
#              backup, staleness report and a health file. Every step runs even when an
#              earlier one fails; each result is recorded and written to the health file.
#              It reads and writes only inside folders the path loader returns: the
#              vault, the repos folder, the state, cache, logs, output and index folders.
#              Optional inputs live in the state folder: repos.list (repos to mirror) and
#              meetings-source (a folder of exported meeting notes, one line).
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Scheduled by the cron setup script (see docs/scripts/cron.md)
# Usage:       nightly_index.sh [--dry-run] [--skip-index] [--notify]
#   --dry-run     print the steps and the folders it would write, run nothing
#   --skip-index  leave out the snapshot, rebuild and backup steps
#   --notify      show a desktop notification when a step failed
# ChangeLog:
#   Initial version

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "$HERE/.." && pwd)"
TG_PATH="$SCRIPTS/core/tg_path"

DRY=0; SKIP_INDEX=0; NOTIFY=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --skip-index) SKIP_INDEX=1 ;;
    --notify) NOTIFY=1 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

get() { "$TG_PATH" "$1" 2>/dev/null; }
VAULT="$(get vault)"   || { echo "not set up" >&2; exit 2; }
STATE="$(get state)"   || { echo "not set up" >&2; exit 2; }
LOGS="$(get logs)"     || { echo "not set up" >&2; exit 2; }
CACHE="$(get cache)"   || { echo "not set up" >&2; exit 2; }
OUTPUT="$(get output)" || { echo "not set up" >&2; exit 2; }
INDEX="$(get index)"   || { echo "not set up" >&2; exit 2; }

PYTHON_NOTE=""
if [ -n "${TOLLGATE_PYTHON:-}" ]; then PYTHON="$TOLLGATE_PYTHON"
elif [ -x "$STATE/venv/bin/python3" ]; then PYTHON="$STATE/venv/bin/python3"
else PYTHON="python3"; PYTHON_NOTE="no venv found at $STATE/venv, using python3"; fi
LOG_DIR="$LOGS/nightly"
LOG="$LOG_DIR/$(date '+%Y-%m-%d').log"

# A scheduled job has a short PATH; add the usual tool folders.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
# Never block on a credential prompt.
export GIT_TERMINAL_PROMPT=0

REPO_LIST="$STATE/repos.list"
MEETINGS_SOURCE_FILE="$STATE/meetings-source"
MEETINGS_SOURCE=""
[ -f "$MEETINGS_SOURCE_FILE" ] && MEETINGS_SOURCE="$(head -n 1 "$MEETINGS_SOURCE_FILE")"

if [ "$DRY" = "1" ]; then
  echo "nightly_index dry run. Nothing is run or written."
  echo "log file:      $LOG"
  echo "health file:   $STATE/nightly-health.json"
  echo "steps:"
  [ -f "$REPO_LIST" ] && echo "  sync_repos        (mirrors into $(get repos 2>/dev/null || echo 'the repos folder'))"
  [ -n "$MEETINGS_SOURCE" ] && echo "  sync_meetings     (into $(get meetings))"
  echo "  sync_conversations (into $(get conversations))"
  echo "  lint_wikilinks    (inside $VAULT)"
  if [ "$SKIP_INDEX" = "0" ]; then
    echo "  index_snapshot    (into $CACHE)"
    echo "  build_index       (into $INDEX)"
    echo "  backup_index      (into $OUTPUT)"
  fi
  echo "  vault_staleness   (report into $OUTPUT)"
  exit 0
fi

mkdir -p "$LOG_DIR" "$STATE"
echo "=== Nightly index, $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG"
[ -n "$PYTHON_NOTE" ] && echo "$PYTHON_NOTE" >> "$LOG"

# The scheduled job file holds the folder variables as they were when the job was set up. If the
# vault was moved since, stop with a clear message instead of failing step by step.
if [ ! -d "$VAULT" ]; then
  MSG="ABORT: the vault folder does not exist: $VAULT. If it moved, add a 'vault:' line to the paths file or run setup_cron.py again."
  echo "$MSG" >> "$LOG"
  echo "$MSG" >&2
  exit 1
fi

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ABORT: python not found ($PYTHON)" >> "$LOG"
  exit 1
fi

# No "set -e": every step must run even when one fails.
STEP_RESULTS=()

run_step() {
  local name="$1"; shift
  echo "Step [$name]: $(date '+%H:%M:%S')" >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local code=$?
  if [ $code -eq 0 ]; then STEP_RESULTS+=("$name:PASS"); else STEP_RESULTS+=("$name:FAIL:$code"); fi
  echo "" >> "$LOG"
}

run_step_with_retry() {
  local name="$1"; shift
  echo "Step [$name]: $(date '+%H:%M:%S')" >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local code=$?
  if [ $code -ne 0 ]; then
    echo "  failed (exit $code), retrying in 30s" >> "$LOG"
    sleep 30
    "$@" >> "$LOG" 2>&1
    code=$?
  fi
  if [ $code -eq 0 ]; then STEP_RESULTS+=("$name:PASS"); else STEP_RESULTS+=("$name:FAIL:$code"); fi
  echo "" >> "$LOG"
}

# Network steps may retry; local steps do not (a local failure is a real problem).
if [ -f "$REPO_LIST" ]; then
  run_step_with_retry sync_repos bash "$SCRIPTS/sync/sync_repos.sh" "$REPO_LIST"
fi
if [ -n "$MEETINGS_SOURCE" ]; then
  run_step_with_retry sync_meetings "$PYTHON" "$SCRIPTS/sync/sync_meetings.py" --source "$MEETINGS_SOURCE"
fi
run_step sync_conversations "$PYTHON" "$SCRIPTS/sync/sync_conversations.py"
run_step lint_wikilinks "$PYTHON" "$SCRIPTS/sync/lint_wikilinks.py"

if [ "$SKIP_INDEX" = "0" ]; then
  # Snapshot the last good index before the rebuild (inside the cache folder).
  SNAP="$CACHE/index-backup"
  echo "Snapshot: index -> cache/index-backup" >> "$LOG"
  rm -rf "${SNAP:?}"
  if [ -d "$INDEX" ]; then cp -R "$INDEX" "$SNAP" 2>> "$LOG"; fi
  if [ ! -d "$SNAP" ]; then echo "  note: no index to snapshot yet" >> "$LOG"; fi
  echo "" >> "$LOG"

  run_step build_index bash "$SCRIPTS/search/rebuild.sh"
  run_step backup_index bash "$SCRIPTS/state/backup_index.sh"
fi

run_step vault_staleness "$PYTHON" "$SCRIPTS/cron/vault_staleness.py" --report-only

HEALTH_ARGS=()
[ "$NOTIFY" = "1" ] && HEALTH_ARGS+=(--notify)
"$PYTHON" "$SCRIPTS/cron/write_nightly_health.py" ${HEALTH_ARGS[@]+"${HEALTH_ARGS[@]}"} "${STEP_RESULTS[@]}" 2>> "$LOG"
if [ $? -ne 0 ]; then
  echo "ERROR: write_nightly_health.py failed, the health file may be stale" >> "$LOG"
fi

echo "Done." >> "$LOG"
echo "" >> "$LOG"
exit 0
