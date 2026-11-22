#!/usr/bin/env bash
# File: bootstrap-dispatch.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Launch the dispatch worker session with its identity prompt injected.
# ChangeLog:
#   Initial port.

set -euo pipefail

exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_worker_common.sh" "dispatch" "dispatch"
