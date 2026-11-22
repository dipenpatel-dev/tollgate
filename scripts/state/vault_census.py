# Module:      vault_census.py
# Description: Scan C, the independent census for the earlier vault retrieval cleanup. It
#              walks the vault, reads line one frontmatter with a YAML parser, and prints
#              counts of files with all four retrieval fields, some, none, no frontmatter,
#              and unparseable frontmatter. It also counts catalog_type, doc_role, and
#              indexable triples, terminal status files with indexable true, ticket files
#              with catalog_type unknown, and in scope ticket files missing a field. Every
#              count is split by top level folder. The --check-writes mode reads run
#              reports and proves each added, created, or rewritten file carries its kind
#              row triple from this module's own copy of the policy table. The census is
#              read only, never imports the backfill tool, and prints counts, paths, and
#              closed codes only. the earlier change adds its own copy of the folder policy table (N1
#              to N10): a Run 4 report is checked against it, and the check also counts
#              scope A notes that still miss a field.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       Vault markdown frontmatter census; the earlier change spec policy table (K1 to K14);
#              the earlier change spec folder policy table (N1 to N10)
# Version:     1.2
# ChangeLog:
#   Initial implementation
#   Spec Q2 change: session-notes.md is a ticket summary, K10 not K9; KindRow exclusions
#   Own copy of folder rows N1 to N10, Run 4 report check, scope A missing count

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Sequence, Tuple

import yaml

logger = logging.getLogger(__name__)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import folder_name, ticket_prefix_depth, subdir_prefixes  # noqa: E402

SYSTEM_MAP_DIR = folder_name("system_map")
REFERENCE_DIR = folder_name("reference")
TICKETS_DIR = folder_name("tickets")
KNOWLEDGE_DIR = folder_name("knowledge")
EDUCATION_DIR = folder_name("education")
CONVERSATIONS_DIR_NAME = folder_name("conversations")
THREADS_DIR_NAME = folder_name("chat_threads")

Triple = Tuple[str, str, bool]

FIELD_NAMES: Tuple[str, ...] = ("catalog_type", "doc_role", "indexable", "indexed")
TRIPLE_FIELDS: Tuple[str, ...] = ("catalog_type", "doc_role", "indexable")
FIELD_CATALOG_TYPE = "catalog_type"
FIELD_DOC_ROLE = "doc_role"
FIELD_INDEXABLE = "indexable"
FIELD_INDEXED = "indexed"
STATUS_KEY = "status"
UNKNOWN_VALUE = "unknown"
TERMINAL_STATUSES: FrozenSet[str] = frozenset(
    {"cancelled", "superseded", "dropped", "archived", "absorbed"}
)

DELIMITER = b"---"
EOL_LF = b"\n"
CARRIAGE_RETURN = b"\r"
OPENING_LF = DELIMITER + EOL_LF
OPENING_CRLF = DELIMITER + CARRIAGE_RETURN + EOL_LF
ENCODING = "utf-8"

MARKDOWN_SUFFIX = ".md"
PATH_SEPARATOR = "/"
HIDDEN_DIR_PREFIX = "."
# The memory folder is a top level layout folder. Nothing else is skipped by name.
MEMORY_DIR = folder_name("memory")
EXCLUDED_PATH_PREFIXES: Tuple[str, ...] = ((MEMORY_DIR + "/"),)
ROOT_FOLDER_LABEL = "<root>"

TICKETS_FOLDER = TICKETS_DIR
MIN_TICKET_PATH_PARTS = 3
STATE_DEPTH = 3
FOLDER_PREFIX_JOINER = "-"
STATE_SUFFIX = "-state.md"
ARCHIVE_FOLDERS: FrozenSet[str] = frozenset({"archive", "history"})

CATALOG_TICKET = "ticket"
ROLE_STATE = "state"
ROLE_REFERENCE = "reference"
NAME_TICKET_SUMMARY = "session-notes.md"
ROW_ARCHIVE = "K1"
ROW_STATE = "K2"
SPECIAL_ARCHIVE = "archive_folder"
SPECIAL_STATE = "state_file"
SPECIAL_FOLDER_NAME = "folder_name"

