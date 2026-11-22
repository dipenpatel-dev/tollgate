#!/usr/bin/env bash
# Installer tests VGT-01 to VGT-09: the vault git setting. Sourced by run.sh, which supplies check(),
# WORK and TOLLGATE_DIR. Every install runs in a throwaway home (see helpers.sh). Nothing here uses the
# network, and no remote is ever added.
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"
make_repo_copy

echo "── VGT vault git setting ───────────────────────────────────────"

vg_inst() { local h="$1" v="$2"; shift 2; run_install "$h" --non-interactive --name "Ada Tester" --vault "$v" --initials at --ticket-prefix tk "$@"; }
vg_line() { sed -n 's/^vault_git: //p' "$1/.claude/tollgate/paths.yaml"; }
vg_has_git() { [ -e "$1/.git" ] && echo true || echo false; }

# VGT-01 the flag sets the mode; none leaves the vault without git
H=$(new_world vgt01); V="$WORK/vgt01/vault"
vg_inst "$H" "$V" --vault-git none; rc=$?
check "VGT-01 --vault-git none: exit 0, paths file says none, no git init" \
    "$([ $rc -eq 0 ] && [ "$(vg_line "$H")" = none ] && [ "$(vg_has_git "$V")" = false ] && echo true || echo false)"

# VGT-02 local with the flag: git init on the vault, no remote
H=$(new_world vgt02); V="$WORK/vgt02/vault"
vg_inst "$H" "$V" --vault-git local; rc=$?
check "VGT-02 --vault-git local: saved, vault is a git repo, no remote" \
    "$([ $rc -eq 0 ] && [ "$(vg_line "$H")" = local ] && [ "$(vg_has_git "$V")" = true ] && [ -z "$(git -C "$V" remote)" ] && echo true || echo false)"

# VGT-03 remote: init, no remote added, one line telling the user to add it
H=$(new_world vgt03); V="$WORK/vgt03/vault"
vg_inst "$H" "$V" --vault-git=remote; rc=$?
check "VGT-03 --vault-git remote: saved, repo made, no remote added, user told to add one" \
    "$([ $rc -eq 0 ] && [ "$(vg_line "$H")" = remote ] && [ "$(vg_has_git "$V")" = true ] && [ -z "$(git -C "$V" remote)" ] \
       && grep -q 'remote add origin' "$WORK/vgt03/last.out" && echo true || echo false)"

# VGT-04 the env variable works, and the flag beats it
H=$(new_world vgt04); V="$WORK/vgt04/vault"
( export TOLLGATE_VAULT_GIT=local; vg_inst "$H" "$V" )
_env_only="$(vg_line "$H")"
H2=$(new_world vgt04b); V2="$WORK/vgt04b/vault"
( export TOLLGATE_VAULT_GIT=local; vg_inst "$H2" "$V2" --vault-git none )
check "VGT-04 TOLLGATE_VAULT_GIT is used when no flag is given (local, git init); the flag wins over it (none)" \
    "$([ "$_env_only" = local ] && [ "$(vg_has_git "$V")" = true ] && [ "$(vg_line "$H2")" = none ] && [ "$(vg_has_git "$V2")" = false ] && echo true || echo false)"

