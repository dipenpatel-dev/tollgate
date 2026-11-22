# Module:      test_plane_connector.py
# Description: Connector tests CON-01 to CON-04 for plane: not set up, first use, restart, off.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import contextlib
import importlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

from connector_helpers import FakeSecretStore, MockClient, assert_no_network
from connectors import connect, registry
from connectors.plane import cli
from plane_stub_server import WORKSPACE
from plane_sync_test_support import (
    ROOT, SCRIPTS, SYNC_TICKET, StubHttp, SyncTestCase, fake_key,
)
from throwaway_home import throwaway_home

ADDRESS = "https://plane.example.invalid"
WORK_ITEM_FIELDS = "id,sequence_id,name,state,external_id"


class ConnectorCase(SyncTestCase):
    """A throwaway home, a fake secret store and a mock http object. The connector starts off."""

    def setUp(self) -> None:
        super().setUp()
        manager = throwaway_home()
        self.home, self.env = manager.__enter__()
        self.addCleanup(lambda: manager.__exit__(None, None, None))
        self.env["TOLLGATE_NONINTERACTIVE"] = "1"
        self.secrets = FakeSecretStore()
        self.mock = MockClient()
        registry.set_store(self.secrets)
        registry.set_http_factory(lambda: self.mock)
        self.addCleanup(registry.set_store, None)
        self.addCleanup(registry.set_http_factory, None)
        self.secret = fake_key()

    def run_plane(self, argv: list[str]) -> tuple[int, str]:
        self.lines = []
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(argv, env=self.env, settings=self.settings, tickets_root=self.tickets,
                            state_root=self.state, out=self.lines.append)
        return code, err.getvalue()

    def turn_on(self, address: str = ADDRESS) -> int:
        os.environ["TG_TEST_KEY"] = self.secret
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return connect.main(["on", "plane", "--address", address, "--key-from-env", "TG_TEST_KEY"],
                                    env=self.env)
        finally:
            del os.environ["TG_TEST_KEY"]

    def projects_url(self) -> str:
        return f"{ADDRESS}/api/v1/workspaces/{WORKSPACE}/projects/?per_page=100"

    def cards_url(self) -> str:
        query = urlencode({"per_page": "100", "fields": WORK_ITEM_FIELDS})
        return f"{ADDRESS}/api/v1/workspaces/{WORKSPACE}/projects/p1/work-items/?{query}"

    def script_drift_replies(self) -> None:
        self.mock.responses[("GET", self.projects_url())] = {
            "status": 200, "body": {"results": [{"id": "p1", "identifier": "T"}], "next_page_results": False}}
        self.mock.responses[("GET", self.cards_url())] = {
            "status": 200, "body": {"results": [], "next_page_results": False}}


