# Module:      backfill_vault_frontmatter.py
# Description: One-shot backfill that adds the four retrieval fields (catalog_type,
#              doc_role, indexable, indexed) to existing vault markdown files by
#              inserting lines directly above the closing frontmatter delimiter.
#              The module holds the pure core (byte-level frontmatter span, YAML
#              classification, line insertion), the vault safety layer (scan, git
#              snapshot, per file planner, atomic apply), and the run wiring (report,
#              command line, exit codes). Preview is the default; --apply writes.
#              the earlier change adds the ticket policy core: the kind rows chosen by file name, the
#              terminal status test, block creation, and exact line replacement. Those
#              functions are pure. It also adds the run planner, the run wiring, the run
#              report, and the --run and --approved-report switches. Without --run the
#              tool behaves as in the earlier change. With --run N it plans four write classes (add,
#              create, flip, rewrite) and, with --apply, refuses unless the tree is clean
#              and every planned write equals an entry in the approved preview report.
#              the earlier change adds Run 4, which labels notes outside the tickets folder by folder: ten
#              folder rows (N1 to N10) decide the values and doc_type is ignored.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Vault markdown frontmatter; the earlier change mapping table and five row contract;
#              the earlier change ticket policy table (14 kind rows, K14 is the absence of a row);
#              the earlier change folder policy table (10 folder rows N1 to N10)
# Version:     1.7
# ChangeLog:
#   Initial implementation
#   Vault safety layer: scan, git snapshot, planner, atomic apply
#   Report, CLI, run wiring; apply_edit refuses read only files
#   QA F-01: parse_block, verify_edit, plan_file contain any YAML exception
#   Ticket policy core: kind rows, terminal status, block create, line replace
#   Run planner, run wiring, run report, --run and --approved-report
#   Spec Q2 change: session-notes.md is a ticket summary, K10 not K9; KindRow exclusions
#   Run 4: folder rows N1 to N10, scope A walk, run 4 planner path

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Sequence, Tuple

import yaml

logger = logging.getLogger(__name__)


if "__file__" in globals():  # absent when a test runs the source text with exec
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import folder_name, ticket_prefix_depth, subdir_prefixes  # noqa: E402

SYSTEM_MAP_DIR = folder_name("system_map")
REFERENCE_DIR = folder_name("reference")
TICKETS_DIR = folder_name("tickets")
KNOWLEDGE_DIR = folder_name("knowledge")
EDUCATION_DIR = folder_name("education")
CONVERSATIONS_DIR_NAME = folder_name("conversations")
THREADS_DIR_NAME = folder_name("chat_threads")

FIELD_ORDER: Tuple[str, ...] = ("catalog_type", "doc_role", "indexable", "indexed")
CONFLICT_FIELDS: Tuple[str, ...] = ("catalog_type", "doc_role", "indexable")
DOC_TYPE_KEY = "doc_type"
TYPE_KEY = "type"
CONFLICT_PREFIX = "CONFLICT_"

DELIMITER = b"---"
EOL_LF = b"\n"
EOL_CRLF = b"\r\n"
CARRIAGE_RETURN = b"\r"
ENCODING = "utf-8"

STATE_ROOT_FOLDER = TICKETS_DIR
STATE_FILE_SUFFIX = "-state.md"
STATE_PATH_PARTS = 3
PATH_SEPARATOR = "/"

ROW_STATE = 1
ROW_DOC_TYPE_MAPPED = 2
ROW_DOC_TYPE_UNMAPPED = 3
ROW_TYPE_MAPPED = 4
ROW_NOT_TARGET = 5

LABEL_MAX_LENGTH = 64
LABEL_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,%d}" % LABEL_MAX_LENGTH)
LABEL_NON_STRING = "<non-string>"
LABEL_UNPRINTABLE = "<unprintable>"

MARKDOWN_SUFFIX = ".md"
HIDDEN_DIR_PREFIX = "."
# The memory folder is a top level layout folder. Nothing else is skipped by name.
MEMORY_DIR = folder_name("memory")
EXCLUDED_PATH_PREFIXES: Tuple[str, ...] = ((MEMORY_DIR + "/"),)

KIND_NOT_TARGET = "not_target"
KIND_ALREADY_COMPLETE = "already_complete"
KIND_WRITE = "write"
KIND_SKIPPED = "skipped"

REASON_NO_FRONTMATTER = "NO_FRONTMATTER"
REASON_PARSE_ERROR = "PARSE_ERROR"
REASON_UNCOMMITTED = "UNCOMMITTED"
REASON_UNTRACKED = "UNTRACKED"
REASON_GITIGNORED = "GITIGNORED"
REASON_SYMLINK = "SYMLINK"
REASON_UNREADABLE = "UNREADABLE"
REASON_VERIFY_FAILED = "VERIFY_FAILED"
REASON_CHANGED_DURING_RUN = "CHANGED_DURING_RUN"
REASON_WRITE_FAILED = "WRITE_FAILED"

GIT_COMMAND = "git"
GIT_TIMEOUT_SECONDS = 30
GIT_NUL = b"\0"
GIT_LIST_TRACKED_ARGS: Tuple[str, ...] = ("ls-files", "-z")
GIT_LIST_DIFFERING_ARGS: Tuple[str, ...] = (
    "diff", "--no-renames", "--relative", "--name-only", "-z", "HEAD",
)
GIT_LIST_IGNORED_ARGS: Tuple[str, ...] = (
    "ls-files", "-o", "-i", "--exclude-standard", "-z",
)
GIT_ERROR_NONZERO_EXIT = "GIT_NONZERO_EXIT"
GIT_ERROR_TIMEOUT = "GIT_TIMEOUT"
GIT_ERROR_UNAVAILABLE = "GIT_UNAVAILABLE"

TMP_PREFIX = "backfill_vault_frontmatter_"
TMP_SUFFIX = ".tmp"
WRITE_MODE_BINARY = "wb"

EXIT_OK = 0
EXIT_PRECONDITION = 2
EXIT_WRITE_FAILED = 3

MODE_PREVIEW = "preview"
MODE_APPLY = "apply"
REPORT_ROWS: Tuple[int, ...] = (
    ROW_STATE, ROW_DOC_TYPE_MAPPED, ROW_DOC_TYPE_UNMAPPED, ROW_TYPE_MAPPED,
)
STOP_RULE_EXCLUDED_REASONS: Tuple[str, ...] = (REASON_PARSE_ERROR, REASON_NO_FRONTMATTER)
REPORT_JSON_INDENT = 2
REPORT_ENCODING = "utf-8"
LOG_FORMAT = "%(levelname)s %(message)s"

PATHS_VAULT_NAME = "vault"
ERROR_VAULT_ROOT_NOT_A_FOLDER = "VAULT_ROOT_NOT_A_FOLDER"
ERROR_REPORT_PATH_INVALID = "REPORT_PATH_INVALID"
ERROR_MANIFEST_UNREADABLE = "PATHS_MANIFEST_UNREADABLE"
ERROR_REPORT_WRITE_FAILED = "REPORT_WRITE_FAILED"

STATUS_KEY = "status"
TERMINAL_STATUSES: FrozenSet[str] = frozenset(
    {"cancelled", "superseded", "dropped", "archived", "absorbed"}
)

KIND_ID_PREFIX = "K"
KIND_ID_ARCHIVE = "K1"
KIND_ID_STATE = "K2"
ARCHIVE_FOLDERS: FrozenSet[str] = frozenset({"archive", "history"})
ROLE_FALLBACK = "reference"
MIN_TICKET_PATH_PARTS = 3
REFUSED_PATH_PARTS: FrozenSet[str] = frozenset({"", ".", ".."})
NAME_JOINER = "-"
FOLDER_MAIN_PATTERN = "<folder>.md"
NAME_TICKET_SUMMARY = "session-notes.md"
GLOB_STAR = "*"
ERROR_KIND_ROWS_INVALID = "KIND_ROWS_INVALID"

FIELD_COLON = b":"
FIELD_SEPARATOR = b": "
LINE_BREAK_CHARS: Tuple[str, ...] = ("\r", "\n")
EDIT_PARTS = 3
UNSAFE_TOP_PREFIXES: Tuple[bytes, ...] = (
    b"\xef\xbb\xbf",
    b"\xff\xfe",
    b"\xfe\xff",
    DELIMITER,
)

RUN_ADD_FLIP = 1
RUN_CREATE = 2
RUN_REWRITE = 3
RUN_NONTICKET = 4
RUN_NUMBERS: Tuple[int, ...] = (RUN_ADD_FLIP, RUN_CREATE, RUN_REWRITE, RUN_NONTICKET)

CLASS_ADD = "add"
CLASS_CREATE = "create"
CLASS_FLIP = "flip"
CLASS_REWRITE = "rewrite"
CLASS_NAMES: Tuple[str, ...] = (CLASS_ADD, CLASS_CREATE, CLASS_FLIP, CLASS_REWRITE)
WRITTEN_CLASSES: Tuple[str, ...] = (CLASS_ADD, CLASS_CREATE)
CHANGED_CLASSES: Tuple[str, ...] = (CLASS_FLIP, CLASS_REWRITE)

REASON_NO_KIND_ROW = "NO_KIND_ROW"
REASON_UNSAFE_TOP = "UNSAFE_TOP"
REASON_UNEXPECTED_LINE_FORM = "UNEXPECTED_LINE_FORM"
REASON_MIXED_EDIT = "MIXED_EDIT"
NOTE_DIFFERS_FROM_ROW = "DIFFERS_FROM_ROW"

ERROR_DIRTY_TREE = "DIRTY_TREE"
ERROR_FLAG_COMBINATION = "FLAG_COMBINATION"
ERROR_APPROVED_REPORT_REQUIRED = "APPROVED_REPORT_REQUIRED"
ERROR_APPROVED_REPORT_INVALID = "APPROVED_REPORT_INVALID"
ERROR_APPROVED_REPORT_MISMATCH = "APPROVED_REPORT_MISMATCH"
ERROR_NOT_APPROVED = "NOT_APPROVED"

GIT_STATUS_ARGS: Tuple[str, ...] = (
    "--no-optional-locks", "status", "--porcelain", "-z", "--untracked-files=all",
)
TICKETS_PREFIX = STATE_ROOT_FOLDER + PATH_SEPARATOR
NOT_LABELED_FOLDERS: Tuple[str, ...] = (CONVERSATIONS_DIR_NAME, THREADS_DIR_NAME)
INDEXABLE_KEY = "indexable"
KIND_NONE = "none"
LABEL_NONE = "none"
RESOLVED_KEY = "resolved"
LEFT_KEY = "left"
REPORT_RUN_KEY = "run"
REPORT_WRITES_KEY = "writes"
REPORT_PATH_KEY = "path"
REPORT_MODE_KEY = "mode"

