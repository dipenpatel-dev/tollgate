#!/usr/bin/env bash
# Trigger: PreToolUse - Write|Edit|NotebookEdit
# Scope: file_path in Write/Edit/NotebookEdit tool_input; checks against TOLLGATE_CODE_DIR
# Action: block writes to the read-only code reference directory, and block any model write to a
#         file named *-gate-override.md (the owner creates those from a terminal), and block writes to
#         Tollgate's own files (hooks, settings, credentials, ~/.tollgate, shell profiles)
# Bash commands are covered by pre-tool-bash-guard-code-dir.py (separate hook entry).
# On block: prints JSON with hookEventName + permissionDecision:deny + permissionDecisionReason, then exit 0
# If filter: none - Write|Edit|NotebookEdit matcher limits scope; path check is O(1)

# Read full stdin payload; parse file_path with Python to handle JSON safely
PAYLOAD=$(cat)

# Fail closed: a payload that cannot be read blocks the write (exit 2).
FILE_PATH=$(echo "$PAYLOAD" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if not isinstance(data, dict):
    raise ValueError('payload is not an object')
tool_input = data.get('tool_input') or {}
if not isinstance(tool_input, dict):
    tool_input = {}
value = tool_input.get('file_path') or tool_input.get('notebook_path') or ''
print(value if isinstance(value, str) else '')
" 2>/dev/null) || {
    printf '\nBLOCKED: pre-tool-write-guard-path could not read the tool payload, so the write is blocked.\n\n' >&2
    exit 2
}

# Gate override files (*-gate-override.md) are created by the owner from a terminal, never by the
# model. Checked first so it holds even when TOLLGATE_CODE_DIR is unset. Compared lower case (case
# insensitive file systems) on both the typed name and the symlink resolved name.
if [ -n "$FILE_PATH" ]; then
    TYPED_NAME="$(basename "$FILE_PATH" | tr '[:upper:]' '[:lower:]')"
    REAL_NAME="$(python3 -c "import os,sys; print(os.path.basename(os.path.realpath(sys.argv[1])).lower())" "$FILE_PATH" 2>/dev/null || echo "")"
    case "$TYPED_NAME:$REAL_NAME" in
        *-gate-override.md:*|*:*-gate-override.md)
            python3 -c "
import json
result = {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': 'Write blocked: gate override files are created by the owner from a terminal, not by the model.'
    }
}
print(json.dumps(result))
"
            exit 0
            ;;
    esac
fi

# Tollgate's own files (hooks, settings, credentials, ~/.tollgate, shell profiles) are never written
# by the model. The list lives in lib/protected_paths.py. Exit 10 = protected, 0 = fine, anything else
# (crash, missing file) blocks, so this check fails closed.
if [ -n "$FILE_PATH" ]; then
    GUARD_DIR="$(dirname "$0")"
    python3 "$GUARD_DIR/lib/protected_paths.py" "$FILE_PATH" 2>/dev/null
    case "$?" in
        0) ;;
        10)
            python3 -c "
import json
result = {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': 'Write blocked: this is one of Tollgate own files (hooks, settings, credentials, ~/.tollgate or a shell profile). The owner edits these from a terminal, not the model.'
    }
}
print(json.dumps(result))
"
            exit 0
            ;;
        *)
            printf '\nBLOCKED: pre-tool-write-guard-path could not check the protected file list, so the write is blocked.\n\n' >&2
            exit 2
            ;;
    esac
fi

# Code dir guard is inactive if TOLLGATE_CODE_DIR is not configured. Say so visibly (systemMessage
# shown to the user, same text on stderr for logs) but never block: an unset variable must not stop
# real work.
if [ -z "${TOLLGATE_CODE_DIR:-}" ]; then
    WARN="WARNING: TOLLGATE_CODE_DIR is not set, so the read-only code directory guard is NOT active. Set it in your shell profile to protect the code mirror."
    echo "$WARN" >&2
    python3 -c "import json,sys; print(json.dumps({'systemMessage': sys.argv[1]}))" "$WARN"
    exit 0
fi

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Normalize paths with symlink resolution. Both sides use realpath for consistent comparison;
# Python os.path.realpath handles non-existent paths on macOS where GNU realpath -m is unavailable.
CODE_DIR_NORM="$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$TOLLGATE_CODE_DIR" 2>/dev/null || echo "$TOLLGATE_CODE_DIR")"
FILE_PATH_NORM="$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")"

# Add trailing slash to CODE_DIR to prevent prefix false-positives (e.g. /code vs /codebackup)
CODE_DIR_PREFIX="${CODE_DIR_NORM%/}/"

if [[ "$FILE_PATH_NORM/" == "$CODE_DIR_PREFIX"* ]] || [[ "$FILE_PATH_NORM" == "$CODE_DIR_NORM" ]]; then
    python3 -c "
import json
result = {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': 'Write blocked: target path is under TOLLGATE_CODE_DIR (read-only search source). Work in your dev directory instead.'
    }
}
print(json.dumps(result))
"
fi

exit 0
