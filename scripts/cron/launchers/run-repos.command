#!/bin/bash
# Double click launcher: runs the "repos" task and waits for a key.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
HERE="$(cd "$(dirname "$0")" && pwd)"
"$HERE/run_task.sh" repos
echo ""
echo "Press any key to close..."
read -r -n 1
