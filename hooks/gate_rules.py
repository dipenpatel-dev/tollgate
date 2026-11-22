"""Gate rules for the chain skills: pure functions over file text.

Scope: reads the `Status:` line of the state, spec, design and edge-case
validation files and checks the per-skill rules for arch, dev and qa. The
accepted values match the dotfiles chain commands. No file I/O, no hook
framing, no environment reads. Callers pass file contents (str or bytes, or
None when the file is missing). Reasons name the missing or malformed file and
the expected line, never file contents.
Ticket: n/a

ChangeLog:
  - Gate now reads `Status:` lines (dotfiles format) instead of dated
    Approved and Validated lines. Date parsers removed.
  - Initial version: line parsers, status reader, arch/dev/qa checks.
  - CommonMark style fence tracking, ASCII digits only, split lines on LF and
    CRLF only, strip a leading BOM, block reasons never print the Status value from a file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

TextInput = Union[str, bytes, None]

TEXT_ENCODING = "utf-8"
STATUS_PREFIX = "Status:"
MAX_FENCE_INDENT = 3
MIN_FENCE_LENGTH = 3
BOM = "\ufeff"

STATE_SPEC_APPROVED = "SPEC_APPROVED"
STATE_DESIGN_APPROVED = "DESIGN_APPROVED"
STATE_IN_DEV = "IN_DEV"
STATE_DEV_COMPLETE = "DEV_COMPLETE"
SPEC_APPROVED_STATUS = "APPROVED"
DESIGN_APPROVED_STATUS = "DESIGN_APPROVED"
VALIDATION_STATUSES = ("DOCUMENTED", "VALIDATED")
DEV_ALLOWED_STATES = (STATE_DESIGN_APPROVED, STATE_IN_DEV)

STATE_NAME = "state file"
SPEC_NAME = "spec.md"
DESIGN_NAME = "design.md"
VALIDATION_NAME = "edge-case-validation.md"

_FENCE_RE = re.compile(r"^ {{0,{0}}}(`{{{1},}}|~{{{1},}})(.*)$".format(MAX_FENCE_INDENT, MIN_FENCE_LENGTH))
_LINE_SPLIT_RE = re.compile(r"\r?\n")


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a gate check: ok flag plus a plain reason when blocked."""

    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class StatusResult:
    """Outcome of reading a Status value: the value, or why it is malformed."""

    ok: bool
    value: str = ""
    reason: str = ""


def decode_text(data: TextInput) -> Optional[str]:
    """Return str for str or UTF-8 bytes; None for None or undecodable bytes.

    A leading byte order mark is removed so it cannot hide the first line.
    """
    if data is None:
        return None
    if isinstance(data, bytes):
        try:
            data = data.decode(TEXT_ENCODING)
        except UnicodeDecodeError:
            return None
    return data[1:] if data.startswith(BOM) else data


def split_lines(text: str) -> List[str]:
    """Split on LF and CRLF only. U+2028, U+0085 and a lone CR do not split."""
    return _LINE_SPLIT_RE.split(text)


def _fence_open(line: str) -> Optional[Tuple[str, int]]:
    """Return (marker character, run length) if line opens a fence, else None."""
    match = _FENCE_RE.match(line)
    if match is None:
        return None
    run, info = match.group(1), match.group(2)
    if run[0] == "`" and "`" in info:
        return None
    return run[0], len(run)


def _fence_closes(line: str, marker: str, length: int) -> bool:
    """True if line closes a fence opened with `length` copies of `marker`."""
    match = _FENCE_RE.match(line)
    if match is None:
        return False
    run, info = match.group(1), match.group(2)
    return run[0] == marker and len(run) >= length and not info.strip()


