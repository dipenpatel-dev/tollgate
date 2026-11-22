#!/usr/bin/env bash
# install.sh — One-button setup for Tollgate
# Run once after cloning. Safe to re-run: backs up files, skips already-done steps.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
MIN_CLAUDE_VERSION="2.1.295"   # first Claude Code with the hook field onFailure: "block"
TG_STATE_DIR="$CLAUDE_DIR/tollgate"
MANIFEST="$TG_STATE_DIR/manifest.json"
INSTALLED_VERSION_FILE="$TG_STATE_DIR/installed-version"
KEEP_BACKUPS=3
CREDS_SCRIPT="$CLAUDE_DIR/credentials.sh"
KC_PREFIX="tollgate"
OS="$(uname -s)"   # Darwin | Linux | MINGW* | CYGWIN*

# ── Non-interactive mode (automated tests, CI) ────────────────────────────────
# ./install.sh --non-interactive   or   TOLLGATE_NONINTERACTIVE=1 ./install.sh
# Every prompt takes its default. Service connections are skipped. An existing
# setup is always migrated, never cleaned, so ~/.claude is never wiped unattended.
# ./install.sh --dry-run   prints every action that would change disk, runs none.
# Answers can be given as flags, so no question is asked for them:
#   --vault PATH   --initials AB   --ticket-prefix T   --name "Full Name"
#   --vault-git none|local|remote   (or env TOLLGATE_VAULT_GIT)  how the vault is saved
# ./install.sh --restore-settings   puts the newest settings.json backup back.
# ./install.sh --uninstall   removes only what Tollgate installed (see the manifest below).
# ./install.sh --with-venv / --skip-venv   build (or never build) the Python venv and search index.
# ./install.sh --with-cron   schedule the nightly search-index job (macOS launchd).
# ./install.sh --strict   stop, instead of warning, when Claude Code is older than the minimum.
# ./install.sh --help   prints every flag.
DRY_RUN=0
RESTORE_SETTINGS=0
UNINSTALL=0
WITH_CRON=0
WITH_VENV=0
SKIP_VENV=0
STRICT=0
FLAG_VAULT_GIT=""; FLAG_VAULT=""; FLAG_INITIALS=""; FLAG_TICKET_PREFIX=""; FLAG_NAME=""

REPO_DIR_EARLY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOLLGATE_VERSION="$(tr -d ' \r\n' < "$REPO_DIR_EARLY/VERSION" 2>/dev/null || true)"
[ -n "$TOLLGATE_VERSION" ] || TOLLGATE_VERSION="unknown"

usage() {
  cat <<USAGE
Tollgate installer ${TOLLGATE_VERSION}
Usage: ./install.sh [flags]

  --non-interactive     Take every default; ask nothing. Never cleans ~/.claude.
  --dry-run             Print what would change; change nothing.
  --vault PATH          Notes folder (vault).
  --vault-git MODE      How the vault is saved: none, local or remote. Env TOLLGATE_VAULT_GIT works too.
  --initials AB         Your initials (letters only).
  --ticket-prefix T     Ticket prefix (letters only).
  --name "Full Name"    Your name.
  --restore-settings    Put the newest settings.json backup back, then stop.
  --uninstall           Remove only what Tollgate installed: the command files and the settings.json
                        hooks, permissions and env names listed in ~/.claude/tollgate/manifest.json,
                        plus the scheduled job it made. Your own files and settings are kept. Settings
                        are backed up first; removed command files are moved to a backup folder.
  --with-venv           Build the Python venv and the search index without asking.
  --skip-venv           Never build the venv or the search index.
  --with-cron           Schedule the nightly search-index job without asking (macOS only).
  --strict              Stop (exit 1) when Claude Code is older than ${MIN_CLAUDE_VERSION:-2.1.295} or not found.
                        Without it, that is only a warning.
  --help                Show this text.

Each run writes ~/.claude/tollgate/manifest.json (what Tollgate owns) and
~/.claude/tollgate/installed-version. An update removes owned entries that upstream dropped.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --non-interactive)   TOLLGATE_NONINTERACTIVE=1 ;;
    --dry-run)           DRY_RUN=1 ;;
    --restore-settings)  RESTORE_SETTINGS=1 ;;
    --uninstall)         UNINSTALL=1 ;;
    --with-cron)         WITH_CRON=1 ;;
    --with-venv)         WITH_VENV=1 ;;
    --skip-venv)         SKIP_VENV=1 ;;
    --strict)            STRICT=1 ;;
    --help|-h)           usage; exit 0 ;;
    --vault=*)           FLAG_VAULT="${1#*=}" ;;
    --vault-git=*)       FLAG_VAULT_GIT="${1#*=}" ;;
    --initials=*)        FLAG_INITIALS="${1#*=}" ;;
    --ticket-prefix=*)   FLAG_TICKET_PREFIX="${1#*=}" ;;
    --name=*)            FLAG_NAME="${1#*=}" ;;
    --vault|--vault-git|--initials|--ticket-prefix|--name)
      if [ $# -lt 2 ]; then echo "  $1 needs a value." >&2; exit 2; fi
      case "$1" in
        --vault)         FLAG_VAULT="$2" ;;
        --vault-git)     FLAG_VAULT_GIT="$2" ;;
        --initials)      FLAG_INITIALS="$2" ;;
        --ticket-prefix) FLAG_TICKET_PREFIX="$2" ;;
        --name)          FLAG_NAME="$2" ;;
      esac
      shift ;;
    *) echo "  Unknown flag: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done
TOLLGATE_NONINTERACTIVE="${TOLLGATE_NONINTERACTIVE:-0}"

# Initials and ticket prefix are letters only. Checked here so a bad flag stops
# the run before anything is written.
for _flag in "initials:$FLAG_INITIALS" "ticket-prefix:$FLAG_TICKET_PREFIX"; do
  if [ -n "${_flag#*:}" ] && [[ ! "${_flag#*:}" =~ ^[A-Za-z]+$ ]]; then
    echo "  --${_flag%%:*} must be letters only (A to Z). Got: ${_flag#*:}" >&2
    exit 2
  fi
done

# The vault git mode is none, local or remote. A bad flag or env value stops the run before
# anything is written. A flag wins over the env variable.
VAULT_GIT_EXPLICIT="${FLAG_VAULT_GIT:-${TOLLGATE_VAULT_GIT:-}}"
VAULT_GIT_EXPLICIT="$(printf '%s' "$VAULT_GIT_EXPLICIT" | tr 'A-Z' 'a-z')"
case "$VAULT_GIT_EXPLICIT" in
  ""|none|local|remote) ;;
  *) echo "  --vault-git must be none, local or remote. Got: $VAULT_GIT_EXPLICIT" >&2; exit 2 ;;
esac

# Prompt reads (read -p / -rp / -rsp) are answered with "" (the default) in
# non-interactive mode. Reads without -p (while read loops) use the builtin.
read() {
  local _a _is_prompt=false _var="REPLY"
  for _a in "$@"; do
    [[ "$_a" =~ ^-[a-z]*p[a-z]*$ ]] && _is_prompt=true
  done
  if [ "$TOLLGATE_NONINTERACTIVE" != "1" ] || [ "$_is_prompt" = false ]; then
    builtin read "$@"
    return
  fi
  _a="${!#}"
  [[ "$_a" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && _var="$_a"
  case "$_var" in
    _choice) printf -v "$_var" '%s' "m" ;;   # migrate, never clean
    *)       printf -v "$_var" '%s' "" ;;
  esac
  echo "" >&2   # stderr: ask() returns its answer on stdout via $(...)
}

# ── Python check ──────────────────────────────────────────────────────────────
# Hooks and the settings merge need python3 >= 3.12. Checked by running it, not by
# `command -v`: on macOS without Command Line Tools /usr/bin/python3 is a stub
# that exists but opens an install dialog and fails.
MIN_PYTHON="3.12"
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
  _py_found="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)" || _py_found=""
  echo "  Tollgate needs Python ${MIN_PYTHON} or newer, found ${_py_found:-no working python3}"
  echo "  The command python3 --version must print ${MIN_PYTHON} or newer."
  echo "  Put the Python ${MIN_PYTHON} folder first on your PATH, then re-run ./install.sh"
  echo "  macOS: brew install python@3.12 (then use the python3 in brew's bin folder)"
  echo "  Linux: install python3.12 (deadsnakes on Ubuntu, pyenv or uv elsewhere); see docs/prerequisites.md"
  exit 1
fi

# Rewritten command calls hold the repo path unquoted (a quoted path would no longer match the
# permission rule), so a path with whitespace is refused here, before anything is written.
case "$REPO_DIR" in
  *[[:space:]]*)
    echo "  The Tollgate folder path contains a space: $REPO_DIR"
    echo "  Move the repo to a path without spaces, then re-run ./install.sh"
    exit 1 ;;
esac

# An existing search environment (venv) on an older Python would run the hooks and the
# index job at run time, so it must be 3.12 or newer too. One helper, two call sites:
# before any backup or wipe of an existing ~/.claude, and again once the vault path is
# final. The venv folder comes from the paths file, else the default state folder.
# It only reads and prints; it deletes nothing. Argument: the vault path, if known.
check_existing_search_python() {
  local _state _venv_py _found
  _state="$(TOLLGATE_PATHS="${TOLLGATE_PATHS:-$CLAUDE_DIR/tollgate/paths.yaml}" TOLLGATE_KNOWLEDGE="${1:-}" \
    "$REPO_DIR/scripts/core/tg_path" state 2>/dev/null)" || _state=""
  [ -n "$_state" ] || _state="$HOME/.tollgate/state"
  _venv_py="$_state/venv/bin/python3"
  [ -x "$_venv_py" ] || return 0
  "$_venv_py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1 && return 0
  _found="$("$_venv_py" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)" || _found=""
  echo "  Tollgate needs Python ${MIN_PYTHON} or newer, existing search environment uses ${_found:-an unknown version}: delete ${_state}/venv and re-run"
  exit 1
}

# ── Restore the settings backup and stop ─────────────────────────────────────
if [ "$RESTORE_SETTINGS" = 1 ]; then
  python3 "$REPO_DIR/installer/merge_settings.py" --restore "$CLAUDE_DIR/settings.json"
  exit $?
fi

# Standard skills list (used in migration analysis and custom-skill detection)
STANDARD_SKILLS="tg-arch tg-close tg-dev tg-devops tg-doc-gen tg-draft tg-explain tg-explore tg-handoff tg-influence tg-learn tg-pr-review tg-pull-notes tg-qa tg-retrieve tg-save tg-spec tg-sre tg-start tg-status tg-support tg-sweep tg-sync tg-terraform tg-think-calibrate tg-ticket tg-weekly tg-whiteboard"

# ── Formatting ────────────────────────────────────────────────────────────────
BOLD='\033[1m'; RESET='\033[0m'; GREEN='\033[0;32m'
YELLOW='\033[0;33m'; DIM='\033[2m'; CYAN='\033[0;36m'

header() { echo -e "\n${BOLD}── $1 ──${RESET}"; }
ok()     { echo -e "  ${GREEN}✓${RESET}  $1"; }
note()   { echo -e "  ${YELLOW}→${RESET}  $1"; }
dim()    { echo -e "  ${DIM}$1${RESET}"; }
info()   { echo -e "  ${CYAN}$1${RESET}"; }

# ── Plain-text prompt ─────────────────────────────────────────────────────────
ask() {
  local prompt="$1" default="${2:-}" result
  if [ -n "$default" ]; then
    read -rp "  $prompt [$default]: " result
    echo "${result:-$default}"
  else
    read -rp "  $prompt: " result
    echo "$result"
  fi
}

