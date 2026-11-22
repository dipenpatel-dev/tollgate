#!/usr/bin/env bash
# Run the leak scanner tests. To scan a repo instead:
#   tests/leak/run.sh scan <repo-folder> [--denylist FILE]
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "${1:-}" = "scan" ]; then
  shift
  exec python3 "$DIR/scan_leaks.py" "$@"
fi
exec python3 -m unittest discover -s "$DIR" -p 'test_*.py' -v
