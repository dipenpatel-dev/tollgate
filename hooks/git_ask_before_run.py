#!/usr/bin/env python3
"""Ask the user before a git commit or git push runs, and block protected pushes.

Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: PreToolUse Bash hook helper. Mode "commit" asks before every git commit.
       Mode "push" asks before every git push, and denies a push to a protected
       branch unless TOLLGATE_ALLOW_PROTECTED_PUSH is 1. Mode "readonly" denies the
       ways an auto-approved git status, log, diff, show or config can run code,
       write a file or read any file (-c, --config-env, --output, --ext-diff, diff --no-index,
       a diff of two paths outside the repo, config writes of keys that name a program).
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Readonly mode denies git diff --no-index (and abbreviations) and a diff of two paths outside
    the repo, which git treats as --no-index and which printed any file on disk.
  - Commands are now parsed with shlex per shell segment: env and VAR=value prefixes, a path to
    git, global options (-c, -C, --no-pager, --git-dir, --work-tree), subshells, and sh -c, bash -c
    and eval strings no longer hide a commit or push. Added the readonly mode. A payload that
    cannot be read or an unexpected error now exits 2 (blocks) instead of allowing.
  - Created. Ported from the dotfiles version; branch list and override come
    from TOLLGATE_PROTECTED_BRANCHES and TOLLGATE_ALLOW_PROTECTED_PUSH.

Trigger: PreToolUse, Bash (called by git_commit_guard.sh and git_push_guard.sh)
Output: JSON decision on stdout (ask or deny) and exit 0. No output means allow. Exit 2 with a
stderr message when the payload cannot be read or the hook hits an unexpected error (fails closed).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys
from typing import Optional

HOOK_EVENT = "PreToolUse"
DEFAULT_PROTECTED = "main master"
MAX_LISTED_ITEMS = 15
GIT_TIMEOUT_SECONDS = 5
FORCE_FLAGS = ("--force", "-f", "--force-with-lease", "--force-if-includes")
WHOLE_REPO_FLAGS = ("--all", "--mirror")
PUSH_VALUE_FLAGS = frozenset({"--repo", "--receive-pack", "--exec", "-o", "--push-option"})

logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("git_ask_before_run")


SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})
LEADING_WORDS = frozenset({"{", "}", "!", "if", "then", "else", "elif", "do", "while", "until"})
WRAPPER_ARG_FLAGS = {
    "env": frozenset({"-u", "-C"}),
    "sudo": frozenset({"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"}),
    "nice": frozenset({"-n"}),
    "timeout": frozenset({"-s", "-k"}),
    "command": frozenset(),
    "exec": frozenset({"-a"}),
    "nohup": frozenset(),
    "time": frozenset(),
    "builtin": frozenset(),
}
GIT_GLOBAL_WITH_VALUE = frozenset({"--git-dir", "--work-tree", "--namespace", "--super-prefix",
                                   "--config-env", "--attr-source"})
VAR_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
BREAK_RE = re.compile(r"^[;&|()]+$")
SHELL_C_RE = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")
MAX_DEPTH = 5


class GitCall:
    """One parsed git invocation: verb, its arguments, the -C path and any -c / --config-env values."""

    def __init__(self, verb: str, args: list[str], repo: Optional[str], configs: list[str]) -> None:
        self.verb = verb
        self.args = args
        self.repo = repo
        self.configs = configs


def lex(text: str) -> list[str]:
    """Split a shell line into tokens, with control operators as their own tokens.

    Newlines and backticks count as command separators. If the quotes do not balance, fall back to
    a crude split on operators so the detection stays on (it over-detects rather than misses).
    """
    flat = text.replace("\n", " ; ").replace("`", " ; ")
    try:
        lexer = shlex.shlex(flat, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        out: list[str] = []
        for chunk in re.split(r"[;&|()]", flat):
            out.extend(chunk.split())
            out.append(";")
        return out


def split_segments(tokens: list[str]) -> list[list[str]]:
    """Cut a token list at control operators."""
    segments: list[list[str]] = [[]]
    for token in tokens:
        if BREAK_RE.match(token):
            segments.append([])
        else:
            segments[-1].append(token)
    return [seg for seg in segments if seg]


def split_words(text: str) -> list[str]:
    """Split an env -S string into words the way env does; fall back to blanks if quotes break."""
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def split_string_value(seg: list[str], i: int) -> Optional[tuple[str, int]]:
    """For env -S STRING, -SSTRING, --split-string STRING or --split-string=STRING at seg[i], return
    (STRING, words used); otherwise None."""
    tok = seg[i]
    if tok in ("-S", "--split-string") and i + 1 < len(seg):
        return seg[i + 1], 2
    if tok.startswith("--split-string="):
        return tok.split("=", 1)[1], 1
    if tok.startswith("-S") and len(tok) > 2:
        return tok[2:], 1
    return None


def strip_prefixes(seg: list[str]) -> list[str]:
    """Drop leading VAR=value words, leading shell keywords and wrapper commands (env, sudo, ...)."""
    i = 0
    while i < len(seg):
        tok = seg[i]
        base = os.path.basename(tok)
        if VAR_ASSIGN_RE.match(tok) or tok in LEADING_WORDS:
            i += 1
        elif base in WRAPPER_ARG_FLAGS and base not in ("git",):
            flags = WRAPPER_ARG_FLAGS[base]
            i += 1
            while i < len(seg):
                nxt = seg[i]
                if base == "env" and split_string_value(seg, i) is not None:
                    value, used = split_string_value(seg, i)
                    seg = seg[:i] + split_words(value) + seg[i + used:]
                    break
                if nxt in flags and i + 1 < len(seg):
                    i += 2
                elif nxt.startswith("-") or VAR_ASSIGN_RE.match(nxt) or (
                        base in ("timeout", "nice") and re.fullmatch(r"[0-9.]+[smhd]?", nxt)):
                    i += 1
                else:
                    break
        else:
            break
    return seg[i:]


def parse_git_call(seg: list[str]) -> Optional[GitCall]:
    """Parse `git [global options] verb args` from a stripped segment."""
    if not seg or os.path.basename(seg[0]) != "git":
        return None
    repo: Optional[str] = None
    configs: list[str] = []
    i = 1
    while i < len(seg):
        tok = seg[i]
        if tok == "-c" and i + 1 < len(seg):
            configs.append(seg[i + 1])
            i += 2
        elif tok == "-C" and i + 1 < len(seg):
            repo = seg[i + 1]
            i += 2
        elif tok in GIT_GLOBAL_WITH_VALUE and i + 1 < len(seg):
            if tok == "--config-env":
                configs.append(seg[i + 1])
            i += 2
        elif tok.startswith("--config-env="):
            configs.append(tok.split("=", 1)[1])
            i += 1
        elif tok.startswith("-"):
            i += 1
        else:
            return GitCall(tok, seg[i + 1:], repo, configs)
    return None


def git_calls(cmd: str, depth: int = 0) -> list[GitCall]:
    """Every git invocation in a command line, including ones inside sh -c, eval, $( ) and backticks."""
    calls: list[GitCall] = []
    if depth > MAX_DEPTH:
        return calls
    for seg in split_segments(lex(cmd)):
        seg = strip_prefixes(seg)
        if not seg:
            continue
        head = os.path.basename(seg[0])
        call = parse_git_call(seg)
        if call is not None:
            calls.append(call)
        elif head in SHELLS:
            for idx, tok in enumerate(seg[1:], start=1):
                if SHELL_C_RE.match(tok) and idx + 1 < len(seg):
                    calls.extend(git_calls(seg[idx + 1], depth + 1))
                    break
        elif head == "eval":
            calls.extend(git_calls(" ".join(seg[1:]), depth + 1))
        for tok in seg:
            if "$(" in tok:
                calls.extend(git_calls(tok.replace("$(", " ; ").replace(")", " ; "), depth + 1))
    return calls


def run_git(repo: str, args: list[str]) -> str:
    """Run a read-only git command in repo; return stdout, or empty text on failure."""
    try:
        out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                             timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("git call failed: %s", exc)
        return ""
    return out.stdout.strip()


def extract_message(cmd: str) -> Optional[str]:
    """Return the first -m value when the command line parses cleanly, else None."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return None
    for index, token in enumerate(tokens[:-1]):
        if token == "-m":
            return tokens[index + 1]
    return None


