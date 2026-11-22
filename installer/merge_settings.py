#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: merge Tollgate's settings.json template into ~/.claude/settings.json without
       destroying the user's own settings; back the file up first; restore it on request
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Removed the SKILL_PREFIX argument and env.TOLLGATE_SKILL_PREFIX: commands have fixed tg- names. An old
    TOLLGATE_SKILL_PREFIX in the user's settings is removed on the next run (the manifest lists it).
  - Added the literal dollar escape: "$$" in a template string stays a single "$" and is never substituted,
    so a permission rule can keep the text $TOLLGATE_HOME. Duplicate template rules are listed once.
  - Owned-entries manifest (--manifest FILE): hooks, permission rules and env names Tollgate added are
    recorded; on the next run owned entries no longer in the template are removed (user entries never are).
    --uninstall removes every manifest-listed entry. Settings backups are pruned to the last 3.
  - Added --set (extra env values and placeholders), --template (extra repo settings
    fragments), --backup (copy before a changing write) and --restore.
  - Hook ownership now skips interpreters (python3, bash) so a user hook that runs the
    same interpreter is never mistaken for a Tollgate hook. Mixed groups keep the user's hooks.
  - Nothing is written, and no backup is made, when the merge changes nothing.
  - The settings file keeps its file mode after a merge.
  - History: an earlier version let an explicit empty SKILL_PREFIX remove env.TOLLGATE_SKILL_PREFIX and an omitted
    one keep it. Superseded by the fixed tg- names: the SKILL_PREFIX argument no longer exists.
  - History: an earlier version had an optional SKILL_PREFIX argument that wrote env.TOLLGATE_SKILL_PREFIX (gate
    hook). Superseded the same way.
  - Retired Tollgate allow rules (RETIRED_ALLOW_RULES) are removed on update even when the manifest does not list
    them, for users installed before the manifest recorded permissions. Exact text match only.
  - Created. Replaces the sed overwrite in install.sh, which discarded every
    user key (hooks, permissions, env, model, plugins, statusLine).

Rules:
  - Literal dollar escape: write "$$" in the template where a single "$" must survive. The substitution
    runs on a copy where "$$" is hidden, so "$$TOLLGATE_HOME/x" installs as the literal text
    "$TOLLGATE_HOME/x". Used for the permission rule that matches the command text Claude sends, which
    holds the unexpanded $TOLLGATE_HOME, beside the rule with the absolute path.
  - Placeholders ($CLAUDE_DOTFILES, $TOLLGATE_KNOWLEDGE, $TOLLGATE_SCRIPTS, and the name of
    every --set value) are substituted inside parsed JSON strings, so paths with quotes or
    backslashes cannot break the JSON.
  - hooks: Tollgate owned hooks (any command whose script file name is a Tollgate hook) are
    removed, including stale paths from a moved repo, then the template groups are added.
    User hooks, and user hooks sitting in the same group, are kept untouched.
  - permissions allow/ask/deny and additionalDirectories: union, order preserved.
  - env: TOLLGATE_KNOWLEDGE, TOLLGATE_CODE_DIR, CLAUDE_DOTFILES set (GUI launched editors do not load
    the shell profile), plus every --set KEY=VALUE. TOLLGATE_SKILL_PREFIX from an older install is
    removed. Other env keys kept.
  - Any other key (model, plugins, statusLine, ...): user value wins; template adds keys the
    user does not have.
  - Unreadable existing file: backed up when --backup is given, merge starts from {} and says so.
  - Write is atomic (temp file + os.replace) and goes through symlinks to the real file.
  - A second run with the same inputs writes nothing and makes no backup.

Usage:
  merge_settings.py [OPTIONS] TEMPLATE TARGET REPO_DIR VAULT_DIR SCRIPTS_DIR CODE_DIR
  merge_settings.py --restore TARGET [BACKUP_FILE]
  merge_settings.py --uninstall --manifest FILE [--backup] TARGET
Options: --set KEY=VALUE (repeatable), --template FILE (repeatable), --backup,
         --manifest FILE (owned-entries manifest; see installer/manifest.py)