# ── Cross-platform credential read ────────────────────────────────────────────
cred_read() {
  local service="${KC_PREFIX}-$1"
  case "$OS" in
    Darwin)
      security find-generic-password -a "$USER" -s "$service" -w 2>/dev/null || echo ""
      ;;
    Linux)
      if command -v secret-tool &>/dev/null; then
        secret-tool lookup service "$service" account "$USER" 2>/dev/null || echo ""
      else
        # No plain secret file is ever read. Without secret-tool nothing is stored.
        echo ""
      fi
      ;;
    MINGW*|CYGWIN*|MSYS*)
      cmdkey /list | grep -q "tollgate-$1" \
        && powershell -Command "(Get-StoredCredential -Target '${service}').GetNetworkCredential().Password" 2>/dev/null \
        || echo ""
      ;;
    *) echo "";;
  esac
}

# ── Cross-platform credential write ──────────────────────────────────────────
cred_store() {
  local service="$1" value="$2"
  if [ -z "$value" ]; then
    note "Skipped (empty): ${service}"
    return
  fi
  local key="${KC_PREFIX}-${service}"
  if [ "$DRY_RUN" = 1 ]; then
    note "[dry-run] would store credential: ${service}"
    return
  fi
  case "$OS" in
    Darwin)
      # -w with no value (last option) makes security prompt on the terminal.
      # A value after -w would sit in the process list, readable by every user.
      note "macOS Keychain will ask for the ${service} value (type it twice)."
      security add-generic-password -a "$USER" -s "$key" -U -w
      ok "Saved to Keychain: ${service}"
      ;;
    Linux)
      if command -v secret-tool &>/dev/null; then
        printf '%s' "$value" | secret-tool store --label="$key" service "$key" account "$USER" 2>/dev/null
        ok "Saved to Secret Service: ${service}"
      else
        # Refuse: a plain secrets file is not allowed. Skip storing, keep installing.
        note "Not saved: ${service}. secret-tool is missing, so the installer will not store a secret in a plain file."
        note "Fix: sudo apt install libsecret-tools   (then run the installer again)"
      fi
      ;;
    MINGW*|CYGWIN*|MSYS*)
      cmdkey /generic:"$key" /user:"$USER" /pass:"$value" &>/dev/null
      ok "Saved to Credential Manager: ${service}"
      ;;
    *)
      note "Unknown OS — could not save ${service}. You may need to re-enter it next time."
      ;;
  esac
}

# ── Hidden token prompt (credential-store-aware) ──────────────────────────────
ask_secret() {
  local prompt="$1" service="$2" result existing masked
  existing=$(cred_read "$service")
  if [ -n "$existing" ]; then
    masked="****${existing: -4}"
    read -rsp "  $prompt [saved: ${masked} — press Enter to keep]: " result
    echo "" >&2
    if [ -z "$result" ]; then echo "$existing"; else echo "$result"; fi
  else
    read -rsp "  $prompt [press Enter to skip]: " result
    echo "" >&2
    echo "$result"
  fi
}

# ── Connection chooser ────────────────────────────────────────────────────────
# Sets global CONNECTION_CHOICE to "mcp", "api", or "skip"
CONNECTION_CHOICE=""
choose_connection() {
  local service="$1" has_mcp="$2" result
  if [ "$TOLLGATE_NONINTERACTIVE" = "1" ]; then
    CONNECTION_CHOICE="skip"
    return
  fi
  echo ""
  if [ "$has_mcp" = "yes" ]; then
    echo "    b) Sign in with your browser   Easiest — a login page opens automatically, no key needed."
    echo "    k) Paste an API key            If you already have one ready."
  else
    echo "    k) Paste an API key            Required for this service."
  fi
  echo "    s) Skip for now                Add this later by re-running install.sh."
  echo ""
  while true; do
    if [ "$has_mcp" = "yes" ]; then
      read -rp "  Choice [b/k/s]: " result
      result=$(echo "$result" | tr '[:upper:]' '[:lower:]')
      case "$result" in
        b) CONNECTION_CHOICE="mcp";  return;;
        k) CONNECTION_CHOICE="api";  return;;
        s) CONNECTION_CHOICE="skip"; return;;
        *) echo "  Please type b, k, or s.";;
      esac
    else
      read -rp "  Choice [k/s]: " result
      result=$(echo "$result" | tr '[:upper:]' '[:lower:]')
      case "$result" in
        k) CONNECTION_CHOICE="api";  return;;
        s) CONNECTION_CHOICE="skip"; return;;
        *) echo "  Please type k or s.";;
      esac
    fi
  done
}

# ── Escape user input for sed replacement strings ────────────────────────────
# Escapes \, &, and the | delimiter so user-supplied strings (names, company)
# cannot corrupt sed expressions or produce garbled output files.
_sed_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/&/\\&/g; s/|/\\|/g'
}

# ── Backup + symlink ──────────────────────────────────────────────────────────
backup() {
  local path="$1"
  if [ -e "$path" ] && [ ! -L "$path" ]; then
    mv "$path" "$path.bak.$(date +%Y%m%d%H%M%S)"
    note "Backed up: $(basename "$path")"
    prune_bak "$path"
  fi
}

# Keep only the newest $KEEP_BACKUPS "<path>.bak.<14 digit time>" copies of one file.
prune_bak() {
  local path="$1" keep="${2:-$KEEP_BACKUPS}" f
  { ls -1 "$path".bak.* 2>/dev/null | grep -E '\.bak\.[0-9]{14}(-[0-9]+)?$' | sort \
      | awk -v k="$keep" '{a[NR]=$0} END{for(i=1;i<=NR-k;i++)print a[i]}' \
      | while IFS= read -r f; do rm -rf -- "$f"; done; } || true
}

# Keep only the newest $KEEP_BACKUPS full copies of ~/.claude made by this installer.
# Only folders named ~/.claude.backup.<14 digit time> are ever deleted.
prune_full_backups() {
  [ "$DRY_RUN" = 1 ] && return 0
  local keep="${1:-$KEEP_BACKUPS}" f
  { ls -1d "$HOME"/.claude.backup.* 2>/dev/null | grep -E '/\.claude\.backup\.[0-9]{14}$' | sort \
      | awk -v k="$keep" '{a[NR]=$0} END{for(i=1;i<=NR-k;i++)print a[i]}' \
      | while IFS= read -r f; do rm -rf -- "$f"; done; } || true
}

# ── Backup ~/.claude as a full copy, verified ─────────────────────────────────
# Sets BACKUP_DIR and BACKUP_VERIFIED. Returns non-zero when the copy is not
# complete; the caller decides whether that is fatal (clean mode: always).
_count_all_files() { find -L "$1" -type f 2>/dev/null | wc -l | tr -d ' '; }

backup_claude_dir() {
  BACKUP_VERIFIED=0
  BACKUP_DIR="$HOME/.claude.backup.$(date +%Y%m%d%H%M%S)"
  if [ "$DRY_RUN" = 1 ]; then
    note "[dry-run] would copy $CLAUDE_DIR to $BACKUP_DIR and verify file counts"
    return 0
  fi
  cp -rL "$CLAUDE_DIR" "$BACKUP_DIR" 2>/dev/null \
    || cp -r "$CLAUDE_DIR" "$BACKUP_DIR" 2>/dev/null \
    || { BACKUP_DIR=""; return 1; }
  local _src _dst
  _src=$(_count_all_files "$CLAUDE_DIR")
  _dst=$(_count_all_files "$BACKUP_DIR")
  if [ "$_src" != "$_dst" ]; then
    note "Backup check failed: $_src files in source, $_dst in copy ($BACKUP_DIR)."
    BACKUP_DIR=""
    return 1
  fi
  BACKUP_VERIFIED=1
}

# ── Wipe ~/.claude. Only runs after a verified backup. ────────────────────────
clean_claude_dir() {
  if [ "$DRY_RUN" = 1 ]; then
    note "[dry-run] would delete $CLAUDE_DIR and recreate it empty"
    return 0
  fi
  if [ "$BACKUP_VERIFIED" != 1 ] || [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
    echo "  Clean aborted: no verified backup. $CLAUDE_DIR was not touched." >&2
    return 1
  fi
  rm -rf "$CLAUDE_DIR"
  mkdir -p "$CLAUDE_DIR"
}

# Move a freshly rendered file into place. An identical file is left alone, so a
# second run changes nothing and leaves no backup. A different file is backed up.
install_rendered() {
  local tmp="$1" dest="$2"
  if [ -f "$dest" ] && cmp -s "$tmp" "$dest"; then rm -f "$tmp"; return 0; fi
  if [ -L "$dest" ]; then cat "$tmp" > "$dest"; rm -f "$tmp"; return 0; fi
  backup "$dest"
  mv "$tmp" "$dest"
}

symlink() {
  local src="$1" dest="$2"
  backup "$dest"
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
    ok "Already linked: $(basename "$dest")"
  else
    ln -sf "$src" "$dest"
    ok "Linked: $(basename "$dest")"
  fi
}

# ── Claude Code version check ─────────────────────────────────────────────────
# The PHI and secret hooks use the hook field onFailure: "block", which needs
# Claude Code MIN_CLAUDE_VERSION or later. On older builds a hook that cannot
# start fails open. Warns by default; --strict stops the install instead.
_version_number() {   # 2.1.311 -> 2000001000311 (compare as plain integers, bash 3.2 safe)
  printf '%s' "$1" | awk -F. '{printf "%.0f", $1*1000000000000 + $2*1000000 + $3}'
}
check_claude_version() {
  local raw ver
  CLAUDE_VERSION_STATUS="ok"
  if ! command -v claude >/dev/null 2>&1; then
    CLAUDE_VERSION_STATUS="missing"
  else
    raw="$(claude --version 2>/dev/null || true)"
    ver="$(printf '%s' "$raw" | sed -n 's/^[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -1)"
    if [ -z "$ver" ]; then
      CLAUDE_VERSION_STATUS="missing"
    elif [ "$(_version_number "$ver")" -lt "$(_version_number "$MIN_CLAUDE_VERSION")" ]; then
      CLAUDE_VERSION_STATUS="old"
    fi
  fi
  case "$CLAUDE_VERSION_STATUS" in
    ok) ;;
    old)
      note "Claude Code $ver is older than $MIN_CLAUDE_VERSION."
      note "The PHI and secret hooks will NOT fail closed on this version: a hook that cannot start lets the action through."
      note "Upgrade Claude Code to $MIN_CLAUDE_VERSION or later, then re-run ./install.sh."
      ;;
    missing)
      note "Claude Code was not found (or its version could not be read)."
      note "The PHI and secret hooks need Claude Code $MIN_CLAUDE_VERSION or later to fail closed. Install or upgrade it."
      ;;
  esac
  if [ "$CLAUDE_VERSION_STATUS" != "ok" ] && [ "$STRICT" = 1 ]; then
    echo "  --strict given: stopping because Claude Code is $CLAUDE_VERSION_STATUS (need $MIN_CLAUDE_VERSION or later)." >&2
    exit 1
  fi
}

