#!/usr/bin/env bash
# Installer tests INS-00 to INS-11. Sourced by run.sh, which supplies check(),
# WORK and TOLLGATE_DIR. Every install runs in a throwaway home (see helpers.sh).

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"
make_repo_copy

echo "── INS installer answers, files and settings ───────────────────"

# The throwaway home must never be the real one.
_real_user="$(id -un)"
check "INS-00 test user is not the real user" "$([ "$FAKE_USER" != "$_real_user" ] && echo true || echo false)"

# ── INS-01 fresh install into an empty throwaway home ────────────────────────
H=$(new_world ins01)
VAULT="$WORK/ins01/vault"
run_install "$H" --non-interactive --name "Ada Tester" --vault "$VAULT" --initials at --ticket-prefix tk; rc=$?
check "INS-01 fresh install exits 0" "$([ $rc -eq 0 ] && echo true || echo false)"
_missing=""
for f in .claude/tollgate-config .claude/settings.json .claude/CLAUDE.md .claude/credentials.sh \
         .claude/tollgate/paths.yaml .claude/tollgate/connectors.yaml .zshrc \
         .claude/commands/tg-start.md; do
    [ -e "$H/$f" ] || _missing="$_missing $f"
done
# Commands install under their shipped tg- names; there is no per-install prefix.
[ -f "$H/.claude/commands/tg-ticket.md" ] || _missing="$_missing commands/tg-ticket.md"
for d in 00-landing 02-tickets 03-knowledge-base/decisions 06-chat-threads output; do
    [ -d "$VAULT/$d" ] || _missing="$_missing vault/$d"
done
[ -n "$(ls "$H"/Developer/*/*.code-workspace 2>/dev/null)" ] || _missing="$_missing workspace-file"
check "INS-01 every expected file and folder exists${_missing:+ (missing:$_missing)}" "$([ -z "$_missing" ] && echo true || echo false)"
check "INS-01 connectors file is empty, paths file holds only the references and vault_git lines" \
    "$([ -f "$H/.claude/tollgate/paths.yaml" ] && [ "$(grep -c . "$H/.claude/tollgate/paths.yaml")" = 2 ] \
       && grep -q '^references: ' "$H/.claude/tollgate/paths.yaml" && grep -q '^vault_git: ' "$H/.claude/tollgate/paths.yaml" \
       && [ -f "$H/.claude/tollgate/connectors.yaml" ] && [ ! -s "$H/.claude/tollgate/connectors.yaml" ] && echo true || echo false)"
_env_ok=$(python3 -I - "$H/.claude/settings.json" "$H" "$VAULT" <<'PY'
import json, sys
env = json.load(open(sys.argv[1]))["env"]; home = sys.argv[2]
want = {"TOLLGATE_KNOWLEDGE": sys.argv[3], "TOLLGATE_INITIALS": "AT", "TOLLGATE_TICKET_PREFIX": "TK",
        "TOLLGATE_PATHS": home + "/.claude/tollgate/paths.yaml",
        "TOLLGATE_CONNECTORS": home + "/.claude/tollgate/connectors.yaml"}
ok = all(env.get(k) == v for k, v in want.items()) and env.get("TOLLGATE_HOME") and env.get("CLAUDE_DOTFILES")
print("true" if ok else "false")
PY
)
check "INS-01 settings env block holds the new variables" "$_env_ok"
check "INS-01 shell profile exports the new variables" \
    "$(grep -q 'export TOLLGATE_INITIALS="AT"' "$H/.zshrc" && grep -q 'export TOLLGATE_TICKET_PREFIX="TK"' "$H/.zshrc" \
       && grep -q "export TOLLGATE_PATHS=" "$H/.zshrc" && echo true || echo false)"
check "INS-01 hooks in settings point into the repo copy" \
    "$(grep -q "$WORK/repo/hooks/" "$H/.claude/settings.json" && echo true || echo false)"