LABEL_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,64}")
LABEL_NON_STRING = "<non-string>"
LABEL_UNSAFE = "<unsafe>"
LABEL_NON_BOOL = "<non-bool>"
TRIPLE_JOINER = "|"
TRUE_LABEL = "true"
FALSE_LABEL = "false"

KIND_ALL = "with_all_four"
KIND_SOME = "with_some"
KIND_NONE = "with_none"
KIND_NO_FRONTMATTER = "no_frontmatter"
KIND_UNPARSEABLE = "unparseable"
KIND_SYMLINK = "symlinks"
KIND_UNREADABLE = "unreadable"
KEY_FILES = "files"
KEY_CATALOG_TYPE = "catalog_type"
KEY_DOC_ROLE = "doc_role"
KEY_TRIPLE = "triple"
KEY_TERMINAL = "terminal_indexable_true"
KEY_UNKNOWN = "catalog_type_unknown_tickets"
KEY_IN_SCOPE_MISSING = "in_scope_missing_fields"
KEY_BY_FOLDER = "by_folder"
KEY_EXCLUSIONS = "exclusions"
NO_VALUE_KINDS: FrozenSet[str] = frozenset({KIND_UNPARSEABLE, KIND_SYMLINK, KIND_UNREADABLE})

GIT_COMMAND = "git"
GIT_TIMEOUT_SECONDS = 30
GIT_NUL = b"\0"
GIT_LIST_TRACKED_ARGS: Tuple[str, ...] = ("ls-files", "-z")
GIT_LIST_DIFFERING_ARGS: Tuple[str, ...] = (
    "diff", "--no-renames", "--relative", "--name-only", "-z", "HEAD",
)
GIT_ENV_OPTIONAL_LOCKS = "GIT_OPTIONAL_LOCKS"
GIT_ENV_DISABLED = "0"

CLASS_ADD = "add"
CLASS_CREATE = "create"
CLASS_REWRITE = "rewrite"
CLASS_FLIP = "flip"
CHECKED_CLASSES: FrozenSet[str] = frozenset({CLASS_ADD, CLASS_CREATE, CLASS_REWRITE})
REPORT_WRITES_KEY = "writes"
ENTRY_PATH_KEY = "path"
ENTRY_CLASS_KEY = "class"
REPORT_RUN_KEY = "run"
RUN_NONTICKET = 4
KEY_SCOPE_A_MISSING = "scope_a_missing_fields"
KNOWLEDGE_BASE = (KNOWLEDGE_DIR + "/")
RUN4_EXCLUDED_PATH_PREFIXES: Tuple[str, ...] = EXCLUDED_PATH_PREFIXES
ERROR_FOLDER_ROWS_INVALID = "FOLDER_ROWS_INVALID"

CODE_MALFORMED_ENTRY = "MALFORMED_ENTRY"
CODE_PATH_UNSAFE = "PATH_UNSAFE"
CODE_FILE_UNREADABLE = "FILE_UNREADABLE"
CODE_NO_FRONTMATTER = "NO_FRONTMATTER"
CODE_UNPARSEABLE = "FRONTMATTER_UNPARSEABLE"
CODE_NO_KIND_ROW = "NO_KIND_ROW"
CODE_FIELD_MISSING = "FIELD_MISSING"
CODE_INDEXED_NOT_NULL = "INDEXED_NOT_NULL"
CODE_TRIPLE_DIFFERS = "TRIPLE_DIFFERS"
NO_VALUE_CODES: Dict[str, str] = {
    KIND_SYMLINK: CODE_FILE_UNREADABLE,
    KIND_UNREADABLE: CODE_FILE_UNREADABLE,
    KIND_NO_FRONTMATTER: CODE_NO_FRONTMATTER,
    KIND_UNPARSEABLE: CODE_UNPARSEABLE,
}

ERROR_VAULT_ROOT_NOT_A_FOLDER = "VAULT_ROOT_NOT_A_FOLDER"
ERROR_REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
ERROR_REPORT_UNREADABLE = "REPORT_UNREADABLE"
ERROR_REPORT_UNPARSEABLE = "REPORT_UNPARSEABLE"
ERROR_REPORT_SHAPE_INVALID = "REPORT_SHAPE_INVALID"
ERROR_GIT_TIMEOUT = "GIT_TIMEOUT"
ERROR_GIT_UNAVAILABLE = "GIT_UNAVAILABLE"
ERROR_GIT_NONZERO_EXIT = "GIT_NONZERO_EXIT"

