# Module:      plane_work_item_client.py
# Description: Seven paced Plane API calls for projects, states, work items and comments. No retry anywhere. All HTTP goes through the http object the framework hands in.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       plane sync HTTP client; errors carry method, path, status and reason only
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode

from connectors.plane.plane_sync_settings import PlaneAddressError

logger = logging.getLogger(__name__)

API_PREFIX = "api/v1/workspaces"
TOKEN_HEADER = "X-API-Key"
HTTP_OK_MIN = 200
HTTP_OK_MAX = 204
JSON_HEADERS = {"Content-Type": "application/json"}
WORK_ITEM_LIST_FIELDS = "id,sequence_id,name,state,external_id"
NO_STATUS_TEXT = "none"
HTTPS_PREFIX = "https://"


@dataclass(frozen=True)
class PlaneProjectRecord:
    project_id: str
    project_key: str


@dataclass(frozen=True)
class PlaneWorkItemRecord:
    work_item_id: str
    number: int
    name: str
    state_id: str | None
    external_id: str | None
    description_html: str | None


class PlaneApiError(RuntimeError):
    """A Plane call failed. The message holds method, path, status and reason only."""

    def __init__(self, method: str, path: str, status: int | None, reason: str) -> None:
        self.method = method
        self.path = path
        self.status = status
        status_text = NO_STATUS_TEXT if status is None else str(status)
        super().__init__(f"{method} {path} failed: status {status_text} ({reason})")


def _optional_text(reply: Mapping[str, Any], key: str, method: str, path: str) -> str | None:
    value = reply.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PlaneApiError(method, path, None, f"field {key} is not text")
    return value


def _required_text(reply: Mapping[str, Any], key: str, method: str, path: str) -> str:
    value = reply.get(key)
    if not isinstance(value, str):
        raise PlaneApiError(method, path, None, f"field {key} is missing")
    return value


def _work_item_from_reply(reply: Any, method: str, path: str) -> PlaneWorkItemRecord:
    if not isinstance(reply, dict):
        raise PlaneApiError(method, path, None, "reply is not an object")
    number = reply.get("sequence_id")
    if not isinstance(number, int) or isinstance(number, bool):
        raise PlaneApiError(method, path, None, "field sequence_id is missing")
    return PlaneWorkItemRecord(
        work_item_id=_required_text(reply, "id", method, path),
        number=number,
        name=_required_text(reply, "name", method, path),
        state_id=_optional_text(reply, "state", method, path),
        external_id=_optional_text(reply, "external_id", method, path),
        description_html=_optional_text(reply, "description_html", method, path),
    )


def _status_of(error: Exception) -> int | None:
    code = getattr(error, "code", None)
    return code if isinstance(code, int) and not isinstance(code, bool) else None


def _decode(raw: Any, method: str, path: str, status: int) -> Any:
    """Turn the reply body into JSON data. The http object may hand back text, bytes or data."""
    if raw is None or raw == "" or raw == b"":
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode("utf-8", errors="replace")
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        raise PlaneApiError(method, path, status, "reply is not valid JSON") from None