"""

from __future__ import annotations

import glob
import json
import os
import shlex
import shutil
import stat
import sys
import tempfile
import time

LIST_PERMISSION_KEYS = ("allow", "ask", "deny", "additionalDirectories")
KEEP_BACKUPS = 3
N_ARGS = 6
OLD_SKILL_PREFIX_ENV = "TOLLGATE_SKILL_PREFIX"   # written by older installs; removed on update
# Broad allow rules an early Tollgate shipped. $CLAUDE_DOTFILES is matched both as written and as the repo dir.
RETIRED_ALLOW_RULES = ("Bash(git config:*)", "Bash(python3 $CLAUDE_DOTFILES/rag/query_index.py:*)")
DOLLAR_ESCAPE = "$$"
DOLLAR_HIDDEN = "\x00tollgate-dollar\x00"
INTERPRETERS = {"python", "python3", "bash", "sh", "zsh", "env", "node", "exec", "sudo"}
USAGE = "Usage: merge_settings.py [--set K=V] [--template FILE] [--manifest FILE] [--backup] TEMPLATE TARGET REPO_DIR " \
        "VAULT_DIR SCRIPTS_DIR CODE_DIR   |   merge_settings.py --restore TARGET [BACKUP_FILE]"


def substitute(node: object, values: dict[str, str]) -> object:
    """Replace placeholders in every string of a parsed JSON tree. "$$" is hidden during the
    replacement and comes back as one literal "$", so "$$TOLLGATE_HOME" is kept as "$TOLLGATE_HOME"."""
    if isinstance(node, str):
        node = node.replace(DOLLAR_ESCAPE, DOLLAR_HIDDEN)
        for key, value in values.items():
            node = node.replace(key, value)
        return node.replace(DOLLAR_HIDDEN, "$")
    if isinstance(node, list):
        return [substitute(item, values) for item in node]
    if isinstance(node, dict):
        return {k: substitute(v, values) for k, v in node.items()}
    return node


def command_basename(command: str) -> str:
    """File name of the script a command runs. Interpreters and their flags are skipped."""
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    for part in parts:
        name = os.path.basename(part)
        if part.startswith("-") or name in INTERPRETERS or "=" in part.split("/")[0]:
            continue
        return name
    return ""


def hook_key(hook: dict) -> str:
    """Identity of one hook entry: script name for commands, full JSON for anything else."""
    if isinstance(hook, dict) and hook.get("type", "command") == "command" and hook.get("command"):
        name = command_basename(hook["command"])
        if name:
            return "cmd:" + name
    return "json:" + json.dumps(hook, sort_keys=True)


def hook_basenames(hooks: dict) -> set[str]:
    """Identities of every hook in a hooks tree (kept under this name for older callers)."""
    return {hook_key(h) for groups in hooks.values() for g in groups for h in g.get("hooks", [])}


def merge_hooks(user: dict, template: dict, previously_owned=()) -> dict:
    """Drop Tollgate owned hooks from the user's hooks, then append the template's groups.

    previously_owned: hook identities the manifest says Tollgate added earlier. They are removed
    too, so a hook dropped or renamed upstream does not stay in the user's settings.
    """
    owned = hook_basenames(template) | set(previously_owned)
    merged: dict[str, list] = {}
    for event, groups in user.items():
        kept = []
        for group in groups:
            hooks = group.get("hooks", [])
            mine = [h for h in hooks if hook_key(h) not in owned]
            if len(mine) == len(hooks):
                kept.append(group)
            elif mine:
                kept.append({**group, "hooks": mine})
        if kept:
            merged[event] = kept
    for event, groups in template.items():
        merged.setdefault(event, []).extend(groups)
    return merged


def union(first: list, second: list) -> list:
    return first + [item for item in second if item not in first]


def combine_templates(base: dict, extra: dict) -> dict:
    """Fold a second repo settings fragment into the base template."""
    out = dict(base)
    for key, value in extra.items():
        if key == "hooks":
            hooks = {e: list(g) for e, g in (out.get("hooks") or {}).items()}
            for event, groups in value.items():
                have = hooks.setdefault(event, [])
                have.extend(g for g in groups if g not in have)
            out["hooks"] = hooks
        elif key == "permissions":
            perms = dict(out.get("permissions") or {})
            for pkey, pvalue in value.items():
                perms[pkey] = union(perms.get(pkey) or [], pvalue) if pkey in LIST_PERMISSION_KEYS \
                    else perms.get(pkey, pvalue)
            out["permissions"] = perms
        elif key == "env":
            out["env"] = {**(out.get("env") or {}), **value}
        else:
            out.setdefault(key, value)
    return out


def merge_permissions(user_perms: dict, tmpl_perms: dict, old_owned: dict, repo_dir: str = "") -> tuple[dict, dict]:
    """Union the template into the user's permissions, dropping owned rules the template no longer has.

    Returns (permissions, owned) where owned lists the rules Tollgate added (never one the user
    already had before Tollgate added it, and never a user rule).
    """
    perms = dict(user_perms)
    owned: dict[str, list] = {}
    for key, value in tmpl_perms.items():
        if key not in LIST_PERMISSION_KEYS:
            perms.setdefault(key, value)
    for key in LIST_PERMISSION_KEYS:
        tmpl = list(dict.fromkeys(tmpl_perms.get(key) or []))   # a rule listed twice (both forms equal) is kept once
        old = old_owned.get(key) or []
        have = perms.get(key) or []
        stale = [r for r in old if r not in tmpl]
        if key == "allow":
            retired = set(RETIRED_ALLOW_RULES) | {r.replace("$CLAUDE_DOTFILES", repo_dir) for r in RETIRED_ALLOW_RULES if repo_dir}
            stale += [r for r in have if r in retired and r not in tmpl]
        base = [r for r in have if r not in stale]
        mine = [r for r in tmpl if r in old or r not in have]
        result = union(base, tmpl)
        if result or key in perms:
            perms[key] = result
        if mine:
            owned[key] = mine
    return perms, owned


def merge_full(user: dict, template: dict, env: dict[str, str], manifest: dict | None = None) -> tuple[dict, dict]:
    """Merge, and also return what Tollgate owns now: {hooks, permissions, env}."""
    manifest = manifest or {}
    result = dict(user)
    for key, value in template.items():
        if key not in ("hooks", "permissions", "env"):
            result.setdefault(key, value)
    result["hooks"] = merge_hooks(user.get("hooks") or {}, template.get("hooks") or {}, manifest.get("hooks") or [])
    result["permissions"], owned_perms = merge_permissions(
        user.get("permissions") or {}, template.get("permissions") or {}, manifest.get("permissions") or {}, env.get("CLAUDE_DOTFILES", ""))
    result["env"] = {**(user.get("env") or {}), **(template.get("env") or {}), **env}
    result["env"].pop(OLD_SKILL_PREFIX_ENV, None)
    owned = {"hooks": sorted(hook_basenames(template.get("hooks") or {})),
             "permissions": owned_perms,
             "env": sorted(set((template.get("env") or {}).keys()) | set(env.keys()))}
    return result, owned


def merge(user: dict, template: dict, env: dict[str, str], manifest: dict | None = None) -> dict:
    return merge_full(user, template, env, manifest)[0]


def strip_owned(user: dict, manifest: dict) -> dict:
    """Remove every entry the manifest lists. Used by --uninstall. User entries are kept."""
    result = dict(user)
    hooks = merge_hooks(user.get("hooks") or {}, {}, manifest.get("hooks") or [])
    if hooks:
        result["hooks"] = hooks
    else:
        result.pop("hooks", None)
    perms = dict(user.get("permissions") or {})
    for key, rules in (manifest.get("permissions") or {}).items():
        if key in perms:
            perms[key] = [r for r in perms[key] if r not in rules]
            if not perms[key]:
                del perms[key]
    if perms:
        result["permissions"] = perms
    else:
        result.pop("permissions", None)
    env = {k: v for k, v in (user.get("env") or {}).items() if k not in (manifest.get("env") or [])}
    if env:
        result["env"] = env
    else:
        result.pop("env", None)
    return result


def load_user(target: str) -> dict:
    if not os.path.exists(target):
        return {}
    try:
        with open(target) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        print(f"  Existing {target} is not valid JSON; starting from empty (backup kept).", file=sys.stderr)
        return {}


def write_text_atomic(target: str, text: str) -> None:
    real = os.path.realpath(target)
    os.makedirs(os.path.dirname(real), exist_ok=True)
    mode = stat.S_IMODE(os.stat(real).st_mode) if os.path.exists(real) else None
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(real), prefix=".settings.", suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, real)


def write_atomic(target: str, data: dict) -> None:
    write_text_atomic(target, json.dumps(data, indent=2) + "\n")


def unique_path(base: str) -> str:
    stamp = time.strftime("%Y%m%d%H%M%S")
    path = f"{base}.{stamp}"
    n = 0
    while os.path.exists(path):
        n += 1
        path = f"{base}.{stamp}-{n}"
    return path


def make_backup(target: str) -> str:
    """Copy the settings file (symlinks followed) beside it. Returns the backup path."""
    path = unique_path(target + ".bak")
    shutil.copyfile(target, path)
    prune_backups(target)
    return path


def prune_backups(target: str, keep: int = KEEP_BACKUPS) -> None:
    """Keep only the newest `keep` settings.json.bak.<time> files (the ones this tool makes)."""
    found = sorted(glob.glob(target + ".bak.*"))
    for old in found[:-keep] if len(found) > keep else []:
        try:
            os.remove(old)
        except OSError:
            pass


def restore(target: str, backup: str | None) -> int:
    if backup is None:
        found = glob.glob(target + ".bak.*")
        if not found:
            print(f"  No settings backup found next to {target}.", file=sys.stderr)
            return 1
        backup = max(found, key=lambda p: (os.stat(p).st_mtime_ns, p))
    if not os.path.isfile(backup):
        print(f"  Backup file not found: {backup}", file=sys.stderr)
        return 1
    with open(backup) as fh:
        text = fh.read()
    if os.path.exists(target):
        saved = unique_path(target + ".before-restore")
        shutil.copyfile(target, saved)
        print(f"  Current settings saved to {saved}")
    write_text_atomic(target, text)
    print(f"  Restored {target} from {backup}")
    return 0


def parse_options(args: list[str]) -> tuple[list[str], dict[str, str], list[str], bool, str, bool]:
    positional: list[str] = []
    sets: dict[str, str] = {}
    templates: list[str] = []
    backup = False
    manifest = ""
    uninstall = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--backup":
            backup = True
        elif arg == "--uninstall":
            uninstall = True
        elif arg in ("--set", "--template", "--manifest") and i + 1 < len(args):
            i += 1
            if arg == "--manifest":
                manifest = args[i]
            elif arg == "--template":
                templates.append(args[i])
            else:
                key, _, value = args[i].partition("=")
                sets[key] = value
        else:
            positional.append(arg)
        i += 1
    return positional, sets, templates, backup, manifest, uninstall


def uninstall(target: str, manifest_path: str, do_backup: bool) -> int:
    manifest = load_manifest(manifest_path)
    if not manifest:
        print("  No Tollgate manifest found; no settings entries removed.")
        return 0
    existing = load_user(target)
    cleaned = strip_owned(existing, manifest)
    if not os.path.exists(target) or cleaned == existing:
        print("  No Tollgate entries found in settings.")
        return 0
    if do_backup:
        print(f"  Backed up settings to {make_backup(target)}")
    write_atomic(target, cleaned)
    print("  Removed Tollgate hooks, permissions and env entries from settings.")
    return 0


def load_manifest(path: str) -> dict:
    if not path:
        return {}
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import manifest as manifest_module
    return manifest_module.load(path)


def save_manifest(path: str, owned: dict) -> None:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import manifest as manifest_module
    data = manifest_module.load(path)
    data.update(owned)
    manifest_module.save(path, data)


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "--restore":
        return restore(argv[2], argv[3] if len(argv) > 3 else None)
    positional, sets, extra_templates, do_backup, manifest_path, do_uninstall = parse_options(argv[1:])
    if do_uninstall:
        if len(positional) != 1:
            print(USAGE, file=sys.stderr)
            return 2
        return uninstall(positional[0], manifest_path, do_backup)
    if len(positional) != N_ARGS:
        print(USAGE, file=sys.stderr)
        return 2
    template_path, target, repo_dir, vault_dir, scripts_dir, code_dir = positional
    with open(template_path) as fh:
        template = json.load(fh)
    for path in extra_templates:
        with open(path) as fh:
            template = combine_templates(template, json.load(fh))
    placeholders = {"$CLAUDE_DOTFILES": repo_dir, "$TOLLGATE_KNOWLEDGE": vault_dir,
                    "$TOLLGATE_SCRIPTS": scripts_dir}
    placeholders.update({"$" + k: v for k, v in sets.items()})
    ordered = dict(sorted(placeholders.items(), key=lambda kv: -len(kv[0])))
    template = substitute(template, ordered)
    env = {"TOLLGATE_KNOWLEDGE": vault_dir, "TOLLGATE_CODE_DIR": code_dir, "CLAUDE_DOTFILES": repo_dir}
    env.update(sets)
    existing = load_user(target)
    merged, owned = merge_full(existing, template, env, load_manifest(manifest_path))
    if manifest_path:
        save_manifest(manifest_path, owned)
    if os.path.exists(target) and merged == existing:
        print("  Settings already up to date; nothing written.")
        return 0
    if do_backup and os.path.exists(target):
        print(f"  Backed up settings to {make_backup(target)}")
    write_atomic(target, merged)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