def lines_outside_fences(text: str) -> List[str]:
    """Return the lines of text that are not inside a fenced code block.

    A fence opens with 3 or more backticks or tildes (up to 3 spaces of indent)
    and closes only with the same character, at least as many markers and no
    info text. Fence lines are dropped. An unclosed fence hides the rest.
    """
    kept: List[str] = []
    open_fence: Optional[Tuple[str, int]] = None
    for line in split_lines(text):
        if open_fence is None:
            open_fence = _fence_open(line)
            if open_fence is None:
                kept.append(line)
        elif _fence_closes(line, open_fence[0], open_fence[1]):
            open_fence = None
    return kept


def read_status(data: TextInput) -> StatusResult:
    """Read the first top-level `Status:` value.

    Malformed: None, undecodable bytes, empty file, no Status line, an empty
    value, or two Status lines with different values. Repeating the same
    value is accepted.
    """
    text = decode_text(data)
    if text is None:
        return StatusResult(False, reason="missing or not valid UTF-8 text")
    if not text.strip():
        return StatusResult(False, reason="file is empty")
    values = [
        line[len(STATUS_PREFIX):].strip()
        for line in lines_outside_fences(text)
        if line.startswith(STATUS_PREFIX)
    ]
    if not values:
        return StatusResult(False, reason="no `Status:` line")
    if any(not value for value in values):
        return StatusResult(False, reason="`Status:` line has no value")
    if len(set(values)) > 1:
        return StatusResult(False, reason="two different `Status:` lines")
    return StatusResult(True, value=values[0])


def _status_problem(data: TextInput, name: str, allowed: tuple) -> Optional[str]:
    """Return a problem text unless the file's `Status:` value is one of `allowed`.

    The reason names the file and the expected values, never the value found.
    """
    text = decode_text(data)
    if text is None:
        return "{0} is missing or not valid UTF-8 text".format(name)
    status = read_status(text)
    if status.ok and status.value in allowed:
        return None
    expected = " or ".join("`{0} {1}`".format(STATUS_PREFIX, value) for value in allowed)
    if not status.ok:
        return "{0} is malformed: {1}; it needs {2}".format(name, status.reason, expected)
    return "{0} needs {1}".format(name, expected)


def _state_problem(data: TextInput, allowed: tuple) -> Optional[str]:
    status = read_status(data)
    if not status.ok:
        return "{0} is malformed: {1}".format(STATE_NAME, status.reason)
    if status.value in allowed:
        return None
    return "{0} does not hold an allowed `Status:` value, expected one of: {1}".format(
        STATE_NAME, ", ".join(allowed)
    )


def _first_problem(problems: List[Optional[str]]) -> CheckResult:
    found = [p for p in problems if p]
    if not found:
        return CheckResult(True)
    return CheckResult(False, "; ".join(found))


def check_arch(spec: TextInput, state: TextInput) -> CheckResult:
    """arch needs `Status: APPROVED` in the spec and state SPEC_APPROVED."""
    return _first_problem(
        [
            _status_problem(spec, SPEC_NAME, (SPEC_APPROVED_STATUS,)),
            _state_problem(state, (STATE_SPEC_APPROVED,)),
        ]
    )


def check_dev(design: TextInput, state: TextInput) -> CheckResult:
    """dev needs `Status: DESIGN_APPROVED` in the design and state DESIGN_APPROVED or IN_DEV."""
    return _first_problem(
        [
            _status_problem(design, DESIGN_NAME, (DESIGN_APPROVED_STATUS,)),
            _state_problem(state, DEV_ALLOWED_STATES),
        ]
    )


def check_qa(
    state: TextInput, spec: TextInput, design: TextInput, validation: TextInput
) -> CheckResult:
    """qa needs state DEV_COMPLETE, approved spec and design, and a documented validation file."""
    return _first_problem(
        [
            _state_problem(state, (STATE_DEV_COMPLETE,)),
            _status_problem(spec, SPEC_NAME, (SPEC_APPROVED_STATUS,)),
            _status_problem(design, DESIGN_NAME, (DESIGN_APPROVED_STATUS,)),
            _status_problem(validation, VALIDATION_NAME, VALIDATION_STATUSES),
        ]
    )