# The harness refuses a command with an unresolved variable, so the installed commands call tg-search by
# its absolute path, the same path the permission rule in settings holds.
check "INS-01 installed commands call tg-search by absolute path, no \$TOLLGATE_HOME left" \
    "$(grep -q "$WORK/repo/scripts/search/tg-search" "$H/.claude/commands/tg-retrieve.md" \
       && ! grep -q '\$TOLLGATE_HOME/scripts/search/tg-search' "$H/.claude/commands/tg-retrieve.md" \
       && grep -q "Bash($WORK/repo/scripts/search/tg-search:\*)" "$H/.claude/settings.json" && echo true || echo false)"
check "INS-01 nothing written outside the throwaway folder" \
    "$([ ! -e "$H/security.log" ] && echo true || echo false)"

# ── INS-02 flags give the same result as the questions ───────────────────────
# World A answers the questions from a pipe. World B gives the same answers as flags.
# Question order: start, advanced?, name, title, company, industry, initials, ticket
# prefix, notes folder, then Jira, Notion, Slack (skip), vault search (no).
HA=$(new_world ins02a); HB=$(new_world ins02b)
VAULT2="$WORK/ins02-vault"
{ printf '\n\n'; printf '%s\n' "Ada Tester" "" "" "" "ab" "tk" "$VAULT2" "" "n" "s" "s" "s" "n"; } > "$WORK/ins02.answers"
INSTALL_STDIN="$WORK/ins02.answers" run_install "$HA"; rcA=$?
run_install "$HB" --non-interactive --name "Ada Tester" --vault "$VAULT2" --initials AB --ticket-prefix tk; rcB=$?
check "INS-02 questions run exits 0" "$([ $rcA -eq 0 ] && echo true || echo false)"
check "INS-02 flags run exits 0 with stdin closed (no prompt waits)" "$([ $rcB -eq 0 ] && echo true || echo false)"
_same=true
for f in .claude/tollgate-config .claude/settings.json .zshrc .claude/CLAUDE.md; do
    if [ "$(normalise "$HA" "$HA/$f")" != "$(normalise "$HB" "$HB/$f")" ]; then _same=false; echo "  differs: $f" >&2; fi
done
check "INS-02 config, settings, shell profile and CLAUDE.md match between the two runs" "$_same"
check "INS-02 same set of files in both homes" \
    "$([ "$(cd "$HA" && find . -type f -not -name '*.bak.*' -not -path './.claude.backup.*' -not -name 'last.out' | sort)" = \
         "$(cd "$HB" && find . -type f -not -name '*.bak.*' -not -path './.claude.backup.*' -not -name 'last.out' | sort)" ] && echo true || echo false)"
HC=$(new_world ins02c)
run_install "$HC" --non-interactive --name "Ada Tester" --vault "$WORK/ins02c-vault" --initials "a1"; rcC=$?
check "INS-02 initials with a digit are refused (exit 2) before anything is written" \
    "$([ $rcC -eq 2 ] && [ ! -e "$HC/.claude" ] && [ ! -e "$WORK/ins02c-vault" ] && echo true || echo false)"
run_install "$HC" --non-interactive --name "Ada Tester" --vault "$WORK/ins02c-vault" --ticket-prefix "T-"; rcD=$?
check "INS-02 ticket prefix with a dash is refused (exit 2)" "$([ $rcD -eq 2 ] && [ ! -e "$HC/.claude" ] && echo true || echo false)"
# The question loop refuses a bad answer and asks again.
HE=$(new_world ins02e)
{ printf '\n\n'; printf '%s\n' "Ada Tester" "" "" "" "a1" "ab" "t-" "tk" "$WORK/ins02e-vault" "" "n" "s" "s" "s" "n"; } > "$WORK/ins02e.answers"
INSTALL_STDIN="$WORK/ins02e.answers" run_install "$HE"; rcE=$?
check "INS-02 a bad typed answer is asked again, then accepted" \
    "$([ $rcE -eq 0 ] && grep -q 'TOLLGATE_INITIALS="AB"' "$HE/.claude/tollgate-config" \
       && grep -q 'TOLLGATE_TICKET_PREFIX="TK"' "$HE/.claude/tollgate-config" && echo true || echo false)"

