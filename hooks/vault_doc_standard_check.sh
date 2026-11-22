#!/usr/bin/env bash
# Trigger: PostToolUse -- Write|Edit
# Scope: .md files inside the vault folder (TOLLGATE_KNOWLEDGE); with the variable unset it does nothing
# Action: after a write, check the file for the vault doc standard frontmatter
# On result: prints additionalContext when frontmatter is missing or incomplete; never blocks
# Required fields: doc_type (underscore value), status (ALL_CAPS), date, last_updated, tags, links
#
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# ChangeLog:
#   - Created. Reads the payload with python3 instead of jq so no extra tool is needed.

VAULT="${TOLLGATE_KNOWLEDGE:-}"
[[ -z "$VAULT" ]] && exit 0

input=$(cat)
FILE=$(python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('tool_input', {}).get('file_path', '') or '')
except Exception:
    print('')
" <<< "$input" 2>/dev/null || true)

[[ -z "$FILE" ]] && exit 0
[[ "$FILE" != *.md ]] && exit 0
[[ ! -f "$FILE" ]] && exit 0

VAULT_REAL=$(cd "$VAULT" 2>/dev/null && pwd -P) || exit 0
FILE_DIR=$(cd "$(dirname "$FILE")" 2>/dev/null && pwd -P) || exit 0
case "$FILE_DIR/" in
  "$VAULT_REAL"/*) ;;
  *) exit 0 ;;
esac

emit() {
  python3 -c "
import json, sys
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': sys.argv[1]}}))
" "$1"
}

NAME=$(basename "$FILE")
FIRST_LINE=$(head -1 "$FILE" 2>/dev/null)
if [[ "$FIRST_LINE" != "---" ]]; then
  emit "VAULT DOC STANDARD: $NAME has no YAML frontmatter. Add: doc_type (underscore_value), status (ALL_CAPS), date (YYYY-MM-DD), last_updated (YYYY-MM-DD), tags ([underscore_list]), links ([\"[[wiki_link]]\"])."
  exit 0
fi

FRONTMATTER=$(awk '/^---/{c++; if(c==2) exit; next} c==1{print}' "$FILE" | head -30)
MISSING=""
for field in doc_type status date last_updated tags links; do
  echo "$FRONTMATTER" | grep -q "^${field}:" || MISSING="$MISSING $field"
done

if [[ -n "$MISSING" ]]; then
  emit "VAULT DOC STANDARD: $NAME frontmatter missing:$MISSING. Required: doc_type=underscore, status=ALL_CAPS, date, last_updated, tags=underscore list, links=wiki links."
fi
exit 0