EXIT_OK = 0
EXIT_PRECONDITION = 2
JSON_INDENT = 2
LOG_FORMAT = "%(levelname)s %(message)s"


class PreconditionError(Exception):
    """A fatal precondition failed. The message is a closed code, never exception text."""


@dataclass(frozen=True)
class KindRow:
    """One row of this module's own copy of the earlier spec policy table.

    names match the whole lowercase name, prefixes match its start, and patterns match
    it fully. exclusions are whole lowercase names the row never takes, so a later row can
    take them. special names the three rows that need more than a name: the archive
    folder row, the state file row, and the ticket main file row.
    """

    row_id: str
    catalog_type: str
    doc_role: str
    indexable: bool
    special: str = ""
    names: Tuple[str, ...] = ()
    prefixes: Tuple[str, ...] = ()
    patterns: Tuple[str, ...] = ()
    exclusions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class FolderRow:
    """One row of this module's own copy of the earlier folder policy table.

    A note whose vault relative path starts with one of the prefixes takes the row. The
    note's doc_type is never read.
    """

    row_id: str
    prefixes: Tuple[str, ...]
    catalog_type: str
    doc_role: str
    indexable: bool


@dataclass(frozen=True)
class PathInfo:
    """A ticket path split for matching. Every text field except depth is lowercase."""

    folder: str
    depth: int
    middle: Tuple[str, ...]
    name: str
    match_name: str


@dataclass(frozen=True)
class FileFacts:
    """What one file shows: its count kind and its parsed frontmatter when it has one."""

    kind: str
    fm: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class GitSnapshot:
    """Vault relative POSIX paths git tracks, and those that differ from HEAD."""

    tracked: FrozenSet[str]
    differing: FrozenSet[str]


# Source: the spec, Policy Table, typed here row by row. Rows are tried in this order
# and the first match wins. Matching uses the lowercase name with a leading "<folder>-"
# removed (the spec, Policy Rules). K14 (any other name) has no row: no entry here.
KIND_ROWS: Tuple[KindRow, ...] = (
    KindRow("K1", "ticket", "role_by_name", False, special=SPECIAL_ARCHIVE),
    KindRow("K2", "ticket", "state", True, special=SPECIAL_STATE),
    KindRow(
        "K3", "ticket", "review", False,
        prefixes=("cursor", "qa-cursor", "arch-review"),
    ),
    KindRow(
        "K4", "ticket", "reference", False,
        prefixes=("prompt", "starter-prompt"), patterns=(r"block_.*-diff\.md",),
    ),
    KindRow("K5", "ticket", "spec", True, names=("spec.md", "pre-spec.md")),
    KindRow("K6", "ticket", "design", True, names=("design.md", "arch.md")),
    KindRow("K7", "ticket", "qa", True, prefixes=("qa-findings",)),
    KindRow("K8", "ticket", "qa", True, names=("edge-case-validation.md",)),
    KindRow(
        "K9", "ticket", "session_log", True,
        prefixes=("session",), exclusions=(NAME_TICKET_SUMMARY,),
    ),
    KindRow(
        "K10", "ticket", "reference", True,
        special=SPECIAL_FOLDER_NAME, names=(NAME_TICKET_SUMMARY,),
    ),
    KindRow("K11", "ticket", "reference", True, names=("context.md", "diagrams.md")),
    KindRow("K12", "ticket", "reference", True, names=("shipped.md",)),
    KindRow(
        "K13", "ticket", "reference", True,
        names=(
            "handoff.md", "support-handoff.md", "notes.md", "plan.md",
            "jira-draft.md", "coord.md",
        ),
    ),
)
ROLE_ROWS: Tuple[KindRow, ...] = tuple(
    row for row in KIND_ROWS if row.row_id not in (ROW_ARCHIVE, ROW_STATE)
)

def _system_map_sub(*names: str) -> Tuple[str, ...]:
    return subdir_prefixes("system_map", names)


