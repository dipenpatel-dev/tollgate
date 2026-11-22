#!/usr/bin/env bash
# Module:      run.sh
# Description: Run the end to end tests. E2E-01 and E2E-02 first, then E2E-03: the hook tests and every
#              script suite together in one run.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Usage:       TOLLGATE_TEST_PYTHON=<python with chromadb> [TOLLGATE_REAL_VAULT=<real vault>] bash tests/system/run.sh
# Python 3.12 is the minimum: point TOLLGATE_TEST_PYTHON at a 3.12 or newer venv (pyyaml + scripts/requirements.txt).
set -u -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
fail=0

echo "== E2E-01 and E2E-02"
"${TOLLGATE_TEST_PYTHON:-python3}" -B -m unittest discover -s "$HERE" -p 'test_e2e.py' || fail=1

if [ "${1:-}" != "--quick" ]; then
  echo "== E2E-03 hook tests"
  "${TOLLGATE_TEST_PYTHON:-python3}" -B -m unittest discover -s "$REPO/tests/hooks" -p 'test_*.py' 2>&1 | tail -4 || fail=1
  echo "== E2E-03 script suites"
  for area in core search cache state sync cron chart qa validation connectors connectors/plane connectors/comms connectors/data; do
    out="$(bash "$REPO/tests/scripts/$area/run.sh" 2>&1)"; rc=$?
    printf '%s: %s\n' "$area" "$(printf '%s\n' "$out" | grep -E '^Ran |^OK|^FAILED' | tr '\n' ' ')"
    [ "$rc" -eq 0 ] || fail=1
  done
fi
[ "$fail" -eq 0 ] && echo "E2E: all passed" || echo "E2E: FAILED"
exit "$fail"
