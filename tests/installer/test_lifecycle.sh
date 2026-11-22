#!/usr/bin/env bash
# Installer lifecycle tests LIF-01 to LIF-13. Sourced by run.sh, which supplies check(), WORK and
# TOLLGATE_DIR. Every install runs in a throwaway home (see helpers.sh). No launchd job is ever loaded:
# the scheduler call goes to a stub launcher, and pip and python for the venv are stubs.
# Author: Dipen Patel (dipenpatel-dev)
# Date:

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"
make_repo_copy

echo "── LIF update path, manifest, backups, uninstall, version, venv, cron ──"

_flags() { echo "--non-interactive --name Ada\ Tester --vault $1 --initials at --ticket-prefix tk"; }
# install HOME VAULT [extra args]
inst() { local h="$1" v="$2"; shift 2; run_install "$h" --non-interactive --name "Ada Tester" --vault "$v" --initials at --ticket-prefix tk "$@"; }
hooks_from_tollgate() { grep -c "/hooks/" "$1" 2>/dev/null || true; }

# ── LIF-01 re-run with a custom command present (the update path) ────────────
H=$(new_world lif01); V="$WORK/lif01/vault"
mkdir -p "$H/.claude/commands"
echo "my own command" > "$H/.claude/commands/my-own.md"
inst "$H" "$V"; rc1=$?
inst "$H" "$V"; rc2=$?
check "LIF-01 first run with a custom command exits 0" "$([ $rc1 -eq 0 ] && echo true || echo false)"
check "LIF-01 second run (update) with a custom command exits 0, settings merge still ran" \
    "$([ $rc2 -eq 0 ] && grep -q 'Settings already up to date\|Settings merged' "$WORK/lif01/last.out" && echo true || { tail -5 "$WORK/lif01/last.out" >&2; echo false; })"
check "LIF-01 custom command is untouched" "$([ "$(cat "$H/.claude/commands/my-own.md")" = "my own command" ] && echo true || echo false)"
check "LIF-01 nothing is copied into the repo (no commands/custom)" "$([ ! -e "$WORK/repo/commands/custom" ] && echo true || echo false)"
check "LIF-01 custom command is not in the manifest" \
    "$(! grep -q 'my-own.md' "$H/.claude/tollgate/manifest.json" && echo true || echo false)"

# ── LIF-02 idempotent second run, manifest and version file ──────────────────
H=$(new_world lif02); V="$WORK/lif02/vault"
inst "$H" "$V"
snapshot "$H" > "$WORK/lif02.s1"
inst "$H" "$V"; rc=$?
snapshot "$H" > "$WORK/lif02.s2"
check "LIF-02 second run exits 0 and changes no file (manifest included)" \
    "$([ $rc -eq 0 ] && diff "$WORK/lif02.s1" "$WORK/lif02.s2" >/dev/null && echo true || echo false)"
check "LIF-02 installed-version matches the VERSION file" \
    "$([ "$(cat "$H/.claude/tollgate/installed-version")" = "$(cat "$TOLLGATE_DIR/VERSION")" ] && echo true || echo false)"
check "LIF-02 manifest lists the commands, hooks and the version" \
    "$(python3 -I - "$H/.claude/tollgate/manifest.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
print("true" if "tg-start.md" in m["commands"] and m["hooks"] and m["version"] and "env" in m else "false")
PY
)"
check "LIF-02 no full ~/.claude copy was made on the update run" \
    "$([ -z "$(ls -d "$H"/.claude.backup.* 2>/dev/null)" ] && echo true || echo false)"

# ── LIF-03 a command dropped upstream is removed; a rename is remove plus add ─
R3=$(clone_repo repo-lif03)
H=$(new_world lif03); V="$WORK/lif03/vault"
echo "old command" > "$R3/commands/zz-old.md"
echo "mine" > /dev/null; mkdir -p "$H/.claude/commands"; echo "user file" > "$H/.claude/commands/user-own.md"
INSTALL_REPO="$R3" inst "$H" "$V"
_had=$([ -f "$H/.claude/commands/zz-old.md" ] && echo true || echo false)
rm "$R3/commands/zz-old.md"
echo "renamed command" > "$R3/commands/tg-zz-old.md"
INSTALL_REPO="$R3" inst "$H" "$V"; rc=$?
check "LIF-03 the command was installed first" "$_had"
check "LIF-03 after it is dropped upstream the old file is gone from ~/.claude/commands" \
    "$([ $rc -eq 0 ] && [ ! -e "$H/.claude/commands/zz-old.md" ] && echo true || echo false)"