class PlaneWorkItemClient:
    """Talks to Plane through the http object it is given. Waits between calls, never retries."""

    def __init__(
        self,
        address: str,
        workspace_slug: str,
        api_key: str,
        http: Any,
        *,
        external_source: str,
        min_seconds_between_calls: float,
        timeout_seconds: float,
        page_size: int,
        allow_insecure_http: bool = False,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not allow_insecure_http and not address.startswith(HTTPS_PREFIX):
            raise PlaneAddressError("the connector address must start with https://")
        self._root = f"{address.rstrip('/')}/{API_PREFIX}/{quote(workspace_slug, safe='')}/"
        self._external_source = external_source
        self._min_seconds = min_seconds_between_calls
        self._timeout = timeout_seconds
        self._page_size = page_size
        self._sleep = sleep
        self._clock = clock
        self._last_start: float | None = None
        self._http = http
        self._headers = {TOKEN_HEADER: api_key, **JSON_HEADERS}

    def _pace(self) -> None:
        if self._last_start is not None:
            wait = self._min_seconds - (self._clock() - self._last_start)
            if wait > 0:
                self._sleep(wait)
        self._last_start = self._clock()

    def _send(
        self,
        method: str,
        path: str,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Any:
        self._pace()
        url = self._root + path + (("?" + urlencode(dict(query))) if query else "")
        data = json.dumps(dict(body)) if body is not None else None
        try:
            reply = self._http.request(
                method, url, headers=dict(self._headers), data=data, timeout=self._timeout
            )
        except Exception as error:
            status = _status_of(error)
            reason = "unexpected status" if status is not None else type(error).__name__
            raise PlaneApiError(method, path, status, reason) from None
        status = reply.get("status") if isinstance(reply, dict) else None
        logger.debug("plane call %s %s status %s", method, path, status)
        if not isinstance(status, int) or not HTTP_OK_MIN <= status <= HTTP_OK_MAX:
            raise PlaneApiError(method, path, status if isinstance(status, int) else None, "unexpected status")
        return _decode(reply.get("body"), method, path, status)

    def _list_all(self, path: str, extra_query: Mapping[str, str] | None = None) -> list[Any]:
        rows: list[Any] = []
        cursor: str | None = None
        while True:
            query = {"per_page": str(self._page_size), **(extra_query or {})}
            if cursor is not None:
                query["cursor"] = cursor
            reply = self._send("GET", path, query)
            if not isinstance(reply, dict) or not isinstance(reply.get("results"), list):
                raise PlaneApiError("GET", path, None, "field results is missing")
            rows.extend(reply["results"])
            if reply.get("next_page_results") is not True:
                return rows
            next_cursor = reply.get("next_cursor")
            if not isinstance(next_cursor, str) or next_cursor == cursor:
                raise PlaneApiError("GET", path, None, "cursor did not advance")
            cursor = next_cursor

    def list_projects(self) -> list[PlaneProjectRecord]:
        path = "projects/"
        records = []
        for row in self._list_all(path):
            if not isinstance(row, dict):
                raise PlaneApiError("GET", path, None, "row is not an object")
            records.append(PlaneProjectRecord(
                project_id=_required_text(row, "id", "GET", path),
                project_key=_required_text(row, "identifier", "GET", path),
            ))
        return records

    def list_state_ids(self, project_id: str) -> dict[str, str]:
        path = f"projects/{quote(project_id, safe='')}/states/"
        states: dict[str, str] = {}
        for row in self._list_all(path):
            if not isinstance(row, dict):
                raise PlaneApiError("GET", path, None, "row is not an object")
            states[_required_text(row, "name", "GET", path)] = _required_text(row, "id", "GET", path)
        return states

    def list_work_items(self, project_id: str) -> list[PlaneWorkItemRecord]:
        path = f"projects/{quote(project_id, safe='')}/work-items/"
        rows = self._list_all(path, {"fields": WORK_ITEM_LIST_FIELDS})
        return [_work_item_from_reply(row, "GET", path) for row in rows]

    def get_work_item(self, project_id: str, work_item_id: str) -> PlaneWorkItemRecord:
        path = f"projects/{quote(project_id, safe='')}/work-items/{quote(work_item_id, safe='')}/"
        return _work_item_from_reply(self._send("GET", path), "GET", path)

    def create_work_item(self, project_id: str, *, name: str, state_id: str) -> PlaneWorkItemRecord:
        path = f"projects/{quote(project_id, safe='')}/work-items/"
        reply = self._send("POST", path, None, {"name": name, "state": state_id})
        return _work_item_from_reply(reply, "POST", path)

    def update_work_item(self, project_id: str, work_item_id: str, fields: Mapping[str, str]) -> None:
        path = f"projects/{quote(project_id, safe='')}/work-items/{quote(work_item_id, safe='')}/"
        self._send("PATCH", path, None, dict(fields))

    def post_comment(self, project_id: str, work_item_id: str, comment_html: str, external_id: str) -> str:
        path = (
            f"projects/{quote(project_id, safe='')}/work-items/"
            f"{quote(work_item_id, safe='')}/comments/"
        )
        body = {
            "comment_html": comment_html,
            "external_id": external_id,
            "external_source": self._external_source,
        }
        reply = self._send("POST", path, None, body)
        if not isinstance(reply, dict):
            raise PlaneApiError("POST", path, None, "reply is not an object")
        return _required_text(reply, "id", "POST", path)