# ── INS-03 second install changes nothing; user settings survive both runs ──
H=$(new_world ins03)
seed_user_settings "$H"
VAULT3="$WORK/ins03/vault"
FLAGS3=(--non-interactive --name "Ada Tester" --vault "$VAULT3" --initials at --ticket-prefix tk)
run_install "$H" "${FLAGS3[@]}"; rc1=$?
check "INS-03 first install over existing user settings exits 0" "$([ $rc1 -eq 0 ] && echo true || echo false)"
check "INS-03 user settings survive the first run" "$(user_settings_survive "$H/.claude/settings.json")"
snapshot "$H" > "$WORK/ins03.snap1"
run_install "$H" "${FLAGS3[@]}"; rc2=$?
snapshot "$H" > "$WORK/ins03.snap2"
check "INS-03 second install exits 0" "$([ $rc2 -eq 0 ] && echo true || echo false)"
check "INS-03 user settings survive the second run" "$(user_settings_survive "$H/.claude/settings.json")"
check "INS-03 second install changes no file (config, settings, commands, profile, paths)" \
    "$(diff "$WORK/ins03.snap1" "$WORK/ins03.snap2" >/dev/null && echo true || { diff "$WORK/ins03.snap1" "$WORK/ins03.snap2" >&2; echo false; })"
check "INS-03 shell profile holds exactly one Tollgate block" \
    "$([ "$(grep -c '^# Tollgate (' "$H/.zshrc")" = 1 ] && echo true || echo false)"
check "INS-03 each Tollgate hook appears once in settings" \
    "$(python3 -I - "$H/.claude/settings.json" <<'PY'
import json, sys, collections
s = json.load(open(sys.argv[1]))
cmds = [(ev, g.get("matcher", ""), h["command"]) for ev, gs in s["hooks"].items() for g in gs for h in g["hooks"]]
mine = [c for c in cmds if "/hooks/" in c[2]]
print("true" if mine and len(mine) == len(set(mine)) else "false")
PY
)"
check "INS-03 second run made no extra settings backup" \
    "$([ "$(ls "$H"/.claude/settings.json.bak.* 2>/dev/null | wc -l | tr -d ' ')" = 1 ] && echo true || echo false)"

# ── INS-04 config holds the three answers and no secret ──────────────────────
H=$(new_world ins04)
VAULT4="$WORK/ins04/vault"
# Fake secrets are built here at run time, never written whole in this file.
FAKE1="sk-ant-""fake""$(printf '%s' 0123456789abcdef)"
FAKE2="xox""b-""$(printf '%s' 111111-222222-fakefake)"
(
    export ANTHROPIC_API_KEY="$FAKE1" SLACK_BOT_TOKEN="$FAKE2" NOTION_TOKEN="$FAKE1" GITHUB_TOKEN="$FAKE2"
    run_install "$H" --non-interactive --name "Ada Tester" --vault "$VAULT4" --initials at --ticket-prefix tk
); rc=$?
check "INS-04 install exits 0 with fake secrets in the environment" "$([ $rc -eq 0 ] && echo true || echo false)"
CFG="$H/.claude/tollgate-config"
_cfg_vals=$( ( set -u; . "$CFG"; echo "$TOLLGATE_KNOWLEDGE|$TOLLGATE_INITIALS|$TOLLGATE_TICKET_PREFIX" ) )
check "INS-04 config holds vault folder, initials and ticket prefix" \
    "$([ "$_cfg_vals" = "$VAULT4|AT|TK" ] && echo true || echo false)"
_leak=false
for f in "$CFG" "$H/.claude/settings.json" "$H/.zshrc" "$H/.claude/tollgate/paths.yaml" "$H/.claude/tollgate/connectors.yaml"; do
    grep -qF -e "$FAKE1" -e "$FAKE2" "$f" && _leak=true
