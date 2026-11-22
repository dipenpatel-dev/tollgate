#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: Bash side of the read-only code directory guard (TOLLGATE_CODE_DIR) and of the
       protected Tollgate files list (hooks/lib/protected_paths.py)
Ticket: none (Tollgate is not Jira tracked)
ChangeLog:
  - Also denies writes to Tollgate's own files (hooks, settings, credentials, ~/.tollgate, shell
    profiles), sh -c bodies are checked, and python -c / node -e bodies that name a protected
    path and write. Paths compare in lower case.
  - Created.

Trigger: PreToolUse, Bash
Action: deny a command that writes into TOLLGATE_CODE_DIR. Detected, per command segment:
        rm mv cp touch tee mkdir rmdir ln install truncate dd chmod chown
        (cp, install and ln only when the protected dir is the destination, so reading from it is fine), `sed -i`,
        output redirection (> >> &>), and any git subcommand other than a read-only one
        when the target is inside the protected directory (path argument, `git -C`, or the
        working directory set by an earlier `cd` or by the session).
Method: conservative path-prefix match on the command text. Paths are tokenized, ~ is expanded,
        relative paths are resolved against the tracked working directory, then realpath is
        compared to the realpath of TOLLGATE_CODE_DIR. $TOLLGATE_CODE_DIR is expanded textually.
Limits (not caught): paths built from other variables expanded later, command substitution,
        obfuscated or encoded paths, scripts that write there internally, interpreters writing
        through code (python -c, perl -e), symlinks created after the check, writes by tools
        that take the target from a config file.
The code dir part is inactive and silent when TOLLGATE_CODE_DIR is unset (the Write/Edit hook
prints the warning); the protected Tollgate files part is always active.
Fails closed on unreadable input, a missing helper module or any internal error (exit 2).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)
try:
    import protected_paths as pp
except Exception as exc:  # fail closed: without the file list this guard cannot decide
    sys.stderr.write("pre-tool-bash-guard-code-dir: %s importing protected_paths; blocking (fails closed).\n"
                     % type(exc).__name__)
    sys.exit(2)

HOOK_EVENT = "PreToolUse"
ENV_NAME = "TOLLGATE_CODE_DIR"
SEPARATORS_CHARS = set(";&|")
DEST_ONLY_VERBS = {"cp", "install", "ln"}
WRITE_VERBS = {"rm", "mv", "touch", "tee", "mkdir", "rmdir", "truncate",
               "dd", "chmod", "chown"}
GIT_READ_ONLY = {"status", "log", "diff", "show", "ls-files", "ls-tree", "rev-parse", "blame", "grep",
                 "describe", "cat-file", "shortlog", "remote", "config", "version", "help"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
INTERPRETER_RE = re.compile(r"^(python[0-9.]*|node|nodejs|perl|ruby|php)$")
INLINE_FLAGS = {"-c", "-e", "-E", "-p", "-r", "--eval", "--command"}
# Names a model could type to reach a protected file without the full path.
PATH_MARKERS = (".zshrc", ".bashrc", ".bash_profile", ".profile", ".tollgate",
                ".claude/settings.json", ".claude/credentials.sh", ".claude/tollgate")
WRITE_HINT_RE = re.compile(
    r"open\s*\([^)]*,\s*['\"][rbt]*[wax+]|open\s*\([^)]*['\"]\s*\+?>|write|append|unlink|remove|rename|"
    r"replace\s*\(|shutil|copy|symlink|\blink\s*\(|\bfs\.|touch|truncate|chmod|rmtree|system\s*\(|popen|"
    r"subprocess|exec", re.IGNORECASE)
WRAPPERS = {"sudo", "command", "env", "time", "nice", "nohup", "exec"}
REASON = ("Bash write blocked: the command writes into TOLLGATE_CODE_DIR (read-only search source) "
          "or into one of Tollgate's own files (hooks, settings, credentials, ~/.tollgate, shell "
          "profiles). Work in your dev directory instead. The owner changes these from a terminal.")


def deny() -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": HOOK_EVENT, "permissionDecision": "deny",
                                             "permissionDecisionReason": REASON}}))
    sys.exit(0)


def real(path: str) -> str:
    return os.path.realpath(path)


def inside(path: str, cwd: str, roots: list) -> bool:
    """True when path (relative paths resolved against cwd) is a protected file, or is or sits below
    a protected folder (the code dir and Tollgate's own folders). Case-insensitive."""
    return pp.is_protected(path, roots, cwd)


