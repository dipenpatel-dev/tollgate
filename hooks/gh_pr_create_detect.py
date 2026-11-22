#!/usr/bin/env python3
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Decide whether a Bash command line actually invokes `gh pr create`, so the
#        PR gate hook blocks real invocations and ignores text that only mentions the
#        phrase (quoted strings, commit messages, heredoc prose). Fails closed: a
#        command that cannot be parsed falls back to a text match.
# Ticket: none (Tollgate is not Jira tracked)
# ChangeLog:
#   - Created. Ported from the dotfiles version.
#
# Usage: the command text on stdin; prints "yes" or "no" on stdout.

from __future__ import annotations

import os
import re
import shlex
import sys

MAX_DEPTH: int = 3
WORDS_AFTER_GH: int = 2
CONTROL_CHARS: frozenset = frozenset(";&|()<>")
VALUE_FLAGS: frozenset = frozenset({"-R", "--repo", "--hostname"})
SHELL_C_FLAG_RE = re.compile(r"^-[A-Za-z]*c$")
SUBSTITUTION_RE = re.compile(r"\$\(|`")
FALLBACK_RE = re.compile(r"\bgh\s+(?:-\S+\s+)*pr\s+create\b")


def tokenize(command: str) -> list[str]:
    """Split a command line into shell words and control operators."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def words_after_gh(tokens: list[str], start: int) -> tuple[str, str]:
    """Return the first two non flag words after `gh`, stopping at a control operator."""
    words: list[str] = []
    index = start
    while index < len(tokens) and len(words) < WORDS_AFTER_GH:
        token = tokens[index]
        if set(token) <= CONTROL_CHARS:
            break
        if token in VALUE_FLAGS:
            index += 2
            continue
        if not token.startswith("-"):
            words.append(token)
        index += 1
    words += [""] * (WORDS_AFTER_GH - len(words))
    return words[0], words[1]


def is_wrapped_command(tokens: list[str], index: int) -> bool:
    """True when the token is a script passed to a shell, eval, or a substitution."""
    previous = tokens[index - 1] if index else ""
    return (
        previous == "eval"
        or bool(SHELL_C_FLAG_RE.match(previous))
        or bool(SUBSTITUTION_RE.search(tokens[index]))
    )


def invokes_pr_create(command: str, depth: int = 0) -> bool:
    """True when `gh pr create` appears as an invocation, including inside bash -c."""
    tokens = tokenize(command)
    for index, token in enumerate(tokens):
        if os.path.basename(token) == "gh" and words_after_gh(tokens, index + 1) == ("pr", "create"):
            return True
        if depth < MAX_DEPTH and is_wrapped_command(tokens, index):
            if invokes_pr_create(token, depth + 1):
                return True
    return False


def is_pr_create(command: str) -> bool:
    """Parse the command; if it cannot be parsed, fall back to a text match (fail closed)."""
    try:
        return invokes_pr_create(command)
    except ValueError:
        return bool(FALLBACK_RE.search(command))


def main() -> None:
    """Read a command from stdin and print yes or no."""
    sys.stdout.write("yes" if is_pr_create(sys.stdin.read()) else "no")


if __name__ == "__main__":
    main()
