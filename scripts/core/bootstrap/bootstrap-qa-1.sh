#!/usr/bin/env bash
# File: bootstrap-qa-1.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Launch the qa-1 worker session with its identity prompt injected.
# ChangeLog:
#   Initial port.

set -euo pipefail

exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_worker_common.sh" "qa-1" "qa"
