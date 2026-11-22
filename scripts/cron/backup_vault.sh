#!/bin/bash
# Module:      backup_vault
# Description: Encrypted backup of the vault into the output folder (backups subfolder),
#              with an optional second copy to a folder you name. The archive is piped
#              straight into the encryption step, so no plain tarball lands on disk.
#              The key is read once from a command you give with --key-cmd (for example a
#              call to your own secret store) and handed to openssl through a file
#              descriptor. It is never exported, never written to disk, never printed.
#              Old backups rotate: 7 daily, 4 weekly, 12 monthly, in each folder.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Vault backup
# Version:     1.0
# Usage:       backup_vault.sh --key-cmd "COMMAND" [--copy-to DIR] [--dry-run]
#   --key-cmd   command that prints the key (required)
#   --copy-to   second folder, must already exist (a mounted drive, for example)
#   --dry-run   print what would be written, run nothing
# ChangeLog:
#   Initial version

set -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TG_PATH="$HERE/../core/tg_path"
PYTHON="${TOLLGATE_PYTHON:-python3}"

KEY_CMD=""; COPY_TO=""; DRY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --key-cmd) [ $# -ge 2 ] || { echo "backup_vault: missing value for --key-cmd" >&2; exit 2; }; KEY_CMD="$2"; shift 2 ;;
        --copy-to) [ $# -ge 2 ] || { echo "backup_vault: missing value for --copy-to" >&2; exit 2; }; COPY_TO="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        *) echo "backup_vault: unknown option: $1" >&2; exit 2 ;;
    esac
done

VAULT="$("$TG_PATH" vault)"   || { echo "not set up" >&2; exit 2; }
OUTPUT="$("$TG_PATH" output)" || { echo "not set up" >&2; exit 2; }
BACKUPS="$OUTPUT/backups"

PBKDF2_ITERS=600000
TODAY=$(date '+%Y-%m-%d')
BACKUP_FILENAME="vault-${TODAY}.enc"
ENC_TMP="$BACKUPS/.vault-enc-tmp-$$"
VAULT_PARENT="$(dirname "$VAULT")"
VAULT_BASENAME="$(basename "$VAULT")"

if [ "$DRY" = "1" ]; then
    echo "backup_vault dry run. Nothing is read or written."
    echo "would write: $BACKUPS/$BACKUP_FILENAME"
    [ -n "$COPY_TO" ] && echo "would copy to: $COPY_TO"
    exit 0
fi

if [ -z "$KEY_CMD" ]; then
    echo "backup_vault: ERROR: --key-cmd is required (a command that prints the key)" >&2
    exit 1
fi
if [ ! -d "$VAULT" ]; then
    echo "backup_vault: ERROR: vault folder not found" >&2
    exit 1
fi
if [ -n "$COPY_TO" ] && [ ! -d "$COPY_TO" ]; then
    # Never create the folder: an absent mount point would silently become a plain local
    # folder and the copy would never leave this machine.
    echo "backup_vault: ERROR: copy folder not found (is the drive mounted?)" >&2
    exit 1
fi

cleanup() {
    if [ -f "$ENC_TMP" ]; then
        rm -f "$ENC_TMP"
        echo "backup_vault: cleaned partial tmp on exit"
    fi
}
trap cleanup EXIT

# The key command must give a value; check without keeping it.
if [ -z "$(bash -c "$KEY_CMD" 2>/dev/null)" ]; then
    echo "backup_vault: ERROR: the key command gave no key" >&2
    exit 1
fi

mkdir -p "$BACKUPS"

# Key delivery via fd 3. Never export it.
exec 3< <(bash -c "$KEY_CMD" 2>/dev/null)

tar -czf - -C "$VAULT_PARENT" "$VAULT_BASENAME" \
    | openssl enc -aes-256-cbc -salt -pbkdf2 -iter "$PBKDF2_ITERS" \
        -pass fd:3 -out "$ENC_TMP"
PIPE_EXIT=$?
exec 3<&-

if [ $PIPE_EXIT -ne 0 ]; then
    echo "backup_vault: ERROR: encrypt pipe failed (exit $PIPE_EXIT)" >&2
    exit $PIPE_EXIT
fi

mv "$ENC_TMP" "$BACKUPS/$BACKUP_FILENAME"
echo "backup_vault: backup written: $BACKUP_FILENAME ($(du -sh "$BACKUPS/$BACKUP_FILENAME" | cut -f1))"

rotate_dir() {
    "$PYTHON" - "$1" "$2" <<'PYEOF'
import re
import sys
from datetime import date, timedelta
from pathlib import Path

DAILY_DAYS, WEEKLY_COUNT, MONTHLY_COUNT = 7, 4, 12
ENC_PAT = re.compile(r'^vault-(\d{4}-\d{2}-\d{2})\.enc$')

dirpath, today_str = sys.argv[1], sys.argv[2]
today = date.fromisoformat(today_str)
files = list(Path(dirpath).glob('vault-????-??-??.enc'))
dated = {}
for f in files:
    m = ENC_PAT.match(f.name)
    if m:
        try:
            dated[f.name] = date.fromisoformat(m.group(1))
        except ValueError:
            pass

daily_keep = {fn for fn, d in dated.items() if d >= today - timedelta(days=DAILY_DAYS - 1)}

def newest_per_bucket(key_fn, current, count):
    rep = {}
    for fn, d in dated.items():
        k = key_fn(d)
        if k == current:
            continue
        if k not in rep or d > rep[k][1]:
            rep[k] = (fn, d)
    return {rep[k][0] for k in sorted(rep, reverse=True)[:count]}

weekly_keep = newest_per_bucket(lambda d: d.strftime('%G-W%V'), today.strftime('%G-W%V'), WEEKLY_COUNT)
monthly_keep = newest_per_bucket(lambda d: d.strftime('%Y-%m'), today.strftime('%Y-%m'), MONTHLY_COUNT)
keep = daily_keep | weekly_keep | monthly_keep
for f in files:
    if f.name not in keep:
        f.unlink()
        print("backup_vault: rotated: " + f.name)
PYEOF
}

rotate_dir "$BACKUPS" "$TODAY"
echo "backup_vault: local rotation complete"

if [ -n "$COPY_TO" ]; then
    if ! cp "$BACKUPS/$BACKUP_FILENAME" "$COPY_TO/"; then
        echo "backup_vault: copy failed; local backup is current, copy folder not rotated" >&2
        exit 1
    fi
    echo "backup_vault: copy succeeded: $BACKUP_FILENAME"
    rotate_dir "$COPY_TO" "$TODAY"
    echo "backup_vault: copy rotation complete"
fi
exit 0