# ── Uninstall: remove only what the manifest lists ────────────────────────────
if [ "$UNINSTALL" = 1 ]; then
  header "Uninstall Tollgate"
  _ts="$(date +%Y%m%d%H%M%S)"
  _cron_launcher="${TOLLGATE_CRON_LAUNCHER:-launchctl}"
  if [ ! -f "$MANIFEST" ]; then
    note "No manifest at $MANIFEST. Nothing Tollgate installed is known, so nothing was removed."
    exit 0
  fi
  if [ "$DRY_RUN" = 1 ]; then
    note "[dry-run] would remove the settings.json entries listed in $MANIFEST (settings backed up first)"
    note "[dry-run] would move the command files listed there out of $CLAUDE_DIR/commands into $TG_STATE_DIR/removed/"
    note "[dry-run] would remove the scheduled job Tollgate made, then the manifest and installed-version files"
    exit 0
  fi
  python3 "$REPO_DIR/installer/merge_settings.py" --uninstall --backup \
    --manifest "$MANIFEST" "$CLAUDE_DIR/settings.json"
  python3 "$REPO_DIR/installer/manifest.py" uninstall-commands --manifest "$MANIFEST" \
    --commands-dir "$CLAUDE_DIR/commands" --backup-dir "$TG_STATE_DIR/removed/removed.$_ts"
  while IFS= read -r _job; do
    [ -n "$_job" ] || continue
    python3 "$REPO_DIR/scripts/cron/setup_cron.py" --home "$HOME" --job "$_job" --remove \
      --yes-install-job --launcher "$_cron_launcher" || note "Could not remove scheduled job: $_job"
  done < <(python3 "$REPO_DIR/installer/manifest.py" get-list --manifest "$MANIFEST" --key cron)
  rm -f "$MANIFEST" "$INSTALLED_VERSION_FILE"
  ok "Tollgate entries removed. Your own commands, settings, notes and memory were not touched."
  dim "Left in place on purpose: CLAUDE.md, tollgate-config, credentials.sh, the shell profile block, the memory link."
  dim "Removed command files are in $TG_STATE_DIR/removed/. Settings backup: settings.json.bak.*"
  exit 0
fi

check_claude_version

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Tollgate ${TOLLGATE_VERSION}  -  AI assistant setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Sets up Claude Code to work the way your team works."
echo "  Takes about 5 minutes."
echo ""
echo "  What it does:"
echo "    • Creates a personal notes folder for your work"
echo "    • Connects Claude to Jira, Notion, and Slack"
echo "    • Saves your details so Claude knows who you are"
echo ""
echo "  Press Enter at any prompt to use the suggested answer."
echo "  Questions? hello@dipenpatel.dev"
echo ""
read -rp "  Ready? Press Enter to start (or Ctrl-C to exit): "
echo ""

echo "  Setup mode:"
echo "    Simple   — auto-configures folders and paths (recommended for most teams)"
echo "    Advanced — manually set folder paths, code reference dir, and repo cloning"
echo ""
_mode_input=""
read -rp "  Advanced setup? [y/N]: " _mode_input
if [[ "$_mode_input" == [yY] || "$_mode_input" == [yY][eE][sS] ]]; then
  SIMPLE_MODE=false
else
  SIMPLE_MODE=true
fi
echo ""

# ── Detect existing setup ─────────────────────────────────────────────────────
INSTALL_MODE="fresh"
DETECTED_VAULT=""
DETECTED_NAME=""
DETECTED_TITLE=""
DETECTED_COMPANY=""
DETECTED_DOMAIN=""
DETECTED_BASE=""
CUSTOM_SKILLS=()
BACKUP_DIR=""
TOLLGATE_CONFIG="${TOLLGATE_CONFIG:-$HOME/.claude/tollgate-config}"

# Escape a value so it is safe inside double quotes in the saved config, which
# later runs source. Backslash, quote, dollar and backtick get a backslash;
# line breaks become spaces so a value cannot add a second line.
_dq() { printf '%s' "$1" | tr '\r\n' '  ' | sed 's/[\\"$`]/\\&/g'; }

# Load saved config from a previous run so users don't re-enter everything
if [ -f "$TOLLGATE_CONFIG" ]; then
  # shellcheck source=/dev/null
  source "$TOLLGATE_CONFIG"
fi