class TestCon(ConnectorCase):
    def test_con01_not_set_up_message_exit_and_no_network_call(self) -> None:
        for argv in (["drift", SYNC_TICKET], ["sync", SYNC_TICKET], CREATE_FOR_TEST):
            with assert_no_network():
                code, err = self.run_plane(argv)
            self.assertNotIn(code, (0, None))
            self.assertIn("plane: not set up", err)
            self.assertIn("connect.py on plane", err)
        self.assertEqual(self.mock.calls, [])
        self.assertFalse(os.path.exists(self.env["TOLLGATE_CONNECTORS"]))

    def test_con01_subprocess_exit_code_and_message(self) -> None:
        run = subprocess.run([sys.executable, "-B", str(SCRIPTS / "connectors" / "plane" / "plane_sync.py"),
                              "drift", SYNC_TICKET], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("plane: not set up", run.stderr)
        self.assertEqual(run.stdout, "")

    def test_con02_first_use_stores_the_key_in_the_secret_store_and_in_no_file(self) -> None:
        with assert_no_network():
            self.assertEqual(self.turn_on(), 0)
        self.assertTrue(self.secrets.asked_to_store("plane"))
        self.assertEqual(self.secrets.get("plane"), self.secret)
        needle = self.secret.encode()
        for root in (ROOT, Path(self.home)):
            for folder, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d != ".git"]
                for name in files:
                    try:
                        data = (Path(folder) / name).read_bytes()
                    except OSError:
                        continue
                    self.assertNotIn(needle, data, str(Path(folder) / name))
        text = Path(self.env["TOLLGATE_CONNECTORS"]).read_text(encoding="utf-8")
        self.assertIn("plane", text)
        self.assertIn(ADDRESS, text)

    def test_con02_first_use_in_a_terminal_asks_for_address_and_key(self) -> None:
        self.script_drift_replies()
        with mock.patch.object(registry, "interactive", lambda env=None: True), \
                mock.patch("builtins.input", return_value=ADDRESS), \
                mock.patch.object(connect.getpass, "getpass", return_value=self.secret), \
                contextlib.redirect_stderr(io.StringIO()):
            code, _ = self.run_plane(["drift", SYNC_TICKET])
        self.assertEqual(code, 2)
        self.assertTrue(self.secrets.asked_to_store("plane"))
        self.assertTrue(registry.is_on("plane", self.env))
        self.assertEqual(self.mock.calls[0]["url"], self.projects_url())

    def test_con03_on_survives_a_restart_and_the_next_call_reaches_the_mock_client(self) -> None:
        self.assertEqual(self.turn_on(), 0)
        registry._FACTORIES.clear()
        importlib.reload(cli)
        self.assertIn("plane", registry.registered())
        self.script_drift_replies()
        code, _ = self.run_plane(["drift", SYNC_TICKET])
        self.assertEqual(code, 2)
        self.assertEqual([c["url"] for c in self.mock.calls], [self.projects_url(), self.cards_url()])
        self.assertEqual(self.mock.calls[0]["kwargs"]["headers"]["X-API-Key"], self.secret)
        self.assertEqual(registry.load_state(self.env)["plane"], {"address": ADDRESS, "on": True})

    def test_con03_the_key_is_not_in_any_output_line(self) -> None:
        self.turn_on()
        self.script_drift_replies()
        self.run_plane(["drift", SYNC_TICKET])
        self.assertNotIn(self.secret, "\n".join(self.lines))

    def test_con04_off_returns_to_not_set_up(self) -> None:
        self.turn_on()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(connect.main(["off", "plane"], env=self.env), 0)
        self.assertIsNone(self.secrets.get("plane"))
        with assert_no_network():
            code, err = self.run_plane(["drift", SYNC_TICKET])
        self.assertNotIn(code, (0, None))
        self.assertIn("plane: not set up", err)
        self.assertEqual(self.mock.calls, [])

    def test_status_command_shows_on_and_off(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(connect.main(["status", "plane"], env=self.env), 1)
            self.turn_on()
            self.assertEqual(connect.main(["status", "plane"], env=self.env), 0)
        self.assertIn("plane: not set up", out.getvalue())
        self.assertIn("plane: on", out.getvalue())


class TestStubIsLocal(unittest.TestCase):
    def test_the_stub_binds_to_the_loop_back_address_only(self) -> None:
        from plane_stub_server import PlaneStubServer
        server = PlaneStubServer().start()
        self.addCleanup(server.stop)
        self.assertEqual(server.server_address[0], "127.0.0.1")
        self.assertTrue(server.base_url.startswith("http://127.0.0.1:"))

    def test_the_test_http_object_refuses_any_other_host(self) -> None:
        with assert_no_network():
            with self.assertRaises(AssertionError):
                StubHttp().request("GET", "https://plane.example.invalid/x")


CREATE_FOR_TEST = ["create", "--prefix", "T", "--title", "x", "--priority", "P2", "--scope", "s",
                   "--repo", "r", "--type", "feature", "--yes"]


if __name__ == "__main__":
    unittest.main()
