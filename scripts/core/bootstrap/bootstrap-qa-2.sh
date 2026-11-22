#!/usr/bin/env bash
# File: bootstrap-qa-2.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Launch the qa-2 worker session with its identity prompt injected.
# ChangeLog:
#   Initial port.

set -euo pipefail

exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_worker_common.sh" "qa-2" "qa"