def _knowledge_sub(*names: str) -> Tuple[str, ...]:
    return subdir_prefixes("knowledge", names)


# Source: the spec, Policy table, typed here row by row and not imported from the
# backfill tool. Subfolders come from the layout table (core.paths), not from text in this file. First match wins. A path under no prefix has no row.
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
SCOPE_A_PREFIXES: Tuple[str, ...] = (
    (SYSTEM_MAP_DIR + "/"),
    (EDUCATION_DIR + "/"),
) + _knowledge_sub("decisions", "learnings", "patterns")
if len({row.row_id for row in FOLDER_ROWS}) != len(FOLDER_ROWS):
    raise ValueError(ERROR_FOLDER_ROWS_INVALID)


def split_ticket_path(rel: str) -> Optional[PathInfo]:
    """Split a vault relative path under the tickets folder, or return None for any other path."""
    parts = rel.split(PATH_SEPARATOR)
    if len(parts) < MIN_TICKET_PATH_PARTS or parts[0] != TICKETS_FOLDER or not parts[1]:
        return None
    lower = [part.lower() for part in parts]
    # A vault may keep tickets under a prefix folder (tickets/PROJ/PROJ-312/...). Skip that level so the
    # ticket folder, the middle folders and the depth read the same in both layouts.
    skip = ticket_prefix_depth(parts[1:])
    first = 1 + skip
    folder, name = lower[first], lower[-1]
    prefix = folder + FOLDER_PREFIX_JOINER
    match_name = name[len(prefix):] if name.startswith(prefix) else name
    return PathInfo(folder, len(parts) - skip, tuple(lower[first + 1:-1]), name, match_name)


def name_matches(row: KindRow, name: str) -> bool:
    """True when a lowercase name equals a row name, starts with a prefix, or fits a pattern.

    A name the row lists as an exclusion never matches it.
    """
    if name in row.exclusions:
        return False
    if name in row.names or name.startswith(row.prefixes):
        return True
    return any(re.fullmatch(pattern, name) is not None for pattern in row.patterns)


def row_matches(row: KindRow, info: PathInfo) -> bool:
    """Apply one row's matcher to a split ticket path."""
    if row.special == SPECIAL_ARCHIVE:
        return any(part in ARCHIVE_FOLDERS for part in info.middle)
    if row.special == SPECIAL_STATE:
        return info.depth == STATE_DEPTH and info.name == info.folder + STATE_SUFFIX
    if row.special == SPECIAL_FOLDER_NAME:
        return info.name == info.folder + MARKDOWN_SUFFIX or name_matches(row, info.match_name)
    return name_matches(row, info.match_name)


def role_by_name(info: PathInfo) -> str:
    """Return the doc_role for an archive file: the first of K3 to K13 that fits, else reference.

    The K2 test is loosened to any name that ends with -state.md.
    """
    if info.name.endswith(STATE_SUFFIX):
        return ROLE_STATE
    for row in ROLE_ROWS:
        if row_matches(row, info):
            return row.doc_role
    return ROLE_REFERENCE


def is_terminal_status(fm: Optional[Dict[str, Any]]) -> bool:
    """True when status is a string that, trimmed and without case, is a terminal value."""
    if fm is None:
        return False
    status = fm.get(STATUS_KEY)
    if not isinstance(status, str):
        return False
    return status.strip().lower() in TERMINAL_STATUSES


def expected_triple(rel: str, fm: Optional[Dict[str, Any]]) -> Optional[Triple]:
    """Return the (catalog_type, doc_role, indexable) a ticket file must carry, or None.

    None means the path has no kind row: outside the tickets folder, at its root, or row K14.
    A terminal status in fm forces indexable false.
    """
    info = split_ticket_path(rel)
    if info is None:
        return None
    for row in KIND_ROWS:
        if row_matches(row, info):
            role = role_by_name(info) if row.row_id == ROW_ARCHIVE else row.doc_role
            indexable = row.indexable and not is_terminal_status(fm)
            return (row.catalog_type, role, indexable)
    return None


