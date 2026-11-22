#!/bin/bash
# Module:      sync_repos
# Description: Pull the default branch of each repository named in a list file into the
#              repos folder (a read only mirror: AI reads from it, nobody edits it).
#              The list file has one repository per line: a git address, optionally
#              preceded by a folder name and a space. Lines starting with # are skipped.
#              The default list is repos.list in the state folder. The repos folder comes
#              from the path loader. A local path or a file address works as an address.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# Usage:       sync_repos.sh [LIST_FILE]
# ChangeLog:
#   Initial version

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TG_PATH="$HERE/../core/tg_path"
REPOS_DIR="$("$TG_PATH" repos)" || { echo "not set up" >&2; exit 2; }
STATE_DIR="$("$TG_PATH" state)" || { echo "not set up" >&2; exit 2; }
LIST="${1:-$STATE_DIR/repos.list}"

# Never block on a credential prompt; fail fast instead.
export GIT_TERMINAL_PROMPT=0

if [ ! -f "$LIST" ]; then
  echo "no repo list at the expected place, nothing to sync"
  exit 0
fi

FAILED=()
mkdir -p "$REPOS_DIR"

echo "================================================"
echo "Repo sync, $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================"

while IFS= read -r LINE || [ -n "$LINE" ]; do
  case "$LINE" in ''|'#'*) continue ;; esac
  set -- $LINE
  if [ "$#" -ge 2 ]; then NAME="$1"; URL="$2"; else URL="$1"; NAME="$(basename "${URL%.git}")"; fi
  DEST="$REPOS_DIR/$NAME"
  echo ""
  echo "-- $NAME"

  if [ ! -d "$DEST/.git" ]; then
    if git clone "$URL" "$DEST" --quiet 2>/dev/null; then
      echo "   Cloned."
    else
      echo "   ERROR: clone failed, skipping."
      FAILED+=("$NAME (clone)")
    fi
    continue
  fi

  # Default branch from local git metadata (no network call)
  BRANCH=$(git -C "$DEST" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
  [ -z "$BRANCH" ] && BRANCH="main"

  if ! git -C "$DEST" fetch origin "$BRANCH" --quiet 2>/dev/null; then
    echo "   ERROR: fetch failed, skipping."
    FAILED+=("$NAME (fetch)")
    continue
  fi

  LOCAL=$(git -C "$DEST" rev-parse HEAD)
  REMOTE=$(git -C "$DEST" rev-parse "origin/$BRANCH")
  if [ "$LOCAL" = "$REMOTE" ]; then
    echo "   Up to date."
  else
    COUNT=$(git -C "$DEST" rev-list "HEAD..origin/$BRANCH" --count)
    if ! git -C "$DEST" reset --hard "origin/$BRANCH" --quiet 2>/dev/null; then
      echo "   ERROR: reset failed, skipping."
      FAILED+=("$NAME (reset)")
      continue
    fi
    echo "   Pulled $COUNT new commit(s)."
  fi
done < "$LIST"

echo ""
echo "================================================"
echo "Done. The repos folder is a read only mirror, do not edit files in it."
echo "================================================"

if [ ${#FAILED[@]} -gt 0 ]; then
  echo ""
  echo "SYNC FAILURES (${#FAILED[@]}):"
  for F in "${FAILED[@]}"; do
    echo "  FAILED $F"
  done
  exit 1
fi
exit 0
