#!/usr/bin/env bash
# Run the port tool. Usage: tools/port/run.sh SOURCE DEST [--dry-run] [--map F] [--denylist F]
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/env python3 "$here/port.py" "$@"
