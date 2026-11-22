#!/usr/bin/env bash
# File: bootstrap-dev-2.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Launch the dev-2 worker session with its identity prompt injected.
# ChangeLog:
#   Initial port.

set -euo pipefail

exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_worker_common.sh" "dev-2" "dev"