FOLDER_ROW_ID_PREFIX = "N"
KNOWLEDGE_BASE_PREFIX = (KNOWLEDGE_DIR + "/")
RUN4_EXCLUDED_PATH_PREFIXES: Tuple[str, ...] = EXCLUDED_PATH_PREFIXES
ERROR_FOLDER_ROWS_INVALID = "FOLDER_ROWS_INVALID"

FieldEdit = Tuple[str, str, str]
Replacement = Tuple[int, int, bytes]


class GitStateError(Exception):
    """The git snapshot could not be taken. The message is a closed code, never git output."""


class PreconditionError(Exception):
    """A fatal precondition failed. The message is a closed code, never exception text."""


@dataclass(frozen=True)
class Values:
    """The three derived field values for one classification row."""

    catalog_type: str
    doc_role: str
    indexable: bool


@dataclass(frozen=True)
class Span:
    """Location of a frontmatter block inside the raw bytes of a file."""

    block: bytes
    close_start: int
    eol: bytes


@dataclass(frozen=True)
class Classification:
    """Result of the five row contract for one file."""

    row: int
    values: Optional[Values]
    label: Optional[str]


@dataclass(frozen=True)
class GitState:
    """One git snapshot of the vault, as sets of POSIX paths relative to the vault root.

    tracked: files in the index. differing: files that differ from HEAD (staged or not).
    ignored: untracked files that an ignore rule covers.
    """

    tracked: FrozenSet[str]
    differing: FrozenSet[str]
    ignored: FrozenSet[str]


@dataclass(frozen=True)
class Outcome:
    """The single outcome of planning one file.

    original and new_raw are set only when kind is write. reason is set only when kind
    is skipped, except that run mode marks an already complete file whose values differ
    from its kind row with the closed note DIFFERS_FROM_ROW. row is the contract row
    when the file was classified, else None.

    The last three fields belong to run mode. change_class is add, create, flip,
    or rewrite for a write. kind_id is the kind row id, or none when no row applies.
    changes lists (field, old, new) for a flip or rewrite. In run mode label carries the
    normalized terminal status for a flip and the doc_type label for a rewrite candidate.
    """

    rel: str
    kind: str
    reason: Optional[str] = None
    row: Optional[int] = None
    label: Optional[str] = None
    additions: Dict[str, Any] = field(default_factory=dict)
    original: Optional[bytes] = None
    new_raw: Optional[bytes] = None
    change_class: Optional[str] = None
    kind_id: Optional[str] = None
    changes: Tuple[Tuple[str, str, str], ...] = ()


# Source: the spec, doc_type Mapping (37 rows). Columns: doc_type,
# catalog_type, doc_role, indexable.
_MAPPING_ROWS: Tuple[Tuple[str, str, str, bool], ...] = (
    ("session-start", "session", "session_log", True),
    ("coordinator-session", "session", "index", True),
    ("client-reference", "reference", "reference", True),
    ("repo-index", "reference", "index", True),
    ("architecture-reference", "reference", "reference", True),
    ("product-reference", "reference", "reference", True),
    ("databricks-reference", "reference", "reference", True),
    ("ticket_state", "ticket", "state", True),
    ("ticket_spec", "ticket", "spec", True),
    ("ticket_design", "ticket", "design", True),
    ("ticket_arch", "ticket", "design", True),
    ("ticket_qa", "ticket", "qa", True),
    ("ticket_session", "ticket", "session_log", True),
    ("ticket_whiteboard", "ticket", "whiteboard", True),
    ("ticket_diagram", "ticket", "reference", True),
    ("ticket_context", "ticket", "reference", True),
    ("ticket_other", "ticket", "reference", True),
    ("decision", "knowledge", "decision", True),
    ("learning", "knowledge", "learning", True),
    ("pattern", "knowledge", "pattern", True),
    ("whiteboard", "knowledge", "whiteboard", True),
    ("review", "knowledge", "review", True),
    ("standard", "knowledge", "standard", True),
    ("education", "knowledge", "education", True),
    ("conversation", "session", "log", False),
    ("trajectory", "session", "trajectory", False),
    ("module", "code_doc", "module", True),
    ("config", "code_doc", "config", True),
    ("test", "code_doc", "test", True),
    ("notebook", "code_doc", "notebook", True),
    ("sql", "code_doc", "sql", True),
    ("pipeline", "code_doc", "pipeline", True),
    ("script", "code_doc", "script", True),
    ("terraform", "code_doc", "terraform", True),
    ("shell", "code_doc", "shell", True),
    ("dockerfile", "code_doc", "dockerfile", True),
    ("repo_index", "code_doc", "index", True),
)

MAPPING: Dict[str, Values] = {
    row[0]: Values(row[1], row[2], row[3]) for row in _MAPPING_ROWS
}
SENTINEL_VALUES = Values("unknown", "unknown", False)
STATE_VALUES = Values("ticket", "state", True)
NOT_TARGET = Classification(ROW_NOT_TARGET, None, None)


def _opening_eol(raw: bytes) -> Optional[bytes]:
    """Return the line ending after a line one delimiter, or None if absent."""
    if raw.startswith(DELIMITER + EOL_CRLF):
        return EOL_CRLF
    if raw.startswith(DELIMITER + EOL_LF):
        return EOL_LF
    return None


def _find_close(raw: bytes, start: int) -> Optional[int]:
    """Return the offset of the first line from start that is exactly the delimiter."""
    pos = start
    while pos < len(raw):
        newline = raw.find(EOL_LF, pos)
        line_end = len(raw) if newline == -1 else newline
        line = raw[pos:line_end]
        if line.endswith(CARRIAGE_RETURN):
            line = line[:-1]
        if line == DELIMITER:
            return pos
        if newline == -1:
            return None
        pos = newline + 1
    return None


def split_frontmatter(raw: bytes) -> Optional[Span]:
    """Locate the frontmatter block in raw bytes, or return None if there is none.

    The opening delimiter must be line one with no BOM and no leading blank line.
    The first later line that is exactly the delimiter closes the block.
    """
    eol = _opening_eol(raw)
    if eol is None:
        return None
    block_start = len(DELIMITER) + len(eol)
    close_start = _find_close(raw, block_start)
    if close_start is None:
        return None
    return Span(block=raw[block_start:close_start], close_start=close_start, eol=eol)


def parse_block(block: bytes) -> Optional[Dict[str, Any]]:
    """Parse a frontmatter block to a mapping, or return None when it cannot be read.

    An empty block gives an empty mapping. Any exception means the block is unreadable:
    PyYAML 6.0.3 raises KeyError, AttributeError, and IndexError, not only YAMLError,
    for tags such as !!bool, !!timestamp, and !!int with a bad value. Only the exception
    class name is logged, because exception text can be the frontmatter value itself.
    """
    try:
        loaded = yaml.safe_load(block.decode(ENCODING))
    except Exception as exc:
        logger.debug("frontmatter parse failed: %s", type(exc).__name__)
        return None
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        return None
    return loaded


def is_ticket_state_path(rel: str) -> bool:
    """True only for <tickets>/<folder>/<folder>-state.md, or <tickets>/<PREFIX>/<folder>/<folder>-state.md."""
    parts = rel.split(PATH_SEPARATOR)
    if not parts or parts[0] != STATE_ROOT_FOLDER:
        return False
    skip = ticket_prefix_depth(parts[1:])
    if len(parts) != STATE_PATH_PARTS + skip:
        return False
    folder, name = parts[1 + skip], parts[-1]
    return bool(folder) and name == folder + STATE_FILE_SUFFIX


def lookup_values(value: Any) -> Optional[Values]:
    """Return the table row for a doc_type or type value, or None.

    Only exact strings match. No hyphen, case, or whitespace normalization.
    """
    if not isinstance(value, str):
        return None
    return MAPPING.get(value)


def unmapped_label(value: Any) -> str:
    """Return a report safe label for an unmapped doc_type value."""
    if not isinstance(value, str):
        return LABEL_NON_STRING
    if LABEL_PATTERN.fullmatch(value) is None:
        return LABEL_UNPRINTABLE
    return value


def classify(rel: str, fm: Optional[Dict[str, Any]]) -> Classification:
    """Apply the five row contract. The first matching row wins."""
    if is_ticket_state_path(rel):
        return Classification(ROW_STATE, STATE_VALUES, None)
    if fm is None:
        return NOT_TARGET
    if DOC_TYPE_KEY in fm:
        values = lookup_values(fm[DOC_TYPE_KEY])
        if values is not None:
            return Classification(ROW_DOC_TYPE_MAPPED, values, None)
        label = unmapped_label(fm[DOC_TYPE_KEY])
        return Classification(ROW_DOC_TYPE_UNMAPPED, SENTINEL_VALUES, label)
    if TYPE_KEY in fm:
        values = lookup_values(fm[TYPE_KEY])
        if values is not None:
            return Classification(ROW_TYPE_MAPPED, values, None)
    return NOT_TARGET


def _derived_value(name: str, values: Values) -> Any:
    """Return the value a field should carry. The indexed field is always None."""
    derived: Dict[str, Any] = {
        "catalog_type": values.catalog_type,
        "doc_role": values.doc_role,
        "indexable": values.indexable,
        "indexed": None,
    }
    return derived[name]


def missing_additions(fm: Dict[str, Any], values: Values) -> Dict[str, Any]:
    """Return the fields absent from fm, in FIELD_ORDER. Present fields are untouched."""
    return {
        name: _derived_value(name, values)
        for name in FIELD_ORDER
        if name not in fm
    }


def find_conflict(fm: Dict[str, Any], values: Values) -> Optional[str]:
    """Return CONFLICT_<FIELD> for the first present field that disagrees, else None.

    Compares by type and value, so YAML integer 1 does not equal true. The indexed
    field is a machine stamp and is never compared.
    """
    for name in CONFLICT_FIELDS:
        if name not in fm:
            continue
        existing = fm[name]
        derived = _derived_value(name, values)
        if type(existing) is not type(derived) or existing != derived:
            return CONFLICT_PREFIX + name.upper()
    return None


def _render_value(value: Any) -> str:
    """Render one field value as plain YAML text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def render_additions(additions: Dict[str, Any], eol: bytes) -> bytes:
    """Render one 'name: value' line per addition, each ended with the file's eol."""
    lines = [
        "{}: {}".format(name, _render_value(value)).encode(ENCODING) + eol
        for name, value in additions.items()
    ]
    return b"".join(lines)