# VGT-05 non-interactive with no flag or env follows the folder: a fresh vault (no folder yet) is none
# and is not git-initialised; an existing git vault with no remote is local; one with a remote is remote;
# a plain folder is none.
H=$(new_world vgt05a); V="$WORK/vgt05a/vault"
vg_inst "$H" "$V"; rc=$?
_fresh="$(vg_line "$H")"; _fresh_git="$(vg_has_git "$V")"
H=$(new_world vgt05b); V="$WORK/vgt05b/vault"; mkdir -p "$V"; git init -q "$V"
vg_inst "$H" "$V"; _local="$(vg_line "$H")"
H=$(new_world vgt05c); V="$WORK/vgt05c/vault"; mkdir -p "$V"; git init -q "$V"; git -C "$V" remote add origin https://example.invalid/v.git
vg_inst "$H" "$V"; _remote="$(vg_line "$H")"
H=$(new_world vgt05d); V="$WORK/vgt05d/vault"; mkdir -p "$V"
vg_inst "$H" "$V"; _plain="$(vg_line "$H")"; _plain_git="$(vg_has_git "$V")"
check "VGT-05 non-interactive default: fresh=none (no git init), plain vault=none, git vault=local, git+remote=remote" \
    "$([ $rc -eq 0 ] && [ "$_fresh" = none ] && [ "$_fresh_git" = false ] && [ "$_plain" = none ] && [ "$_plain_git" = false ] \
       && [ "$_local" = local ] && [ "$_remote" = remote ] && echo true || echo false)"
check "VGT-05 the installer never added a remote or pushed" \
    "$([ "$(git -C "$WORK/vgt05b/vault" remote | wc -l | tr -d ' ')" = 0 ] && [ "$(git -C "$WORK/vgt05c/vault" remote)" = origin ] && echo true || echo false)"
# VGT-05e a saved local setting on a vault that has no .git becomes none on an unattended re-run
H=$(new_world vgt05e); V="$WORK/vgt05e/vault"; mkdir -p "$V"
vg_inst "$H" "$V" --vault-git none
sed -i.bak 's/^vault_git: .*/vault_git: local/' "$H/.claude/tollgate/paths.yaml"
vg_inst "$H" "$V"; rc=$?
check "VGT-05e saved local with no .git: unattended re-run saves none, no git init" \
    "$([ $rc -eq 0 ] && [ "$(vg_line "$H")" = none ] && [ "$(vg_has_git "$V")" = false ] && echo true || echo false)"

# VGT-06 a saved value is the default on update
H=$(new_world vgt06); V="$WORK/vgt06/vault"
vg_inst "$H" "$V" --vault-git none
vg_inst "$H" "$V"; rc=$?
check "VGT-06 update with no flag keeps the saved value (none), one vault_git line" \
    "$([ $rc -eq 0 ] && [ "$(vg_line "$H")" = none ] && [ "$(grep -c '^vault_git:' "$H/.claude/tollgate/paths.yaml")" = 1 ] && [ "$(vg_has_git "$V")" = false ] && echo true || echo false)"
vg_inst "$H" "$V" --vault-git local
check "VGT-06 an explicit flag on update replaces the saved value" "$([ "$(vg_line "$H")" = local ] && echo true || echo false)"

# VGT-07 a bad value is refused before anything is written
H=$(new_world vgt07); V="$WORK/vgt07/vault"
vg_inst "$H" "$V" --vault-git sometimes; rc=$?
check "VGT-07 bad --vault-git exits 2 and writes nothing" \
    "$([ $rc -eq 2 ] && [ ! -e "$H/.claude/tollgate/paths.yaml" ] && echo true || echo false)"

# VGT-08 tg_vault_git agrees with what the installer saved
H=$(new_world vgt08); V="$WORK/vgt08/vault"
vg_inst "$H" "$V" --vault-git local
_cli=$(TOLLGATE_PATHS="$H/.claude/tollgate/paths.yaml" TOLLGATE_KNOWLEDGE="$V" "$WORK/repo/scripts/core/tg_vault_git")
check "VGT-08 tg_vault_git prints the saved mode" "$([ "$_cli" = local ] && echo true || echo false)"

# VGT-09 dry run writes no paths file
H=$(new_world vgt09); V="$WORK/vgt09/vault"
vg_inst "$H" "$V" --vault-git local --dry-run; rc=$?
check "VGT-09 --dry-run saves nothing and makes no repo" \
    "$([ $rc -eq 0 ] && [ ! -e "$H/.claude/tollgate/paths.yaml" ] && [ "$(vg_has_git "$V")" = false ] && echo true || echo false)"