_count_files() { { ls "$1"/*.md 2>/dev/null || true; } | wc -l | tr -d ' '; }

if [ -d "$CLAUDE_DIR" ] && [ "$(ls -A "$CLAUDE_DIR" 2>/dev/null)" ]; then
  EXISTING_COMMANDS=0
  EXISTING_MEMORIES=0

  [ -d "$CLAUDE_DIR/commands" ] && EXISTING_COMMANDS=$(_count_files "$CLAUDE_DIR/commands")
  EXISTING_MEMORIES=$(find "$CLAUDE_DIR/projects" -name "*.md" 2>/dev/null | wc -l | tr -d ' ' || echo "0")

  # An older install exported <PREFIX>_KNOWLEDGE next to TOLLGATE_KNOWLEDGE; only the latter is read now.
  [ -n "${TOLLGATE_KNOWLEDGE:-}" ] && DETECTED_VAULT="$TOLLGATE_KNOWLEDGE"

  if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    DETECTED_NAME=$(grep -m1 "^\*\*Name:\*\*" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null \
      | sed 's/\*\*Name:\*\* //' | tr -d '\r' || echo "")
    DETECTED_TITLE=$(grep -m1 "^\*\*Title:\*\*" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null \
      | sed 's/\*\*Title:\*\* //' | tr -d '\r' || echo "")
    DETECTED_COMPANY=$(grep -m1 "^\*\*Company:\*\*" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null \
      | sed 's/\*\*Company:\*\* //' | tr -d '\r' || echo "")
  fi

  if [ "$SIMPLE_MODE" = true ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Existing setup found"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    [ -n "$DETECTED_NAME" ] && echo "  Name on file: $DETECTED_NAME"
    echo ""
    echo "  What would you like to do?"
    echo ""
    echo "    k) Keep and update   Upgrade to the latest version, keep your notes."
    echo "    f) Start fresh       Wipe everything and start over."
    echo ""
    while true; do
      read -rp "  Choice [k/f, default k]: " _m_choice
      _m_choice="${_m_choice:-k}"
      _m_choice=$(echo "$_m_choice" | tr '[:upper:]' '[:lower:]')
      case "$_m_choice" in
        k) INSTALL_MODE="migrate"; break;;
        f) INSTALL_MODE="clean";   break;;
        *) echo "  Please type k or f.";;
      esac
    done
  else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Existing Claude Code setup found"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    printf "  %-22s %s\n" "Commands found:"   "$EXISTING_COMMANDS files"
    printf "  %-22s %s\n" "Memory files:"     "$EXISTING_MEMORIES files"
    [ -n "$DETECTED_NAME" ]   && printf "  %-22s %s\n" "Detected name:"    "$DETECTED_NAME"
    [ -n "$DETECTED_VAULT" ]  && printf "  %-22s %s\n" "Existing vault:"   "$DETECTED_VAULT"
    echo ""
    echo "  What would you like to do?"
    echo ""
    echo "    m) Migrate   Keep your memory and vault, install new skills alongside them."
    echo "    c) Clean     Wipe ~/.claude/ and start completely fresh."
    echo ""
    echo "  Either way, your existing ~/.claude/ is backed up first."
    echo ""
    while true; do
      read -rp "  Choice [m/c]: " _choice
      _choice=$(echo "$_choice" | tr '[:upper:]' '[:lower:]')
      case "$_choice" in
        m) INSTALL_MODE="migrate"; break;;
        c) INSTALL_MODE="clean";   break;;
        *) echo "  Enter m or c.";;
      esac
    done
  fi

  echo ""

  # Before anything is backed up or wiped: an old search environment ends the run here.
  check_existing_search_python "$DETECTED_VAULT"

  # Full backup on a first install, a migration and a clean start. An update of a
  # Tollgate install (manifest present) backs up file by file (.bak), not the whole folder.
  BACKUP_VERIFIED=0
  if [ "$INSTALL_MODE" = "migrate" ] && [ -f "$MANIFEST" ]; then
    dim "Update of an existing Tollgate install: files are backed up one at a time (.bak), no full copy."
  elif backup_claude_dir; then
    [ "$DRY_RUN" = 1 ] || ok "Backed up existing setup to: $BACKUP_DIR"
  elif [ "$INSTALL_MODE" = "clean" ]; then
    echo "  Could not back up $CLAUDE_DIR. Clean mode needs a backup, so nothing was deleted." >&2
    exit 1
  else
    note "Could not fully back up $CLAUDE_DIR — continuing anyway (original untouched)."
  fi
  prune_full_backups
  echo ""

  if [ "$INSTALL_MODE" = "clean" ]; then
    clean_claude_dir || exit 1
    [ "$DRY_RUN" = 1 ] || ok "Cleared existing setup — starting fresh"
    echo ""
  fi

  # Advanced mode only: detailed migration analysis
  if [ "$INSTALL_MODE" = "migrate" ] && [ "$SIMPLE_MODE" = false ]; then
    echo ""
    echo "  ── Migration Analysis ──"
    echo ""
    echo "  Skill files:"
    SKILLS_USE_NEW=()
    SKILLS_MODIFIED=()

    if [ -d "$CLAUDE_DIR/commands" ]; then
      for _skill in $STANDARD_SKILLS; do
        _existing_path="$CLAUDE_DIR/commands/${_skill}.md"
        _repo_path="$REPO_DIR/commands/${_skill}.md"
        [ ! -f "$_existing_path" ] && continue
        [ ! -f "$_repo_path" ]    && continue
        _lines_existing=$(wc -l < "$_existing_path" | tr -d ' ')
        _lines_new=$(wc -l < "$_repo_path" | tr -d ' ')
        _diff=$(( _lines_new - _lines_existing ))
        if [ "$_diff" -gt 20 ]; then
          printf "    %-28s existing %s lines / new %s lines  → new has additions, use new\n" \
            "/$_skill" "$_lines_existing" "$_lines_new"
          SKILLS_USE_NEW+=("$_skill")
        elif [ "$_diff" -lt -20 ]; then
          printf "    %-28s existing %s lines / new %s lines  → existing was modified, review\n" \
            "/$_skill" "$_lines_existing" "$_lines_new"
          SKILLS_MODIFIED+=("$_skill")
        else
          printf "    %-28s existing %s lines / new %s lines  → comparable, use new\n" \
            "/$_skill" "$_lines_existing" "$_lines_new"
          SKILLS_USE_NEW+=("$_skill")
        fi
      done
    fi

    echo ""
    echo "  CLAUDE.md:"
    _ref_dir="${BACKUP_DIR:-$CLAUDE_DIR}"
    if [ -f "$_ref_dir/CLAUDE.md" ]; then
      _existing_lines=$(wc -l < "$_ref_dir/CLAUDE.md" | tr -d ' ')
      _template_lines=$(wc -l < "$REPO_DIR/CLAUDE.md" | tr -d ' ')
      if [ "$_existing_lines" -gt $(( _template_lines + 10 )) ]; then
        printf "    Existing has %s lines vs template %s lines.\n" "$_existing_lines" "$_template_lines"
        echo "    Likely has custom rules. New CLAUDE.md will be used (identity pre-filled)."
        echo "    Review $_ref_dir/CLAUDE.md after install to recover any custom rules."
      else
        echo "    No significant customization detected. New CLAUDE.md will be used."
      fi
    fi
    echo ""
    _mem_count=$(find "$_ref_dir/projects" -name "*.md" 2>/dev/null | wc -l | tr -d ' ' || echo "0")
    echo "  Memory files:"
    printf "    %s feedback memory files found — all preserved.\n" "$_mem_count"
    echo ""
    echo "  Migration plan:"
    echo "    - All standard skills: install new versions"
    [ "${#SKILLS_MODIFIED[@]}" -gt 0 ] && \
      echo "    - Modified skills: new installed, old saved to $BACKUP_DIR for manual review"
    [ "${#CUSTOM_SKILLS[@]}" -gt 0 ] && \
      echo "    - Custom skills: left where they are in ~/.claude/commands"
    echo "    - Memory files: left where they are (never copied into this repo)"
    echo ""
    read -rp "  Proceed with this migration plan? [Y/n]: " _confirm
    echo ""
    if [[ "$_confirm" =~ ^[Nn]$ ]]; then
      echo "  Migration cancelled. Your backup is at: ${BACKUP_DIR:-none made (update run)}"
      echo "  Re-run install.sh to start over."
      exit 0
    fi
  fi

  # Custom skill detection (both modes)
  if [ "$INSTALL_MODE" = "migrate" ] && [ -d "$CLAUDE_DIR/commands" ]; then
    # A command file is Tollgate's when this repo ships it, or when the manifest lists it (an older
    # install's names, which an update replaces). Anything else is the user's own and is always kept.
    _owned_cmds=" $(python3 "$REPO_DIR/installer/manifest.py" get-list --manifest "$MANIFEST" --key commands 2>/dev/null | tr '\n' ' ') "
    for _f in "$CLAUDE_DIR/commands/"*.md; do
      [ ! -f "$_f" ] && continue
      _base=$(basename "$_f" .md)
      _is_standard=false
      for _s in $STANDARD_SKILLS; do
        [ "$_base" = "$_s" ] && _is_standard=true && break
      done
      [ -f "$REPO_DIR/commands/$_base.md" ] && _is_standard=true
      case "$_owned_cmds" in *" $_base.md "*) _is_standard=true ;; esac
      [ "$_is_standard" = false ] && CUSTOM_SKILLS+=("$_f")
    done

    if [ "${#CUSTOM_SKILLS[@]}" -gt 0 ] && [ "$SIMPLE_MODE" = false ]; then
      echo "  Custom skills (always kept):"
      for _f in "${CUSTOM_SKILLS[@]}"; do
        printf "    %s\n" "$(basename "$_f")"
      done
      echo ""
    fi
  fi
fi  # end existing-setup detection

# ── Dry run stops here: everything below writes to disk or asks for secrets ──
if [ "$DRY_RUN" = 1 ]; then
  header "Dry run: remaining actions (none executed)"
  note "[dry-run] would write $TOLLGATE_CONFIG (saved answers)"
  note "[dry-run] would create empty paths and connectors files under $CLAUDE_DIR/tollgate"
  note "[dry-run] would save the vault git setting (none, local or remote) in the paths file"
  note "[dry-run] would create the notes vault, scripts and code folders"
  note "[dry-run] would clone or update repos listed during setup"
  note "[dry-run] would install commands into $CLAUDE_DIR/commands and CLAUDE.md"
  note "[dry-run] would store service credentials in the OS keychain"
  note "[dry-run] would write $CREDS_SCRIPT and register MCP servers"
  note "[dry-run] would append an env block to your shell profile"
  note "[dry-run] would merge hooks into $CLAUDE_DIR/settings.json"
  note "[dry-run] would record what it installed in $MANIFEST and write $INSTALLED_VERSION_FILE ($TOLLGATE_VERSION)"
  note "[dry-run] would optionally build the Python venv, the search index and the nightly job"
  echo ""
  exit 0
fi

# ── Step 1: Your Details ──────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = true ]; then
  header "Your Details"
else
  header "Step 1: Your Identity"
  dim "Written into CLAUDE.md so Claude knows your role and context."
fi
echo ""

GIT_NAME=$(git config user.name 2>/dev/null || echo "")
GIT_EMAIL=$(git config user.email 2>/dev/null || echo "")
_default_name="${FLAG_NAME:-${SAVED_NAME:-${DETECTED_NAME:-$GIT_NAME}}}"
# Nothing to ask in non-interactive mode, so an empty name gets a placeholder
# instead of looping forever.
[ -z "$_default_name" ] && [ "$TOLLGATE_NONINTERACTIVE" = "1" ] && _default_name="Tollgate User"
_default_title="${SAVED_TITLE:-${DETECTED_TITLE:-Engineer}}"
_default_company="${SAVED_COMPANY:-${DETECTED_COMPANY:-}}"
_default_domain="${SAVED_DOMAIN:-Health AI}"

USER_NAME=$(ask  "Your full name"    "$_default_name")
while [ -z "$USER_NAME" ]; do
  echo "  Name is required."
  USER_NAME=$(ask "Your full name" "")
done
USER_TITLE=$(ask "Your job title"    "$_default_title")
USER_COMPANY=$(ask "Your company"   "$_default_company")
USER_DOMAIN=$(ask  "Your industry (e.g. Health AI, FinTech, Insurance)" "$_default_domain")

# Initials and ticket prefix: letters only, saved upper case. A flag skips the question.
_to_upper() { printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; }
make_initials() {
  printf '%s' "$1" | awk '{r=""; for(i=1;i<=NF&&i<=3;i++) r=r substr($i,1,1); print r}' \
    | tr -cd 'A-Za-z' | tr '[:lower:]' '[:upper:]'
}
ask_letters() {
  local prompt="$1" default="$2" answer
  while true; do
    answer=$(_to_upper "$(ask "$prompt" "$default")")
    if [[ "$answer" =~ ^[A-Z]+$ ]]; then echo "$answer"; return; fi
    echo "  Letters only, please (A to Z)." >&2
  done
}
_default_initials=$(_to_upper "${TOLLGATE_INITIALS:-}")
[[ "$_default_initials" =~ ^[A-Z]+$ ]] || _default_initials=$(make_initials "$USER_NAME")
[ -z "$_default_initials" ] && _default_initials="TG"
_default_ticket=$(_to_upper "${TOLLGATE_TICKET_PREFIX:-}")
[[ "$_default_ticket" =~ ^[A-Z]+$ ]] || _default_ticket="T"
if [ -n "$FLAG_INITIALS" ]; then
  USER_INITIALS=$(_to_upper "$FLAG_INITIALS")
else
  USER_INITIALS=$(ask_letters "Your initials, used in ticket and file names (letters only)" "$_default_initials")
fi
if [ -n "$FLAG_TICKET_PREFIX" ]; then
  TICKET_PREFIX=$(_to_upper "$FLAG_TICKET_PREFIX")
else
  TICKET_PREFIX=$(ask_letters "Ticket prefix, for example T gives T-001 (letters only)" "$_default_ticket")
fi

# Commands always install as tg-*.md, so there is no per-install command prefix. FOLDER_STEM only
# names the folders beside the vault (<stem>-scripts, <stem>-code ...). A re-run of an older install
# keeps the stem it saved, so its folders are not renamed; a new install uses "tollgate".
FOLDER_STEM="${SAVED_FOLDER_STEM:-${SAVED_PREFIX:-tollgate}}"

# Save answers so re-runs don't require re-entry
mkdir -p "$CLAUDE_DIR"
cat > "$TOLLGATE_CONFIG" << SAVEDCONFIG
SAVED_NAME="$(_dq "$USER_NAME")"
SAVED_TITLE="$(_dq "$USER_TITLE")"
SAVED_COMPANY="$(_dq "$USER_COMPANY")"
SAVED_DOMAIN="$(_dq "$USER_DOMAIN")"
SAVED_FOLDER_STEM="$(_dq "$FOLDER_STEM")"
SAVEDCONFIG

# ── Step 2: Folder Setup ──────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 2: Folder Setup"
  dim "Everything lives under one base folder."
fi
echo ""

NAME_SLUG=$(echo "$USER_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
DEFAULT_BASE="$HOME/Developer/${NAME_SLUG}"

if [ "$SIMPLE_MODE" = true ]; then
  _default_vault="${DETECTED_VAULT:-${DEFAULT_BASE}/${FOLDER_STEM}-knowledge}"
  if [ -n "$FLAG_VAULT" ]; then
    VAULT_DIR="$FLAG_VAULT"
  else
    echo "  Your notes will be saved to:"
    echo "    $_default_vault"
    echo ""
    read -rp "  Press Enter to use this, or type a different path: " _vault_input
    VAULT_DIR="${_vault_input:-$_default_vault}"
  fi
  # All other dirs derive from DEFAULT_BASE so they stay consistent
  BASE_DIR="$DEFAULT_BASE"
  DOTFILES_DIR="${BASE_DIR}/${FOLDER_STEM}-dotfiles"
  SCRIPTS_DIR="${BASE_DIR}/${FOLDER_STEM}-scripts"
  MEETINGS_DIR="${VAULT_DIR}/meetings"
  CODE_DIR="${BASE_DIR}/${FOLDER_STEM}-code"
  DEV_DIR="${BASE_DIR}/${FOLDER_STEM}-dev"
else
  BASE_DIR=$(ask "Base folder path (press Enter for default)" "${SAVED_BASE:-$DEFAULT_BASE}")
  BASE_DIR="${BASE_DIR/#\~/$HOME}"
  DOTFILES_DIR="${BASE_DIR}/${FOLDER_STEM}-dotfiles"
  if [ -n "$FLAG_VAULT" ]; then
    VAULT_DIR="$FLAG_VAULT"
  else
    VAULT_DIR=$(ask "Notes folder (your vault)" "${DETECTED_VAULT:-${BASE_DIR}/${FOLDER_STEM}-knowledge}")
  fi
  SCRIPTS_DIR="${BASE_DIR}/${FOLDER_STEM}-scripts"
  MEETINGS_DIR="${VAULT_DIR}/meetings"
  CODE_DIR="${BASE_DIR}/${FOLDER_STEM}-code"
  DEV_DIR="${BASE_DIR}/${FOLDER_STEM}-dev"
  echo ""
  ok "Base:      $BASE_DIR"
  ok "Dotfiles:  $DOTFILES_DIR"
  ok "Knowledge: $VAULT_DIR"
  ok "Scripts:   $SCRIPTS_DIR"
  ok "Meetings:  $MEETINGS_DIR (inside knowledge)"
  ok "Code:      $CODE_DIR  (read-only source)"
  ok "Dev:       $DEV_DIR   (active checkouts)"
  echo ""
  if [ "$REPO_DIR" != "$DOTFILES_DIR" ]; then
    note "This repo is at: $REPO_DIR"
    note "Expected at:     $DOTFILES_DIR"
    note "Consider moving: mv \"$REPO_DIR\" \"$DOTFILES_DIR\""
    echo ""
  fi
fi

# The vault must be an absolute path: hooks run from other folders.
VAULT_DIR="${VAULT_DIR/#\~/$HOME}"
case "$VAULT_DIR" in /*) ;; *) VAULT_DIR="$PWD/$VAULT_DIR" ;; esac
MEETINGS_DIR="$(TOLLGATE_PATHS="${TOLLGATE_PATHS:-$CLAUDE_DIR/tollgate/paths.yaml}" TOLLGATE_KNOWLEDGE="$VAULT_DIR" \
  "$REPO_DIR/scripts/core/tg_path" meetings 2>/dev/null)" || MEETINGS_DIR="${VAULT_DIR}/meetings"

# Refuse when an existing search environment is on an older Python (see the helper
# above). The vault path is final here, so the venv is located exactly. In a run that
# found an existing ~/.claude the same check already ran before any backup or wipe.
check_existing_search_python "$VAULT_DIR"

mkdir -p "$BASE_DIR" "$SCRIPTS_DIR"

# Persist the resolved base path for future re-runs
echo "SAVED_BASE=\"$(_dq "$BASE_DIR")\"" >> "$TOLLGATE_CONFIG"

# The new Tollgate variables (docs/variables.md). Answers and folder names only,
# never a secret. TOLLGATE_PATHS and TOLLGATE_CONNECTORS are empty files the
# path loader and the connector framework fill in later; they are created once
# and never overwritten.
TOLLGATE_HOME="$REPO_DIR"
TOLLGATE_PATHS="${TOLLGATE_PATHS:-$CLAUDE_DIR/tollgate/paths.yaml}"
TOLLGATE_CONNECTORS="${TOLLGATE_CONNECTORS:-$CLAUDE_DIR/tollgate/connectors.yaml}"
{
  echo "TOLLGATE_KNOWLEDGE=\"$(_dq "$VAULT_DIR")\""
  echo "TOLLGATE_INITIALS=\"$USER_INITIALS\""
  echo "TOLLGATE_TICKET_PREFIX=\"$TICKET_PREFIX\""
  echo "TOLLGATE_HOME=\"$(_dq "$TOLLGATE_HOME")\""
  echo "TOLLGATE_PATHS=\"$(_dq "$TOLLGATE_PATHS")\""
  echo "TOLLGATE_CONNECTORS=\"$(_dq "$TOLLGATE_CONNECTORS")\""
} >> "$TOLLGATE_CONFIG"
for _f in "$TOLLGATE_PATHS" "$TOLLGATE_CONNECTORS"; do
  mkdir -p "$(dirname "$_f")"
  [ -e "$_f" ] || : > "$_f"
done

# The library folder sits beside the vault, outside it. It holds epubs and
# documents. Its path goes into the paths file once, and is never rewritten.
LIBRARY_DIR="${BASE_DIR}/${FOLDER_STEM}-library"
mkdir -p "$LIBRARY_DIR"
if ! grep -q '^[[:space:]]*references[[:space:]]*:' "$TOLLGATE_PATHS" 2>/dev/null; then
  echo "references: $LIBRARY_DIR" >> "$TOLLGATE_PATHS"
fi

# ── Vault git setting ─────────────────────────────────────────────────────────
# How the vault is saved: none (plain files), local (a git repo, commands print the commit lines)
# or remote (same, plus a printed push line). Tollgate never runs those lines and never adds a remote.
# Default: a flag or TOLLGATE_VAULT_GIT, else the saved value, else the detected mode of an existing
# vault, else local. Unattended runs with no mode given follow the folder: no .git means none.
# The answer goes in the paths file as `vault_git: MODE`.
_vg_valid() { case "$1" in none|local|remote) return 0 ;; *) return 1 ;; esac; }
_vg_saved=$(sed -n 's/^[[:space:]]*vault_git[[:space:]]*:[[:space:]]*//p' "$TOLLGATE_PATHS" 2>/dev/null | head -n 1 | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//' | tr 'A-Z' 'a-z')
_vg_valid "$_vg_saved" || _vg_saved=""
_vg_detected=""
if [ -d "$VAULT_DIR" ]; then
  if [ -e "$VAULT_DIR/.git" ]; then
    if [ -n "$(git -C "$VAULT_DIR" remote 2>/dev/null)" ]; then _vg_detected="remote"; else _vg_detected="local"; fi
  else
    _vg_detected="none"
  fi
fi
_vg_default="${_vg_saved:-${_vg_detected:-local}}"
if [ -n "$VAULT_GIT_EXPLICIT" ]; then
  VAULT_GIT="$VAULT_GIT_EXPLICIT"
else
  while :; do
    _vg_answer=$(ask "How should your vault be saved? none / local / remote" "$_vg_default")
    VAULT_GIT=$(printf '%s' "$_vg_answer" | tr 'A-Z' 'a-z')
    _vg_valid "$VAULT_GIT" && break
    echo "  Please answer none, local or remote." >&2
    [ "$TOLLGATE_NONINTERACTIVE" = "1" ] && { VAULT_GIT="$_vg_default"; break; }
  done
  # Unattended with no mode given: follow the folder. A vault without .git (or no vault yet) is none,
  # so the setting never claims git the folder does not have.
  if [ "$TOLLGATE_NONINTERACTIVE" = "1" ] && [ "$VAULT_GIT" != "none" ] && [ ! -e "$VAULT_DIR/.git" ]; then
    VAULT_GIT="none"
  fi
fi
_vg_tmp="$TOLLGATE_PATHS.tmp.$$"
{ grep -v '^[[:space:]]*vault_git[[:space:]]*:' "$TOLLGATE_PATHS" 2>/dev/null || true; echo "vault_git: $VAULT_GIT"; } > "$_vg_tmp"
mv "$_vg_tmp" "$TOLLGATE_PATHS"
VAULT_GIT_INIT_DONE=0
if [ "$VAULT_GIT" != "none" ] && [ ! -e "$VAULT_DIR/.git" ]; then
  _vg_init="y"
  if [ -z "$VAULT_GIT_EXPLICIT" ] && [ "$TOLLGATE_NONINTERACTIVE" = "1" ]; then _vg_init="n"; fi
  if [ "$_vg_init" = "y" ] && [ -z "$VAULT_GIT_EXPLICIT" ]; then
    _vg_init=$(ask "Your vault is not a git repo yet. Run git init on it? (y/n)" "y")
  fi
  case "$_vg_init" in
    y|Y|yes|YES|Yes)
      mkdir -p "$VAULT_DIR"
      if git init -q "$VAULT_DIR" >/dev/null 2>&1; then
        VAULT_GIT_INIT_DONE=1
        ok "Vault is now a git repo: $VAULT_DIR"
      else
        note "Could not run git init on $VAULT_DIR. Run it yourself when git is available."
      fi ;;
    *) note "Vault left without git. Run: git -C \"$VAULT_DIR\" init" ;;
  esac