def insert_lines(raw: bytes, span: Span, added: bytes) -> bytes:
    """Return raw with added placed directly above the closing delimiter line."""
    return raw[: span.close_start] + added + raw[span.close_start :]


def _insertion_bytes_match(raw: bytes, span: Span, added: bytes, new_raw: bytes) -> bool:
    """True only if new_raw is raw with exactly added inserted at the close offset."""
    cut = span.close_start
    end = cut + len(added)
    return (
        new_raw[:cut] == raw[:cut]
        and new_raw[cut:end] == added
        and new_raw[end:] == raw[cut:]
    )


def verify_edit(
    raw: bytes,
    span: Span,
    added: bytes,
    new_raw: bytes,
    fm: Dict[str, Any],
    additions: Dict[str, Any],
) -> bool:
    """Self check before any write: byte equality, then parsed equality.

    A comparison that raises, such as RecursionError on a self referencing anchor,
    fails the check. Only the exception class name is logged.
    """
    if not _insertion_bytes_match(raw, span, added, new_raw):
        return False
    new_span = split_frontmatter(new_raw)
    if new_span is None:
        return False
    parsed = parse_block(new_span.block)
    if parsed is None:
        return False
    expected = dict(fm)
    expected.update(additions)
    try:
        return parsed == expected
    except Exception as exc:
        logger.debug("self check comparison failed: %s", type(exc).__name__)
        return False


@dataclass(frozen=True)
class KindRow:
    """One row of the ticket policy table, chosen by file name.

    patterns hold lowercase name patterns with at most one star. They are tried against
    the file name after the ticket folder prefix is removed. K1 and K2 carry no patterns
    because the folder position and the state file path pick them. exclusions hold whole
    lowercase names the row never takes, so a later row can take them.
    """

    kind_id: str
    catalog_type: str
    doc_role: str
    indexable: bool
    patterns: Tuple[str, ...] = ()
    exclusions: Tuple[str, ...] = ()


# Source: the spec, Policy Table, with the five matching rules of the spec.
# K14 (any other name below a ticket folder) is not a row: kind_row_for returns None.
# K1 holds the fallback role here; kind_row_for swaps in the role the file name gives.
KIND_ROWS: Tuple[KindRow, ...] = (
    KindRow("K1", "ticket", "reference", False),
    KindRow("K2", "ticket", "state", True),
    KindRow("K3", "ticket", "review", False, ("cursor*", "qa-cursor*", "arch-review*")),
    KindRow("K4", "ticket", "reference", False, ("block_*-diff.md", "prompt*", "starter-prompt*")),
    KindRow("K5", "ticket", "spec", True, ("spec.md", "pre-spec.md")),
    KindRow("K6", "ticket", "design", True, ("design.md", "arch.md")),
    KindRow("K7", "ticket", "qa", True, ("qa-findings*",)),
    KindRow("K8", "ticket", "qa", True, ("edge-case-validation.md",)),
    KindRow("K9", "ticket", "session_log", True, ("session*",), exclusions=(NAME_TICKET_SUMMARY,)),
    KindRow("K10", "ticket", "reference", True, (FOLDER_MAIN_PATTERN, NAME_TICKET_SUMMARY)),
    KindRow("K11", "ticket", "reference", True, ("context.md", "diagrams.md")),
    KindRow("K12", "ticket", "reference", True, ("shipped.md",)),
    KindRow(
        "K13", "ticket", "reference", True,
        ("handoff.md", "support-handoff.md", "notes.md", "plan.md", "jira-draft.md", "coord.md"),
    ),
)


def check_kind_rows(rows: Sequence[KindRow]) -> None:
    """Raise ValueError unless the ids run K1, K2, and so on in order and patterns are sound.

    Ordered ids cannot repeat. A pattern must be lowercase and hold at most one star,
    because names are lowercased before matching and a star splits a name in two. An
    exclusion must be lowercase for the same reason.
    """
    for number, row in enumerate(rows, start=1):
        if row.kind_id != KIND_ID_PREFIX + str(number):
            raise ValueError(ERROR_KIND_ROWS_INVALID)
        for pattern in row.patterns:
            if pattern != pattern.lower() or pattern.count(GLOB_STAR) > 1:
                raise ValueError(ERROR_KIND_ROWS_INVALID)
        if any(name != name.lower() for name in row.exclusions):
            raise ValueError(ERROR_KIND_ROWS_INVALID)


check_kind_rows(KIND_ROWS)
_ROWS_BY_ID: Dict[str, KindRow] = {row.kind_id: row for row in KIND_ROWS}


@dataclass(frozen=True)
class FolderRow:
    """One row of the earlier folder policy table: path prefixes and the triple they give.

    A note whose root relative path starts with one of the prefixes takes the row. The
    row decides the values and the note's doc_type is never read.
    """

    row_id: str
    prefixes: Tuple[str, ...]
    catalog_type: str
    doc_role: str
    indexable: bool


def _system_map_sub(*names: str) -> Tuple[str, ...]:
    return subdir_prefixes("system_map", names)


def _knowledge_sub(*names: str) -> Tuple[str, ...]:
    return subdir_prefixes("knowledge", names)


# Source: the spec, Policy table. Subfolders come from the layout table (core.paths). First match wins. Ids start with N so they never
# clash with the ticket rows K1 to K14. A path under no prefix has no row (NO_KIND_ROW).
FOLDER_ROWS: Tuple[FolderRow, ...] = (
    FolderRow("N1", _system_map_sub("clients"), "reference", "reference", True),
    FolderRow(
        "N2", _system_map_sub("pipelines", "architecture", "data-model"),
        "reference", "reference", True,
    ),
    FolderRow("N3", _system_map_sub("platform-learning"), "knowledge", "learning", True),
    FolderRow("N4", _knowledge_sub("decisions"), "knowledge", "decision", True),
    FolderRow("N5", _knowledge_sub("learnings"), "knowledge", "learning", True),
    FolderRow("N6", _knowledge_sub("patterns"), "knowledge", "pattern", True),
    FolderRow("N10", ((EDUCATION_DIR + "/"),), "knowledge", "education", True),
)

# Scope A: the folders run 4 may touch. Every other path is not a target.
SCOPE_A_PREFIXES: Tuple[str, ...] = (
    (SYSTEM_MAP_DIR + "/"),
    (EDUCATION_DIR + "/"),
) + _knowledge_sub("decisions", "learnings", "patterns")


