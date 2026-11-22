#!/usr/bin/env bash
# Throwaway HOME helpers for Tollgate tests. Source this file.
#   tg_make_home        sets TG_ROOT and TG_HOME (fake user dir)
#   tg_run_in_home CMD  runs CMD with HOME and TOLLGATE_* pointed at the throwaway home
#   tg_clean_home       removes the throwaway home
# Real TOLLGATE_* values are unset first so nothing leaks in.

tg_make_home() {
  local fake="tgtester"
  [ "$fake" = "$(id -un)" ] && fake="tgtesterx"
  TG_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/tollgate-test-XXXXXX")"
  TG_HOME="$TG_ROOT/$fake"
  mkdir -p "$TG_HOME/vault" "$TG_HOME/code" "$TG_HOME/.claude" "$TG_HOME/.tollgate/state"
  export TG_ROOT TG_HOME
}

tg_run_in_home() {
  local unset_args=() v
  for v in $(compgen -e | grep '^TOLLGATE_' || true); do unset_args+=(-u "$v"); done
  (cd "$TG_HOME" && env ${unset_args[@]+"${unset_args[@]}"} \
    "HOME=$TG_HOME" \
    "TOLLGATE_KNOWLEDGE=$TG_HOME/vault" \
    "TOLLGATE_CODE_DIR=$TG_HOME/code" \
    "TOLLGATE_STATE_DIR=$TG_HOME/.tollgate/state" \
    "TOLLGATE_CONFIG=$TG_HOME/.claude/tollgate-config" \
    "TOLLGATE_HOME=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)" \
    "TOLLGATE_PATHS=$TG_HOME/.tollgate/paths.yaml" \
    "TOLLGATE_CONNECTORS=$TG_HOME/.tollgate/connectors" \
    "TOLLGATE_GATE_LOG=$TG_HOME/.tollgate/gate.log" \
    "TOLLGATE_NONINTERACTIVE=1" \
    "$@")
}

tg_clean_home() {
  [ -n "${TG_ROOT:-}" ] && [ -d "$TG_ROOT" ] && rm -rf "$TG_ROOT"
  unset TG_ROOT TG_HOME
}