fi
if [ "$VAULT_GIT" = "remote" ]; then
  note "Add your remote yourself: git -C \"$VAULT_DIR\" remote add origin <your-url>. Tollgate never adds one or pushes."
fi
ok "Vault git setting: $VAULT_GIT"

# ── Step 3: Create Folder Structure ──────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 3: Creating Folders"
  echo ""
fi

# The folder list comes from scripts/core/paths.py, the one table of vault folder names.
if ! _layout_out=$(TOLLGATE_KNOWLEDGE="$VAULT_DIR" TOLLGATE_PATHS="$TOLLGATE_PATHS" \
      python3 "$REPO_DIR/scripts/core/paths.py" dirs 2>&1) || [ -z "$_layout_out" ]; then
  echo "  Could not read the vault folder list from scripts/core/paths.py (needs python3 3.12+)." >&2
  echo "  ${_layout_out:-no output}" >&2
  exit 1
fi

mkdir -p "$VAULT_DIR"
while IFS= read -r dir; do
  [ -n "$dir" ] || continue
  mkdir -p "$VAULT_DIR/$dir"
  [ "$SIMPLE_MODE" = false ] && ok "$dir"
done <<< "$_layout_out"
[ "$SIMPLE_MODE" = true ] && ok "Notes folder ready: $VAULT_DIR"

mkdir -p "$CODE_DIR" "$DEV_DIR"

# Advanced only: optional scripts git tracking and read-only repo sync
if [ "$SIMPLE_MODE" = false ]; then
  echo ""
  echo "  ${FOLDER_STEM}-scripts/ — your personal reusable scripts folder"
  dim "  Optional: back this up with git so your scripts are version controlled and recoverable."
  SCRIPTS_GIT=""
  read -rp "  Track scripts with git? [y/N]: " SCRIPTS_GIT
  echo ""
  if [[ "$SCRIPTS_GIT" =~ ^[Yy]$ ]]; then
    if ! command -v git &>/dev/null; then
      note "git not found — skipping scripts git tracking. Install git and re-run install.sh."
    elif [ ! -d "$SCRIPTS_DIR/.git" ]; then
      git -C "$SCRIPTS_DIR" init
      ok "Git initialized in ${FOLDER_STEM}-scripts"
    else
      ok "Git already initialized in ${FOLDER_STEM}-scripts"
    fi
    cat > "$SCRIPTS_DIR/.gitignore" << 'GITIGNORE'
__pycache__/
*.pyc
*.pyo
.env
*.log
.DS_Store
*.credentials
*.key
GITIGNORE
    ok "Created .gitignore for scripts"
    dim "  Paste the GitHub repo URL where your scripts should be pushed (e.g. https://github.com/you/my-scripts)."
    dim "  This is for YOUR scripts repo — not a company repo you read from."
    SCRIPTS_REMOTE=$(ask "  GitHub repo URL for scripts (Enter to skip)" "")
    if [ -n "$SCRIPTS_REMOTE" ]; then
      if git -C "$SCRIPTS_DIR" remote get-url origin &>/dev/null; then
        git -C "$SCRIPTS_DIR" remote set-url origin "$SCRIPTS_REMOTE"
      else
        git -C "$SCRIPTS_DIR" remote add origin "$SCRIPTS_REMOTE"
      fi
      ok "Remote set: $SCRIPTS_REMOTE"
    fi
  else
    ok "Scripts folder created (no git tracking)"
  fi

  echo ""
  echo "  Code repo directories (read-only source + active dev)"
  echo ""
  info "  ${FOLDER_STEM}-code/  →  read-only mirror. Claude reads your company repos here"
  info "                            for design validation. You never edit files here."
  info "  ${FOLDER_STEM}-dev/   →  your active working checkouts. All feature branch"
  info "                            work happens here."
  echo ""
  echo "  Which company repos do you want mirrored into ${FOLDER_STEM}-code/ (read-only)?"
  dim "  These are repos you need Claude to read for context — e.g. your data platform repo."
  dim "  Enter full GitHub clone URLs, one per line. Press Enter on a blank line when done."
  echo ""
  SYNC_REPOS=()
  while true; do
    read -rp "  Repo URL (or Enter to finish): " _repo_url
    [ -z "$_repo_url" ] && break
    SYNC_REPOS+=("$_repo_url")
  done
  if [ "${#SYNC_REPOS[@]}" -gt 0 ]; then
    if ! command -v git &>/dev/null; then
      note "git not found — skipping repo clone. Install git and re-run install.sh."
    fi
    echo ""
    note "Cloning repos into ${CODE_DIR}..."
    for _url in "${SYNC_REPOS[@]}"; do
      _repo_name=$(basename "$_url" .git)
      if [ -d "${CODE_DIR}/${_repo_name}/.git" ]; then
        git -C "${CODE_DIR}/${_repo_name}" pull --quiet
        ok "Updated: $_repo_name"
      else
        git clone --quiet "$_url" "${CODE_DIR}/${_repo_name}"
        ok "Cloned: $_repo_name"
      fi
    done
  else
    note "No repos cloned. Add later: git clone <url> ${CODE_DIR}/<repo-name>"
  fi
fi

# ── Step 4: Install Claude Code Config ───────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 4: Installing Claude Code Config"
  echo ""
fi

# Claude Code names a project folder after its path with every character that is not a letter or
# digit turned into "-" (so "/", "." and "_" all become "-").
SLUG=$(printf '%s' "$REPO_DIR" | sed 's|[^A-Za-z0-9]|-|g')
MEMORY_TARGET="$CLAUDE_DIR/projects/$SLUG/memory"

mkdir -p "$CLAUDE_DIR" "$(dirname "$MEMORY_TARGET")"

# Global settings (hooks, permissions, env) are merged near the end of the
# install, once every path including CODE_DIR is known. See "Merge settings".

symlink "$REPO_DIR/memory" "$MEMORY_TARGET"

# Escape user-supplied strings before embedding in sed replacement positions.
# & means "matched text" in sed replacements; | closes our delimiter; \ is the escape char.
USER_NAME_ESC=$(_sed_escape "$USER_NAME")
USER_TITLE_ESC=$(_sed_escape "$USER_TITLE")
USER_COMPANY_ESC=$(_sed_escape "$USER_COMPANY")
USER_DOMAIN_ESC=$(_sed_escape "$USER_DOMAIN")
TOLLGATE_HOME_ESC=$(_sed_escape "$TOLLGATE_HOME")

# Placeholders from before the fixed tg- names (a guard only: shipped files no longer use them).
_LEGACY_SED=(-e "s|{prefix}-|tg-|g" -e "s|{PREFIX_UPPER}_|TOLLGATE_|g" -e "s|{SKILL_PREFIX}|tg|g")

# Install commands as shipped: commands/tg-*.md go to ~/.claude/commands/ under the same name.
mkdir -p "$CLAUDE_DIR/commands" "$TG_STATE_DIR"
INSTALLED_COMMANDS=()
for src_file in "$REPO_DIR/commands/"*.md; do
  dest_name=$(basename "$src_file")
  _tmp="$CLAUDE_DIR/commands/.$dest_name.tollgate-tmp"
  sed \
    "${_LEGACY_SED[@]}" \
    -e "s|{NAME}|${USER_NAME_ESC}|g" \
    -e "s|{COMPANY}|${USER_COMPANY_ESC}|g" \
    -e "s|[\$]TOLLGATE_HOME/|${TOLLGATE_HOME_ESC}/|g" \
    "$src_file" > "$_tmp"
  install_rendered "$_tmp" "$CLAUDE_DIR/commands/$dest_name"
  INSTALLED_COMMANDS+=("$dest_name")
  [ "$SIMPLE_MODE" = false ] && ok "Installed: $dest_name"