done
check "INS-04 no fake secret value reached config, settings, profile, paths or connectors" "$([ "$_leak" = false ] && echo true || echo false)"
check "INS-04 every config line is a plain NAME=\"value\" answer" \
    "$(! grep -vE '^[A-Z_]+="[^"]*"$' "$CFG" >/dev/null && echo true || echo false)"
check "INS-04 config has no key-like text" \
    "$(! grep -qiE '(sk-[a-z]|xox[a-z]-|ghp_|AKIA|secret_|password|token|api[_-]?key)' "$CFG" && echo true || echo false)"
check "INS-04 config is not world writable" \
    "$([ -z "$(find "$CFG" -perm -002)" ] && echo true || echo false)"

# ── INS-05 settings backup exists before the merge and restores earlier state ─
H=$(new_world ins05)
seed_user_settings "$H"
cp "$H/.claude/settings.json" "$WORK/ins05.original.json"
VAULT5="$WORK/ins05/vault"
run_install "$H" --non-interactive --name "Ada Tester" --vault "$VAULT5" --initials at --ticket-prefix tk; rc=$?
BK=$(ls "$H"/.claude/settings.json.bak.* 2>/dev/null | head -1)
check "INS-05 install exits 0" "$([ $rc -eq 0 ] && echo true || echo false)"
check "INS-05 a settings backup exists and equals the file as it was before the merge" \
    "$([ -n "$BK" ] && cmp -s "$BK" "$WORK/ins05.original.json" && echo true || echo false)"
check "INS-05 the merged file differs from the backup (the merge did change it)" \
    "$([ "$(json_equal "$H/.claude/settings.json" "$WORK/ins05.original.json")" = false ] && echo true || echo false)"
run_install "$H" --restore-settings; rc=$?
check "INS-05 --restore-settings exits 0" "$([ $rc -eq 0 ] && echo true || echo false)"
check "INS-05 restore brings back the earlier settings exactly" \
    "$(cmp -s "$H/.claude/settings.json" "$WORK/ins05.original.json" && echo true || echo false)"
check "INS-05 restore keeps a copy of the file it replaced" \
    "$([ -n "$(ls "$H"/.claude/settings.json.before-restore.* 2>/dev/null)" ] && echo true || echo false)"
# An unreadable settings file is also backed up byte for byte before the merge.
H=$(new_world ins05b)
mkdir -p "$H/.claude"; printf '{ not json at all' > "$H/.claude/settings.json"
run_install "$H" --non-interactive --name "Ada Tester" --vault "$WORK/ins05b/vault" --initials at --ticket-prefix tk; rc=$?
BK=$(ls "$H"/.claude/settings.json.bak.* 2>/dev/null | head -1)
check "INS-05 broken settings file is backed up unchanged, install still exits 0" \
    "$([ $rc -eq 0 ] && [ -n "$BK" ] && [ "$(cat "$BK")" = '{ not json at all' ] && echo true || echo false)"

# ── INS-06 a saved name can never run as shell code on the next run (Q-05) ───
# Each odd name is saved by run one and read back by run two. The marker file
# must never appear, and the name must come back unchanged.
_i=0
for _nm in 'Ada $(touch MARK)' 'Ada `touch MARK`' 'Ada"; touch MARK; "' 'Ada \$(touch MARK) back\slash' "Ada O'Neil" 'Ada Tester'; do
    _i=$((_i + 1))
    H=$(new_world ins06_$_i)
    MARK="$WORK/ins06_$_i/MARK"
    _nm_run="${_nm//MARK/$MARK}"
    run_install "$H" --non-interactive --name "$_nm_run" --vault "$WORK/ins06_$_i/vault" --initials at --ticket-prefix tk; rc1=$?
    run_install "$H" --non-interactive --vault "$WORK/ins06_$_i/vault" --initials at --ticket-prefix tk; rc2=$?
    _saved=$(bash -c 'set -u; source "$1" >/dev/null 2>&1; printf %s "$SAVED_NAME"' _ "$H/.claude/tollgate-config" 2>/dev/null)
    check "INS-06 name case $_i: both runs exit 0, no marker file, name saved intact" \
        "$([ $rc1 -eq 0 ] && [ $rc2 -eq 0 ] && [ ! -e "$MARK" ] && [ ! -e "$H/MARK" ] && [ "$_saved" = "$_nm_run" ] && echo true || echo false)"
done

# ── INS-07 Linux without secret-tool refuses to store a secret (no plain file) ─
# A stub uname says Linux. secret-tool is not on the path (an empty-path check
# below proves it). The installer must finish, say what to install, and write
# no .secrets file anywhere in the throwaway home.
H=$(new_world ins07)
printf '#!/bin/sh\n[ "$1" = "-s" ] && { echo Linux; exit 0; }\nexec /usr/bin/uname "$@"\n' > "$H/bin/uname"
chmod +x "$H/bin/uname"
_fake_tok="not-a-real-""token-0000"
{ printf '\n\n'; printf '%s\n' "Ada Tester" "" "" "" "ab" "tk" "$WORK/ins07/vault" "" "n" "k" "https://example.invalid" "ada@example.invalid" "$_fake_tok" "s" "s" "n"; } > "$WORK/ins07.answers"
INSTALL_STDIN="$WORK/ins07.answers" run_install "$H"; rc=$?
check "INS-07 secret-tool is not on the test path" "$(PATH="$H/bin:/usr/bin:/bin" command -v secret-tool >/dev/null 2>&1 && echo false || echo true)"
check "INS-07 install finishes with exit 0" "$([ $rc -eq 0 ] && echo true || echo false)"
check "INS-07 message names the fix (sudo apt install libsecret-tools)" \
    "$(grep -q 'sudo apt install libsecret-tools' "$WORK/ins07/last.out" && echo true || echo false)"
check "INS-07 no .secrets file exists anywhere in the home" \
    "$([ -z "$(find "$H" -name '.secrets*' 2>/dev/null)" ] && echo true || echo false)"
check "INS-07 the token text is written to no file in the home" \
    "$(grep -rqF -- "$_fake_tok" "$H" 2>/dev/null && echo false || echo true)"

# ── INS-08 vault layout, library folder and the references line ──────────────
H=$(new_world ins08)
VAULT="$WORK/ins08/vault"
run_install "$H" --non-interactive --name "Ada Tester" --vault "$VAULT" --initials at --ticket-prefix tk; rc=$?
_got=$(cd "$VAULT" && find . -mindepth 1 -type d -not -path './.cursor*' | sed 's|^\./||' | sort | tr '\n' ' ')
_want="00-landing 01-system-map 01-system-map/architecture 01-system-map/clients 01-system-map/data-model 01-system-map/pipelines 01-system-map/platform-learning 02-tickets 03-knowledge-base 03-knowledge-base/decisions 03-knowledge-base/learnings 03-knowledge-base/patterns 03-knowledge-base/whiteboard 04-education 05-conversations 06-chat-threads 08-reference memory output "
check "INS-08 vault holds exactly the target folders (got: $_got)" "$([ "$_got" = "$_want" ] && echo true || echo false)"
check "INS-08 old folders 07-workflows, 05-claude-conversations, 06-meetings-summaries are not created" \
    "$([ ! -e "$VAULT/07-workflows" ] && [ ! -e "$VAULT/05-claude-conversations" ] && [ ! -e "$VAULT/06-meetings-summaries" ] && echo true || echo false)"
check "INS-08 no meetings folder is created at install" "$([ ! -e "$VAULT/meetings" ] && echo true || echo false)"
_lib=$(ls -d "$H"/Developer/*/*-library 2>/dev/null | head -1)
check "INS-08 library folder is created beside the vault area" "$([ -n "$_lib" ] && [ -d "$_lib" ] && echo true || echo false)"
check "INS-08 paths file has one references line pointing at the library" \
    "$([ "$(grep -c '^references:' "$H/.claude/tollgate/paths.yaml")" = 1 ] && grep -qxF "references: $_lib" "$H/.claude/tollgate/paths.yaml" && echo true || echo false)"
check "INS-08 meetings path in the profile is <vault>/meetings" \
    "$(grep -q "_MEETINGS=\"$VAULT/meetings\"" "$H/.zshrc" && echo true || echo false)"
# A second run keeps an existing references line and the order of the other lines.
printf 'references: /somewhere/else\nstandards: /my/standards\n' > "$H/.claude/tollgate/paths.yaml"
run_install "$H" --non-interactive --vault "$VAULT" --initials at --ticket-prefix tk; rc2=$?
check "INS-08 re-run never overwrites or reorders an existing paths file" \
    "$([ $rc2 -eq 0 ] && [ "$(grep -v '^vault_git:' "$H/.claude/tollgate/paths.yaml")" = "$(printf 'references: /somewhere/else\nstandards: /my/standards')" ] && echo true || echo false)"
# A paths file without a references line gets one, once, after the existing lines.
printf 'standards: /my/standards\n' > "$H/.claude/tollgate/paths.yaml"
run_install "$H" --non-interactive --vault "$VAULT" --initials at --ticket-prefix tk
run_install "$H" --non-interactive --vault "$VAULT" --initials at --ticket-prefix tk
check "INS-08 references line is added once, existing line stays first" \
    "$([ "$(head -1 "$H/.claude/tollgate/paths.yaml")" = 'standards: /my/standards' ] && [ "$(grep -c '^references:' "$H/.claude/tollgate/paths.yaml")" = 1 ] && echo true || echo false)"

# ── INS-09 minimum Python is 3.12 ────────────────────────────────────────────
# A python3 shim that runs the real one but reports an older version_info for `-c` checks.
_real_py="$(command -v python3)"
_shim_bin="$WORK/ins09-shim"
mkdir -p "$_shim_bin"
cat > "$_shim_bin/python3" <<SHIM
#!/bin/sh
if [ "\$1" = "-c" ]; then
  exec "$_real_py" -c "import sys; sys.version_info = (\${FAKE_PY_MAJOR:-3}, \${FAKE_PY_MINOR:-9}, 0, 'final', 0); exec(sys.argv[1])" "\$2"
fi
exec "$_real_py" "\$@"
SHIM
chmod +x "$_shim_bin/python3"

H=$(new_world ins09a)
RUN_PATH="$_shim_bin:$H/bin:$PATH" FAKE_PY_MINOR=11 run_install "$H" --non-interactive --name "Ada Tester" --vault "$WORK/ins09a/vault" --initials at --ticket-prefix tk; rc=$?
check "INS-09 Python 3.11 is refused with exit 1 and the one-line message" \
    "$([ $rc -eq 1 ] && grep -qF 'Tollgate needs Python 3.12 or newer, found 3.11' "$H/../last.out" && echo true || echo false)"
check "INS-09 a refused run writes nothing (no vault, no settings)" \
    "$([ ! -e "$WORK/ins09a/vault" ] && [ ! -e "$H/.claude/settings.json" ] && echo true || echo false)"

H=$(new_world ins09b)
RUN_PATH="$_shim_bin:$H/bin:$PATH" FAKE_PY_MINOR=12 run_install "$H" --non-interactive --name "Ada Tester" --vault "$WORK/ins09b/vault" --initials at --ticket-prefix tk; rc=$?
check "INS-09 Python 3.12 passes the version check" \
    "$([ $rc -eq 0 ] && ! grep -qF 'Tollgate needs Python' "$H/../last.out" && echo true || echo false)"

# ── INS-10 an existing search environment must also be 3.12 or newer ─────────
# The venv python is a stub that runs the real python3 but reports an older version_info.
_make_old_venv() {   # _make_old_venv HOME MINOR
    local vb="$1/.tollgate/state/venv/bin"
    mkdir -p "$vb"
    printf '#!/bin/sh\nif [ "$1" = "-c" ]; then\n  exec "%s" -c "import sys; sys.version_info = (3, %s, 0, '"'"'final'"'"', 0); exec(sys.argv[1])" "$2"\nfi\nexec "%s" "$@"\n' \
        "$_real_py" "$2" "$_real_py" > "$vb/python3"
    chmod +x "$vb/python3"
}

H=$(new_world ins10a)
_make_old_venv "$H" 11
run_install "$H" --non-interactive --name "Ada Tester" --vault "$WORK/ins10a/vault" --initials at --ticket-prefix tk; rc=$?
check "INS-10 an existing venv on Python 3.11 is refused with exit 1 and the one-line message" \
    "$([ $rc -eq 1 ] && grep -qF "Tollgate needs Python 3.12 or newer, existing search environment uses 3.11: delete $H/.tollgate/state/venv and re-run" "$H/../last.out" && echo true || { cat "$H/../last.out" >&2; echo false; })"
check "INS-10 the refused run writes no vault, no settings, no paths file, and deletes nothing" \
    "$([ ! -e "$WORK/ins10a/vault" ] && [ ! -e "$H/.claude/settings.json" ] && [ ! -e "$H/.claude/tollgate/paths.yaml" ] && [ -x "$H/.tollgate/state/venv/bin/python3" ] && echo true || echo false)"

H=$(new_world ins10b)
_make_old_venv "$H" 12
run_install "$H" --non-interactive --name "Ada Tester" --vault "$WORK/ins10b/vault" --initials at --ticket-prefix tk; rc=$?
check "INS-10 an existing venv on Python 3.12 passes the version check" \
    "$([ $rc -eq 0 ] && ! grep -qF 'existing search environment' "$H/../last.out" && echo true || echo false)"

# Clean mode: an old venv must end the run BEFORE the backup and the wipe of ~/.claude.
# The menu is driven from a stdin file (no --non-interactive, which never picks Clean):
# Enter to start, Enter for simple mode, then "f" (Start fresh, which is Clean in simple mode).
H=$(new_world ins10c)
_make_old_venv "$H" 11
echo "keep me" > "$H/.claude/marker.txt" 2>/dev/null || { mkdir -p "$H/.claude"; echo "keep me" > "$H/.claude/marker.txt"; }
printf '\n\nf\n' > "$WORK/ins10c.answers"
INSTALL_STDIN="$WORK/ins10c.answers" run_install "$H" --vault "$WORK/ins10c/vault"; rc=$?
check "INS-10 Clean mode with an old venv is refused with exit 1 and the message" \
    "$([ $rc -eq 1 ] && grep -qF "existing search environment uses 3.11: delete $H/.tollgate/state/venv and re-run" "$H/../last.out" && echo true || { cat "$H/../last.out" >&2; echo false; })"
check "INS-10 Clean mode refusal leaves ~/.claude untouched: marker kept, no backup copy, no vault" \
    "$([ "$(cat "$H/.claude/marker.txt" 2>/dev/null)" = "keep me" ] && [ -z "$(ls -d "$H"/.claude.backup.* 2>/dev/null)" ] && [ ! -e "$WORK/ins10c/vault" ] && echo true || echo false)"

# ── INS-11 installed commands, refused path, escapes, profile quoting, meetings folder ──
H=$(new_world ins11a)
run_install "$H" --non-interactive --name "Ada Tester" --vault "$WORK/ins11a/vault" --initials at --ticket-prefix tk; rc=$?
_left=$(grep -l '\$TOLLGATE_HOME/' "$H"/.claude/commands/*.md 2>/dev/null | xargs -n1 basename 2>/dev/null | tr '\n' ' ')
check "INS-11 no installed command holds an unexpanded \$TOLLGATE_HOME/ (left in: ${_left:-none})" \
    "$([ $rc -eq 0 ] && [ -z "$_left" ] && echo true || echo false)"
check "INS-11 installed commands call the other scripts by absolute repo path" \
    "$(grep -q "$WORK/repo/scripts/core/tg_path" "$H/.claude/commands/tg-start.md" && echo true || echo false)"
check "INS-11 installed settings allow the tg_path and tg_ticket_dir calls by absolute path" \
    "$(grep -qF "Bash($WORK/repo/scripts/core/tg_path:*)" "$H/.claude/settings.json" && grep -qF "Bash($WORK/repo/scripts/core/tg_ticket_dir:*)" "$H/.claude/settings.json" && echo true || echo false)"
check "INS-11 tg-search call is the unquoted absolute form" \
    "$(grep -q " $WORK/repo/scripts/search/tg-search " "$H/.claude/commands/tg-retrieve.md" || grep -q "\`$WORK/repo/scripts/search/tg-search " "$H/.claude/commands/tg-retrieve.md" && ! grep -q "\"$WORK/repo/scripts/search/tg-search" "$H/.claude/commands/tg-retrieve.md" && echo true || echo false)"
# B5: the meetings folder in the profile is what the path loader prints.
_mtg=$(TOLLGATE_PATHS="$H/.claude/tollgate/paths.yaml" TOLLGATE_KNOWLEDGE="$WORK/ins11a/vault" "$WORK/repo/scripts/core/tg_path" meetings 2>/dev/null)
check "INS-11 profile TOLLGATE_MEETINGS equals what tg_path meetings prints" \
    "$([ -n "$_mtg" ] && grep -qxF "export TOLLGATE_MEETINGS=\"$_mtg\"" "$H/.zshrc" && echo true || echo false)"

# B2: a repo path with a space is refused before anything is written.
_sp="$WORK/with space/repo"
mkdir -p "$_sp"
tar -C "$TOLLGATE_DIR" --exclude=.git --exclude=__pycache__ -cf - . | tar -C "$_sp" -xf -
H=$(new_world ins11b)
INSTALL_REPO="$_sp" run_install "$H" --non-interactive --name "Ada Tester" --vault "$WORK/ins11b/vault" --initials at --ticket-prefix tk; rc=$?
check "INS-11 repo path with a space is refused with exit 1 and a clear line" \
    "$([ $rc -eq 1 ] && grep -qF 'Move the repo to a path without spaces' "$H/../last.out" && echo true || echo false)"
check "INS-11 refused spaced-path run writes nothing (no vault, settings, profile)" \
    "$([ ! -e "$WORK/ins11b/vault" ] && [ ! -e "$H/.claude/settings.json" ] && [ ! -e "$H/.zshrc" ] && echo true || echo false)"

# B3: a workspace path holding & and | lands intact in CLAUDE.md.
H=$(new_world ins11c)
run_install "$H" --non-interactive --name 'A&B|C' --vault "$WORK/ins11c/vault" --initials at --ticket-prefix tk; rc=$?
_ws=$(ls "$H"/Developer/*/*.code-workspace 2>/dev/null | head -1)
check "INS-11 workspace path with & and | is written intact into CLAUDE.md" \
    "$([ $rc -eq 0 ] && [ -n "$_ws" ] && grep -qF "workspace file at \`$_ws\`" "$H/.claude/CLAUDE.md" && echo true || echo false)"

# B4: a vault path with $ and " gives a profile that bash accepts and sources back exactly.
_qv="$WORK/ins11d/va\$ult\"x"
H=$(new_world ins11d)
run_install "$H" --non-interactive --name "Ada Tester" --vault "$_qv" --initials at --ticket-prefix tk; rc=$?
_back=$(bash -c 'source "$1" >/dev/null 2>&1; printf %s "$TOLLGATE_KNOWLEDGE"' _ "$H/.zshrc" 2>/dev/null)
check "INS-11 profile with a \$ and \" in the vault path passes bash -n and sources back the exact path" \
    "$([ $rc -eq 0 ] && bash -n "$H/.zshrc" && [ "$_back" = "$_qv" ] && echo true || echo false)"