def mark_breaks(command: str) -> str:
    """Turn newline, CR, backtick, $( and ) into ' ; ' outside single quotes (the quote is closed and
    reopened around a substitution inside double quotes)."""
    out, quote, back, i = [], "", False, 0
    while i < len(command):
        c, two = command[i], command[i:i + 2]
        if c == "\\" and quote != "'" and two[1:]:
            out.append(two); i += 2; continue
        if quote == "'":
            quote = "" if c == "'" else quote
            out.append(c)
        elif quote == '"' and (two == "$(" or c == "`"):
            out.append('" ; '); quote, back = "", True; i += len(two) if c == "$" else 1; continue
        elif quote == '"':
            quote = "" if c == '"' else quote
            out.append(c)
        elif back and c in ")`":
            out.append(' ; "'); quote, back = '"', False
        elif c in "'\"":
            quote = c; out.append(c)
        elif c in "\n\r`)" or two == "$(":
            out.append(" ; "); i += len(two) if c == "$" else 1; continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(mark_breaks(command), posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def is_separator(tok: str) -> bool:
    return bool(tok) and all(c in SEPARATORS_CHARS for c in tok)


def is_redirect_out(tok: str) -> bool:
    return bool(tok) and ">" in tok and all(c in "&<>" for c in tok)


def split_segments(tokens: list[str]) -> list[list[str]]:
    segments, current = [], []
    for tok in tokens:
        if is_separator(tok):
            segments.append(current)
            current = []
        else:
            current.append(tok)
    segments.append(current)
    return segments


def command_words(segment: list[str]) -> list[str]:
    """Segment without leading env assignments and wrapper commands such as sudo."""
    i = 0
    while i < len(segment) and ("=" in segment[i].split("/")[0] or os.path.basename(segment[i]) in WRAPPERS):
        i += 1
    return segment[i:]


def redirect_hits(segment: list[str], cwd: str, roots: list) -> bool:
    for i, tok in enumerate(segment):
        if is_redirect_out(tok) and i + 1 < len(segment) and inside(segment[i + 1], cwd, roots):
            return True
    return False


def args_hit(words: list[str], cwd: str, roots: list) -> bool:
    return any(inside(w.removeprefix("of="), cwd, roots) for w in words[1:])


def destination_hit(words: list[str], cwd: str, roots: list) -> bool:
    """cp, install and ln only write to the last argument (or the -t value); sources may be read."""
    args = words[1:]
    targets = [args[i + 1] for i, a in enumerate(args[:-1]) if a in {"-t", "--target-directory"}]
    targets += [a.split("=", 1)[1] for a in args if a.startswith("--target-directory=")]
    targets += args[-1:]
    return any(inside(t, cwd, roots) for t in targets)


def sed_in_place(words: list[str]) -> bool:
    for w in words[1:]:
        if w == "--in-place" or w.startswith("--in-place="):
            return True
        if w.startswith("-") and not w.startswith("--") and "i" in w[1:]:
            return True
    return False


def git_writes(words: list[str], cwd: str, roots: list) -> bool:
    """A git command whose target is the code dir and whose subcommand is not read-only."""
    args, target, i = words[1:], cwd, 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            target = os.path.join(target, os.path.expanduser(args[i + 1]))
            i += 1
        i += 1
    sub = args[i] if i < len(args) else ""
    in_dir = inside(target, cwd, roots) or args_hit(words, cwd, roots)
    return in_dir and sub not in GIT_READ_ONLY


def inline_body_hits(words: list[str], roots: list) -> bool:
    """python -c, node -e, perl -e ...: the code text names a protected path and writes."""
    for i, w in enumerate(words[1:-1], start=1):
        if w in INLINE_FLAGS:
            body = words[i + 1].lower().replace("~/", os.path.expanduser("~").lower() + "/")
            if not WRITE_HINT_RE.search(body):
                return False
            if any(marker in body for marker in PATH_MARKERS):
                return True
            return any(root in body for root, _ in roots)
    return False


def shell_body(words: list[str]) -> str:
    """The command string of `sh -c '...'`, else an empty string."""
    for i, w in enumerate(words[1:-1], start=1):
        if w.startswith("-") and not w.startswith("--") and "c" in w[1:]:
            return words[i + 1]
    return ""


def segment_violates(segment: list[str], cwd: str, roots: list, git_roots: list) -> bool:
    if redirect_hits(segment, cwd, roots):
        return True
    words = command_words([t for t in segment if not is_redirect_out(t)])
    if not words:
        return False
    verb = os.path.basename(words[0])
    if verb == "git":
        return git_writes(words, cwd, git_roots) if git_roots else False
    if verb in SHELLS:
        body = shell_body(words)
        return bool(body) and violates(body, cwd, roots, git_roots)
    if INTERPRETER_RE.match(verb):
        return inline_body_hits(words, roots)
    if verb in DEST_ONLY_VERBS:
        return destination_hit(words, cwd, roots)
    if verb in WRITE_VERBS or (verb == "sed" and sed_in_place(words)):
        return args_hit(words, cwd, roots)
    return False


def next_cwd(segment: list[str], cwd: str) -> str:
    words = command_words(segment)
    if len(words) >= 2 and words[0] in {"cd", "pushd"}:
        return real(os.path.join(cwd, os.path.expanduser(words[1])))
    return cwd


def violates(command: str, cwd: str, roots: list, git_roots: list) -> bool:
    for segment in split_segments(tokenize(command)):
        if segment_violates(segment, cwd, roots, git_roots):
            return True
        cwd = next_cwd(segment, cwd)
    return False


def main() -> None:
    raw_dir = os.environ.get(ENV_NAME, "")
    try:
        payload = json.loads(sys.stdin.read())
        command = str(payload["tool_input"]["command"])
        cwd = str(payload.get("cwd") or os.getcwd())
        roots = pp.protected_roots()
        git_roots = []
        if raw_dir:
            code_dir = real(raw_dir)
            command = command.replace("${%s}" % ENV_NAME, code_dir).replace("$" + ENV_NAME, code_dir)
            git_roots = pp.dir_root(code_dir)
            roots = roots + git_roots
        command = pp.expand_vars(command)
        if violates(command, cwd, roots, git_roots):
            deny()
    except SystemExit:
        raise
    except Exception as exc:
        sys.stderr.write("pre-tool-bash-guard-code-dir: %s; blocking (fails closed).\n" % type(exc).__name__)
        sys.exit(2)
    sys.exit(0)


main()