def check_folder_rows(rows: Sequence[FolderRow]) -> None:
    """Raise ValueError unless every row id starts with N, no id repeats, and each row has a prefix."""
    ids = [row.row_id for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(ERROR_FOLDER_ROWS_INVALID)
    for row in rows:
        if not row.row_id.startswith(FOLDER_ROW_ID_PREFIX) or not row.prefixes:
            raise ValueError(ERROR_FOLDER_ROWS_INVALID)


check_folder_rows(FOLDER_ROWS)


def is_scope_a_path(rel: str) -> bool:
    """True when rel is a markdown path under a scope A folder with no empty, dot, or dot dot part."""
    if not isinstance(rel, str) or not rel.startswith(SCOPE_A_PREFIXES):
        return False
    parts = rel.split(PATH_SEPARATOR)
    if any(part in REFUSED_PATH_PARTS for part in parts):
        return False
    return parts[-1].lower().endswith(MARKDOWN_SUFFIX)


def folder_row_for(rel: str) -> Optional[KindRow]:
    """Return the folder row of a scope A path as a KindRow whose id is N1 to N10, else None.

    Rows are tried in order and the first prefix match wins. None means the path is
    outside scope A or sits under no row. The KindRow form lets the run-mode edit builders
    and report entries be reused as they are.
    """
    if not is_scope_a_path(rel):
        return None
    for row in FOLDER_ROWS:
        if rel.startswith(row.prefixes):
            return KindRow(row.row_id, row.catalog_type, row.doc_role, row.indexable)
    return None


def row_for_run(run: int, rel: str) -> Optional[KindRow]:
    """Return the row a run uses for a path: the folder row for Run 4, else the ticket kind row."""
    return folder_row_for(rel) if run == RUN_NONTICKET else kind_row_for(rel)


def _ticket_parts(rel: str) -> Optional[Tuple[str, Tuple[str, ...], str]]:
    """Split a root relative path into (ticket folder, folders between, file name).

    Returns None when the path is not a string, sits outside a ticket folder, is not a
    markdown file, or holds an empty, dot, or dot dot part.
    """
    if not isinstance(rel, str):
        return None
    parts = rel.split(PATH_SEPARATOR)
    if len(parts) < MIN_TICKET_PATH_PARTS or parts[0] != STATE_ROOT_FOLDER:
        return None
    if any(part in REFUSED_PATH_PARTS for part in parts):
        return None
    if not parts[-1].lower().endswith(MARKDOWN_SUFFIX):
        return None
    first = 1 + ticket_prefix_depth(parts[1:])
    return parts[first], tuple(parts[first + 1:-1]), parts[-1]


def _matching_name(folder: str, name: str) -> str:
    """Rules one and two: lowercase the name, then drop a leading '<folder>-' when present."""
    lowered = name.lower()
    prefix = folder.lower() + NAME_JOINER
    if lowered.startswith(prefix):
        return lowered[len(prefix):]
    return lowered


def _pattern_matches(pattern: str, folder: str, text: str) -> bool:
    """Rule three: a star splits a pattern into prefix and suffix; no star means the whole name."""
    if pattern == FOLDER_MAIN_PATTERN:
        return text == folder.lower() + MARKDOWN_SUFFIX
    if GLOB_STAR not in pattern:
        return text == pattern
    head, tail = pattern.split(GLOB_STAR, 1)
    return (
        len(text) >= len(head) + len(tail)
        and text.startswith(head)
        and text.endswith(tail)
    )


def _name_row(folder: str, name: str) -> Optional[KindRow]:
    """Return the first of K3 to K13 whose pattern fits the file name, else None.

    A row skips a name it lists as an exclusion, so the next row can take that name.
    """
    text = _matching_name(folder, name)
    for row in KIND_ROWS:
        if text in row.exclusions:
            continue
        if any(_pattern_matches(pattern, folder, text) for pattern in row.patterns):
            return row
    return None


def role_by_name(rel: str) -> str:
    """Return the doc_role the file name gives, for K1 (rule five). The default is reference.

    The first of K3 to K13 that fits supplies the role. The K2 test is loosened to any
    name ending in -state.md and is tried first, as in the table order.
    """
    parts = _ticket_parts(rel)
    if parts is None:
        return ROLE_FALLBACK
    folder, _between, name = parts
    if name.lower().endswith(STATE_FILE_SUFFIX):
        return _ROWS_BY_ID[KIND_ID_STATE].doc_role
    row = _name_row(folder, name)
    return ROLE_FALLBACK if row is None else row.doc_role


def kind_row_for(rel: str) -> Optional[KindRow]:
    """Return the kind row for a root relative path, or None when no row applies.

    Rows are tried in order K1 to K14 and the first match wins. None covers K14, a path
    outside a ticket folder, and any path that is not a markdown file. A K1 result
    carries the role the file name gives.
    """
    parts = _ticket_parts(rel)
    if parts is None:
        return None
    folder, between, name = parts
    if any(part.lower() in ARCHIVE_FOLDERS for part in between):
        return replace(_ROWS_BY_ID[KIND_ID_ARCHIVE], doc_role=role_by_name(rel))
    if is_ticket_state_path(rel):
        return _ROWS_BY_ID[KIND_ID_STATE]
    return _name_row(folder, name)


def is_terminal_status(fm: Dict[str, Any]) -> bool:
    """True only when the status value is a string that, trimmed and lowercased, is terminal.

    A missing, empty, or non string status is not terminal, and neither is a value such
    as 'active | archived' that merely contains a terminal word.
    """
    if not isinstance(fm, dict):
        return False
    status = fm.get(STATUS_KEY)
    if not isinstance(status, str):
        return False
    return status.strip().lower() in TERMINAL_STATUSES


def row_values(row: KindRow, fm: Dict[str, Any]) -> Values:
    """Return the field values a row gives a file; a terminal status forces indexable false."""
    return Values(
        row.catalog_type,
        row.doc_role,
        row.indexable and not is_terminal_status(fm),
    )


def is_placeholder(fm: Dict[str, Any]) -> bool:
    """True only for the exact unknown placeholder: two strings 'unknown' and a boolean false.

    Whether the indexed field is present is a question for the planner, not this test.
    """
    if not isinstance(fm, dict):
        return False
    return (
        fm.get("catalog_type") == SENTINEL_VALUES.catalog_type
        and fm.get("doc_role") == SENTINEL_VALUES.doc_role
        and fm.get("indexable") is SENTINEL_VALUES.indexable
    )


def choose_eol(raw: bytes) -> bytes:
    """Return CRLF when the first line ending in raw is CRLF, else LF (also for no line ending)."""
    first = raw.find(EOL_LF)
    if first > 0 and raw[first - 1 : first] == CARRIAGE_RETURN:
        return EOL_CRLF
    return EOL_LF


def render_block(values: Values, eol: bytes) -> bytes:
    """Render a whole block: opening delimiter, the four field lines in order, closing delimiter."""
    fields = {name: _derived_value(name, values) for name in FIELD_ORDER}
    return DELIMITER + eol + render_additions(fields, eol) + DELIMITER + eol


def create_block(raw: bytes, block: bytes) -> bytes:
    """Return the block followed by every original byte, unchanged."""
    return block + raw


def is_safe_top(raw: bytes) -> bool:
    """True when a block may be created above raw.

    An empty file, a byte order mark, and three leading dashes are refused. Three
    dashes are an unclosed frontmatter or a horizontal rule, and a block placed over
    either would cover broken structure.
    """
    return bool(raw) and not raw.startswith(UNSAFE_TOP_PREFIXES)


def _same_by_type_and_value(actual: Dict[Any, Any], wanted: Dict[Any, Any]) -> bool:
    """True when both mappings hold the same keys and each value matches by type, then value.

    Integer 1 does not equal true. A comparison that raises, such as RecursionError on
    a self referencing anchor, counts as unequal. Only the exception class name is logged.
    """
    try:
        if set(actual) != set(wanted):
            return False
        return all(
            type(actual[key]) is type(wanted[key]) and actual[key] == wanted[key]
            for key in wanted
        )
    except Exception as exc:
        logger.debug("self check comparison failed: %s", type(exc).__name__)
        return False


def _block_has_four_fields(block: bytes, values: Values) -> bool:
    """True when block parses to exactly the four fields, in order, with exact types."""
    parsed = parse_block(block)
    if parsed is None or list(parsed) != list(FIELD_ORDER):
        return False
    wanted = {name: _derived_value(name, values) for name in FIELD_ORDER}
    return _same_by_type_and_value(parsed, wanted)


def verify_create(raw: bytes, block: bytes, new_raw: bytes, values: Values) -> bool:
    """Self check before any create: top safety, byte equality, then parsed equality.

    New bytes must equal the block followed by raw. The frontmatter found in them must
    close exactly where the block ends, use the first line ending of raw, and parse to
    the four fields with exact types.
    """
    if not is_safe_top(raw):
        return False
    if new_raw[: len(block)] != block or new_raw[len(block) :] != raw:
        return False
    new_span = split_frontmatter(new_raw)
    if new_span is None or new_span.eol != choose_eol(raw):
        return False
    if new_span.close_start + len(DELIMITER) + len(new_span.eol) != len(block):
        return False
    return _block_has_four_fields(new_span.block, values)


def _block_lines(span: Span) -> List[Tuple[int, bytes]]:
    """Return (raw offset, line with its line feed) for each line of the block.

    Lines split on the line feed only, as split_frontmatter does, so a carriage return
    stays part of its line.
    """
    offset = len(DELIMITER) + len(span.eol)
    pieces = span.block.split(EOL_LF)
    last = len(pieces) - 1
    lines: List[Tuple[int, bytes]] = []
    for index, piece in enumerate(pieces):
        line = piece + EOL_LF if index < last else piece
        if line:
            lines.append((offset, line))
        offset += len(line)
    return lines


def _encode(text: str) -> Optional[bytes]:
    """Encode text as UTF 8, or return None when it is not a string or cannot be encoded."""
    if not isinstance(text, str):
        return None
    try:
        return text.encode(ENCODING)
    except UnicodeEncodeError:
        return None


def field_line_span(span: Span, name: str) -> Optional[Tuple[int, int]]:
    """Return (start, end) in raw for the one column zero line that begins 'name:', else None.

    end is exclusive and includes the line ending. None means the field is absent,
    appears more than once, or the name is empty or cannot be encoded.
    """
    key = _encode(name)
    if not key:
        return None
    prefix = key + FIELD_COLON
    hits = [
        (offset, offset + len(line))
        for offset, line in _block_lines(span)
        if line.startswith(prefix)
    ]
    return hits[0] if len(hits) == 1 else None


def _span_matches(raw: bytes, span: Span) -> bool:
    """True when span describes raw: its block sits between the opening line and close_start."""
    start = len(DELIMITER) + len(span.eol)
    return raw[start : span.close_start] == span.block


def _one_replacement(raw: bytes, span: Span, edit: FieldEdit) -> Optional[Replacement]:
    """Plan one replacement, or None unless the line is exactly 'name: old' plus the file ending."""
    if not isinstance(edit, tuple) or len(edit) != EDIT_PARTS:
        return None
    name, old, new = edit
    texts = [_encode(text) for text in edit]
    if None in texts or old == new:
        return None
    if any(mark in new for mark in LINE_BREAK_CHARS):
        return None
    located = field_line_span(span, name)
    if located is None:
        return None
    key, old_bytes, new_bytes = texts
    if raw[located[0] : located[1]] != key + FIELD_SEPARATOR + old_bytes + span.eol:
        return None
    return located[0], located[1], key + FIELD_SEPARATOR + new_bytes + span.eol


def _plan_replacements(
    raw: bytes, span: Span, edits: Sequence[FieldEdit]
) -> Optional[List[Replacement]]:
    """Plan every replacement in raw order, or return None if any edit is refused.

    No edits, a span that does not describe raw, and two edits on one line all refuse.
    """
    if not edits or not _span_matches(raw, span):
        return None
    plan: List[Replacement] = []
    for edit in edits:
        item = _one_replacement(raw, span, edit)
        if item is None:
            return None
        plan.append(item)
    plan.sort()
    if len({item[0] for item in plan}) != len(plan):
        return None
    return plan


def replace_field_lines(
    raw: bytes, span: Span, edits: Sequence[Tuple[str, str, str]]
) -> Optional[bytes]:
    """Replace named lines in raw, or return None and change nothing.

    Each edit is (name, old, new). The line must be the only one that begins 'name:' at
    column zero and must equal 'name: old' followed by the file's own line ending. The
    new line keeps that ending. Any other form of the line refuses the whole call.
    """
    plan = _plan_replacements(raw, span, edits)
    if plan is None:
        return None
    result = raw
    for start, end, line in reversed(plan):
        result = result[:start] + line + result[end:]
    return result


def _only_planned_lines_changed(raw: bytes, new_raw: bytes, plan: List[Replacement]) -> bool:
    """True when new_raw is raw with only the planned line ranges swapped for the planned lines."""
    cursor = 0
    position = 0
    for start, end, line in plan:
        gap = raw[cursor:start]
        if new_raw[position : position + len(gap)] != gap:
            return False
        position += len(gap)
        if new_raw[position : position + len(line)] != line:
            return False
        position += len(line)
        cursor = end
    return new_raw[position:] == raw[cursor:]


def verify_replace(
    raw: bytes,
    span: Span,
    edits: Sequence[Tuple[str, str, str]],
    new_raw: bytes,
    fm: Dict[str, Any],
    expected: Dict[str, Any],
) -> bool:
    """Self check before any replace: byte equality, then parsed equality.

    Every byte outside the replaced lines must be unchanged and each replaced line must
    keep its ending. The parsed result must equal fm with only the keys of expected
    changed, compared by type and value. expected must name exactly the edited fields.
    """
    plan = _plan_replacements(raw, span, edits)
    if plan is None or not isinstance(fm, dict) or not isinstance(expected, dict):
        return False
    if set(expected) != {edit[0] for edit in edits}:
        return False
    if not _only_planned_lines_changed(raw, new_raw, plan):
        return False
    start = len(DELIMITER) + len(span.eol)
    parsed = parse_block(new_raw[start : span.close_start + len(new_raw) - len(raw)])
    if parsed is None:
        return False
    return _same_by_type_and_value(parsed, {**fm, **expected})


def _is_excluded_dir(
    rel_dir: str, excluded: Tuple[str, ...] = EXCLUDED_PATH_PREFIXES
) -> bool:
    """True when a root relative directory path falls under an excluded prefix."""
    return (rel_dir + PATH_SEPARATOR).startswith(excluded)


def _kept_dirs(
    dirnames: List[str],
    prefix: str,
    at_root: bool,
    excluded: Tuple[str, ...] = EXCLUDED_PATH_PREFIXES,
) -> List[str]:
    """Return the sorted child directories worth walking.

    Hidden directories are pruned at the vault root only. Excluded prefixes are
    pruned at any depth they match.
    """
    kept: List[str] = []
    for name in sorted(dirnames):
        if at_root and name.startswith(HIDDEN_DIR_PREFIX):
            continue
        if _is_excluded_dir(prefix + name, excluded):
            continue
        kept.append(name)
    return kept


def iter_vault_files(
    root: Path, excluded: Tuple[str, ...] = EXCLUDED_PATH_PREFIXES
) -> Iterator[str]:
    """Yield POSIX root relative paths of in scope markdown files.

    Directory symlinks are not followed. File symlinks are yielded so the planner
    can report them as SYMLINK instead of hiding them. excluded holds the folder
    prefixes to prune; the default is the standard list, and Run 4 passes its own.
    """
    root_str = str(root)
    for dirpath, dirnames, filenames in os.walk(root_str, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root_str)
        at_root = rel_dir == os.curdir
        prefix = "" if at_root else rel_dir.replace(os.sep, PATH_SEPARATOR) + PATH_SEPARATOR
        dirnames[:] = _kept_dirs(dirnames, prefix, at_root, excluded)
        for name in sorted(filenames):
            if name.endswith(MARKDOWN_SUFFIX):
                yield prefix + name


def _git_paths(root: Path, args: Sequence[str]) -> FrozenSet[str]:
    """Run one git listing command in root and return its NUL separated paths.

    Every failure becomes a GitStateError that carries only a closed code. Git output
    and exception text are never kept.
    """
    try:
        result = subprocess.run(
            [GIT_COMMAND, *args],
            cwd=str(root),
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise GitStateError(GIT_ERROR_TIMEOUT) from None
    except OSError:
        raise GitStateError(GIT_ERROR_UNAVAILABLE) from None
    if result.returncode != 0:
        raise GitStateError(GIT_ERROR_NONZERO_EXIT)
    return frozenset(os.fsdecode(item) for item in result.stdout.split(GIT_NUL) if item)


def load_git_state(root: Path) -> GitState:
    """Take one git snapshot of the vault: tracked, differing from HEAD, ignored."""
    return GitState(
        tracked=_git_paths(root, GIT_LIST_TRACKED_ARGS),
        differing=_git_paths(root, GIT_LIST_DIFFERING_ARGS),
        ignored=_git_paths(root, GIT_LIST_IGNORED_ARGS),
    )


def unrestorable_reason(git: GitState, rel: str) -> Optional[str]:
    """Return the skip code for a file git cannot restore, or None when it can.

    A staged but uncommitted file sits in both tracked and differing, so it is
    UNCOMMITTED. A force added file that matches an ignore rule is tracked, so it
    is restorable.
    """
    if rel in git.differing:
        return REASON_UNCOMMITTED
    if rel not in git.tracked:
        return REASON_GITIGNORED if rel in git.ignored else REASON_UNTRACKED
    return None


def _skipped(
    rel: str, reason: str, row: Optional[int] = None, label: Optional[str] = None
) -> Outcome:
    """Build a skipped outcome. The file stays byte identical."""
    return Outcome(rel, KIND_SKIPPED, reason=reason, row=row, label=label)


def _not_target(rel: str) -> Outcome:
    """Build a not_target outcome (row five)."""
    return Outcome(rel, KIND_NOT_TARGET, row=ROW_NOT_TARGET)


def _plan_values(
    rel: str,
    raw: bytes,
    span: Span,
    fm: Dict[str, Any],
    found: Classification,
    values: Values,
    git: GitState,
) -> Outcome:
    """Second half of the planner: additions, conflict, git check, build, self check."""
    additions = missing_additions(fm, values)
    if not additions:
        return Outcome(rel, KIND_ALREADY_COMPLETE, row=found.row, label=found.label)
    conflict = find_conflict(fm, values)
    if conflict is not None:
        return _skipped(rel, conflict, found.row, found.label)
    reason = unrestorable_reason(git, rel)
    if reason is not None:
        return _skipped(rel, reason, found.row, found.label)
    added = render_additions(additions, span.eol)
    new_raw = insert_lines(raw, span, added)
    if not verify_edit(raw, span, added, new_raw, fm, additions):
        logger.error("self check failed, file skipped: %s", rel)
        return _skipped(rel, REASON_VERIFY_FAILED, found.row, found.label)
    return Outcome(
        rel, KIND_WRITE, None, found.row, found.label, additions, raw, new_raw
    )


def _plan_bytes(rel: str, raw: bytes, git: GitState) -> Outcome:
    """First half of the planner: frontmatter span, parse, and classification."""
    span = split_frontmatter(raw)
    if span is None:
        if is_ticket_state_path(rel):
            return _skipped(rel, REASON_NO_FRONTMATTER, row=ROW_STATE)
        return _not_target(rel)
    fm = parse_block(span.block)
    if fm is None:
        return _skipped(rel, REASON_PARSE_ERROR)
    found = classify(rel, fm)
    if found.row == ROW_NOT_TARGET or found.values is None:
        return _not_target(rel)
    return _plan_values(rel, raw, span, fm, found, found.values, git)


def plan_file(root: Path, rel: str, git: GitState) -> Outcome:
    """Plan one file into exactly one outcome. Nothing is written; no exception escapes.

    An unexpected error while planning is a tool bug signal. It is logged at ERROR with
    the exception class name only, and the file is skipped as VERIFY_FAILED. An
    interrupt is not an Exception and still propagates to run.
    """
    path = root / rel
    if os.path.islink(path):
        return _skipped(rel, REASON_SYMLINK)
    try:
        raw = path.read_bytes()
    except OSError:
        return _skipped(rel, REASON_UNREADABLE)
    try:
        return _plan_bytes(rel, raw, git)
    except Exception as exc:
        logger.error("planning failed, file skipped: %s %s", rel, type(exc).__name__)
        return _skipped(rel, REASON_VERIFY_FAILED)


@dataclass(frozen=True)
class Shape:
    """What the frontmatter of one file looks like to the run planner.

    span is None when the file has no frontmatter. parse_failed is True when a block
    exists and does not parse; fm is None in both cases.
    """

    span: Optional[Span]
    fm: Optional[Dict[str, Any]]
    parse_failed: bool


@dataclass(frozen=True)
class Candidacy:
    """What one run may do with one file.

    change_class is None when the file is complete or not a target for this run. mixed
    marks a file that needs both an add and a flip. complete marks a file with all four
    fields that no change class claims.
    """

    change_class: Optional[str] = None
    mixed: bool = False
    complete: bool = False


NO_CANDIDACY = Candidacy()


def _read_shape(raw: bytes) -> Shape:
    """Locate and parse the frontmatter of raw. A block that does not parse sets parse_failed."""
    span = split_frontmatter(raw)
    if span is None:
        return Shape(None, None, False)
    fm = parse_block(span.block)
    return Shape(span, fm, fm is None)


def is_flip_candidate(fm: Dict[str, Any]) -> bool:
    """True for a terminal status file whose indexable reads true, as the boolean or as text.

    The text form (quoted true) is a candidate only so that the planner can refuse it
    with UNEXPECTED_LINE_FORM and show it; the replacer never writes it.
    """
    if not is_terminal_status(fm):
        return False
    value = fm.get(INDEXABLE_KEY)
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() == _render_value(True)


def _flip_candidate(run: int, rel: str, fm: Optional[Dict[str, Any]]) -> bool:
    """True when this is Run 1, the file is outside the unlabeled folders, and it needs a flip."""
    if run != RUN_ADD_FLIP or fm is None:
        return False
    if rel.partition(PATH_SEPARATOR)[0] in NOT_LABELED_FOLDERS:
        return False
    return is_flip_candidate(fm)


def _nonticket_candidacy(rel: str, shape: Shape) -> Candidacy:
    """Run 4: decide what the run does with a file, by folder. Only scope A files are targets.

    A file with no frontmatter gets a block, a file missing a field gets the missing
    lines, the exact placeholder is rewritten, and a file with all four fields is complete.
    """
    fm = shape.fm
    if not is_scope_a_path(rel):
        return NO_CANDIDACY
    if shape.span is None or fm is None:
        return Candidacy(CLASS_CREATE)
    if any(name not in fm for name in FIELD_ORDER):
        return Candidacy(CLASS_ADD)
    if is_placeholder(fm):
        return Candidacy(CLASS_REWRITE)
    return Candidacy(complete=True)


def _candidacy(run: int, rel: str, shape: Shape) -> Candidacy:
    """Decide what this run may do with a file whose frontmatter parsed (or is absent).

    Outside the tickets folder only the Run 1 flip applies. Inside it, Run 1 adds to files that
    have frontmatter and lack a field, Run 2 creates a block where there is none, and
    Run 3 rewrites the exact placeholder. A file with all four fields is complete.
    Run 4 decides by folder instead (see _nonticket_candidacy).
    """
    if run == RUN_NONTICKET:
        return _nonticket_candidacy(rel, shape)
    fm = shape.fm
    flip = _flip_candidate(run, rel, fm)
    if not rel.startswith(TICKETS_PREFIX):
        return Candidacy(CLASS_FLIP) if flip else NO_CANDIDACY
    if shape.span is None or fm is None:
        return Candidacy(CLASS_CREATE) if run == RUN_CREATE else NO_CANDIDACY
    if any(name not in fm for name in FIELD_ORDER):
        return Candidacy(CLASS_ADD, mixed=flip) if run == RUN_ADD_FLIP else NO_CANDIDACY
    if flip:
        return Candidacy(CLASS_FLIP)
    if run == RUN_REWRITE and is_placeholder(fm):
        return Candidacy(CLASS_REWRITE)
    return Candidacy(complete=True)


def _needs_row(cand: Candidacy) -> bool:
    """A flip changes one named line and needs no kind row. Every other class, and a mixed file, does."""
    return cand.change_class != CLASS_FLIP or cand.mixed


def _candidate_label(cand: Candidacy, fm: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return the report safe label a candidate carries, else None.

    A rewrite candidate carries its doc_type label (none when the key is absent). A flip
    carries its terminal status, trimmed and lowercased, which is one of five closed words.
    """
    if fm is None or cand.mixed:
        return None
    if cand.change_class == CLASS_REWRITE:
        return unmapped_label(fm[DOC_TYPE_KEY]) if DOC_TYPE_KEY in fm else LABEL_NONE
    if cand.change_class == CLASS_FLIP:
        status = fm.get(STATUS_KEY)
        return status.strip().lower() if isinstance(status, str) else None
    return None


def _differs_from_row(rel: str, fm: Dict[str, Any], run: int = RUN_ADD_FLIP) -> bool:
    """True when a complete file disagrees with its row and is neither placeholder nor flip.

    Placeholders are Run 3 and Run 4 targets and flip candidates are Run 1 targets, so no
    run leaves them alone and neither is listed. Run 4 has no flip, so a terminal file
    whose indexable reads true is listed. A file with no row cannot differ.
    """
    if is_placeholder(fm) or (run != RUN_NONTICKET and is_flip_candidate(fm)):
        return False
    row = row_for_run(run, rel)
    if row is None:
        return False
    return find_conflict(fm, row_values(row, fm)) is not None


def _settled_outcome(
    rel: str, shape: Shape, cand: Candidacy, run: int = RUN_ADD_FLIP
) -> Outcome:
    """Outcome for a file this run does not change: already complete, or not a target."""
    if not cand.complete or shape.fm is None:
        return _not_target(rel)
    note = NOTE_DIFFERS_FROM_ROW if _differs_from_row(rel, shape.fm, run) else None
    return Outcome(rel, KIND_ALREADY_COMPLETE, reason=note)


def _write_outcome(
    rel: str,
    change_class: str,
    row: Optional[KindRow],
    additions: Dict[str, Any],
    raw: bytes,
    new_raw: bytes,
    changes: Tuple[FieldEdit, ...] = (),
    label: Optional[str] = None,
) -> Outcome:
    """Build a planned write for run mode, tagged with its class, kind, and value changes."""
    return Outcome(
        rel, KIND_WRITE, additions=additions, original=raw, new_raw=new_raw, label=label,
        change_class=change_class,
        kind_id=KIND_NONE if row is None else row.kind_id,
        changes=changes,
    )


def _failed_check(rel: str, label: Optional[str]) -> Outcome:
    """Skip a file whose edit failed its self check. This signals a tool bug, so it is logged."""
    logger.error("self check failed, file skipped: %s", rel)
    return _skipped(rel, REASON_VERIFY_FAILED, label=label)


def _plan_add(
    rel: str, raw: bytes, shape: Shape, row: Optional[KindRow], label: Optional[str]
) -> Outcome:
    """Plan the missing field lines of a file that has frontmatter. Present fields never change."""
    fm, span = shape.fm, shape.span
    if row is None or fm is None or span is None:
        return _failed_check(rel, label)
    values = row_values(row, fm)
    conflict = find_conflict(fm, values)
    if conflict is not None:
        return _skipped(rel, conflict, label=label)
    additions = missing_additions(fm, values)
    added = render_additions(additions, span.eol)
    new_raw = insert_lines(raw, span, added)
    if not verify_edit(raw, span, added, new_raw, fm, additions):
        return _failed_check(rel, label)
    return _write_outcome(rel, CLASS_ADD, row, additions, raw, new_raw, label=label)


def _plan_create(
    rel: str, raw: bytes, shape: Shape, row: Optional[KindRow], label: Optional[str]
) -> Outcome:
    """Plan a four field block at byte zero of a file that has no frontmatter."""
    if row is None:
        return _failed_check(rel, label)
    if not is_safe_top(raw):
        return _skipped(rel, REASON_UNSAFE_TOP, label=label)
    values = row_values(row, {})
    block = render_block(values, choose_eol(raw))
    new_raw = create_block(raw, block)
    if not verify_create(raw, block, new_raw, values):
        return _failed_check(rel, label)
    additions = {name: _derived_value(name, values) for name in FIELD_ORDER}
    return _write_outcome(rel, CLASS_CREATE, row, additions, raw, new_raw, label=label)


def _flip_edits() -> Tuple[FieldEdit, ...]:
    """The one edit of a flip: the indexable line from true to false."""
    return ((INDEXABLE_KEY, _render_value(True), _render_value(False)),)


def _plan_flip(
    rel: str, raw: bytes, shape: Shape, row: Optional[KindRow], label: Optional[str]
) -> Outcome:
    """Plan the replacement of the line 'indexable: true' with 'indexable: false'."""
    fm, span = shape.fm, shape.span
    if fm is None or span is None:
        return _failed_check(rel, label)
    edits = _flip_edits()
    new_raw = replace_field_lines(raw, span, edits)
    if new_raw is None:
        return _skipped(rel, REASON_UNEXPECTED_LINE_FORM, label=label)
    if not verify_replace(raw, span, edits, new_raw, fm, {INDEXABLE_KEY: False}):
        return _failed_check(rel, label)
    return _write_outcome(rel, CLASS_FLIP, row, {}, raw, new_raw, edits, label)


def _rewrite_edits(values: Values) -> Tuple[FieldEdit, ...]:
    """The placeholder to row edits, one per field whose new text differs from the placeholder."""
    edits = [
        (
            name,
            _render_value(_derived_value(name, SENTINEL_VALUES)),
            _render_value(_derived_value(name, values)),
        )
        for name in CONFLICT_FIELDS
    ]
    return tuple(edit for edit in edits if edit[1] != edit[2])


def _plan_rewrite(
    rel: str, raw: bytes, shape: Shape, row: Optional[KindRow], label: Optional[str]
) -> Outcome:
    """Plan the replacement of the placeholder lines with the values of the file's kind row."""
    fm, span = shape.fm, shape.span
    if row is None or fm is None or span is None:
        return _failed_check(rel, label)
    values = row_values(row, fm)
    edits = _rewrite_edits(values)
    new_raw = replace_field_lines(raw, span, edits)
    if new_raw is None:
        return _skipped(rel, REASON_UNEXPECTED_LINE_FORM, label=label)
    expected = {edit[0]: _derived_value(edit[0], values) for edit in edits}
    if not verify_replace(raw, span, edits, new_raw, fm, expected):
        return _failed_check(rel, label)
    return _write_outcome(rel, CLASS_REWRITE, row, {}, raw, new_raw, edits, label)


def _build_planned(
    rel: str,
    raw: bytes,
    shape: Shape,
    cand: Candidacy,
    row: Optional[KindRow],
    label: Optional[str],
) -> Outcome:
    """Build the edit for the candidate's class and run its self check."""
    builders = {
        CLASS_ADD: _plan_add,
        CLASS_CREATE: _plan_create,
        CLASS_FLIP: _plan_flip,
        CLASS_REWRITE: _plan_rewrite,
    }
    if cand.change_class not in builders:
        return _failed_check(rel, label)
    return builders[cand.change_class](rel, raw, shape, row, label)


def _parse_error_applies(run: int, rel: str) -> bool:
    """True when an unparseable block is a skip for this run: scope A for Run 4, tickets otherwise."""
    if run == RUN_NONTICKET:
        return is_scope_a_path(rel)
    return rel.startswith(TICKETS_PREFIX)


def plan_run_file(root: Path, rel: str, git: GitState, run: int) -> Outcome:
    """Plan one file for one run into exactly one outcome. Nothing is written.

    The order is symlink, unreadable, parse, candidacy, kind row, git check, mixed check,
    then the edit with its self check. An unexpected error is a tool bug signal: it is
    logged with the exception class name only and the file is skipped as VERIFY_FAILED.
    """
    path = root / rel
    if os.path.islink(path):
        return _skipped(rel, REASON_SYMLINK)
    try:
        raw = path.read_bytes()
    except OSError:
        return _skipped(rel, REASON_UNREADABLE)
    try:
        shape = _read_shape(raw)
        if shape.parse_failed:
            if not _parse_error_applies(run, rel):
                return _not_target(rel)
            return _skipped(rel, REASON_PARSE_ERROR)
        cand = _candidacy(run, rel, shape)
        if cand.change_class is None:
            return _settled_outcome(rel, shape, cand, run)
        label = _candidate_label(cand, shape.fm)
        row = row_for_run(run, rel)
        if row is None and _needs_row(cand):
            return _skipped(rel, REASON_NO_KIND_ROW, label=label)
        reason = unrestorable_reason(git, rel)
        if reason is not None:
            return _skipped(rel, reason, label=label)
        if cand.mixed:
            return _skipped(rel, REASON_MIXED_EDIT, label=label)
        return _build_planned(rel, raw, shape, cand, row, label)
    except Exception as exc:
        logger.error("planning failed, file skipped: %s %s", rel, type(exc).__name__)
        return _skipped(rel, REASON_VERIFY_FAILED)


def _remove_quietly(tmp_name: Optional[str]) -> None:
    """Delete a temp file if one was created. A second failure is logged, not raised."""
    if tmp_name is None:
        return
    try:
        os.unlink(tmp_name)
    except OSError:
        logger.warning("temp file could not be removed: %s", tmp_name)


def apply_edit(path: Path, original: bytes, new_raw: bytes) -> Optional[str]:
    """Replace path with new_raw atomically, or return a reason code and change nothing.

    The file is read again and must still equal the planned original, and it must be
    writable by this user: os.replace would swap a read only file out of a writable
    folder, so the check keeps read only files untouched. The new bytes go to a temp
    file in the same folder, the mode is copied, the data is synced, and os.replace
    swaps it in, so the file is whole or untouched. Returns None on success.
    """
    try:
        current = path.read_bytes()
    except OSError:
        return REASON_UNREADABLE
    if current != original:
        return REASON_CHANGED_DURING_RUN
    if not os.access(str(path), os.W_OK):
        return REASON_WRITE_FAILED
    tmp_name: Optional[str] = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=TMP_PREFIX, suffix=TMP_SUFFIX
        )
        with os.fdopen(fd, WRITE_MODE_BINARY) as handle:
            handle.write(new_raw)
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copymode(str(path), tmp_name)
        os.replace(tmp_name, str(path))
    except OSError:
        _remove_quietly(tmp_name)
        return REASON_WRITE_FAILED
    return None


def _apply_outcome(root: Path, outcome: Outcome) -> Outcome:
    """Write one planned file. A failed write becomes a skipped outcome; the file stays whole."""
    if outcome.original is None or outcome.new_raw is None:
        logger.error("write outcome without bytes, file skipped: %s", outcome.rel)
        return _skipped(outcome.rel, REASON_VERIFY_FAILED, outcome.row, outcome.label)
    code = apply_edit(root / outcome.rel, outcome.original, outcome.new_raw)
    if code is None:
        return outcome
    return _skipped(outcome.rel, code, outcome.row, outcome.label)


def _plan_and_apply(root: Path, rel: str, git: GitState, apply: bool) -> Outcome:
    """Plan one file and, only when apply is set, write it. Preview never reaches apply_edit."""
    outcome = plan_file(root, rel, git)
    if apply and outcome.kind == KIND_WRITE:
        return _apply_outcome(root, outcome)
    return outcome


def run(root: Path, apply: bool) -> Dict[str, Any]:
    """Plan every in scope file, write the eligible ones when apply is set, return the report.

    The git snapshot is taken once, first; GitStateError is fatal. An interrupt logs
    how many files were processed and is raised again, so no report prints. Each file
    is whole or untouched, and a rerun finishes the rest.
    """
    git = load_git_state(root)
    outcomes: List[Outcome] = []
    try:
        for rel in iter_vault_files(root):
            outcomes.append(_plan_and_apply(root, rel, git, apply))
    except KeyboardInterrupt:
        logger.warning(
            "interrupted after %d files; each file is whole or untouched; "
            "a rerun finishes the rest",
            len(outcomes),
        )
        raise
    return build_report(MODE_APPLY if apply else MODE_PREVIEW, outcomes)


def check_tree_clean(root: Path) -> Tuple[bool, int]:
    """Return (clean, dirty entry count) from git status. Ignored files do not count.

    Untracked files count one per file. A git failure raises GitStateError with a closed
    code. No exception text or git output is kept.
    """
    entries = _git_paths(root, GIT_STATUS_ARGS)
    return not entries, len(entries)


def _report_shape_ok(loaded: Any) -> bool:
    """True when loaded is a report object whose writes are a list of entries with unique paths."""
    if not isinstance(loaded, dict):
        return False
    writes = loaded.get(REPORT_WRITES_KEY)
    if not isinstance(writes, list):
        return False
    paths = [entry.get(REPORT_PATH_KEY) if isinstance(entry, dict) else None for entry in writes]
    return all(isinstance(path, str) for path in paths) and len(set(paths)) == len(paths)


def _approved_matches_run(approved: Dict[str, Any], run: int) -> bool:
    """True when the approved report is a preview report for this run, by exact int and word."""
    named_run = approved.get(REPORT_RUN_KEY)
    return (
        approved.get(REPORT_MODE_KEY) == MODE_PREVIEW
        and type(named_run) is int
        and named_run == run
    )


def load_approved_report(path: Path, run: int) -> Dict[str, Any]:
    """Read the approved preview report, or raise PreconditionError with a closed code.

    A missing, unreadable, non JSON, or misshapen file is APPROVED_REPORT_INVALID. A report
    that is not a preview, or that names another run, is APPROVED_REPORT_MISMATCH.
    """
    try:
        loaded = json.loads(path.read_text(encoding=REPORT_ENCODING))
    except (OSError, ValueError, RecursionError):
        raise PreconditionError(ERROR_APPROVED_REPORT_INVALID) from None
    if not _report_shape_ok(loaded):
        raise PreconditionError(ERROR_APPROVED_REPORT_INVALID)
    if not _approved_matches_run(loaded, run):
        raise PreconditionError(ERROR_APPROVED_REPORT_MISMATCH)
    return loaded


def _write_entry(item: Outcome) -> Dict[str, Any]:
    """The report entry of one planned write: path, class, kind, added fields, and changes."""
    return {
        REPORT_PATH_KEY: item.rel,
        "class": item.change_class,
        "kind": item.kind_id if item.kind_id is not None else KIND_NONE,
        "added": dict(item.additions),
        "changes": [list(change) for change in item.changes],
    }


def _canonical(entry: Any) -> str:
    """Canonical JSON text, so 1 and true never compare equal."""
    return json.dumps(entry, sort_keys=True)


def unapproved_entries(outcomes: List[Outcome], approved: Dict[str, Any]) -> List[str]:
    """Return the sorted paths of planned writes that match no entry of the approved report.

    A planned write matches only when its path, class, kind, added fields, and changes all
    equal the approved entry. Approved entries that were not planned are ignored, so a
    subset rerun passes.
    """
    writes = approved.get(REPORT_WRITES_KEY)
    entries = writes if isinstance(writes, list) else []
    known = {
        entry[REPORT_PATH_KEY]: _canonical(entry)
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get(REPORT_PATH_KEY), str)
    }
    return sorted(
        item.rel
        for item in outcomes
        if item.kind == KIND_WRITE and known.get(item.rel) != _canonical(_write_entry(item))
    )


def _require_approved(
    outcomes: List[Outcome], approved: Optional[Dict[str, Any]], run: int
) -> None:
    """Raise PreconditionError unless every planned write equals an approved entry."""
    if approved is None:
        raise PreconditionError(ERROR_APPROVED_REPORT_REQUIRED)
    if not _approved_matches_run(approved, run):
        raise PreconditionError(ERROR_APPROVED_REPORT_MISMATCH)
    unapproved = unapproved_entries(outcomes, approved)
    if unapproved:
        logger.error("planned writes missing from the approved report: %d", len(unapproved))
        raise PreconditionError(ERROR_NOT_APPROVED)


def excluded_for_run(run: Optional[int]) -> Tuple[str, ...]:
    """Return the folder prefixes a run's walk skips: the Run 4 list for Run 4, else the earlier list."""
    return RUN4_EXCLUDED_PATH_PREFIXES if run == RUN_NONTICKET else EXCLUDED_PATH_PREFIXES


def _plan_all(root: Path, run: int, git: GitState) -> List[Outcome]:
    """Plan every in scope file. An interrupt here wrote nothing, and is raised again."""
    outcomes: List[Outcome] = []
    try:
        for rel in iter_vault_files(root, excluded_for_run(run)):
            outcomes.append(plan_run_file(root, rel, git, run))
    except KeyboardInterrupt:
        logger.warning(
            "interrupted while planning after %d files; nothing was written", len(outcomes)
        )
        raise
    return outcomes


def _write_planned(root: Path, outcomes: List[Outcome]) -> List[Outcome]:
    """Write each planned file through _apply_outcome and return the outcomes after writing.

    An interrupt logs how many files were processed and is raised again. Each file is
    whole or untouched, and a new preview plans only what is left.
    """
    done: List[Outcome] = []
    try:
        for item in outcomes:
            done.append(_apply_outcome(root, item) if item.kind == KIND_WRITE else item)
    except KeyboardInterrupt:
        logger.warning(
            "interrupted after %d files; each file is whole or untouched; "
            "a new preview plans the rest",
            len(done),
        )
        raise
    return done


def run_policy(
    root: Path, run: int, apply: bool, approved: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Plan every file for one run, and with apply write them, then return the run report.

    Order: tree check, git snapshot, plan every file, then (apply only) the approved report
    check and the writes. Nothing is written before the tree is clean and every planned
    write equals an approved entry. Preview never reaches apply_edit. A dirty tree is
    refused only in apply mode; preview reports it.
    """
    tree = check_tree_clean(root)
    clean, dirty_count = tree
    if apply and not clean:
        logger.error("dirty tree, nothing written: %d entries", dirty_count)
        raise PreconditionError(ERROR_DIRTY_TREE)
    git = load_git_state(root)
    outcomes = _plan_all(root, run, git)
    if apply:
        _require_approved(outcomes, approved, run)
        outcomes = _write_planned(root, outcomes)
    return build_run_report(MODE_APPLY if apply else MODE_PREVIEW, run, outcomes, tree)


def _skipped_by_reason(outcomes: List[Outcome]) -> Dict[str, int]:
    """Count skipped outcomes per reason code. Codes that did not occur are absent."""
    counts: Dict[str, int] = {}
    for item in outcomes:
        if item.kind == KIND_SKIPPED and item.reason is not None:
            counts[item.reason] = counts.get(item.reason, 0) + 1
    return counts


def _count_outcomes(outcomes: List[Outcome], by_reason: Dict[str, int]) -> Dict[str, int]:
    """Build the counts block. classified is already_complete + write + skipped."""
    kinds = [item.kind for item in outcomes]
    written = kinds.count(KIND_WRITE)
    skipped = kinds.count(KIND_SKIPPED)
    already = kinds.count(KIND_ALREADY_COMPLETE)
    excluded = sum(by_reason.get(code, 0) for code in STOP_RULE_EXCLUDED_REASONS)
    indexable = sum(
        1 for item in outcomes
        if item.kind == KIND_WRITE and item.additions.get("indexable") is True
    )
    return {
        "scanned": len(outcomes),
        "not_target": kinds.count(KIND_NOT_TARGET),
        "classified": already + written + skipped,
        "already_complete": already,
        "written": written,
        "skipped": skipped,
        "writes_indexable": indexable,
        "needing_fields": written + skipped - excluded,
    }


def _row_counts(outcomes: List[Outcome]) -> Dict[str, int]:
    """Count outcomes per contract row 1 through 4. Outcomes with no row are not counted."""
    counts = {str(row): 0 for row in REPORT_ROWS}
    for item in outcomes:
        if item.row in REPORT_ROWS:
            counts[str(item.row)] += 1
    return counts


def _unmapped_counts(outcomes: List[Outcome]) -> Dict[str, int]:
    """Count every row 3 outcome per report safe doc_type label, whatever its outcome."""
    counts: Dict[str, int] = {}
    for item in outcomes:
        if item.row == ROW_DOC_TYPE_UNMAPPED and item.label is not None:
            counts[item.label] = counts.get(item.label, 0) + 1
    return counts


def _list_outcomes(
    outcomes: List[Outcome],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return the skipped list and the writes list, each sorted by path."""
    skipped = [
        {"path": item.rel, "reason": item.reason}
        for item in outcomes if item.kind == KIND_SKIPPED
    ]
    writes = [
        {"path": item.rel, "added": dict(item.additions)}
        for item in outcomes if item.kind == KIND_WRITE
    ]
    skipped.sort(key=lambda entry: entry["path"])
    writes.sort(key=lambda entry: entry["path"])
    return skipped, writes


def build_report(mode: str, outcomes: List[Outcome]) -> Dict[str, Any]:
    """Turn the outcomes into the report. Only paths, codes, field values, and counts appear."""
    by_reason = _skipped_by_reason(outcomes)
    skipped, writes = _list_outcomes(outcomes)
    return {
        "mode": mode,
        "counts": _count_outcomes(outcomes, by_reason),
        "skipped_by_reason": by_reason,
        "rows": _row_counts(outcomes),
        "skipped": skipped,
        "writes": writes,
        "unmapped_doc_types": _unmapped_counts(outcomes),
        "exclusions": list(EXCLUDED_PATH_PREFIXES),
    }


def _result_indexable(item: Outcome) -> Optional[bool]:
    """Return the indexable value a planned write leaves in the file, read from its new bytes."""
    if item.new_raw is None:
        return None
    span = split_frontmatter(item.new_raw)
    parsed = None if span is None else parse_block(span.block)
    value = None if parsed is None else parsed.get(INDEXABLE_KEY)
    return value if isinstance(value, bool) else None


def _run_counts(outcomes: List[Outcome], writes: List[Outcome]) -> Dict[str, int]:
    """Count the run report's totals. classified is already_complete + written + changed + skipped."""
    kinds = [item.kind for item in outcomes]
    skipped = kinds.count(KIND_SKIPPED)
    already = kinds.count(KIND_ALREADY_COMPLETE)
    results = [_result_indexable(item) for item in writes]
    return {
        "scanned": len(outcomes),
        "not_target": kinds.count(KIND_NOT_TARGET),
        "classified": already + len(writes) + skipped,
        "already_complete": already,
        "written": sum(1 for item in writes if item.change_class in WRITTEN_CLASSES),
        "changed": sum(1 for item in writes if item.change_class in CHANGED_CLASSES),
        "skipped": skipped,
        "result_true": sum(1 for value in results if value is True),
        "result_false": sum(1 for value in results if value is False),
    }


def _class_counts(writes: List[Outcome]) -> Dict[str, int]:
    """Count planned writes per class. All four classes appear, zero when unused."""
    return {name: sum(1 for item in writes if item.change_class == name) for name in CLASS_NAMES}


def _kind_counts(writes: List[Outcome]) -> Dict[str, Dict[str, int]]:
    """Count planned writes per kind id and class. A kind with no write is absent."""
    counts: Dict[str, Dict[str, int]] = {}
    for item in writes:
        kind = item.kind_id if item.kind_id is not None else KIND_NONE
        per_class = counts.setdefault(kind, {name: 0 for name in CLASS_NAMES})
        if item.change_class in per_class:
            per_class[item.change_class] += 1
    return counts


def _flip_status_counts(writes: List[Outcome]) -> Dict[str, int]:
    """Count flips per terminal status word (the label a flip carries)."""
    counts: Dict[str, int] = {}
    for item in writes:
        if item.change_class == CLASS_FLIP and item.label is not None:
            counts[item.label] = counts.get(item.label, 0) + 1
    return counts


def _dispositions(run: int, outcomes: List[Outcome]) -> Dict[str, Dict[str, int]]:
    """Run 3 only: per doc_type label, how many placeholder files resolved and how many are left.

    A rewrite is resolved. A placeholder file the run skipped, for any reason, is left.
    """
    counts: Dict[str, Dict[str, int]] = {}
    if run != RUN_REWRITE:
        return counts
    for item in outcomes:
        if item.label is None:
            continue
        entry = counts.setdefault(item.label, {RESOLVED_KEY: 0, LEFT_KEY: 0})
        entry[RESOLVED_KEY if item.kind == KIND_WRITE else LEFT_KEY] += 1
    return counts


def build_run_report(
    mode: str, run: int, outcomes: List[Outcome], tree: Tuple[bool, int]
) -> Dict[str, Any]:
    """Turn run outcomes into the run report. Only paths, field names, closed values, codes,
    doc_type labels that pass the safe pattern, and counts appear.
    """
    writes = [item for item in outcomes if item.kind == KIND_WRITE]
    skipped = [
        {REPORT_PATH_KEY: item.rel, "reason": item.reason}
        for item in outcomes if item.kind == KIND_SKIPPED
    ]
    clean, dirty_count = tree
    return {
        REPORT_MODE_KEY: mode,
        REPORT_RUN_KEY: run,
        "tree": {"clean": clean, "dirty_count": dirty_count},
        "counts": _run_counts(outcomes, writes),
        "by_class": _class_counts(writes),
        "by_kind": _kind_counts(writes),
        "flips_by_status": _flip_status_counts(writes),
        "skipped_by_reason": _skipped_by_reason(outcomes),
        "skipped": sorted(skipped, key=lambda entry: entry[REPORT_PATH_KEY]),
        REPORT_WRITES_KEY: sorted(
            (_write_entry(item) for item in writes), key=lambda entry: entry[REPORT_PATH_KEY]
        ),
        "complete_differs": sorted(
            item.rel for item in outcomes
            if item.kind == KIND_ALREADY_COMPLETE and item.reason == NOTE_DIFFERS_FROM_ROW
        ),
        "dispositions": _dispositions(run, outcomes),
        "not_labeled": list(NOT_LABELED_FOLDERS),
        "exclusions": list(excluded_for_run(run)),
    }


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """Parse the command line. Preview is the default; abbreviations are refused."""
    parser = argparse.ArgumentParser(
        description="Add catalog_type, doc_role, indexable, and indexed to vault "
        "markdown files. Preview by default; --apply writes.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--vault-root", type=Path, default=None,
        help="Vault folder. Defaults to the vault path from the path loader.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write the planned lines. Without this flag nothing is written.",
    )
    parser.add_argument(
        "--report-path", type=Path, default=None,
        help="Also write the JSON report to this file. The parent folder must exist.",
    )
    parser.add_argument(
        "--run", type=int, choices=RUN_NUMBERS, default=None,
        help="Plan one run: 1 add and flip, 2 create, 3 rewrite (the earlier change, tickets), "
        "4 label notes outside tickets by folder. "
        "Without this flag the earlier behavior runs.",
    )
    parser.add_argument(
        "--approved-report", type=Path, default=None,
        help="The approved preview report for this run. Required with --run and --apply, "
        "and valid only then.",
    )
    return parser.parse_args(argv)


def default_vault_root() -> Path:
    """Return the vault folder from the Tollgate path loader.

    A loader that is not set up, cannot be imported, or gives no answer raises
    PreconditionError, which main turns into exit 2. The loader's own text never
    surfaces.
    """
    scripts_dir = str(Path(__file__).resolve().parents[1])
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from core.paths import get_path
        return Path(get_path(PATHS_VAULT_NAME))
    except Exception:
        raise PreconditionError(ERROR_MANIFEST_UNREADABLE) from None


def _check_run_flags(run: Optional[int], apply: bool, approved_path: Optional[Path]) -> None:
    """Raise PreconditionError for a flag combination run mode refuses.

    --approved-report is valid only with --run and --apply, and --run with --apply
    requires it. Without --run and without --approved-report nothing is checked.
    """
    if approved_path is not None and (run is None or not apply):
        raise PreconditionError(ERROR_FLAG_COMBINATION)
    if run is not None and apply and approved_path is None:
        raise PreconditionError(ERROR_APPROVED_REPORT_REQUIRED)


def _check_preconditions(
    root: Path,
    report_path: Optional[Path],
    run: Optional[int] = None,
    apply: bool = False,
    approved_path: Optional[Path] = None,
) -> None:
    """Raise PreconditionError before anything is read or written."""
    _check_run_flags(run, apply, approved_path)
    if not root.is_dir():
        raise PreconditionError(ERROR_VAULT_ROOT_NOT_A_FOLDER)
    if report_path is None:
        return
    if report_path.is_dir() or not report_path.parent.is_dir():
        raise PreconditionError(ERROR_REPORT_PATH_INVALID)


def _write_report_file(report_path: Path, text: str) -> bool:
    """Write the report file. A failure is logged as a closed code, never raised."""
    try:
        report_path.write_text(text, encoding=REPORT_ENCODING)
    except OSError:
        logger.error("report file not written: %s", ERROR_REPORT_WRITE_FAILED)
        return False
    return True


def _log_run_summary(report: Dict[str, Any]) -> None:
    """Log one line of run counts. No path or value enters the log."""
    counts = report["counts"]
    logger.info(
        "%s run %d: scanned=%d not_target=%d classified=%d already_complete=%d "
        "written=%d changed=%d skipped=%d tree_clean=%s",
        report[REPORT_MODE_KEY], report[REPORT_RUN_KEY], counts["scanned"],
        counts["not_target"], counts["classified"], counts["already_complete"],
        counts["written"], counts["changed"], counts["skipped"], report["tree"]["clean"],
    )


def _log_summary(report: Dict[str, Any]) -> None:
    """Log one line of counts. No path or value enters the log."""
    if REPORT_RUN_KEY in report:
        _log_run_summary(report)
        return
    counts = report["counts"]
    logger.info(
        "%s: scanned=%d not_target=%d classified=%d already_complete=%d "
        "written=%d skipped=%d needing_fields=%d",
        report["mode"], counts["scanned"], counts["not_target"], counts["classified"],
        counts["already_complete"], counts["written"], counts["skipped"],
        counts["needing_fields"],
    )


def _emit_report(report: Dict[str, Any], report_path: Optional[Path]) -> int:
    """Print the report, save it when asked, log the summary, and return the exit code.

    Exit 3 means at least one WRITE_FAILED and wins over a failed report file.
    """
    text = json.dumps(report, sort_keys=True, indent=REPORT_JSON_INDENT) + "\n"
    sys.stdout.write(text)
    report_saved = report_path is None or _write_report_file(report_path, text)
    _log_summary(report)
    if report["skipped_by_reason"].get(REASON_WRITE_FAILED, 0) > 0:
        return EXIT_WRITE_FAILED
    return EXIT_OK if report_saved else EXIT_PRECONDITION


def _execute(root: Path, args: argparse.Namespace) -> Dict[str, Any]:
    """Dispatch to the earlier run, or to the earlier policy run when --run is given.

    The approved report is loaded here, before the policy run, only in apply mode.
    """
    if args.run is None:
        return run(root, args.apply)
    approved = None
    if args.apply:
        approved = load_approved_report(args.approved_report, args.run)
    return run_policy(root, args.run, args.apply, approved)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the backfill from the command line. Returns 0, 2, or 3.

    0: finished (skips do not fail the run). 2: a fatal precondition failed and nothing
    was written. 3: finished with at least one WRITE_FAILED. An interrupt propagates.
    """
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=LOG_FORMAT)
    args = parse_args(argv)
    try:
        root = args.vault_root if args.vault_root is not None else default_vault_root()
        _check_preconditions(
            root, args.report_path, args.run, args.apply, args.approved_report
        )
        report = _execute(root, args)
    except (PreconditionError, GitStateError) as exc:
        logger.error("fatal precondition, nothing written: %s", exc)
        return EXIT_PRECONDITION
    return _emit_report(report, args.report_path)


if __name__ == "__main__":
    sys.exit(main())
