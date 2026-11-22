# Module:      plane_sync_test_support.py
# Description: Shared helpers for the plane connector tests: settings, a stub-backed http object, temp folders, client.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1 and nowhere else
# Version:     1.0
# ChangeLog:
#   - First version.

from __future__ import annotations

import contextlib
import dataclasses
import io
import os
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCRIPTS = ROOT / "scripts"
for entry in (str(HERE), str(SCRIPTS), str(ROOT / "tests" / "harness")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from connector_helpers import FakeSecretStore  # noqa: E402
from connectors import connect, registry  # noqa: E402
from connectors.plane import cli  # noqa: E402
from connectors.plane.plane_sync_settings import PlaneSyncSettings, PrefixRow, load_settings  # noqa: E402
from connectors.plane.plane_ticket_syncer import run_sync  # noqa: E402
from connectors.plane.plane_work_item_client import PlaneWorkItemClient  # noqa: E402
from throwaway_home import throwaway_home  # noqa: E402
from plane_stub_server import WORKSPACE, PlaneStubServer, StubItem  # noqa: E402

EXAMPLE_SETTINGS = SCRIPTS / "connectors" / "plane" / "plane_sync_settings.example.json"
TEMPLATE = SCRIPTS / "connectors" / "plane" / "plane_ticket_state_template.md"
LOCAL_HOST = "127.0.0.1"


def fake_key() -> str:
    """A fake key built at run time. It has upper case, lower case and digits, so the scanner treats it as a secret."""
    return "Fk9" + uuid.uuid4().hex + "Zq"


FAKE_TOKEN = fake_key()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class StubHttp:
    """An http object like the framework one, but it only talks to 127.0.0.1 and never follows a redirect."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)

    def request(self, method: str, url: str, headers: dict | None = None, data: object = None,
                timeout: float = 30) -> dict:
        if urlparse(url).hostname != LOCAL_HOST:
            raise AssertionError("tests may only call " + LOCAL_HOST)
        body = data.encode() if isinstance(data, str) else data
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with self._opener.open(req, timeout=timeout) as reply:
                return {"status": reply.status, "body": reply.read().decode()}
        except urllib.error.HTTPError as error:
            error.close()
            raise


def make_settings(prefix_width: int = 1) -> PlaneSyncSettings:
    """The shipped example settings, with a workspace that matches the stub and no pacing delay."""
    base = load_settings(EXAMPLE_SETTINGS, {})
    table = {"T": PrefixRow("T", r"^T-(\d+)$", prefix_width)}
    return dataclasses.replace(base, workspace_slug=WORKSPACE, min_seconds_between_calls=0.0, prefix_table=table)


def make_client(address: str, settings: PlaneSyncSettings, key: str = FAKE_TOKEN,
                page_size: int = 100) -> PlaneWorkItemClient:
    return PlaneWorkItemClient(
        address, settings.workspace_slug, key, StubHttp(),
        external_source=settings.external_source_name,
        min_seconds_between_calls=0.0, timeout_seconds=5.0, page_size=page_size,
        allow_insecure_http=True,
    )


def read_template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


class StubTestCase(unittest.TestCase):
    """Starts a stub, makes a temp tickets folder with tickets up to a given number, and cleans up."""

    local_highest = 5

    def setUp(self) -> None:
        self.stub = PlaneStubServer().start()
        self.addCleanup(self.stub.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tickets = Path(temp.name) / "tickets"
        self.state = Path(temp.name) / "state"
        for number in range(1, self.local_highest + 1):
            (self.tickets / f"T-{number}").mkdir(parents=True)
            self.stub.state.items.append(StubItem(f"wi-{number}", number, f"old {number}", f"T-{number}"))
        self.settings = make_settings()
        self.client = make_client(self.stub.base_url, self.settings)
        self.lines: list[str] = []

    def create_args(self, title: str = "A new ticket") -> dict[str, str]:
        return dict(prefix="T", title=title, priority="P2", scope="scripts", repo="demo-repo",
                    work_type="feature", today="2026-01-02")

    def folder_names(self) -> list[str]:
        return sorted(p.name for p in self.tickets.iterdir())


SYNC_TICKET = "T-5"
STATE_BODY = "## Current state\nWorking on the sync step.\n\n## Scope\nOne ticket.\n"


def state_text(title: str = "Sync ticket", status: str = "SPEC_APPROVED", body: str = STATE_BODY) -> str:
    return f"---\ntitle: {title}\nstatus: {status}\n---\n{body}"


class SyncTestCase(StubTestCase):
    """A stub card for T-5 plus a ticket folder for it; helpers to write files, run sync and count calls."""

    def setUp(self) -> None:
        super().setUp()
        self.folder = self.tickets / SYNC_TICKET
        self.write_state()

    def write_state(self, **kwargs: str) -> None:
        (self.folder / f"{SYNC_TICKET}-state.md").write_text(state_text(**kwargs), encoding="utf-8")

    def write_file(self, name: str, text: str) -> Path:
        path = self.folder / name
        path.write_text(text, encoding="utf-8")
        return path

    def append_session(self, text: str, name: str = f"{SYNC_TICKET}-session-2026-01-02.md") -> None:
        path = self.folder / name
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_text(old + text, encoding="utf-8")

    def sync(self, extras: str | None = None, from_start: bool = False,
             settings: PlaneSyncSettings | None = None) -> int:
        self.lines = []
        return run_sync(
            settings or self.settings, self.client, self.tickets, self.state, ticket_id=SYNC_TICKET,
            extras=extras, emit=self.lines.append, from_start=from_start,
        )

    def patches(self, key: str | None = None) -> list[dict]:
        calls = self.stub.calls_matching("PATCH", "/work-items/wi-5/")
        return [c.body for c in calls if key is None or key in c.body]

    def comments(self) -> list[dict]:
        return self.stub.state.comments

    def card(self) -> object:
        return next(i for i in self.stub.state.items if i.number == 5)


class CliCase(SyncTestCase):
    """Runs the command line against the stub with a throwaway home, a fake secret store and the connector on."""

    def setUp(self) -> None:
        super().setUp()
        manager = throwaway_home()
        self.home, self.env = manager.__enter__()
        self.addCleanup(lambda: manager.__exit__(None, None, None))
        self.env["TOLLGATE_NONINTERACTIVE"] = "1"
        self.secrets = FakeSecretStore()
        registry.set_store(self.secrets)
        registry.set_http_factory(StubHttp)
        self.addCleanup(registry.set_store, None)
        self.addCleanup(registry.set_http_factory, None)
        self.turn_on()

    def turn_on(self, key: str = FAKE_TOKEN) -> None:
        os.environ["TG_TEST_KEY"] = key
        try:
            host = urlparse(self.stub.base_url)
            with contextlib.redirect_stdout(io.StringIO()), \
                    unittest.mock.patch.object(registry, "interactive", return_value=True):
                code = connect.main(["on", "plane", "--address", self.stub.base_url,
                                     "--allow-host", "%s:%d" % (host.hostname, host.port),
                                     "--key-from-env", "TG_TEST_KEY"], env=self.env)
        finally:
            del os.environ["TG_TEST_KEY"]
        self.assertEqual(code, 0)

    def turn_off(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(connect.main(["off", "plane"], env=self.env), 0)

    def run_cli(self, argv: list[str], **extra: object) -> int:
        self.lines = []
        options = dict(env=self.env, settings=self.settings, tickets_root=self.tickets,
                       state_root=self.state, out=self.lines.append, allow_insecure_http=True)
        options.update(extra)
        return cli.main(argv, **options)  # type: ignore[arg-type]