done
# Record what was installed. Command files recorded earlier that this version no longer ships
# (dropped, or installed under an older prefixed or unprefixed name) are moved to a backup folder.
# Only names the manifest lists are ever removed; a command file of the user's own is never touched.
python3 "$REPO_DIR/installer/manifest.py" sync-commands --manifest "$MANIFEST" \
  --commands-dir "$CLAUDE_DIR/commands" \
  --backup-dir "$TG_STATE_DIR/removed/removed.$(date +%Y%m%d%H%M%S)" \
  --version "$TOLLGATE_VERSION" ${INSTALLED_COMMANDS[@]+"${INSTALLED_COMMANDS[@]}"}
[ "$SIMPLE_MODE" = true ] && ok "Commands installed"

# Cursor rules — each rule is independently toggled
# Disabled rules are stored as .mdc.disabled so users can re-enable without re-running install.sh
if [ -d "$REPO_DIR/cursor-rules" ]; then
  CURSOR_RULES_DEST="$VAULT_DIR/.cursor/rules"
  CURSOR_RULES_DISABLED="$VAULT_DIR/.cursor/rules-disabled"
  mkdir -p "$CURSOR_RULES_DEST" "$CURSOR_RULES_DISABLED"

  _apply_cursor_rule() {
    local src_file="$1" dest="$2"
    # Rendered beside the target, then moved in. An existing different file is backed up first.
    sed \
      "${_LEGACY_SED[@]}" \
      -e "s|\[YOUR NAME\]|${USER_NAME_ESC}|g" \
      -e "s|\[YOUR TITLE\]|${USER_TITLE_ESC}|g" \
      -e "s|\[YOUR COMPANY\]|${USER_COMPANY_ESC}|g" \
      -e "s|Health AI\. PHI/PII rules apply at all times, no exceptions\.|${USER_DOMAIN_ESC}. PHI/PII rules apply at all times, no exceptions.|g" \
      "$src_file" > "$dest.tollgate-tmp"
    install_rendered "$dest.tollgate-tmp" "$dest"
  }

  if [ "$SIMPLE_MODE" = true ]; then
    # Quick mode: install all rules enabled
    for src_file in "$REPO_DIR/cursor-rules/"*.mdc; do
      [ -f "$src_file" ] || continue
      base=$(basename "$src_file")
      _apply_cursor_rule "$src_file" "$CURSOR_RULES_DEST/$base"
    done
    ok "Cursor rules installed (all enabled)"
  else
    echo ""
    echo "  Cursor rules — choose which to enable"
    dim "  Rules that are off are saved to rules-disabled/ and can be moved back any time."
    echo ""

    _RULE_CHOICES=()
    for src_file in "$REPO_DIR/cursor-rules/"*.mdc; do
      [ -f "$src_file" ] || continue
      base=$(basename "$src_file" .mdc)
      # Extract description from frontmatter
      _desc=$(grep -m1 "^description:" "$src_file" 2>/dev/null | sed 's/^description: *//' | tr -d '"' || echo "$base")
      printf "  Enable %-22s %s\n" "$base" "$_desc"
      read -rp "  [Y/n]: " _rule_yn
      _rule_yn="${_rule_yn:-y}"
      _RULE_CHOICES+=("$(basename "$src_file"):${_rule_yn}")
    done

    echo ""
    for _entry in "${_RULE_CHOICES[@]}"; do
      _rfile="${_entry%%:*}"
      _yn="${_entry##*:}"
      src_file="$REPO_DIR/cursor-rules/$_rfile"
      if [[ "$_yn" =~ ^[Yy] ]]; then
        _apply_cursor_rule "$src_file" "$CURSOR_RULES_DEST/$_rfile"
        ok "Cursor rule enabled:  $_rfile"
      else
        _apply_cursor_rule "$src_file" "$CURSOR_RULES_DISABLED/$_rfile"
        note "Cursor rule disabled: $_rfile  (saved to rules-disabled/)"
      fi
    done
    dim "  To toggle later: move .mdc files between .cursor/rules/ and .cursor/rules-disabled/"
  fi
fi

# Custom skills from a migration are already in ~/.claude/commands, which is never wiped in
# migrate mode. They are left exactly where they are: nothing is copied into this repo, and they are
# not in the manifest, so an update or --uninstall never removes them.
if [ "$INSTALL_MODE" = "migrate" ] && [ "${#CUSTOM_SKILLS[@]}" -gt 0 ]; then
  for _cf in "${CUSTOM_SKILLS[@]}"; do
    ok "Kept custom skill: $(basename "$_cf")"
  done
fi

# Your own memory is never copied into this repo. If a memory folder already existed where the
# link now goes, it was moved aside as <name>.bak.<time> by the link step above.

WORKSPACE_FILE="$BASE_DIR/${FOLDER_STEM}.code-workspace"

# ── Step 5: Write CLAUDE.md ───────────────────────────────────────────────────

CLAUDE_DEST="$CLAUDE_DIR/CLAUDE.md"

CODE_DIR_ESC=$(_sed_escape "$CODE_DIR")
DEV_DIR_ESC=$(_sed_escape "$DEV_DIR")
VAULT_DIR_ESC=$(_sed_escape "$VAULT_DIR")
SCRIPTS_DIR_ESC=$(_sed_escape "$SCRIPTS_DIR")
MEETINGS_DIR_ESC=$(_sed_escape "$MEETINGS_DIR")
DOTFILES_DIR_ESC=$(_sed_escape "$DOTFILES_DIR")
WORKSPACE_FILE_ESC=$(_sed_escape "$WORKSPACE_FILE")
sed \
  -e "s|\[YOUR NAME\]|${USER_NAME_ESC}|g" \
  -e "s|\[YOUR TITLE\]|${USER_TITLE_ESC}|g" \
  -e "s|\[YOUR COMPANY\]|${USER_COMPANY_ESC}|g" \
  -e "s|Health AI\. PHI/PII rules apply at all times, no exceptions\.|${USER_DOMAIN_ESC}. PHI/PII rules apply at all times, no exceptions.|g" \
  "${_LEGACY_SED[@]}" \
  -e "s|{CODE_DIR}|${CODE_DIR_ESC}|g" \
  -e "s|{DEV_DIR}|${DEV_DIR_ESC}|g" \
  -e "s|{VAULT_DIR}|${VAULT_DIR_ESC}|g" \
  -e "s|{SCRIPTS_DIR}|${SCRIPTS_DIR_ESC}|g" \
  -e "s|{MEETINGS_DIR}|${MEETINGS_DIR_ESC}|g" \
  -e "s|{DOTFILES_DIR}|${DOTFILES_DIR_ESC}|g" \
  -e "s|{WORKSPACE_FILE}|${WORKSPACE_FILE_ESC}|g" \
  "$REPO_DIR/CLAUDE.md" > "$CLAUDE_DEST.tollgate-tmp"
install_rendered "$CLAUDE_DEST.tollgate-tmp" "$CLAUDE_DEST"

ok "Profile written for $USER_NAME"

# Optional: read-only code reference directory for path guard hook
# In simple mode, CODE_DIR is already set to the auto-derived path from Step 2.
# In advanced mode, the user can override with any path.
if [ "$SIMPLE_MODE" = false ]; then
  CODE_DIR=""
  echo ""
  note "Code reference directory (optional):"
  dim "  A read-only directory Claude should never write to (e.g. a local mirror of your repos at latest main)."
  dim "  The path guard hook blocks any write to this path. Leave blank to skip."
  read -rp "  Code reference directory [blank to skip]: " _code_dir_input
  CODE_DIR="${_code_dir_input:-}"
  if [ -n "$CODE_DIR" ] && [ ! -d "$CODE_DIR" ]; then
    note "Directory not found — skipping code reference guard."
    CODE_DIR=""
  fi
fi
echo "CODE_DIR=\"$(_dq "${CODE_DIR:-}")\"" >> "$TOLLGATE_CONFIG"

# ── Step 6: Service Connections ───────────────────────────────────────────────
if [ "$SIMPLE_MODE" = true ]; then
  header "Connect Your Services"
  echo ""
  echo "  Connect the tools you use every day."
  echo "  Browser sign-in is easiest — just click through the login page that opens."
  echo "  You can skip any service and add it later by re-running install.sh."
else
  header "Step 6: Service Connections"
  echo ""
  dim "For each service, choose browser sign-in, paste an API key, or skip."
fi

ATLASSIAN_METHOD="skip"
SLACK_METHOD="skip"
NOTION_METHOD="skip"

ATLASSIAN_URL=""
ATLASSIAN_USERNAME=""
ATLASSIAN_API_TOKEN=""
SLACK_BOT_TOKEN=""
SLACK_TEAM_ID=""
NOTION_TOKEN=""

# ── Jira + Confluence ─────────────────────────────────────────────────────────
echo ""
echo "  ── Jira and Confluence ──"
if [ "$SIMPLE_MODE" = true ]; then
  echo "  Sign in to read your tickets and look up company docs from inside Claude."
else
  dim "  Browser sign-in: no key needed."
  dim "  API key: create one at id.atlassian.com/manage-profile/security/api-tokens"
fi

choose_connection "Jira and Confluence" "yes"
ATLASSIAN_METHOD="$CONNECTION_CHOICE"

if [ "$ATLASSIAN_METHOD" = "api" ]; then
  echo ""
  ATLASSIAN_URL=$(ask "  Your Atlassian URL (e.g. https://yourcompany.atlassian.net)" "")
  ATLASSIAN_USERNAME=$(ask "  Your Atlassian login email" "$GIT_EMAIL")
  ATLASSIAN_API_TOKEN=$(ask_secret "  API key (from id.atlassian.com/manage-profile/security/api-tokens)" "atlassian-api-token")
  echo ""
  cred_store "atlassian-url"       "$ATLASSIAN_URL"
  cred_store "atlassian-username"  "$ATLASSIAN_USERNAME"
  cred_store "atlassian-api-token" "$ATLASSIAN_API_TOKEN"
elif [ "$ATLASSIAN_METHOD" = "mcp" ]; then
  ok "Jira and Confluence: a login page will open the first time Claude needs them."
else
  note "Jira and Confluence: skipped. Re-run install.sh to add later."
fi

# ── Notion ────────────────────────────────────────────────────────────────────
echo ""
echo "  ── Notion ──"
if [ "$SIMPLE_MODE" = true ]; then
  echo "  Sign in to let Claude read and reference your Notion pages."
else
  dim "  Browser sign-in: no key needed."
  dim "  API key: create one at notion.so/my-integrations"
fi

choose_connection "Notion" "yes"
NOTION_METHOD="$CONNECTION_CHOICE"

if [ "$NOTION_METHOD" = "api" ]; then
  echo ""
  NOTION_TOKEN=$(ask_secret "  Notion integration key (from notion.so/my-integrations, starts with secret_)" "notion-token")
  echo ""
  cred_store "notion-token" "$NOTION_TOKEN"
elif [ "$NOTION_METHOD" = "mcp" ]; then
  ok "Notion: a login page will open the first time Claude needs it."
else
  note "Notion: skipped. Re-run install.sh to add later."
fi

# ── Slack ─────────────────────────────────────────────────────────────────────
echo ""
echo "  ── Slack ──"
if [ "$SIMPLE_MODE" = true ]; then
  echo "  Lets Claude search your Slack messages for context."
  echo "  Note: the npm package is unsupported (no longer supported), kept for now. Needs a bot key from your Slack admin."
  echo "  Skip this if you don't have one — ask your Slack admin for help."
