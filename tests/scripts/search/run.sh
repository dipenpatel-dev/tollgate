#!/usr/bin/env bash
# Run the tests in this folder.
# The search scripts need chromadb and PyYAML. Point TOLLGATE_TEST_PYTHON at a python that has them
# (read only use). Without it the tests fall back to python3 and skip when chromadb is missing.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
export TOLLGATE_EMBEDDER=hash
exec "${TOLLGATE_TEST_PYTHON:-python3}" -B -m unittest discover -s "$DIR" -p 'test_*.py' -v
