#!/usr/bin/env bash
# Run the plane connector tests.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec "${TOLLGATE_TEST_PYTHON:-python3}" -B -m unittest discover -s "$DIR" -p 'test_*.py' -v