def limited(items: list[str]) -> str:
    """Join items one per line, capped so the prompt stays readable."""
    shown = items[:MAX_LISTED_ITEMS]
    extra = len(items) - len(shown)
    lines = [f"  - {item}" for item in shown]
    if extra > 0:
        lines.append(f"  - and {extra} more")
    return "\n".join(lines) if lines else "  (none)"


def protected_branches() -> list[str]:
    """Protected branch names from TOLLGATE_PROTECTED_BRANCHES (space or comma separated)."""
    raw = os.environ.get("TOLLGATE_PROTECTED_BRANCHES", DEFAULT_PROTECTED)
    return [name for name in re.split(r"[\s,]+", raw) if name]


def pushed_branches(args: list[str], repo: str) -> tuple[list[str], bool]:
    """Return (target branch names, whole_repo flag) for the arguments of a push command."""
    whole_repo = any(token in WHOLE_REPO_FLAGS for token in args)
    words: list[str] = []
    skip = False
    for token in args:
        if skip:
            skip = False
        elif token in PUSH_VALUE_FLAGS:
            skip = True
        elif not token.startswith("-"):
            words.append(token)
    refspecs = words[1:]
    current = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    targets: list[str] = []
    for spec in refspecs:
        dest = spec.lstrip("+").split(":")[-1]
        dest = dest.removeprefix("refs/heads/")
        targets.append(current if dest == "HEAD" else dest)
    if not refspecs and current:
        targets.append(current)
    return targets, whole_repo


