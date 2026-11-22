#!/usr/bin/env bash
# Trigger: UserPromptSubmit - all (no matcher)
# Scope: user prompts longer than 25 chars, excluding skill invocations (/command)
# Action: vector search vault, inject matching chunks as <vault_context> block
# On result: exit 0 always - never blocks; vault context injected via stdout
# PHI: excerpts with a finding at any level (deny, ask or warn, via scan_levels in
# phi_patterns.py) are withheld, never injected
# If filter: none - prompt content is not available at if-evaluation time
# Search: scripts/search/query_index.py. The index folder comes from the path loader (paths file or
# TOLLGATE_KNOWLEDGE), never a flag. The prompt goes in on stdin, so it never shows in the process
# list and a prompt that starts with dashes is not read as an option.
# Python: TOLLGATE_PYTHON when the installer set it (it has the search packages), else python3.

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$HOOKS_DIR/.." && pwd)"

QUERY_SCRIPT="${REPO_DIR}/scripts/search/query_index.py"
PYTHON="${TOLLGATE_PYTHON:-python3}"
MIN_SCORE="0.40"
TOP="3"
MIN_PROMPT_CHARS=25

# Bail early if env vars or files are missing - never block the prompt
if [ -z "${TOLLGATE_KNOWLEDGE:-}" ]; then
    exit 0
fi

if [ ! -f "$QUERY_SCRIPT" ]; then
    exit 0
fi

# Read JSON payload from Claude Code (fields: session_id, transcript_path, prompt)
INPUT=$(cat)
PROMPT=$(printf '%s' "$INPUT" | "$PYTHON" -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('prompt', ''))
except:
    print('')
" 2>/dev/null)

# Skip prompts that are too short to be meaningful
if [ "${#PROMPT}" -lt "$MIN_PROMPT_CHARS" ]; then
    exit 0
fi

# Skip skill invocations - /start, /ticket, /close, etc. manage their own context.
# First line only: a later line starting with a path must not skip the search.
if printf '%s\n' "$PROMPT" | head -n 1 | grep -qE '^\s*/[a-zA-Z]'; then
    exit 0
fi

# Run vector search
RESULTS=$(printf '%s' "$PROMPT" | "$PYTHON" "$QUERY_SCRIPT" --stdin \
    --top "$TOP" \
    --min-score "$MIN_SCORE" 2>/dev/null)

if [ -z "$RESULTS" ]; then
    exit 0
fi

# Validate JSON and count results via Python. grep-based '"error"' check is avoided because
# any vault document mentioning "error" (RCAs, error-handling notes) triggers a false positive.
RESULT_COUNT=$(printf '%s' "$RESULTS" | "$PYTHON" -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        print(0)
    else:
        print(len(data))
except Exception:
    print(0)
" 2>/dev/null)

if [ "${RESULT_COUNT:-0}" -eq 0 ]; then
    exit 0
fi

# Format results as a compact context block.
# [V] = VERIFIED (decisions, RCA), [D] = DOCUMENTED (tickets, system map), [O] = OBSERVED (meetings)
printf '%s' "$RESULTS" | "$PYTHON" -c "
import sys, json
sys.path.insert(0, sys.argv[1])
from phi_patterns import scan_levels

TIER_ICONS = {1: '[V]', 2: '[D]', 3: '[O]'}

try:
    results = json.load(sys.stdin)
    if not results:
        sys.exit(0)
    lines = ['<vault_context>']
    for r in results:
        icon = TIER_ICONS.get(r.get('tier', 2), '[D]')
        score = r.get('score', 0)
        file_ = r.get('file', '')
        heading = r.get('heading', '')
        excerpt = r.get('excerpt', '')[:200].strip()
        if scan_levels([excerpt, heading]):
            excerpt = '[excerpt withheld: PHI pattern detected in vault file, review and clean it]'
            heading = ''
        lines.append(f\"{icon} {score:.2f}  {file_}\" + (f\" - {heading}\" if heading else ''))
        lines.append(f\"  {excerpt}\")
        lines.append('')
    lines.append('</vault_context>')
    print('\n'.join(lines))
except Exception:
    sys.exit(0)
" "$HOOKS_DIR" 2>/dev/null

exit 0
