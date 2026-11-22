#!/usr/bin/env bash
# File: run.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Manual trigger for the sync and index jobs, with live output.
# Usage:
#   run.sh [all|sweep|index|lint]
#   sweep  flush staging into the vault (scripts/sync/sweep)
#   index  rebuild the search index (scripts/search/build_index.py)
#   lint   convert markdown links to wiki links (scripts/sync/lint_wikilinks.py)
# Connector jobs (chat pulls, meeting pulls, schema pulls) plug in through the
# connectors folder and are not run from here.
# ChangeLog:
#   Initial port. Connector jobs removed; each job is skipped when its script is absent.

set -u

if [ -z "${TOLLGATE_HOME:-}" ]; then
    echo "not set up: TOLLGATE_HOME is not set" >&2
    exit 1
fi

SCRIPTS="${TOLLGATE_HOME}/scripts"
PYTHON="${TOLLGATE_PYTHON:-python3}"
FAILED=0

step() { printf '\n> %s\n' "$1"; }
ok() { printf '  ok: %s\n' "$1"; }
fail() { printf '  failed: %s\n' "$1"; FAILED=1; }
skip() { printf '  skipped: %s is not installed\n' "$1"; }

run_py() {
    local label="$1" script="$2"
    shift 2
    if [ ! -f "$script" ]; then skip "$label"; return; fi
    step "$label"
    "$PYTHON" "$script" "$@" && ok "done" || fail "$label"
}

run_sweep() {
    local script="${SCRIPTS}/sync/sweep"
    if [ ! -x "$script" ]; then skip "sweep"; return; fi
    step "Flush staging to the vault"
    "$script" && ok "done" || fail "sweep"
}

run_index() { run_py "Rebuild search index" "${SCRIPTS}/search/build_index.py"; }
run_lint() { run_py "Convert links to wiki links" "${SCRIPTS}/sync/lint_wikilinks.py"; }

case "${1:-all}" in
    all)   run_sweep; run_lint; run_index ;;
    sweep) run_sweep ;;
    index) run_index ;;
    lint)  run_lint ;;
    *)
        echo "Usage: $0 [all|sweep|index|lint]" >&2
        exit 2
        ;;
esac

exit "$FAILED"