def split_block(raw: bytes) -> Optional[bytes]:
    """Return the frontmatter block bytes, or None when line one is not an opening delimiter.

    The opening delimiter must be line one with no BOM. The first later line that is
    exactly the delimiter closes the block. An opening with no closing line is no block.
    """
    if raw.startswith(OPENING_CRLF):
        start = len(OPENING_CRLF)
    elif raw.startswith(OPENING_LF):
        start = len(OPENING_LF)
    else:
        return None
    offset = start
    for line in raw[start:].split(EOL_LF):
        text = line[:-1] if line.endswith(CARRIAGE_RETURN) else line
        if text == DELIMITER:
            return raw[start:offset]
        offset += len(line) + len(EOL_LF)
    return None


def parse_block(block: bytes) -> Optional[Dict[str, Any]]:
    """Parse a block to a mapping, or return None when it cannot be read.

    PyYAML raises more than YAMLError on odd input, so any Exception means unreadable.
    Only the exception class name is logged, because exception text can be file content.
    """
    try:
        loaded = yaml.safe_load(block.decode(ENCODING))
    except Exception as exc:
        logger.debug("frontmatter parse failed: %s", type(exc).__name__)
        return None
    if loaded is None:
        return {}
    return loaded if isinstance(loaded, dict) else None


def facts_from_bytes(raw: bytes) -> FileFacts:
    """Classify the raw bytes of one file by its frontmatter."""
    block = split_block(raw)
    if block is None:
        return FileFacts(KIND_NO_FRONTMATTER)
    fm = parse_block(block)
    if fm is None:
        return FileFacts(KIND_UNPARSEABLE)
    present = sum(1 for name in FIELD_NAMES if name in fm)
    if present == len(FIELD_NAMES):
        return FileFacts(KIND_ALL, fm)
    return FileFacts(KIND_NONE if present == 0 else KIND_SOME, fm)


def read_facts(path: Path) -> FileFacts:
    """Read one file, never following a symlink. A read failure is counted, not raised."""
    if os.path.islink(path):
        return FileFacts(KIND_SYMLINK)
    try:
        raw = path.read_bytes()
    except OSError:
        return FileFacts(KIND_UNREADABLE)
    return facts_from_bytes(raw)


def folder_triple(rel: str, fm: Optional[Dict[str, Any]]) -> Optional[Triple]:
    """Return the (catalog_type, doc_role, indexable) a scope A note must carry, or None.

    None means the path is outside scope A or sits under no folder row. A terminal
    status in fm forces indexable false. doc_type is ignored.
    """
    if not rel.startswith(SCOPE_A_PREFIXES):
        return None
    for row in FOLDER_ROWS:
        if rel.startswith(row.prefixes):
            return (row.catalog_type, row.doc_role, row.indexable and not is_terminal_status(fm))
    return None


def kept_dirs(
    dirnames: List[str],
    prefix: str,
    at_root: bool,
    excluded: Tuple[str, ...] = EXCLUDED_PATH_PREFIXES,
) -> List[str]:
    """Return the sorted child folders worth walking.

    Hidden folders are pruned at the vault root only. Excluded prefixes are pruned.
    """
    kept: List[str] = []
    for name in sorted(dirnames):
        if at_root and name.startswith(HIDDEN_DIR_PREFIX):
            continue
        if (prefix + name + PATH_SEPARATOR).startswith(excluded):
            continue
        kept.append(name)
    return kept


def iter_vault_files(
    root: Path, excluded: Tuple[str, ...] = EXCLUDED_PATH_PREFIXES
) -> Iterator[str]:
    """Yield POSIX root relative paths of the in scope markdown files, folder symlinks unfollowed."""
    root_str = str(root)
    for dirpath, dirnames, filenames in os.walk(root_str, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root_str)
        at_root = rel_dir == os.curdir
        prefix = "" if at_root else PATH_SEPARATOR.join(rel_dir.split(os.sep)) + PATH_SEPARATOR
        dirnames[:] = kept_dirs(dirnames, prefix, at_root, excluded)
        for name in sorted(filenames):
            if name.endswith(MARKDOWN_SUFFIX):
                yield prefix + name


