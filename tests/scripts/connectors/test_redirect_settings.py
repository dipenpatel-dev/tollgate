#!/usr/bin/env python3
"""Redirect refusal and connector settings tests (CON-05, CON-06).

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: No key header follows a redirect; settings stay out of secrets.
Change log:
  - First version.
"""
import contextlib
import http.server
import io
import json
import pathlib
import sys
import threading
import unittest
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from connector_helpers import FakeSecretStore
from throwaway_home import throwaway_home
from connectors import registry, connect


def serve(handler_cls):
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class TestRedirect(unittest.TestCase):
    def test_redirect_not_followed_no_header_forwarded(self):
        seen = []

        class Target(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(dict(self.headers))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        target = serve(Target)
        port2 = target.server_address[1]

        class First(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:%d/x" % port2)
                self.end_headers()

            def log_message(self, *a):
                pass

        first = serve(First)
        key = "tgfake-" + uuid.uuid4().hex
        try:
            with self.assertRaises(registry.RedirectRefused) as cm:
                registry.UrlHttp().get(
                    "http://127.0.0.1:%d/" % first.server_address[1],
                    headers={"X-API-Key": key, "Authorization": "Bearer " + key})
        finally:
            first.shutdown()
            target.shutdown()
            first.server_close()
            target.server_close()
        self.assertEqual(seen, [])
        msg = str(cm.exception)
        self.assertIn("302", msg)
        self.assertNotIn(key, msg)
        self.assertNotIn("127.0.0.1", msg)
        self.assertNotIn("Location", msg)

    def test_address_rule(self):
        for bad in ("http://example.com/x", "ftp://example.com", "file:///etc/x"):
            with self.assertRaises(ValueError):
                registry.check_address(bad)
        for ok in ("https://example.com", "http://127.0.0.1:9", "http://localhost/"):
            registry.check_address(ok)


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.cm = throwaway_home()
        self.home, self.env = self.cm.__enter__()
        self.store = FakeSecretStore()
        registry.set_store(self.store)
        self.secret = "tgfake-" + uuid.uuid4().hex

    def tearDown(self):
        registry.set_store(None)
        self.cm.__exit__(None, None, None)

    def on(self, *extra):
        return connect.main(["on", "fakeconn", "--address", "https://a.invalid",
                             "--key-stdin"] + list(extra),
                            stdin=io.StringIO(self.secret), env=self.env)

    def test_con05_settings_survive_on_off_restart(self):
        self.assertEqual(self.on("--set", "warehouse=w1", "--set", "catalog=c=2"), 0)
        want = {"warehouse": "w1", "catalog": "c=2"}
        self.assertEqual(registry.get_settings("fakeconn", self.env), want)
        registry.set_settings("fakeconn", {"limit": 5, "flags": ["a", True]}, self.env)
        self.assertEqual(connect.main(["off", "fakeconn"], env=self.env), 0)
        self.assertFalse(registry.is_on("fakeconn", self.env))
        got = registry.get_settings("fakeconn", self.env)   # fresh read from file
        self.assertEqual(got["warehouse"], "w1")
        self.assertEqual(got["limit"], 5)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            connect.main(["status", "fakeconn"], env=self.env)
        self.assertIn("warehouse = w1", out.getvalue())
        self.assertEqual(self.on(), 0)       # on again keeps them
        self.assertEqual(registry.get_settings("fakeconn", self.env)["catalog"], "c=2")
        with open(self.env["TOLLGATE_CONNECTORS"]) as fh:
            self.assertNotIn(self.secret, fh.read())

    def test_old_file_without_settings_works(self):
        p = pathlib.Path(self.env["TOLLGATE_CONNECTORS"])
        p.write_text(json.dumps({"fakeconn": {"address": "https://a.invalid", "on": True}}))
        self.assertEqual(registry.get_settings("fakeconn", self.env), {})
        registry.set_settings("fakeconn", {"project": "p"}, self.env)
        self.assertTrue(registry.is_on("fakeconn", self.env))

    def test_con06_secret_looking_name_refused_nothing_written(self):
        err = io.StringIO()
        for name in ("api_key", "Token", "client_SECRET", "db-password"):
            with contextlib.redirect_stderr(err):
                code = self.on("--set", name + "=x")
            self.assertNotEqual(code, 0)
        self.assertIn("secret store", err.getvalue())
        self.assertFalse(pathlib.Path(self.env["TOLLGATE_CONNECTORS"]).exists())
        self.assertEqual(self.store.stored_names(), [])
        with self.assertRaises(ValueError):
            registry.set_settings("fakeconn", {"password": "x"}, self.env)
        self.assertFalse(pathlib.Path(self.env["TOLLGATE_CONNECTORS"]).exists())

    def test_bad_value_type_refused(self):
        with self.assertRaises(ValueError):
            registry.set_settings("fakeconn", {"a": {"b": 1}}, self.env)


if __name__ == "__main__":
    unittest.main()