check "LIF-03 the removed file is backed up under tollgate/removed" \
    "$([ -n "$(ls "$H"/.claude/tollgate/removed/*/zz-old.md 2>/dev/null)" ] && echo true || echo false)"
check "LIF-03 the renamed file is installed and listed" \
    "$([ -f "$H/.claude/commands/tg-zz-old.md" ] && grep -q 'tg-zz-old.md' "$H/.claude/tollgate/manifest.json" && echo true || echo false)"
check "LIF-03 a user's own command is never removed" "$([ -f "$H/.claude/commands/user-own.md" ] && echo true || echo false)"

# ── LIF-04 a hook dropped upstream leaves settings; the user's hook stays ─────
R4=$(clone_repo repo-lif04)
H=$(new_world lif04); V="$WORK/lif04/vault"
seed_user_settings "$H"
INSTALL_REPO="$R4" inst "$H" "$V"
_victim=$(python3 -I - "$R4/settings.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
for ev, groups in s["hooks"].items():
    for g in groups:
        if g["hooks"]:
            print(g["hooks"][0]["command"].split("/hooks/")[-1].split('"')[0].split()[0]); raise SystemExit
PY
)
_before=$(grep -c "/hooks/$_victim" "$H/.claude/settings.json" || true)
python3 -I - "$R4/settings.json" "$_victim" <<'PY'
import json, sys
p, victim = sys.argv[1], sys.argv[2]
s = json.load(open(p))
for ev in list(s["hooks"]):
    for g in s["hooks"][ev]:
        g["hooks"] = [h for h in g["hooks"] if "/hooks/" + victim not in h["command"]]
    s["hooks"][ev] = [g for g in s["hooks"][ev] if g["hooks"]]
json.dump(s, open(p, "w"), indent=2)
PY
INSTALL_REPO="$R4" inst "$H" "$V"; rc=$?
_after=$(grep -c "/hooks/$_victim" "$H/.claude/settings.json" || true)
check "LIF-04 the hook ($_victim) was in settings after the first run" "$([ "$_before" -ge 1 ] && echo true || echo false)"
check "LIF-04 after it is dropped from the template it is removed from settings" "$([ $rc -eq 0 ] && [ "$_after" = 0 ] && echo true || echo false)"
check "LIF-04 the user's own hook and settings are all still there" "$(user_settings_survive "$H/.claude/settings.json")"

# ── LIF-05 --uninstall removes only Tollgate's entries ───────────────────────
H=$(new_world lif05); V="$WORK/lif05/vault"
seed_user_settings "$H"
mkdir -p "$H/.claude/commands"; echo "mine" > "$H/.claude/commands/user-own.md"
inst "$H" "$V"
run_install "$H" --uninstall; rc=$?
check "LIF-05 --uninstall exits 0" "$([ $rc -eq 0 ] && echo true || { tail -5 "$WORK/lif05/last.out" >&2; echo false; })"
check "LIF-05 user settings (hooks, permissions, model, plugins) survive" "$(user_settings_survive "$H/.claude/settings.json")"
check "LIF-05 no Tollgate hook is left in settings" "$([ "$(hooks_from_tollgate "$H/.claude/settings.json")" = 0 ] && echo true || echo false)"
check "LIF-05 Tollgate command files are gone, the user's command stays" \
    "$([ ! -e "$H/.claude/commands/tg-start.md" ] && [ -f "$H/.claude/commands/user-own.md" ] && echo true || echo false)"
check "LIF-05 manifest and installed-version are removed" \
    "$([ ! -e "$H/.claude/tollgate/manifest.json" ] && [ ! -e "$H/.claude/tollgate/installed-version" ] && echo true || echo false)"
check "LIF-05 settings were backed up before the change" "$([ -n "$(ls "$H"/.claude/settings.json.bak.* 2>/dev/null)" ] && echo true || echo false)"
check "LIF-05 removed commands are saved under tollgate/removed" "$([ -n "$(ls "$H"/.claude/tollgate/removed/*/tg-start.md 2>/dev/null)" ] && echo true || echo false)"
check "LIF-05 the notes folder and the saved answers are left alone" \
    "$([ -d "$V/02-tickets" ] && [ -f "$H/.claude/tollgate-config" ] && echo true || echo false)"