def git_paths(root: Path, args: Sequence[str]) -> FrozenSet[str]:
    """Run one read only git listing in root and return its NUL separated paths.

    Every failure becomes a PreconditionError with a closed code. Git output is never kept.
    Optional locks are off, so git does not refresh the index file as a side effect.
    """
    env = dict(os.environ)
    env[GIT_ENV_OPTIONAL_LOCKS] = GIT_ENV_DISABLED
    try:
        result = subprocess.run(
            [GIT_COMMAND, *args],
            cwd=str(root),
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise PreconditionError(ERROR_GIT_TIMEOUT) from None
    except OSError:
        raise PreconditionError(ERROR_GIT_UNAVAILABLE) from None
    if result.returncode != 0:
        raise PreconditionError(ERROR_GIT_NONZERO_EXIT)
    return frozenset(os.fsdecode(item) for item in result.stdout.split(GIT_NUL) if item)


def load_git_snapshot(root: Path) -> GitSnapshot:
    """Take one git snapshot of the vault: tracked paths and paths that differ from HEAD."""
    return GitSnapshot(
        tracked=git_paths(root, GIT_LIST_TRACKED_ARGS),
        differing=git_paths(root, GIT_LIST_DIFFERING_ARGS),
    )


def is_in_scope(rel: str, facts: FileFacts, git: GitSnapshot) -> bool:
    """True for a tracked, clean, parseable ticket file that has a kind row.

    A file with no frontmatter is parseable: the run creates its block.
    """
    if facts.kind in NO_VALUE_KINDS:
        return False
    if rel not in git.tracked or rel in git.differing:
        return False
    return expected_triple(rel, facts.fm) is not None


def new_counts() -> Dict[str, Any]:
    """Return an empty count block. Every folder and the total share this shape."""
    block: Dict[str, Any] = {
        KEY_FILES: 0, KIND_ALL: 0, KIND_SOME: 0, KIND_NONE: 0, KIND_NO_FRONTMATTER: 0,
        KIND_UNPARSEABLE: 0, KIND_SYMLINK: 0, KIND_UNREADABLE: 0,
        KEY_TERMINAL: 0, KEY_UNKNOWN: 0, KEY_IN_SCOPE_MISSING: 0,
    }
    for key in (KEY_CATALOG_TYPE, KEY_DOC_ROLE, KEY_TRIPLE):
        block[key] = {}
    return block


def text_label(value: Any) -> str:
    """Return a report safe label: the value when it is a short plain word, else a closed code."""
    if not isinstance(value, str):
        return LABEL_NON_STRING
    return value if LABEL_PATTERN.fullmatch(value) is not None else LABEL_UNSAFE


def indexable_label(value: Any) -> str:
    """Return true or false for a boolean indexable value, else a closed code."""
    if value is True:
        return TRUE_LABEL
    if value is False:
        return FALSE_LABEL
    return LABEL_NON_BOOL


def bump(counter: Dict[str, int], label: str) -> None:
    """Add one to a label's count, starting from zero."""
    counter[label] = counter.get(label, 0) + 1


def tally_values(counts: Dict[str, Any], rel: str, fm: Dict[str, Any]) -> None:
    """Count the classifying field values of one parsed file. A missing key adds nothing."""
    if FIELD_CATALOG_TYPE in fm:
        bump(counts[KEY_CATALOG_TYPE], text_label(fm[FIELD_CATALOG_TYPE]))
    if FIELD_DOC_ROLE in fm:
        bump(counts[KEY_DOC_ROLE], text_label(fm[FIELD_DOC_ROLE]))
    if all(name in fm for name in TRIPLE_FIELDS):
        label = TRIPLE_JOINER.join(
            (
                text_label(fm[FIELD_CATALOG_TYPE]),
                text_label(fm[FIELD_DOC_ROLE]),
                indexable_label(fm[FIELD_INDEXABLE]),
            )
        )
        bump(counts[KEY_TRIPLE], label)
    if is_terminal_status(fm) and fm.get(FIELD_INDEXABLE) is True:
        counts[KEY_TERMINAL] += 1
    if rel.startswith(TICKETS_FOLDER + PATH_SEPARATOR):
        if fm.get(FIELD_CATALOG_TYPE) == UNKNOWN_VALUE:
            counts[KEY_UNKNOWN] += 1


def tally(counts: Dict[str, Any], rel: str, facts: FileFacts, missing_in_scope: bool) -> None:
    """Add one file to a count block."""
    counts[KEY_FILES] += 1
    counts[facts.kind] += 1
    if missing_in_scope:
        counts[KEY_IN_SCOPE_MISSING] += 1
    if facts.fm is not None:
        tally_values(counts, rel, facts.fm)


def folder_of(rel: str) -> str:
    """Return the top level folder of a vault relative path, or the root label."""
    head, separator, _ = rel.partition(PATH_SEPARATOR)
    return head if separator else ROOT_FOLDER_LABEL


def scan_vault(root: Path) -> Dict[str, Any]:
    """Count every in scope markdown file in the vault. Nothing is written.

    The git snapshot is taken first. Unparseable frontmatter is counted, never raised.
    """
    git = load_git_snapshot(root)
    result = new_counts()
    folders: Dict[str, Dict[str, Any]] = {}
    for rel in iter_vault_files(root):
        facts = read_facts(root / rel)
        missing = facts.kind != KIND_ALL and is_in_scope(rel, facts, git)
        tally(result, rel, facts, missing)
        tally(folders.setdefault(folder_of(rel), new_counts()), rel, facts, missing)
    result[KEY_BY_FOLDER] = folders
    result[KEY_EXCLUSIONS] = list(EXCLUDED_PATH_PREFIXES)
    logger.info(
        "scanned=%d all_four=%d some=%d none=%d no_frontmatter=%d unparseable=%d",
        result[KEY_FILES], result[KIND_ALL], result[KIND_SOME], result[KIND_NONE],
        result[KIND_NO_FRONTMATTER], result[KIND_UNPARSEABLE],
    )
    return result


def load_report(path: Path) -> Any:
    """Return the parsed JSON of one run report, or raise PreconditionError with a closed code."""
    if not path.is_file():
        raise PreconditionError(ERROR_REPORT_NOT_FOUND)
    try:
        text = path.read_text(encoding=ENCODING)
    except (OSError, UnicodeDecodeError):
        raise PreconditionError(ERROR_REPORT_UNREADABLE) from None
    try:
        return json.loads(text)
    except ValueError:
        raise PreconditionError(ERROR_REPORT_UNPARSEABLE) from None


def report_writes(report: Any) -> List[Any]:
    """Return the writes list of a parsed run report, or raise PreconditionError."""
    writes = report.get(REPORT_WRITES_KEY) if isinstance(report, dict) else None
    if not isinstance(writes, list):
        raise PreconditionError(ERROR_REPORT_SHAPE_INVALID)
    return writes


def load_report_writes(path: Path) -> List[Any]:
    """Return the writes list of one run report, or raise PreconditionError with a closed code."""
    return report_writes(load_report(path))


def is_nonticket_report(report: Any) -> bool:
    """True when the report names Run 4 by exact integer."""
    named = report.get(REPORT_RUN_KEY) if isinstance(report, dict) else None
    return type(named) is int and named == RUN_NONTICKET


def usable_rel_path(value: Any) -> Optional[str]:
    """Return a report path that is a plain relative POSIX path inside the vault, else None."""
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        return None
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        return None
    return value


def triple_equals(fm: Dict[str, Any], expected: Triple) -> bool:
    """Compare the file's three classifying values with the expected ones by type and value."""
    for name, wanted in zip(TRIPLE_FIELDS, expected):
        if type(fm[name]) is not type(wanted) or fm[name] != wanted:
            return False
    return True


def entry_mismatch(root: Path, rel: str, nonticket: bool = False) -> Optional[str]:
    """Return the closed code for the first way a written file fails its row, else None.

    nonticket selects the folder rows (a Run 4 report) instead of the ticket kind rows.
    """
    facts = read_facts(root / rel)
    fm = facts.fm
    if fm is None:
        return NO_VALUE_CODES.get(facts.kind, CODE_FILE_UNREADABLE)
    expected = folder_triple(rel, fm) if nonticket else expected_triple(rel, fm)
    if expected is None:
        return CODE_NO_KIND_ROW
    if any(name not in fm for name in FIELD_NAMES):
        return CODE_FIELD_MISSING
    if fm[FIELD_INDEXED] is not None:
        return CODE_INDEXED_NOT_NULL
    return None if triple_equals(fm, expected) else CODE_TRIPLE_DIFFERS


def entry_class(entry: Any) -> Optional[str]:
    """Return the class string of one report entry, or None when the entry has none."""
    if not isinstance(entry, dict):
        return None
    value = entry.get(ENTRY_CLASS_KEY)
    return value if isinstance(value, str) else None


def judge_entry(
    root: Path, entry: Any, nonticket: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """Check one add, create, or rewrite entry. Return (mismatch code or None, usable path or None)."""
    rel = usable_rel_path(entry.get(ENTRY_PATH_KEY)) if isinstance(entry, dict) else None
    if entry_class(entry) not in CHECKED_CLASSES:
        return CODE_MALFORMED_ENTRY, rel
    if rel is None:
        return CODE_PATH_UNSAFE, None
    return entry_mismatch(root, rel, nonticket), rel


def count_scope_a_missing(root: Path) -> int:
    """Count parseable scope A notes (or notes with no block) that miss at least one field.

    The walk skips hidden folders, memory, and sql. Git state is not read, so the count
    stays right after an apply, when the tree is dirty. Unparseable, symlinked, and
    unreadable files are not counted: the run cannot label them.
    """
    missing = 0
    for rel in iter_vault_files(root, RUN4_EXCLUDED_PATH_PREFIXES):
        if not rel.startswith(SCOPE_A_PREFIXES):
            continue
        facts = read_facts(root / rel)
        if facts.kind in NO_VALUE_KINDS or facts.kind == KIND_ALL:
            continue
        missing += 1
    return missing


def check_writes(root: Path, report_paths: Sequence[Path]) -> Dict[str, Any]:
    """Prove each add, create, and rewrite entry of the reports against the vault.

    Flip entries are counted and skipped. Every report is loaded before any file is
    read, so a bad report ends the check before any result exists.
    """
    reports = [load_report(path) for path in report_paths]
    tagged = [
        (item, is_nonticket_report(report))
        for report in reports for item in report_writes(report)
    ]
    result: Dict[str, Any] = {
        "reports": len(report_paths), "checked": 0, "mismatches": 0, "flips_skipped": 0,
        "mismatch_codes": {}, "mismatch_paths": [],
    }
    for entry, nonticket in tagged:
        if entry_class(entry) == CLASS_FLIP:
            result["flips_skipped"] += 1
            continue
        result["checked"] += 1
        code, rel = judge_entry(root, entry, nonticket)
        if code is not None:
            result["mismatches"] += 1
            bump(result["mismatch_codes"], code)
            if rel is not None:
                result["mismatch_paths"].append(rel)
    result["mismatch_paths"].sort()
    if any(is_nonticket_report(report) for report in reports):
        result[KEY_SCOPE_A_MISSING] = count_scope_a_missing(root)
    logger.info(
        "checked=%d mismatches=%d flips_skipped=%d",
        result["checked"], result["mismatches"], result["flips_skipped"],
    )
    return result


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """Parse the command line. The vault root is required, so no run falls back to a default."""
    parser = argparse.ArgumentParser(
        description="Read only census of the retrieval fields in a vault. Prints JSON.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--vault-root", type=Path, required=True, help="Vault folder to scan.",
    )
    parser.add_argument(
        "--check-writes", type=Path, nargs="+", default=None, metavar="REPORT",
        help="Check the add, create, and rewrite entries of these run reports "
        "against the vault instead of scanning it.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the census from the command line. Returns 0, or 2 when a precondition failed.

    The JSON result goes to stdout. A failure logs one closed code and prints no result.
    """
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=LOG_FORMAT)
    args = parse_args(argv)
    try:
        if not args.vault_root.is_dir():
            raise PreconditionError(ERROR_VAULT_ROOT_NOT_A_FOLDER)
        if args.check_writes is not None:
            result = check_writes(args.vault_root, args.check_writes)
        else:
            result = scan_vault(args.vault_root)
    except PreconditionError as exc:
        logger.error("fatal precondition: %s", exc)
        return EXIT_PRECONDITION
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=JSON_INDENT) + "\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
