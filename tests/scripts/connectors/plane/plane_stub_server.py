# Module:      plane_stub_server.py
# Description: Local stub of the Plane API on 127.0.0.1 for the plane connector tests. Standard library only.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; binds 127.0.0.1, records every call, can fail or redirect chosen calls
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

WORKSPACE = "ws-test"
DEFAULT_REQUEST_CAP = 2000
PROJECT_ID = "proj-t"
STATE_IDS = {
    "Backlog": "st-backlog", "Ready": "st-ready", "Done": "st-done", "Review": "st-review",
    "Waiting": "st-waiting", "In progress": "st-progress", "Parked": "st-parked", "Cancelled": "st-cancelled",
}


@dataclass
class StubCall:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: Any


@dataclass
class FailRule:
    method: str
    path_suffix: str
    status: int
    location: str | None = None
    remaining: int = 1000000


@dataclass
class StubItem:
    work_item_id: str
    number: int
    name: str
    external_id: str | None = None
    description_html: str | None = None
    state_id: str = "st-backlog"


@dataclass
class StubState:
    items: list[StubItem] = field(default_factory=list)
    calls: list[StubCall] = field(default_factory=list)
    fail_rules: list[FailRule] = field(default_factory=list)
    stuck_cursor: bool = False
    on_create: Callable[[], None] | None = None
    comments: list[dict[str, Any]] = field(default_factory=list)
    request_cap: int = DEFAULT_REQUEST_CAP


def _item_json(item: StubItem) -> dict[str, Any]:
    return {
        "id": item.work_item_id, "sequence_id": item.number, "name": item.name,
        "state": item.state_id, "external_id": item.external_id,
        "description_html": item.description_html,
    }


class _Handler(BaseHTTPRequestHandler):
    server: "PlaneStubServer"

    def log_message(self, format: str, *args: Any) -> None:
        return None

    def _reply(self, status: int, payload: Any = None, location: str | None = None) -> None:
        data = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self) -> None:
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw) if raw else None
        state = self.server.state
        call = StubCall(self.command, url.path, parse_qs(url.query), dict(self.headers), body)
        state.calls.append(call)
        if len(state.calls) > state.request_cap:
            self._reply(500, {"detail": "request cap reached"})
            return
        for rule in state.fail_rules:
            if rule.method == self.command and url.path.endswith(rule.path_suffix) and rule.remaining > 0:
                rule.remaining -= 1
                self._reply(rule.status, {"detail": "stub failure"}, rule.location)
                return
        self._route(call)

    def _route(self, call: StubCall) -> None:
        base = f"/api/v1/workspaces/{WORKSPACE}/"
        rest = call.path[len(base):] if call.path.startswith(base) else None
        if rest is None:
            self._reply(404, {"detail": "not found"})
        elif rest == "projects/":
            self._reply(200, self._page(call, [{"id": PROJECT_ID, "identifier": "T"}]))
        elif rest == f"projects/{PROJECT_ID}/states/":
            rows = [{"id": sid, "name": name} for name, sid in STATE_IDS.items()]
            self._reply(200, self._page(call, rows))
        elif rest == f"projects/{PROJECT_ID}/work-items/":
            self._work_items(call)
        elif rest.startswith(f"projects/{PROJECT_ID}/work-items/"):
            self._single_item(call, rest.split("/"))
        else:
            self._reply(404, {"detail": "not found"})

    def _page(self, call: StubCall, rows: list[Any]) -> dict[str, Any]:
        per_page = int(call.query.get("per_page", ["100"])[0])
        start = int(call.query.get("cursor", ["0"])[0])
        chunk = rows[start:start + per_page]
        more = start + per_page < len(rows)
        cursor = str(start) if self.server.state.stuck_cursor else str(start + per_page)
        return {
            "results": chunk,
            "next_page_results": more or self.server.state.stuck_cursor,
            "next_cursor": cursor,
        }

    def _work_items(self, call: StubCall) -> None:
        state = self.server.state
        if call.method == "GET":
            self._reply(200, self._page(call, [_item_json(i) for i in state.items]))
            return
        if state.on_create is not None:
            state.on_create()
        number = max((i.number for i in state.items), default=0) + 1
        item = StubItem(f"wi-{number}", number, call.body["name"], None, None, call.body["state"])
        state.items.append(item)
        self._reply(201, _item_json(item))

    def _single_item(self, call: StubCall, parts: list[str]) -> None:
        state = self.server.state
        item = next((i for i in state.items if i.work_item_id == parts[3]), None)
        if item is None:
            self._reply(404, {"detail": "not found"})
        elif len(parts) > 5 and parts[4] == "comments":
            state.comments.append({**call.body, "work_item_id": item.work_item_id})
            self._reply(201, {"id": f"cm-{len(state.comments)}"})
        elif call.method == "PATCH":
            item.external_id = call.body.get("external_id", item.external_id)
            item.description_html = call.body.get("description_html", item.description_html)
            item.name = call.body.get("name", item.name)
            item.state_id = call.body.get("state", item.state_id)
            self._reply(200, _item_json(item))
        else:
            self._reply(200, _item_json(item))

    do_GET = _handle
    do_POST = _handle
    do_PATCH = _handle


class PlaneStubServer(ThreadingHTTPServer):
    """A local HTTP server that behaves like the parts of Plane the client uses."""

    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.state = StubState()
        self._thread = threading.Thread(target=lambda: self.serve_forever(poll_interval=0.02), daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def start(self) -> "PlaneStubServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self.shutdown()
        self.server_close()

    def calls_matching(self, method: str, path_suffix: str) -> list[StubCall]:
        return [c for c in self.state.calls if c.method == method and c.path.endswith(path_suffix)]