run_install "$H" --uninstall; rc=$?
check "LIF-05 --uninstall with no manifest is a harmless no-op (exit 0)" "$([ $rc -eq 0 ] && echo true || echo false)"
H=$(new_world lif05b); inst "$H" "$WORK/lif05b/vault"
snapshot "$H" > "$WORK/lif05b.s1"; run_install "$H" --uninstall --dry-run; rc=$?; snapshot "$H" > "$WORK/lif05b.s2"
check "LIF-05 --uninstall --dry-run changes nothing" "$([ $rc -eq 0 ] && diff "$WORK/lif05b.s1" "$WORK/lif05b.s2" >/dev/null && echo true || echo false)"

# ── LIF-06 backup pruning keeps the newest 3 ─────────────────────────────────
H=$(new_world lif06); V="$WORK/lif06/vault"
inst "$H" "$V"
for n in 1 2 3 4 5; do mkdir -p "$H/.claude.backup.2020010100000$n"; echo x > "$H/.claude.backup.2020010100000$n/f"; done
mkdir -p "$H/.claude.backup.mine-keep"; mkdir -p "$H/.claude.backup.20200101"
echo "changed by user" >> "$H/.claude/commands/tg-start.md"
for n in 1 2 3 4 5; do echo old > "$H/.claude/commands/tg-start.md.bak.2020010100000$n"; done
inst "$H" "$V"; rc=$?
_full=$(ls -d "$H"/.claude.backup.2020010100000* 2>/dev/null | wc -l | tr -d ' ')
check "LIF-06 only the newest 3 full backups remain (found $_full)" "$([ $rc -eq 0 ] && [ "$_full" = 3 ] && [ ! -d "$H/.claude.backup.20200101000001" ] && [ -d "$H/.claude.backup.20200101000005" ] && echo true || echo false)"
check "LIF-06 backup-like folders with another name are never deleted" \
    "$([ -d "$H/.claude.backup.mine-keep" ] && [ -d "$H/.claude.backup.20200101" ] && echo true || echo false)"
_bak=$(ls "$H"/.claude/commands/tg-start.md.bak.* 2>/dev/null | wc -l | tr -d ' ')
check "LIF-06 per-file .bak copies are pruned to 3 (found $_bak) and the new one is kept" \
    "$([ "$_bak" = 3 ] && [ -z "$(ls "$H"/.claude/commands/tg-start.md.bak.20200101000001 2>/dev/null)" ] && grep -q 'changed by user' "$(ls "$H"/.claude/commands/tg-start.md.bak.* | sort | tail -1)" && echo true || echo false)"

