#!/usr/bin/env bash
# Throwaway-home helper for the installer tests (sourced by test_ins.sh).
# Self-contained: it does not use any other test harness in this repo.
#
# Every install runs in a home folder made with mktemp, under a user name that is
# not the real one, against a COPY of the repo. The real ~/.claude, the real shell
# profile, the real keychain and the real repo are never touched.

# Optional: INSTALL_REPO (run another repo copy), RUN_PATH (replace PATH inside the run).
# Needs from the caller: WORK (a mktemp -d folder), TOLLGATE_DIR (repo root).

FAKE_USER="tg_tester_$$"

# One private copy of the repo per run. The installer writes a few files into the
# repo it runs from (memory folder, custom commands), so tests never run in the real one.
make_repo_copy() {
    local dest="$WORK/repo"
    [ -d "$dest" ] && return 0
    mkdir -p "$dest"
    tar -C "$TOLLGATE_DIR" --exclude=.git --exclude=__pycache__ -cf - . | tar -C "$dest" -xf -
}

# clone_repo NAME -> prints the path of another private copy of the repo (for tests that change the repo).
clone_repo() {
    local dest="$WORK/$1"
    mkdir -p "$dest"
    tar -C "$TOLLGATE_DIR" --exclude=.git --exclude=__pycache__ -cf - . | tar -C "$dest" -xf -
    echo "$dest"
}

# new_world NAME -> prints the home folder; also makes a stub `security` command so
# a stray keychain call can never reach the real one.
new_world() {
    local h="$WORK/$1/home"
    mkdir -p "$h/bin"
    printf '#!/bin/sh\necho "$@" >> "%s/security.log"\n' "$h" > "$h/bin/security"
    chmod +x "$h/bin/security"
    echo "$h"
}

# run_install HOME [installer args...]; stdin comes from $INSTALL_STDIN (default: closed).
# Output goes to HOME/../last.out. Returns the installer exit code.
run_install() {
    local h="$1"; shift
    local out="$h/../last.out"
    (
        unset TOLLGATE_CONFIG TOLLGATE_PATHS TOLLGATE_CONNECTORS TOLLGATE_KNOWLEDGE TOLLGATE_INITIALS \
              TOLLGATE_TICKET_PREFIX TOLLGATE_HOME TOLLGATE_NONINTERACTIVE TOLLGATE_CODE_DIR \
              TOLLGATE_SKILL_PREFIX CLAUDE_DOTFILES
        export HOME="$h" USER="$FAKE_USER" LOGNAME="$FAKE_USER" SHELL=/bin/zsh
        export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 PYTHONDONTWRITEBYTECODE=1
        export PATH="${RUN_PATH:-$h/bin:$PATH}"
        cd "$h" || exit 99
        if [ -n "${INSTALL_STDIN:-}" ]; then
            bash "${INSTALL_REPO:-$WORK/repo}/install.sh" "$@" < "$INSTALL_STDIN"
        else
            bash "${INSTALL_REPO:-$WORK/repo}/install.sh" "$@" < /dev/null
        fi
    ) > "$out" 2>&1
}

# snapshot HOME -> sorted "path checksum" lines for every file, leaving out the
# backup copies the installer makes on purpose (settings.json.bak.*, .claude.backup.*,
# profile .bak.*). Used to prove a second run changes nothing else.
snapshot() {
    local h="$1"
    ( cd "$h" && find . -type f \
        -not -path './.claude.backup.*' -not -name '*.bak.*' -not -name 'security.log' \
        -not -path './bin/*' | sort | while IFS= read -r f; do
            printf '%s %s\n' "$f" "$(cksum < "$f")"
        done )
}

# Compare JSON files by value, not by spacing. Prints "true" or "false".
json_equal() {
    python3 -I - "$1" "$2" <<'PY'
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
print("true" if a == b else "false")
PY
}

# Replace the throwaway home path in a file with <HOME> so two homes can be compared.
normalise() {
    python3 -I - "$1" "$2" <<'PY'
import sys
print(open(sys.argv[2]).read().replace(sys.argv[1], "<HOME>"), end="")
PY
}

# Write the user's own settings used by INS-03 and INS-05.
seed_user_settings() {
    mkdir -p "$1/.claude"
    cat > "$1/.claude/settings.json" <<'JSON'
{
  "model": "my-model",
  "env": {"MY_OWN_VAR": "keep-me"},
  "enabledPlugins": {"my-plugin@somewhere": true},
  "statusLine": {"type": "command", "command": "echo my-status"},
  "permissions": {"allow": ["Bash(echo my-allowed)"], "deny": ["Read(./my-secret-file)"]},
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 /home/me/my-own-hook.py"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "/home/me/stop.sh"}]}]
  }
}
JSON
}

# user_settings_survive SETTINGS_FILE -> "true" when every seeded user key is still there.
user_settings_survive() {
    python3 -I - "$1" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
cmds = [h["command"] for g in s["hooks"].get("UserPromptSubmit", []) for h in g["hooks"]]
stop = [h["command"] for g in s["hooks"].get("Stop", []) for h in g["hooks"]]
ok = (s.get("model") == "my-model"
      and s["env"].get("MY_OWN_VAR") == "keep-me"
      and s.get("enabledPlugins") == {"my-plugin@somewhere": True}
      and s.get("statusLine") == {"type": "command", "command": "echo my-status"}
      and "Bash(echo my-allowed)" in s["permissions"]["allow"]
      and "Read(./my-secret-file)" in s["permissions"]["deny"]
      and "python3 /home/me/my-own-hook.py" in cmds
      and stop == ["/home/me/stop.sh"])
print("true" if ok else "false")
PY
}