def protected_hit(args: list[str], repo: str) -> Optional[str]:
    """Name what the push touches on a protected branch, or None."""
    protected = protected_branches()
    targets, whole_repo = pushed_branches(args, repo)
    if whole_repo:
        return "all branches (--all or --mirror)"
    for branch in targets:
        if branch in protected:
            return branch
    return None


def describe_commit(cmd: str, repo: str) -> str:
    """Plain description of what this commit will do."""
    branch = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    staged = run_git(repo, ["diff", "--cached", "--name-only"]).splitlines()
    message = extract_message(cmd)
    draft = message if message and "$(" not in message else "(see command; message is built inline)"
    return (f"command: commits staged files on branch {branch}\n"
            f"files staged:\n{limited(staged)}\n"
            f"draft message: {draft}")


def describe_push(cmd: str, repo: str) -> str:
    """Plain description of what this push will send."""
    branch = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    ahead = run_git(repo, ["log", "--oneline", "@{u}..HEAD"]).splitlines()
    if not ahead:
        ahead = run_git(repo, ["log", "--oneline", "-5"]).splitlines()
        scope = "no upstream found, showing latest commits"
    else:
        scope = f"{len(ahead)} commit(s) not yet on the remote"
    forced = [flag for flag in FORCE_FLAGS if re.search(rf"\s{re.escape(flag)}(\s|=|$)", cmd)]
    warn = f"\nFORCE PUSH FLAG: {', '.join(forced)}" if forced else ""
    return (f"command: sends branch {branch} to the remote ({scope})\n"
            f"commits:\n{limited(ahead)}{warn}")


def build_reason(verb: str, cmd: str, repo: str) -> str:
    """Compose the full approval text."""
    body = describe_commit(cmd, repo) if verb == "commit" else describe_push(cmd, repo)
    return f"git {verb} in {repo}\n{body}\nraw command: {cmd}"


READ_VERBS = frozenset({"diff", "log", "show", "status", "config"})
CONFIG_WRITE_FLAGS = frozenset({"--add", "--unset", "--unset-all", "--replace-all", "--edit", "-e",
                                "--rename-section", "--remove-section", "--set-all"})
CONFIG_READ_FLAGS = frozenset({"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l"})
CONFIG_VALUE_FLAGS = frozenset({"--file", "-f", "--blob", "--type", "--default", "--comment"})
DANGEROUS_KEY_RE = re.compile(
    r"^(core\.(fsmonitor|pager|sshcommand|editor|hookspath|askpass|gitproxy)"
    r"|diff\.external|diff\..*\.(textconv|command)|alias\..*|credential\..*|filter\..*"
    r"|merge\..*\.(driver|name)|sequence\.editor|gpg\..*|pager\..*|include.*|url\..*"
    r"|uploadpack\..*|receive\..*|protocol\..*|safe\..*|http\..*"
    r"|(difftool|mergetool|browser|man)\..*\.(cmd|path)|web\.browser|interactive\.diffFilter"
    r"|trailer\..*\.(cmd|command)|core\.alternateRefsCommand)$", re.IGNORECASE)
READONLY_DENY = ("BLOCKED: {what}. This form can run a program or overwrite a file from a git command "
                 "that is otherwise auto-approved. Run it yourself in a terminal if you need it.")


def config_write_key(args: list[str]) -> Optional[str]:
    """For `git config` arguments, return the key being written, or None when it only reads."""
    if args and args[0] in ("get", "list"):
        return None
    if args and args[0] in ("set", "unset", "edit", "rename-section", "remove-section"):
        return args[1] if len(args) > 1 and not args[1].startswith("-") else ""
    positional: list[str] = []
    skip = False
    wrote = False
    for token in args:
        if skip:
            skip = False
        elif token in CONFIG_VALUE_FLAGS:
            skip = True
        elif token in CONFIG_WRITE_FLAGS:
            wrote = True
        elif token in CONFIG_READ_FLAGS:
            return None
        elif not token.startswith("-"):
            positional.append(token)
    if wrote or len(positional) >= 2:
        return positional[0] if positional else ""
    return None


