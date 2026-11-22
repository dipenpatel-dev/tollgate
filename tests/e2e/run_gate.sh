#!/usr/bin/env bash
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: live test of the arch gate and the push guard through a real Claude Code session.
# Ticket: none (Tollgate is not Jira tracked)
# ChangeLog:
#   - Uses the fixed command name tg-arch (no skill prefix is read from settings).
#   - Created. Companion to run.sh, which does not reach the gate or the push guard.
#
# What it does:
#   1. Installs into a throwaway HOME (same as run.sh).
#   2. Makes a ticket folder in the fake vault with no spec, and a throwaway git repo
#      on main with a local bare remote.
#   3. Session A: `claude -p "/tg-arch <KEY>"`. The gate must block it.
#   4. Session B: asks the model to run `git push origin main`. The push guard must deny it.
#   5. check_gate.py asserts on the hook events in both streams.
# Cost: two short Claude sessions. Nothing real is touched; nothing leaves this machine.
# Usage: TOLLGATE_E2E_DIR=<empty folder> tests/e2e/run_gate.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${TOLLGATE_E2E_DIR:-$(mktemp -d /tmp/tollgate-e2e-gate.XXXXXX)}"
FAKE_HOME="$WORK/home"
SANDBOX="$WORK/sandbox"
TICKET="TG-900"
rm -rf "$FAKE_HOME" "$SANDBOX"
mkdir -p "$FAKE_HOME" "$SANDBOX"

echo "-- 1. install (non-interactive)"
env -i HOME="$FAKE_HOME" PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin" \
  SHELL=/bin/zsh TERM=dumb /bin/bash "$REPO_DIR/install.sh" --non-interactive > "$WORK/install.log" 2>&1 \
  || { echo "FAIL install.sh exited non-zero; see $WORK/install.log"; exit 1; }
SETTINGS="$FAKE_HOME/.claude/settings.json"
read_env() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['env'].get(sys.argv[2], ''))" "$SETTINGS" "$1"; }
VAULT="$(read_env TOLLGATE_KNOWLEDGE)"
echo "   vault=$VAULT"
[ -n "$VAULT" ] || { echo "FAIL no TOLLGATE_KNOWLEDGE in installed settings"; exit 1; }
CMD="tg-arch"   # fixed name: there is no per-install prefix

echo "-- 2. fixtures"
mkdir -p "$VAULT/02-tickets/$TICKET"
printf 'Status: NEW\n' > "$VAULT/02-tickets/$TICKET/$TICKET-state.md"
GITREPO="$SANDBOX/pushrepo"
git init -q -b main "$GITREPO"
git -C "$GITREPO" -c user.name=t -c user.email=t@example.invalid commit -q --allow-empty -m init
git init -q --bare "$SANDBOX/remote.git"
git -C "$GITREPO" remote add origin "$SANDBOX/remote.git"

# The session runs with the real HOME and project settings only, so the installed
# commands are made visible as project commands.
mkdir -p "$SANDBOX/.claude/commands"
cp "$FAKE_HOME/.claude/commands/"*.md "$SANDBOX/.claude/commands/"

echo "-- 3. session A: /$CMD $TICKET (gate)"
( cd "$SANDBOX" && claude -p "/$CMD $TICKET" --settings "$SETTINGS" --setting-sources project \
    --max-turns 3 --output-format stream-json --verbose --include-hook-events \
    --debug-file "$WORK/debugA.log" > "$WORK/streamA.jsonl" 2> "$WORK/claudeA.err" ) \
  || echo "   note: claude exited non-zero (assertions decide pass/fail)"

echo "-- 4. session B: git push origin main (push guard)"
PROMPT="Automated hook test. Run exactly one Bash command: git -C $GITREPO push origin main. If it is blocked or denied, do not retry. Reply with the first 10 words of any hook message."
( cd "$SANDBOX" && claude -p "$PROMPT" --settings "$SETTINGS" --setting-sources project \
    --allowedTools "Bash(git:*)" \
    --max-turns 5 --output-format stream-json --verbose --include-hook-events \
    --debug-file "$WORK/debugB.log" > "$WORK/streamB.jsonl" 2> "$WORK/claudeB.err" ) \
  || echo "   note: claude exited non-zero (assertions decide pass/fail)"

echo "-- 5. assertions"
python3 "$REPO_DIR/tests/e2e/check_gate.py" "$WORK" "$SANDBOX/remote.git" "$TICKET"
