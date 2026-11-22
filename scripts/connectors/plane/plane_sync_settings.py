# Module:      plane_sync_settings.py
# Description: Reads and checks the Plane sync settings file into frozen settings objects.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       workspace, project and status mappings; the address and key never live here
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SETTINGS_FILE_NAME = "plane-sync.json"
PATHS_ENV = "TOLLGATE_PATHS"
PREFIX_ENV = "TOLLGATE_TICKET_PREFIX"
DEFAULT_EXTERNAL_SOURCE = "tollgate"
DEFAULT_BLOCKED_WORDS = ("QA_BLOCKED",)
DEFAULT_SECRET_PATTERNS = {
    "private_key_block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "named_secret_assignment": (
        r"(?i)(?<![A-Za-z0-9_\-])[A-Za-z0-9_\-]*(api[_-]?key|secret|token|passw(or)?d|pwd)"
        r"[A-Za-z0-9_\-]*[\"']?\s*[:=]\s*[\"']?\S{8,}"
    ),
    "url_credentials": r"://[^/\s:@]+:[^@\s]+@",
    "bearer_token": r"\bBearer\s+\S{20,}",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "github_token": r"\bgh[pousr]_[A-Za-z0-9]{30,}",
    "slack_token": r"\bxox[baprs]-[A-Za-z0-9-]{10,}",
    "plane_api_key": r"\bplane_api_[A-Za-z0-9]{20,}",
    "json_quoted_secret": (
        r"(?i)\"(?:api_?key|api_?token|access_?token|client_?secret|token|secret)\"\s*:\s*"
        r"\"[A-Za-z0-9!@#$%^&*()+\-_./=]{20,}\""
    ),
    "long_mixed_token": (
        r"\b(?=[A-Za-z0-9_\-]*[A-Z])(?=[A-Za-z0-9_\-]*[a-z])(?=[A-Za-z0-9_\-]*\d)"
        r"(?!(?:[A-Za-z0-9_]*-){3})[A-Za-z0-9_\-]{32,}\b"
    ),
}
DEFAULT_NUMBERS = {
    "min_seconds_between_calls": 1.2,
    "http_timeout_seconds": 30.0,
}
DEFAULT_INTEGERS = {"page_size": 100, "comment_max_chars": 15000}
REQUIRED_STRING_KEYS = ("workspace_slug", "new_ticket_board_status")


class PlaneSyncConfigError(RuntimeError):
    """Raised when the settings file is missing, unreadable, or has a bad key. The message is the key name only."""


class PlaneAddressError(PlaneSyncConfigError):
    """Raised when the connector address is not an https address."""


@dataclass(frozen=True)
class PrefixRow:
    project_key: str
    ticket_pattern: str
    number_width: int


@dataclass(frozen=True)
class PlaneSyncSettings:
    workspace_slug: str
    external_source_name: str
    min_seconds_between_calls: float
    http_timeout_seconds: float
    page_size: int
    comment_max_chars: int
    new_ticket_board_status: str
    prefix_table: Mapping[str, PrefixRow]
    status_map: Mapping[str, str]
    blocked_words: tuple[str, ...]
    secret_patterns: Mapping[str, str]
    template_path: str | None = None


def default_settings_path(env: Mapping[str, str] | None = None) -> Path:
    """The settings file sits next to the paths file named by TOLLGATE_PATHS."""
    source = os.environ if env is None else env
    paths_file = source.get(PATHS_ENV, "").strip()
    if not paths_file:
        raise PlaneSyncConfigError(PATHS_ENV)
    return Path(os.path.expanduser(paths_file)).parent / SETTINGS_FILE_NAME


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _string_map(section: Mapping[str, Any], key: str) -> dict[str, str]:
    value = section.get(key)
    if not isinstance(value, dict):
        raise PlaneSyncConfigError(key)
    for item_key, item_value in value.items():
        if not isinstance(item_key, str) or not isinstance(item_value, str):
            raise PlaneSyncConfigError(key)
    return dict(value)


def _blocked_words(section: Mapping[str, Any]) -> tuple[str, ...]:
    value = section.get("blocked_words", list(DEFAULT_BLOCKED_WORDS))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PlaneSyncConfigError("blocked_words")
    return tuple(value)


def _prefix_row(prefix: str, row: Any) -> PrefixRow:
    if not isinstance(row, dict):
        raise PlaneSyncConfigError("prefix_table")
    project_key = row.get("project_key", prefix)
    width = row.get("number_width", 1)
    if not isinstance(project_key, str) or not _is_integer(width):
        raise PlaneSyncConfigError("prefix_table")
    pattern = row.get("ticket_pattern", "^" + re.escape(prefix) + r"-(\d+)$")
    if not isinstance(pattern, str):
        raise PlaneSyncConfigError("ticket_pattern")
    return PrefixRow(project_key=project_key, ticket_pattern=pattern, number_width=width)


def _prefix_table(section: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, PrefixRow]:
    raw = section.get("prefix_table")
    if raw is None:
        default_prefix = env.get(PREFIX_ENV, "").strip()
        if not default_prefix:
            raise PlaneSyncConfigError("prefix_table")
        raw = {default_prefix: {}}
    if not isinstance(raw, dict) or not raw:
        raise PlaneSyncConfigError("prefix_table")
    return {str(prefix): _prefix_row(str(prefix), row) for prefix, row in raw.items()}


def _numbers(section: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, default in DEFAULT_NUMBERS.items():
        value = section.get(key, default)
        if not _is_number(value):
            raise PlaneSyncConfigError(key)
        values[key] = float(value)
    for key, default in DEFAULT_INTEGERS.items():
        value = section.get(key, default)
        if not _is_integer(value):
            raise PlaneSyncConfigError(key)
        values[key] = value
    return values


def _read_section(config_path: Path) -> Mapping[str, Any]:
    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PlaneSyncConfigError(config_path.name) from error
    if not isinstance(parsed, dict):
        raise PlaneSyncConfigError(config_path.name)
    return parsed


def _optional_text(section: Mapping[str, Any], key: str, default: str | None) -> str | None:
    value = section.get(key, default)
    if value is not None and not isinstance(value, str):
        raise PlaneSyncConfigError(key)
    return value


def load_settings(
    config_path: Path | None = None, env: Mapping[str, str] | None = None
) -> PlaneSyncSettings:
    """Load settings from the settings file. Raises PlaneSyncConfigError naming the bad key."""
    source = os.environ if env is None else env
    section = _read_section(config_path if config_path is not None else default_settings_path(source))
    for key in REQUIRED_STRING_KEYS:
        if not isinstance(section.get(key), str) or not section[key]:
            raise PlaneSyncConfigError(key)
    patterns = _string_map(section, "secret_patterns") if "secret_patterns" in section else dict(DEFAULT_SECRET_PATTERNS)
    return PlaneSyncSettings(
        workspace_slug=section["workspace_slug"],
        external_source_name=_optional_text(section, "external_source_name", DEFAULT_EXTERNAL_SOURCE) or "",
        new_ticket_board_status=section["new_ticket_board_status"],
        prefix_table=_prefix_table(section, source),
        status_map=_string_map(section, "status_map"),
        blocked_words=_blocked_words(section),
        secret_patterns=patterns,
        template_path=_optional_text(section, "template_path", None),
        **_numbers(section),
    )