NO_INDEX_FLAG = "--no-index"
NO_INDEX_MIN_PREFIX = len("--no-in")


def is_no_index_flag(token: str) -> bool:
    """True for --no-index, its =value form, or a long abbreviation of it (git accepts unique prefixes)."""
    name = token.split("=", 1)[0]
    return len(name) >= NO_INDEX_MIN_PREFIX and NO_INDEX_FLAG.startswith(name)


def outside_repo(path: str, base: str, top: str) -> bool:
    """True when a diff path argument is not inside the repository at top (unknown top: outside)."""
    if "$" in path or path.startswith("`"):
        return True
    full = os.path.realpath(os.path.join(base, os.path.expanduser(path)))
    if not top:
        return True
    top = os.path.realpath(top)
    return full != top and not full.startswith(top + os.sep)


def implicit_no_index(call: GitCall, base: str) -> bool:
    """True when git diff would compare two files outside the repo without --no-index.

    Git switches to no-index mode by itself when it is run outside a repository, or when both path
    arguments are outside the repository. That prints any file just like --no-index does.
    """
    words = [t for t in call.args if t != "--" and not t.startswith("-")]
    if len(words) < 2:
        return False
    repo = call.repo or base
    top = run_git(repo, ["rev-parse", "--show-toplevel"])
    first_two = words[:2]
    return all(outside_repo(w, repo, top) for w in first_two)


def readonly_problem(call: GitCall, base: str = ".") -> Optional[str]:
    """Name what is unsafe in a git status, log, diff, show or config call, or None."""
    if call.verb not in READ_VERBS:
        return None
    if call.configs:
        return f"git -c or --config-env on git {call.verb}"
    if call.verb == "diff":
        if any(is_no_index_flag(token) for token in call.args):
            return "git diff --no-index prints any file on disk, including secrets, with no repo needed"
        if implicit_no_index(call, base):
            return "git diff of two paths outside the repo prints any file on disk like --no-index"
    if call.verb in ("diff", "log", "show"):
        for token in call.args:
            if token == "--output" or token.startswith("--output="):
                return f"git {call.verb} --output writes a file"
            if token == "--ext-diff":
                return f"git {call.verb} --ext-diff runs an external program"
    if call.verb == "config":
        key = config_write_key(call.args)
        if key is not None and (key == "" or DANGEROUS_KEY_RE.match(key)):
            return f"git config write of '{key or 'unknown key'}' can make git run a program"
    return None


def decide_readonly(payload: dict) -> Optional[tuple[str, str]]:
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    base = payload.get("cwd") or os.getcwd()
    for call in git_calls(cmd):
        problem = readonly_problem(call, base)
        if problem:
            return "deny", READONLY_DENY.format(what=problem)
    return None


def decide(verb: str, payload: dict) -> Optional[tuple[str, str]]:
    """Return (decision, text) when this call needs a decision, else None."""
    if verb == "readonly":
        return decide_readonly(payload)
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    calls = [call for call in git_calls(cmd) if call.verb == verb]
    if not calls:
        return None
    first_repo = calls[0].repo or payload.get("cwd") or "."
    if verb == "push" and os.environ.get("TOLLGATE_ALLOW_PROTECTED_PUSH", "") != "1":
        for call in calls:
            hit = protected_hit(call.args, call.repo or payload.get("cwd") or ".")
            if hit:
                return "deny", (
                    f"BLOCKED: direct push to protected branch '{hit}'. "
                    "Push a feature branch and open a pull request instead. "
                    "To allow one push, the owner sets TOLLGATE_ALLOW_PROTECTED_PUSH=1 outside Claude.")
    return "ask", build_reason(verb, cmd, first_repo)


def main(argv: list[str]) -> int:
    """Read hook JSON from stdin; print an ask or deny decision when needed."""
    if len(argv) != 2 or argv[1] not in ("commit", "push", "readonly"):
        log.warning("usage: git_ask_before_run.py commit|push|readonly")
        return 2
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        log.warning("git_ask_before_run: payload is not JSON, blocking")
        return 2
    if not isinstance(payload, dict):
        log.warning("git_ask_before_run: payload is not a JSON object, blocking")
        return 2
    result = decide(argv[1], payload)
    if result is None:
        return 0
    decision, reason = result
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": HOOK_EVENT,
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv)
    except Exception as exc:  # fail closed: a hook that cannot decide must not let git through
        log.warning("git_ask_before_run error: %s", exc)
        code = 2
    sys.exit(code)