else
  dim "  Requires a bot token (xoxb-...) from your Slack workspace admin."
  dim "  Note: the npm package is unsupported (no longer supported), kept for now. No browser sign-in option."
  dim "  Admin guide: api.slack.com/apps"
fi

choose_connection "Slack" "no"
SLACK_METHOD="$CONNECTION_CHOICE"

if [ "$SLACK_METHOD" = "api" ]; then
  echo ""
  SLACK_BOT_TOKEN=$(ask_secret "  Slack Bot Token (starts with xoxb-)" "slack-bot-token")
  SLACK_TEAM_ID=$(ask          "  Slack Team ID (the T... code from your Slack URL)" "")
  echo ""
  cred_store "slack-bot-token" "$SLACK_BOT_TOKEN"
  cred_store "slack-team-id"   "$SLACK_TEAM_ID"
else
  note "Slack: skipped. Re-run install.sh to add later."
fi

# ── Credentials loader ────────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 7: Credentials Loader"
  echo ""
fi

cat > "$CREDS_SCRIPT" << 'CREDS'
#!/usr/bin/env bash
# credentials.sh — Cross-platform credential loader.
# Reads tokens from the OS credential store and exports as env vars.
# Sourced by the shell profile and by MCP server launch commands.
# Never edit manually. Re-run install.sh to add or rotate tokens.

_OS="$(uname -s)"
_KC="tollgate"

_kv() {
  local key="${_KC}-$1"
  case "$_OS" in
    Darwin)
      security find-generic-password -a "$USER" -s "$key" -w 2>/dev/null || true
      ;;
    Linux)
      if command -v secret-tool &>/dev/null; then
        secret-tool lookup service "$key" account "$USER" 2>/dev/null || true
      fi
      ;;
    MINGW*|CYGWIN*|MSYS*)
      powershell -Command \
        "(Get-StoredCredential -Target '${key}').GetNetworkCredential().Password" \
        2>/dev/null || true
      ;;
  esac
}

_ATL_URL="$(_kv atlassian-url)"
_ATL_USER="$(_kv atlassian-username)"
_ATL_TOKEN="$(_kv atlassian-api-token)"
_SLACK_BOT="$(_kv slack-bot-token)"
_SLACK_TEAM="$(_kv slack-team-id)"
_NOTION="$(_kv notion-token)"

[ -n "$_ATL_URL" ]    && export JIRA_URL="$_ATL_URL" CONFLUENCE_URL="${_ATL_URL}/wiki"
[ -n "$_ATL_USER" ]   && export JIRA_USERNAME="$_ATL_USER" CONFLUENCE_USERNAME="$_ATL_USER" ATLASSIAN_USERNAME="$_ATL_USER"
[ -n "$_ATL_TOKEN" ]  && export JIRA_API_TOKEN="$_ATL_TOKEN" CONFLUENCE_API_TOKEN="$_ATL_TOKEN" ATLASSIAN_API_TOKEN="$_ATL_TOKEN"
[ -n "$_SLACK_BOT" ]  && export SLACK_BOT_TOKEN="$_SLACK_BOT"
[ -n "$_SLACK_TEAM" ] && export SLACK_TEAM_ID="$_SLACK_TEAM"
[ -n "$_NOTION" ]     && export NOTION_API_KEY="$_NOTION" NOTION_API_TOKEN="$_NOTION"

unset _ATL_URL _ATL_USER _ATL_TOKEN _SLACK_BOT _SLACK_TEAM _NOTION _OS _KC
CREDS

chmod +x "$CREDS_SCRIPT"
ok "Credentials configured (tokens stored in your system keychain, not in files)"

# ── MCP Server Config ─────────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 8: MCP Server Config"
  echo ""
fi

# Register servers with the Claude Code CLI at user scope so they apply in
# every workspace. Browser sign-in uses Claude Code's native HTTP transport
# (OAuth on first use, no Node needed). API-key servers run through npx.
ATLASSIAN_MCP_URL="https://mcp.atlassian.com/v1/mcp"
NOTION_MCP_URL="https://mcp.notion.com/mcp"
CREDS_SOURCE="source \"\$HOME/.claude/credentials.sh\" 2>/dev/null"
# npx packages are pinned to exact versions on purpose: an unpinned name would run
# whatever was last published, with the stored keys in its environment. To bump one,
# pick a release at least 14 days old (npm view <pkg> time --json), edit the version
# here, and re-run tests/installer/run.sh. -y only skips the install prompt.
MCP_REMOTE_PKG="mcp-remote@0.16.5"
NOTION_MCP_PKG="@notionhq/notion-mcp-server@2.6.1"
SLACK_MCP_PKG="@modelcontextprotocol/server-slack@2025.4.25"

_mcp_register() {
  local name="$1"; shift
  claude mcp remove --scope user "$name" >/dev/null 2>&1 || true
  if claude mcp add --scope user "$name" "$@" >/dev/null 2>&1; then
    ok "Connected $name (all workspaces)"
  else
    note "Could not register $name. Run later: claude mcp add --scope user $name $*"
  fi
}

_mcp_register_npx() {
  local name="$1" package="$2"
  if ! command -v npx >/dev/null 2>&1; then
    note "$name needs Node.js (npx not found). Install Node, then re-run install.sh."
    return
  fi
  _mcp_register "$name" -- /bin/bash -c "${CREDS_SOURCE}; exec npx -y ${package}"
}

if ! command -v claude >/dev/null 2>&1; then
  note "Claude Code CLI not found, so services were not connected."
  note "Install Claude Code, then re-run install.sh to connect Jira, Notion, and Slack."
else
  case "$ATLASSIAN_METHOD" in
    mcp) _mcp_register atlassian --transport http "$ATLASSIAN_MCP_URL" ;;
    api) _mcp_register_npx atlassian "${MCP_REMOTE_PKG} ${ATLASSIAN_MCP_URL}" ;;
  esac
  case "$NOTION_METHOD" in
    mcp) _mcp_register notion --transport http "$NOTION_MCP_URL" ;;
    api) _mcp_register_npx notion "$NOTION_MCP_PKG" ;;
  esac
  [ "$SLACK_METHOD" = "api" ] && _mcp_register_npx slack "$SLACK_MCP_PKG"
  ok "Service connections saved"
fi

# ── Shell Profile ─────────────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 9: Shell Profile"
  echo ""
fi

# Pick the file the user's login shell actually reads. zsh ignores ~/.profile,
# and macOS Terminal starts bash as a login shell, which reads ~/.bash_profile.
case "$(basename "${SHELL:-}")" in
  zsh)  SHELL_PROFILE="$HOME/.zshrc" ;;
  bash) if [ "$(uname)" = "Darwin" ]; then SHELL_PROFILE="$HOME/.bash_profile"
        else SHELL_PROFILE="$HOME/.bashrc"; fi ;;
  *)    SHELL_PROFILE="$HOME/.profile" ;;
esac

# The block starts with "# Tollgate (" so blocks written by older installs, which read
# "# Tollgate (prefix: xx)", are still found, replaced and removed. The new marker has no prefix.
ENV_BLOCK="# Tollgate (managed block)
export TOLLGATE_MEETINGS=\"$(_dq "${MEETINGS_DIR}")\"
export TOLLGATE_SCRIPTS=\"$(_dq "${SCRIPTS_DIR}")\"
export TOLLGATE_KNOWLEDGE=\"$(_dq "${VAULT_DIR}")\"
export CLAUDE_DOTFILES=\"$(_dq "${REPO_DIR}")\"
export TOLLGATE_CODE_DIR=\"$(_dq "${CODE_DIR:-}")\"
export TOLLGATE_INITIALS=\"${USER_INITIALS}\"
export TOLLGATE_TICKET_PREFIX=\"${TICKET_PREFIX}\"
export TOLLGATE_HOME=\"$(_dq "${TOLLGATE_HOME}")\"
export TOLLGATE_PATHS=\"$(_dq "${TOLLGATE_PATHS}")\"
export TOLLGATE_CONNECTORS=\"$(_dq "${TOLLGATE_CONNECTORS}")\"
[ -f \"\$HOME/.claude/credentials.sh\" ] && source \"\$HOME/.claude/credentials.sh\""

# Replace any earlier Tollgate block (here or in a profile an older install
# chose) so re-runs pick up moved paths instead of keeping stale values.
_strip_tollgate_block() {
  [ -f "$1" ] || return 0
  grep -q "^# Tollgate (" "$1" || return 0
  cp "$1" "$1.bak.$(date +%Y%m%d%H%M%S)"
  prune_bak "$1"
  sed -i.tollgate-tmp '/^# Tollgate (/,/credentials\.sh/d' "$1" && rm -f "$1.tollgate-tmp"
}
_block_in() { sed -n '/^# Tollgate (/,/credentials\.sh/p' "$1" 2>/dev/null; }
_block_elsewhere=0
for _profile in "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc" "$HOME/.profile"; do
  [ "$_profile" != "$SHELL_PROFILE" ] && [ -f "$_profile" ] \
    && grep -q "^# Tollgate (" "$_profile" && _block_elsewhere=1
done
if [ "$_block_elsewhere" = 0 ] && [ -f "$SHELL_PROFILE" ] \
   && [ "$(_block_in "$SHELL_PROFILE")" = "$ENV_BLOCK" ]; then
  ok "Shell profile already up to date: $SHELL_PROFILE"
else
  for _profile in "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc" "$HOME/.profile"; do
    _strip_tollgate_block "$_profile"
  done
  touch "$SHELL_PROFILE"
  printf '\n%s\n' "$ENV_BLOCK" >> "$SHELL_PROFILE"
  ok "Shell profile updated: $SHELL_PROFILE"
fi

# ── Python environment, vault search index and nightly job ────────────────────
# One function holds the search steps so a later change can swap them out in one place.
SEARCH_PYTHON=""   # the venv python, set when a venv exists; passed to settings as TOLLGATE_PYTHON

# The venv lives where scripts/core/setup_venv.sh puts it: <state folder>/venv.
_venv_dir() {
  local state
  state="$(TOLLGATE_PATHS="$TOLLGATE_PATHS" TOLLGATE_KNOWLEDGE="$VAULT_DIR" \
    "$REPO_DIR/scripts/core/tg_path" state 2>/dev/null)" || return 1
  printf '%s/venv' "$state"
}

# Offer the local embedding model (better search than the built-in embedder). Default yes when asked.
# Non-interactive runs skip it unless TOLLGATE_DOWNLOAD_MODEL=1, so automated runs never use the network.
# TOLLGATE_DOWNLOAD_MODEL=0 always skips. A failure prints one line and the install goes on with the
# built-in embedder, which needs no download.
offer_local_model() {
  local venv_py="$1" _want="" _model_input=""
  case "${TOLLGATE_DOWNLOAD_MODEL:-}" in
    0) dim "  Local embedding model: skipped (TOLLGATE_DOWNLOAD_MODEL=0). Using the built-in embedder."; return 0 ;;
    1) _want=yes ;;
  esac
  if [ -z "$_want" ]; then
    if [ "$TOLLGATE_NONINTERACTIVE" = "1" ]; then
      dim "  Local embedding model: skipped (non-interactive). Using the built-in embedder."
      return 0
    fi
    echo ""
    echo "  ── Local search model (optional) ──"
    echo "  Installs sentence-transformers and downloads an embedding model once (needs the network,"
    echo "  several hundred MB). Search is more accurate with it. Without it, a built-in embedder is used."
    read -rp "  Install the local model now? [Y/n]: " _model_input || true
    case "${_model_input:-y}" in [Nn]*) dim "  Using the built-in embedder."; return 0 ;; esac
  fi
  note "Installing sentence-transformers and downloading the model (this may take several minutes)..."
  if "$venv_py" -m pip install --quiet sentence-transformers \
     && "$venv_py" "$REPO_DIR/scripts/search/download_model.py" --yes-download; then
    ok "Local embedding model ready"
  else
    note "Could not install or download the local model. Continuing with the built-in embedder."
    dim "  Retry later: $venv_py $REPO_DIR/scripts/search/download_model.py --yes-download"
  fi
}

