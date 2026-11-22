#!/usr/bin/env bash
# File: precompact_hook.sh
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: PreCompact helper. Prints a reminder to checkpoint before the context window is compressed.
# Not wired into settings.json by this package; a hook entry may call it.
# ChangeLog:
#   Initial port.

cat <<'EOF'
<precompact_warning>
CONTEXT WINDOW COMPRESSION IMMINENT.

Before compacting: run /save to checkpoint session state to the vault.
If /save is not possible: write a brief summary of:
  - What was decided this session
  - What work was done (files created or changed, commands run)
  - What is still pending

After /save or the summary: proceed with compaction.
</precompact_warning>
EOF

exit 0
