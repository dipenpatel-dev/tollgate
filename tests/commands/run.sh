#!/usr/bin/env bash
# Run the command file tests (CMD-01 to CMD-05).
#   TOLLGATE_REQUIRE_SCRIPTS=1 bash tests/commands/run.sh   # scripts must exist
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -B -m unittest discover -s "$DIR" -p 'test_*.py' -v
