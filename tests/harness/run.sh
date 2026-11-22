#!/usr/bin/env bash
# Run the harness tests.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -m unittest discover -s "$DIR" -p 'test_*.py' -v