# ── LIF-07 cursor rules are backed up before being overwritten ───────────────
H=$(new_world lif07); V="$WORK/lif07/vault"
inst "$H" "$V"
_rule=$(ls "$V"/.cursor/rules/*.mdc 2>/dev/null | head -1)
echo "my edit" >> "$_rule"
inst "$H" "$V"; rc=$?
check "LIF-07 an edited cursor rule is backed up (.bak) and then replaced" \
    "$([ $rc -eq 0 ] && [ -n "$(ls "$_rule".bak.* 2>/dev/null)" ] && grep -q 'my edit' "$(ls "$_rule".bak.* | head -1)" && ! grep -q 'my edit' "$_rule" && echo true || echo false)"

# ── LIF-08 user memory is never copied into the repo; the link slug ──────────
H=$(new_world lif08); V="$WORK/lif08/vault"
mkdir -p "$H/.claude/projects/some-other-project/memory"
echo "private memory" > "$H/.claude/projects/some-other-project/memory/secret_note.md"
R8=$(clone_repo repo-lif08)
INSTALL_REPO="$R8" inst "$H" "$V"; rc=$?
_slug=$(printf '%s' "$R8" | sed 's|[^A-Za-z0-9]|-|g')
check "LIF-08 install exits 0 and no user memory file lands in the repo memory folder" \
    "$([ $rc -eq 0 ] && [ ! -e "$R8/memory/secret_note.md" ] && [ "$(ls "$R8"/memory/*.md | wc -l | tr -d ' ')" = 1 ] && echo true || echo false)"
check "LIF-08 the memory link uses the slug where / . and _ all become - ($_slug)" \
    "$([ -L "$H/.claude/projects/$_slug/memory" ] && [ "$(readlink "$H/.claude/projects/$_slug/memory")" = "$R8/memory" ] && echo true || echo false)"
check "LIF-08 .gitignore keeps memory notes out except the index" \
    "$(grep -qx 'memory/\*.md' "$TOLLGATE_DIR/.gitignore" && grep -qx '!memory/MEMORY.md' "$TOLLGATE_DIR/.gitignore" && echo true || echo false)"

# ── LIF-09 vault folders come from scripts/core/paths.py ─────────────────────
H=$(new_world lif09); V="$WORK/lif09/vault"
inst "$H" "$V"
echo "tickets: $V/my-tix" >> "$H/.claude/tollgate/paths.yaml"
inst "$H" "$V"; rc=$?
check "LIF-09 a paths-file override changes the folder the installer creates" "$([ $rc -eq 0 ] && [ -d "$V/my-tix" ] && echo true || echo false)"
check "LIF-09 install.sh no longer holds its own folder list" "$(! grep -q 'VAULT_DIRS' "$TOLLGATE_DIR/install.sh" && echo true || echo false)"

# ── LIF-10 Claude Code version check ─────────────────────────────────────────
fake_claude() { printf '#!/bin/sh\necho "%s (Claude Code)"\n' "$2" > "$1/bin/claude"; chmod +x "$1/bin/claude"; }
H=$(new_world lif10a); fake_claude "$H" "2.1.311"
inst "$H" "$WORK/lif10a/vault"; rc=$?
check "LIF-10 newer Claude Code: exit 0, no warning" "$([ $rc -eq 0 ] && ! grep -q 'older than\|was not found' "$WORK/lif10a/last.out" && echo true || echo false)"
H=$(new_world lif10b); fake_claude "$H" "2.1.294"
inst "$H" "$WORK/lif10b/vault"; rc=$?
check "LIF-10 older Claude Code: warns that hooks will not fail closed, still installs (exit 0)" \
    "$([ $rc -eq 0 ] && grep -q 'older than 2.1.295' "$WORK/lif10b/last.out" && grep -q 'NOT fail closed' "$WORK/lif10b/last.out" && [ -f "$H/.claude/settings.json" ] && echo true || echo false)"
H=$(new_world lif10b2); fake_claude "$H" "2.0.999"
inst "$H" "$WORK/lif10b2/vault" >/dev/null; 
check "LIF-10 an older major version also counts as older" "$(grep -q 'older than 2.1.295' "$WORK/lif10b2/last.out" && echo true || echo false)"
H=$(new_world lif10c); _pydir=$(dirname "$(command -v python3)")
_nopath="$H/bin:$_pydir:/usr/bin:/bin"
if PATH="$_nopath" command -v claude >/dev/null 2>&1; then
    check "LIF-10 (skipped: a real claude is on the minimal test path)" "true"
else
    RUN_PATH="$_nopath" inst "$H" "$WORK/lif10c/vault"; rc=$?
    check "LIF-10 missing Claude Code: warns, still installs (exit 0)" \
        "$([ $rc -eq 0 ] && grep -q 'was not found' "$WORK/lif10c/last.out" && grep -q '2.1.295' "$WORK/lif10c/last.out" && echo true || echo false)"
    H=$(new_world lif10d)
    RUN_PATH="$H/bin:$_pydir:/usr/bin:/bin" inst "$H" "$WORK/lif10d/vault" --strict; rc=$?
    check "LIF-10 --strict with Claude Code missing stops with exit 1 before anything is written" \
        "$([ $rc -eq 1 ] && [ ! -e "$H/.claude/settings.json" ] && echo true || echo false)"
fi
H=$(new_world lif10e); fake_claude "$H" "2.1.100"
inst "$H" "$WORK/lif10e/vault" --strict; rc=$?
check "LIF-10 --strict with an older Claude Code stops with exit 1" "$([ $rc -eq 1 ] && [ ! -e "$H/.claude/settings.json" ] && echo true || echo false)"
H=$(new_world lif10f); fake_claude "$H" "2.1.295"
inst "$H" "$WORK/lif10f/vault" --strict; rc=$?
check "LIF-10 --strict with exactly the minimum version passes" "$([ $rc -eq 0 ] && echo true || echo false)"

# ── LIF-11 --help, unknown flag ──────────────────────────────────────────────
H=$(new_world lif11)
run_install "$H" --help; rc=$?
_all=true
for f in --uninstall --restore-settings --dry-run --non-interactive --with-cron --skip-venv --with-venv --strict --vault; do
    grep -q -- "$f" "$WORK/lif11/last.out" || _all=false
done
check "LIF-11 --help exits 0, lists every flag, and writes nothing" "$([ $rc -eq 0 ] && [ "$_all" = true ] && [ ! -e "$H/.claude" ] && echo true || echo false)"
run_install "$H" --no-such-flag; rc=$?
check "LIF-11 an unknown flag is refused with exit 2" "$([ $rc -eq 2 ] && [ ! -e "$H/.claude" ] && echo true || echo false)"

# ── LIF-12 venv step: setup_venv.sh, requirements.txt, search deps (stubs only) ─
H=$(new_world lif12); V="$WORK/lif12/vault"
cat > "$H/bin/stubpy" <<'STUB'
#!/bin/sh
# Stand-in base python: only `-m venv DIR` is handled. It makes stub pip and python3 that log their calls.
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin"
  printf '#!/bin/sh\necho "pip $*" >> "%s/calls.log"\n' "$3" > "$3/bin/pip"
  printf '#!/bin/sh\necho "py $*" >> "%s/calls.log"\n' "$3" > "$3/bin/python3"
  chmod +x "$3/bin/pip" "$3/bin/python3"
  exit 0
fi
exec python3 "$@"
STUB
chmod +x "$H/bin/stubpy"
TOLLGATE_BASE_PYTHON="$H/bin/stubpy" inst "$H" "$V" --with-venv; rc=$?
_venv="$H/.tollgate/state/venv"
check "LIF-12 --with-venv exits 0 and builds the venv at the setup_venv.sh path" "$([ $rc -eq 0 ] && [ -x "$_venv/bin/python3" ] && echo true || { tail -8 "$WORK/lif12/last.out" >&2; echo false; })"
check "LIF-12 scripts/requirements.txt is installed with the venv's pip and no model package is added" \
    "$(grep -q 'pip install --quiet -r .*scripts/requirements.txt' "$_venv/calls.log" && ! grep -q 'sentence-transformers' "$_venv/calls.log" && echo true || echo false)"
check "LIF-12 the index build runs scripts/search/build_index.py with the venv python" "$(grep -q 'py .*scripts/search/build_index.py' "$_venv/calls.log" && ! grep -q 'rag/' "$_venv/calls.log" && echo true || echo false)"
check "LIF-12 settings env TOLLGATE_PYTHON points at the venv python" \
    "$(python3 -I - "$H/.claude/settings.json" "$_venv/bin/python3" <<'PY'
import json, sys
print("true" if json.load(open(sys.argv[1]))["env"].get("TOLLGATE_PYTHON") == sys.argv[2] else "false")
PY
)"
H=$(new_world lif12b)
TOLLGATE_BASE_PYTHON=/nonexistent inst "$H" "$WORK/lif12b/vault" --skip-venv; rc=$?
check "LIF-12 --skip-venv builds nothing and never calls pip" "$([ $rc -eq 0 ] && [ ! -e "$H/.tollgate/state/venv" ] && echo true || echo false)"
H=$(new_world lif12c)
inst "$H" "$WORK/lif12c/vault"
check "LIF-12 without a flag, non-interactive mode builds no venv (the question defaults to no)" "$([ ! -e "$H/.tollgate/state/venv" ] && echo true || echo false)"

# ── LIF-13 nightly job offer: stub launcher only ─────────────────────────────
if [ "$(uname -s)" = Darwin ]; then
    H=$(new_world lif13); V="$WORK/lif13/vault"
    printf '#!/bin/sh\necho "$@" >> "%s/launcher.log"\n' "$H" > "$H/bin/stub-launcher"; chmod +x "$H/bin/stub-launcher"
    inst "$H" "$V" --skip-venv
    check "LIF-13 default (no flag, non-interactive): no job file, launcher never called" \
        "$([ ! -e "$H/Library/LaunchAgents/tg-job-nightly-index.plist" ] && [ ! -e "$H/launcher.log" ] && echo true || echo false)"
    TOLLGATE_CRON_LAUNCHER="$H/bin/stub-launcher" inst "$H" "$V" --skip-venv --with-cron; rc=$?
    check "LIF-13 --with-cron writes the job file and hands it to the (stub) launcher" \
        "$([ $rc -eq 0 ] && [ -f "$H/Library/LaunchAgents/tg-job-nightly-index.plist" ] && grep -q bootstrap "$H/launcher.log" && echo true || { tail -6 "$WORK/lif13/last.out" >&2; echo false; })"
    check "LIF-13 the manifest records the job" "$(grep -q 'nightly-index' "$H/.claude/tollgate/manifest.json" && echo true || echo false)"
    TOLLGATE_CRON_LAUNCHER="$H/bin/stub-launcher" run_install "$H" --uninstall; rc=$?
    check "LIF-13 --uninstall removes the job file and unloads it through the launcher" \
        "$([ $rc -eq 0 ] && [ ! -e "$H/Library/LaunchAgents/tg-job-nightly-index.plist" ] && grep -q bootout "$H/launcher.log" && echo true || echo false)"
fi

# ── LIF-14 local embedding model step: never without a yes, never fatal ──────
_model_stub() {   # _model_stub HOME  (a base python whose venv python fails `-m pip install sentence-transformers` on sentence-transformers when MODEL_FAIL=1)
    cat > "$1/bin/stubpy" <<'STUB'
#!/bin/sh
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin"
  printf '#!/bin/sh\necho "pip $*" >> "%s/calls.log"\ncase "$*" in *sentence-transformers*) [ "$MODEL_FAIL" = 1 ] && exit 1;; esac\nexit 0\n' "$3" > "$3/bin/pip"
  printf '#!/bin/sh\necho "py $*" >> "%s/calls.log"\ncase "$*" in *sentence-transformers*) [ "$MODEL_FAIL" = 1 ] && exit 1;; esac\nexit 0\n' "$3" > "$3/bin/python3"
  chmod +x "$3/bin/pip" "$3/bin/python3"
  exit 0
fi
exec python3 "$@"
STUB
    chmod +x "$1/bin/stubpy"
}
H=$(new_world lif14a); _model_stub "$H"
TOLLGATE_BASE_PYTHON="$H/bin/stubpy" inst "$H" "$WORK/lif14a/vault" --with-venv; rc=$?
_calls="$H/.tollgate/state/venv/calls.log"
check "LIF-14 non-interactive without TOLLGATE_DOWNLOAD_MODEL: no model install, no download" \
    "$([ $rc -eq 0 ] && ! grep -q 'sentence-transformers\|download_model' "$_calls" && grep -q 'built-in embedder' "$WORK/lif14a/last.out" && echo true || echo false)"
H=$(new_world lif14b); _model_stub "$H"
TOLLGATE_DOWNLOAD_MODEL=1 TOLLGATE_BASE_PYTHON="$H/bin/stubpy" inst "$H" "$WORK/lif14b/vault" --with-venv; rc=$?
_calls="$H/.tollgate/state/venv/calls.log"
check "LIF-14 TOLLGATE_DOWNLOAD_MODEL=1 installs sentence-transformers and runs download_model.py --yes-download" \
    "$([ $rc -eq 0 ] && grep -q 'pip install --quiet sentence-transformers' "$_calls" && grep -q 'py .*scripts/search/download_model.py --yes-download' "$_calls" && echo true || echo false)"
H=$(new_world lif14c); _model_stub "$H"
MODEL_FAIL=1 TOLLGATE_DOWNLOAD_MODEL=1 TOLLGATE_BASE_PYTHON="$H/bin/stubpy" inst "$H" "$WORK/lif14c/vault" --with-venv; rc=$?
_calls="$H/.tollgate/state/venv/calls.log"
check "LIF-14 a failed model install prints one clear line and the install still finishes (exit 0, index built)" \
    "$([ $rc -eq 0 ] && grep -q 'Could not install or download the local model' "$WORK/lif14c/last.out" && ! grep -q 'download_model' "$_calls" && grep -q 'build_index.py' "$_calls" && echo true || echo false)"
H=$(new_world lif14d); _model_stub "$H"
TOLLGATE_DOWNLOAD_MODEL=0 TOLLGATE_BASE_PYTHON="$H/bin/stubpy" inst "$H" "$WORK/lif14d/vault" --with-venv; rc=$?
check "LIF-14 TOLLGATE_DOWNLOAD_MODEL=0 skips the model" "$([ $rc -eq 0 ] && ! grep -q 'sentence-transformers' "$H/.tollgate/state/venv/calls.log" && echo true || echo false)"

# ── LIF-15 an install made with a skill prefix is upgraded to the fixed tg- names ─
H=$(new_world lif15); V="$WORK/lif15/vault"
inst "$H" "$V"
mkdir -p "$H/.claude/commands"
for n in ah-ticket ah-spec start lens setup-client; do echo "old $n" > "$H/.claude/commands/$n.md"; done
echo "mine" > "$H/.claude/commands/mine.md"
echo "mine too" > "$H/.claude/commands/ah-notes.md"      # prefixed look-alike the manifest never listed
python3 -I - "$H/.claude/tollgate/manifest.json" "$H/.zshrc" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
m["commands"] = sorted(set(m["commands"]) | {"ah-ticket.md", "ah-spec.md", "start.md", "lens.md", "setup-client.md"})
json.dump(m, open(sys.argv[1], "w"))
text = open(sys.argv[2]).read().replace("# Tollgate (managed block)", "# Tollgate (prefix: ah)")
text = text.replace("export TOLLGATE_SCRIPTS=", "export AH_SCRIPTS=\"x\"\nexport TOLLGATE_SCRIPTS=")
open(sys.argv[2], "w").write(text)
PY
inst "$H" "$V"; rc=$?
check "LIF-15 old prefixed and unprefixed command files the manifest lists are removed" \
    "$([ $rc -eq 0 ] && [ ! -e "$H/.claude/commands/ah-ticket.md" ] && [ ! -e "$H/.claude/commands/ah-spec.md" ] && [ ! -e "$H/.claude/commands/start.md" ] && [ ! -e "$H/.claude/commands/lens.md" ] && [ ! -e "$H/.claude/commands/setup-client.md" ] && echo true || echo false)"
check "LIF-15 the user's own command files survive, even one named like an old prefixed command" \
    "$([ -f "$H/.claude/commands/mine.md" ] && [ -f "$H/.claude/commands/ah-notes.md" ] && echo true || echo false)"
check "LIF-15 the removed files are backed up and the tg- commands are installed" \
    "$([ -n "$(ls "$H"/.claude/tollgate/removed/*/ah-ticket.md 2>/dev/null)" ] && [ -f "$H/.claude/commands/tg-ticket.md" ] && [ -f "$H/.claude/commands/tg-start.md" ] && echo true || echo false)"
check "LIF-15 the old '# Tollgate (prefix: ah)' profile block is replaced by one block with no prefix" \
    "$([ "$(grep -c '^# Tollgate (' "$H/.zshrc")" = 1 ] && ! grep -q 'prefix: ah\|AH_SCRIPTS' "$H/.zshrc" && grep -q 'TOLLGATE_KNOWLEDGE' "$H/.zshrc" && echo true || echo false)"
run_install "$H" --uninstall; rc=$?
check "LIF-15 uninstall still leaves the user's own commands" "$([ $rc -eq 0 ] && [ -f "$H/.claude/commands/mine.md" ] && [ -f "$H/.claude/commands/ah-notes.md" ] && echo true || echo false)"
