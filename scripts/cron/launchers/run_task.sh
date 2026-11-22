#!/bin/bash
# Module:      run_task
# Description: Manual trigger for one sync or index job, with live output. The double click
#              launcher files in this folder call it. Every folder comes from the path loader
#              (through the scripts it runs), so a task writes only where a nightly run would.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# Usage:       run_task.sh conv|lint|meetings|repos|index|all [--dry-run]
#   conv      convert Claude session files into the conversations folder
#   lint      convert markdown links into wiki links in the vault
#   meetings  sync exported meeting notes (needs the meetings-source file in the state folder)
#   repos     mirror the repos in repos.list (state folder)
#   index     incremental index rebuild
#   all       conv, lint and index
# ChangeLog:
#   Initial version

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "$HERE/../.." && pwd)"
PYTHON="${TOLLGATE_PYTHON:-python3}"
TASK="${1:-all}"
DRY=0; [ "$2" = "--dry-run" ] && DRY=1

step() { echo ""; echo "== $1"; }
runit() { if [ "$DRY" = "1" ]; then echo "would run: $*"; else "$@"; fi; }

do_conv()     { step "Sync conversations"; runit "$PYTHON" "$SCRIPTS/sync/sync_conversations.py"; }
do_lint()     { step "Convert markdown links to wiki links"; runit "$PYTHON" "$SCRIPTS/sync/lint_wikilinks.py"; }
do_index()    { step "Rebuild the index"; runit bash "$SCRIPTS/search/rebuild.sh"; }
do_repos() {
    step "Mirror repos"
    STATE="$("$SCRIPTS/core/tg_path" state)" || { echo "not set up" >&2; return 2; }
    runit bash "$SCRIPTS/sync/sync_repos.sh" "$STATE/repos.list"
}
do_meetings() {
    step "Sync meeting notes"
    STATE="$("$SCRIPTS/core/tg_path" state)" || { echo "not set up" >&2; return 2; }
    if [ ! -f "$STATE/meetings-source" ]; then echo "not set up: no meetings-source file"; return 1; fi
    runit "$PYTHON" "$SCRIPTS/sync/sync_meetings.py" --source "$(head -n 1 "$STATE/meetings-source")"
}

case "$TASK" in
    conv) do_conv ;;
    lint) do_lint ;;
    meetings) do_meetings ;;
    repos) do_repos ;;
    index) do_index ;;
    all) do_conv; do_lint; do_index ;;
    *) echo "unknown task: $TASK" >&2; exit 2 ;;
esac
