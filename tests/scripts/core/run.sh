#!/usr/bin/env bash
# Run the scripts/core tests.
set -u
export PYTHONDONTWRITEBYTECODE=1
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${TOLLGATE_TEST_PYTHON:-python3}" -B -m unittest discover -s "$DIR" -p 'test_*.py' -v
