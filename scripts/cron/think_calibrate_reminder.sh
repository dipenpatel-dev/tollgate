#!/bin/bash
# Module:      think_calibrate_reminder
# Description: Weekly desktop reminder to run the think-calibrate command. macOS only
#              (uses osascript); on any other system it prints the text and exits 0.
#              It touches no files. Use --dry-run to print the notification text only.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# Usage:       think_calibrate_reminder.sh [--dry-run]
# ChangeLog:
#   Initial version

MESSAGE="Open Claude Code and run the think-calibrate command"
TITLE="Weekly thinking calibration"

if [ "$1" = "--dry-run" ] || ! command -v osascript >/dev/null 2>&1; then
  echo "$TITLE: $MESSAGE"
  exit 0
fi

osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\" sound name \"Ping\""