build_search_index() {
  local venv_dir venv_py
  if ! command -v python3 &>/dev/null; then
    note "Python 3 not found - skipping vault search setup. Install Python 3.12+ and re-run install.sh."
    return 0
  fi
  note "Creating the Python environment and installing scripts/requirements.txt (this may take a minute)..."
  if ! TOLLGATE_PATHS="$TOLLGATE_PATHS" TOLLGATE_KNOWLEDGE="$VAULT_DIR" \
       bash "$REPO_DIR/scripts/core/setup_venv.sh"; then
    note "Could not set up the Python environment - skipping vault search."
    note "Fix Python and re-run install.sh to add it later."
    return 0
  fi
  venv_dir="$(_venv_dir)" || { note "Could not find the venv folder - skipping vault search."; return 0; }
  venv_py="$venv_dir/bin/python3"
  SEARCH_PYTHON="$venv_py"
  ok "Search dependencies installed"
  offer_local_model "$venv_py"
  echo ""
  note "Building search index..."
  dim "  Index: $(TOLLGATE_PATHS="$TOLLGATE_PATHS" TOLLGATE_KNOWLEDGE="$VAULT_DIR" "$REPO_DIR/scripts/core/tg_path" index 2>/dev/null || echo "the index folder from your paths file")"
  echo ""
  TOLLGATE_PATHS="$TOLLGATE_PATHS" TOLLGATE_KNOWLEDGE="$VAULT_DIR" TOLLGATE_PYTHON="$venv_py" \
    bash "$REPO_DIR/scripts/search/rebuild.sh" \
    && ok "Search index built - Claude will search your notes automatically" \
    || note "Index build failed - re-run install.sh after fixing Python to retry."
}

DO_RAG=false
if [ "$SKIP_VENV" = 1 ]; then
  DO_RAG=false
elif [ "$WITH_VENV" = 1 ]; then
  DO_RAG=true
elif [ "$SIMPLE_MODE" = true ]; then
  echo ""
  echo "  ── Vault Search (optional) ──"
  echo "  Lets Claude automatically search your notes when you ask questions."
  echo "  Creates a Python environment and builds a search index of your notes (no model download)."
  echo ""
  read -rp "  Set this up now? [y/N]: " _rag_input || true
  [[ "${_rag_input:-n}" =~ ^[Yy]$ ]] && DO_RAG=true
else
  header "Step 10: Vault Search Index"
  echo ""
  dim "Creates the Python environment (scripts/requirements.txt) and builds the initial index."
  dim "Re-running is safe: only changed files are re-indexed. Skip with --skip-venv."
  echo ""
  DO_RAG=true
fi

if [ "$DO_RAG" = true ]; then
  build_search_index
fi
# A venv from an earlier run is reused even when this run skipped the step.
if [ -z "$SEARCH_PYTHON" ] && _existing_venv="$(_venv_dir)" && [ -x "$_existing_venv/bin/python3" ]; then
  SEARCH_PYTHON="$_existing_venv/bin/python3"
fi

# Nightly index job (macOS launchd). Never loaded without a yes or --with-cron.
setup_nightly_job() {
  if [ "$OS" != "Darwin" ]; then
    note "Nightly job: scheduling is macOS only. Skipped."
    return 0
  fi
  if ( export TOLLGATE_HOME="$TOLLGATE_HOME" TOLLGATE_PATHS="$TOLLGATE_PATHS" TOLLGATE_KNOWLEDGE="$VAULT_DIR"
       [ -z "$SEARCH_PYTHON" ] || export TOLLGATE_PYTHON="$SEARCH_PYTHON"
       python3 "$REPO_DIR/scripts/cron/setup_cron.py" --home "$HOME" --job nightly-index \
         --yes-install-job --launcher "${TOLLGATE_CRON_LAUNCHER:-launchctl}" ); then
    python3 "$REPO_DIR/installer/manifest.py" set-list --manifest "$MANIFEST" --key cron nightly-index
    ok "Nightly search-index job scheduled (2:00 AM)"
  else
    note "Could not schedule the nightly job. Run later: python3 $REPO_DIR/scripts/cron/setup_cron.py --home \"\$HOME\" --job nightly-index --yes-install-job"
  fi
}

DO_CRON=false
if [ "$WITH_CRON" = 1 ]; then
  DO_CRON=true
elif [ "$OS" = "Darwin" ] && [ "$SIMPLE_MODE" = true ]; then
  echo ""
  echo "  ── Nightly search update (optional) ──"
  echo "  Rebuilds your notes index every night at 2:00 AM, so search stays current."
  read -rp "  Schedule it now? [y/N]: " _cron_input || true
  [[ "${_cron_input:-n}" =~ ^[Yy]$ ]] && DO_CRON=true
fi
if [ "$DO_CRON" = true ]; then
  setup_nightly_job
fi

echo ""
if [ "$SIMPLE_MODE" = false ]; then
  note "Pre-commit secret protection hook:"
  dim "  Run in each repo: cp \"$REPO_DIR/hooks/pre-commit-secrets\" <repo>/.git/hooks/pre-commit && chmod +x <repo>/.git/hooks/pre-commit"
  echo ""
fi

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  You're all set."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
printf "  %-20s %s\n" "Name:"    "$USER_NAME"
printf "  %-20s %s\n" "Company:" "$USER_COMPANY"
printf "  %-20s %s\n" "Notes:"   "$VAULT_DIR"
printf "  %-20s %s\n" "Vault git:" "$VAULT_GIT"
echo ""
_conn_label() {
  case "$1" in
    mcp)  echo "Connected (browser sign-in)";;
    api)  echo "Connected (API key)";;
    skip) echo "Not connected — re-run install.sh to add";;
    *)    echo "$1";;
  esac
}
printf "  %-20s %s\n" "Jira / Confluence:" "$(_conn_label "$ATLASSIAN_METHOD")"
printf "  %-20s %s\n" "Notion:"            "$(_conn_label "$NOTION_METHOD")"
printf "  %-20s %s\n" "Slack:"             "$(_conn_label "$SLACK_METHOD")$([ "$SLACK_METHOD" = api ] && echo " (unsupported npm package, kept for now)")"
echo ""

[ "$ATLASSIAN_METHOD" = "mcp" ] && note "Jira: a login page will open the first time Claude accesses Jira."
[ "$NOTION_METHOD"   = "mcp" ] && note "Notion: a login page will open the first time Claude accesses Notion."

# ── VS Code workspace file ────────────────────────────────────────────────────
cat > "$WORKSPACE_FILE" << WORKSPACE
{
  "folders": [
    {
      "name": "${FOLDER_STEM}-knowledge (notes & vault)",
      "path": "${VAULT_DIR}"
    },
    {
      "name": "${FOLDER_STEM}-dotfiles (skills & config)",
      "path": "${REPO_DIR}"
    },
    {
      "name": "${FOLDER_STEM}-scripts (your scripts)",
      "path": "${SCRIPTS_DIR}"
    }
  ],
  "settings": {
    "files.exclude": {
      "**/__pycache__": true
    }
  }
}
WORKSPACE
ok "VS Code workspace created: $WORKSPACE_FILE"

# ── Merge settings ────────────────────────────────────────────────────────────
# Global settings carry the hooks, so they fire in every workspace, not only
# inside this repo. Paths are baked in as absolute values because Claude Code
# does not expand env vars in permission rules. The env block covers editors
# launched from the Dock, which do not load the shell profile.
# Merged, not overwritten: the user's own hooks, permissions, env, and other
# keys are kept (installer/merge_settings.py documents the rules).
chmod +x "$REPO_DIR"/hooks/*.py "$REPO_DIR"/hooks/*.sh 2>/dev/null || true
# The merge script makes the settings backup itself (settings.json.bak.<time>),
# only when the merge would change the file. Undo with: ./install.sh --restore-settings
_merge_extra=()
[ -z "$SEARCH_PYTHON" ] || _merge_extra=(--set "TOLLGATE_PYTHON=$SEARCH_PYTHON")
python3 "$REPO_DIR/installer/merge_settings.py" --backup --manifest "$MANIFEST" \
  ${_merge_extra[@]+"${_merge_extra[@]}"} \
  --set "TOLLGATE_INITIALS=$USER_INITIALS" \
  --set "TOLLGATE_TICKET_PREFIX=$TICKET_PREFIX" \
  --set "TOLLGATE_HOME=$TOLLGATE_HOME" \
  --set "TOLLGATE_PATHS=$TOLLGATE_PATHS" \
  --set "TOLLGATE_CONNECTORS=$TOLLGATE_CONNECTORS" \
  "$REPO_DIR/settings.json" "$CLAUDE_DIR/settings.json" \
  "$REPO_DIR" "$VAULT_DIR" "$SCRIPTS_DIR" "${CODE_DIR:-}"
ok "Settings merged (hooks active globally, your own settings kept)"

# Record which Tollgate version is installed (written only when it changes).
mkdir -p "$TG_STATE_DIR"
if [ "$(cat "$INSTALLED_VERSION_FILE" 2>/dev/null || true)" != "$TOLLGATE_VERSION" ]; then
  printf '%s\n' "$TOLLGATE_VERSION" > "$INSTALLED_VERSION_FILE"
fi

# ── Verify Claude Code hooks ──────────────────────────────────────────────────
# Hooks are defined in settings.json and merged globally above. Confirm
# every referenced hook exists and is executable; a missing PHI or secrets hook
# fails silently at runtime, so surface it here instead.
_hook_missing=$(python3 - "$CLAUDE_DIR/settings.json" <<'PYTHON'
import json, os, shlex, sys
settings = json.load(open(sys.argv[1]))
for groups in settings.get('hooks', {}).values():
    for group in groups:
        for hook in group.get('hooks', []):
            path = shlex.split(hook['command'])[0]
            if not os.access(path, os.X_OK):
                print(path)
PYTHON
)
if [ -z "$_hook_missing" ]; then
  ok "Claude Code hooks active in all workspaces"
  dim "  Hook paths point at ${REPO_DIR} — re-run install.sh after moving this directory"
else
  while IFS= read -r _hook; do note "Hook missing or not executable: $_hook"; done <<< "$_hook_missing"
  note "Some hooks will not run. PHI and secrets scanning may be off until fixed."
fi

echo ""
echo "  What to do next:"
echo ""
echo "    1.  Close this terminal and open a new one"
echo "        (or run:  source $SHELL_PROFILE)"
echo ""
echo "    2.  Open VS Code using your workspace file:"
echo "          code \"$WORKSPACE_FILE\""
echo "        Or: File → Open Workspace from File → $(basename "$WORKSPACE_FILE")"
echo ""
echo "    3.  In VS Code, type:  /start"
echo ""
if [ "$SIMPLE_MODE" = true ]; then
  echo "  To connect services you skipped, or to change any setting:"
  echo "    Re-run: ./install.sh"
  echo ""
else
  echo "  To re-index after adding notes:"
  echo "    TOLLGATE_PYTHON=\"${SEARCH_PYTHON:-python3}\" bash $REPO_DIR/scripts/search/rebuild.sh"
  echo ""
  echo "  To rotate or add tokens at any time:  ./install.sh"
  echo "  Worked example:  docs/walkthrough.md"
  echo ""
  echo "  If you move the Tollgate directory:"
  echo "    Re-run: ./install.sh  (updates hook paths automatically)"
  echo ""
fi
