#!/usr/bin/env bash
# Thin wrapper for scrub_secrets.py. Use it when a caller needs a shell entry point.
# Pins the registry to the folder this wrapper lives in.
here="$(cd "$(dirname "$0")" && pwd)"
export SCRUB_REGISTRY_PATH="${SCRUB_REGISTRY_PATH:-$here/secret_var_registry.txt}"
exec python3 "$here/scrub_secrets.py"
