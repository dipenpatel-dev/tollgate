#!/usr/bin/env python3
"""Connector host allowlist tests (finding 10).

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: A key goes only to a built-in host for that connector, or to a host
         the owner recorded with --allow-host. Checked when the connector is
         turned on and on every request. Address tricks are refused.
Change log:
  - First version.
"""
import contextlib
import io
import json
import os
import pathlib
import sys
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

import connector_helpers
from connector_helpers import FakeSecretStore, MockClient, assert_no_network
from throwaway_home import throwaway_home
from connectors import registry, connect

GOOD = [
    ("jira", "https://acme.atlassian.net"),
    ("jira", "https://api.atlassian.com/ex/jira/abc"),
    ("jira", "https://ACME.Atlassian.NET"),
    ("slack", "https://slack.com/api"),
    ("slack", "https://acme.slack.com/api"),
    ("notion", "https://api.notion.com/v1"),
    ("notion", "https://notion.com"),
    ("databricks", "https://adb-1.2.azuredatabricks.net"),
    ("databricks", "https://acme.cloud.databricks.com"),
    ("databricks", "https://acme.gcp.databricks.com"),
    ("calendar", "https://www.googleapis.com/calendar/v3"),
]

BAD = [
    ("user name in address", "jira", "https://user@acme.atlassian.net"),
    ("password in address", "jira", "https://u:p@acme.atlassian.net"),
    ("plain http", "jira", "http://acme.atlassian.net"),
    ("other host", "jira", "https://attacker.example"),
    ("suffix at the end", "jira", "https://atlassian.net.attacker.example"),
    ("suffix after a hash", "jira", "https://attacker.example#.atlassian.net"),
    ("suffix after a question mark", "jira", "https://attacker.example?.atlassian.net"),
    ("suffix after a slash", "jira", "https://attacker.example/.atlassian.net"),
    ("backslash", "jira", "https://attacker.example\\.atlassian.net"),
    ("trailing dot", "jira", "https://acme.atlassian.net."),
    ("port", "jira", "https://acme.atlassian.net:8443"),
    ("bad port", "jira", "https://acme.atlassian.net:99999"),
    ("IPv4 literal", "jira", "https://203.0.113.9"),
    ("IPv6 literal", "jira", "https://[2001:db8::1]"),
    ("decimal IP", "jira", "https://3405803785"),
    ("bare suffix", "jira", "https://atlassian.net"),
    ("lookalike label", "jira", "https://acmeatlassian.net"),
    ("non-ascii host", "jira", "https://acme.atlassian.net․evil.example"),
    ("space in address", "jira", "https://acme.atlassian.net .evil.example"),
    ("empty host", "jira", "https:///x"),
    ("slack host on jira", "jira", "https://slack.com"),
    ("notion lookalike", "notion", "https://api.notion.com.attacker.example"),
    ("notion subdomain not listed", "notion", "https://x.notion.com"),
    ("slack lookalike", "slack", "https://evilslack.com"),
    ("databricks lookalike", "databricks", "https://x.databricks.com.attacker.example"),
    ("unknown connector", "nolist", "https://acme.atlassian.net"),
]


class _Client:
    def __init__(self, address, key, http):
        self.address, self.key, self.http = address, key, http


class Base(unittest.TestCase):
    def setUp(self):
        self.saved_factories = dict(registry._FACTORIES)
        registry.register("jira", _Client)
        self.saved = dict(registry.BUILTIN_HOSTS)
        registry.BUILTIN_HOSTS.clear()
        registry.BUILTIN_HOSTS.update(connector_helpers.REAL_BUILTIN_HOSTS)
        self.cm = throwaway_home()
        self.home, env = self.cm.__enter__()
        self.env = dict(env, TOLLGATE_NONINTERACTIVE="1")
        self.store = FakeSecretStore()
        registry.set_store(self.store)
        registry.set_http_factory(None)
        self.cred = "tgfake-" + "host-test"

    def tearDown(self):
        registry.set_store(None)
        registry.set_http_factory(None)
        registry.BUILTIN_HOSTS.clear()
        registry.BUILTIN_HOSTS.update(self.saved)
        registry._FACTORIES.clear()
        registry._FACTORIES.update(self.saved_factories)
        self.cm.__exit__(None, None, None)

    def on(self, name, address, *extra, terminal=False):
        os.environ["TG_HOST_KEY"] = self.cred
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                    unittest.mock.patch.object(registry, "interactive",
                                               return_value=terminal):
                code = connect.main(["on", name, "--address", address, *extra,
                                     "--key-from-env", "TG_HOST_KEY"], env=self.env)
        finally:
            del os.environ["TG_HOST_KEY"]
        return code, err.getvalue()

    def write_state(self, data):
        path = registry.state_path(self.env)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))


class TestAllowed(Base):
    def test_built_in_hosts_turn_on(self):
        for name, url in GOOD:
            code, err = self.on(name, url)
            self.assertEqual(code, 0, (name, url, err))


class TestRefused(Base):
    def test_each_trick_is_refused_and_nothing_is_stored(self):
        for label, name, url in BAD:
            code, err = self.on(name, url)
            self.assertEqual(code, 1, (label, url))
            self.assertNotIn(self.cred, err)
            self.assertFalse(registry.is_on(name, self.env), label)
            self.assertIsNone(self.store.get(name), label)

    def test_check_host_raises_for_each_trick(self):
        for label, name, url in BAD:
            with self.assertRaises(ValueError, msg=label):
                registry.check_host(name, url, self.env)

    def test_message_names_the_owner_step(self):
        code, err = self.on("jira", "https://jira.corp.example")
        self.assertEqual(code, 1)
        self.assertIn("--allow-host jira.corp.example", err)


class TestRecordedHost(Base):
    def test_allow_host_needs_a_terminal(self):
        code, err = self.on("jira", "https://jira.corp.example",
                            "--allow-host", "jira.corp.example", terminal=False)
        self.assertEqual(code, 1)
        self.assertIn("terminal", err)
        self.assertFalse(registry.is_on("jira", self.env))

    def test_recorded_host_passes_and_is_saved_in_state(self):
        code, err = self.on("jira", "https://jira.corp.example",
                            "--allow-host", "Jira.Corp.Example", terminal=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(registry.load_state(self.env)["jira"]["allowed_hosts"],
                         ["jira.corp.example"])
        registry.check_host("jira", "https://jira.corp.example/x", self.env)

    def test_recorded_host_does_not_cover_other_hosts_or_connectors(self):
        self.on("jira", "https://jira.corp.example",
                "--allow-host", "jira.corp.example", terminal=True)
        for name, url in (("jira", "https://other.corp.example"),
                          ("jira", "https://sub.jira.corp.example"),
                          ("jira", "https://jira.corp.example:8443"),
                          ("slack", "https://jira.corp.example")):
            with self.assertRaises(ValueError, msg=url):
                registry.check_host(name, url, self.env)

    def test_ip_and_port_work_only_when_recorded_exactly(self):
        code, _ = self.on("plane", "https://203.0.113.9:8443",
                          "--allow-host", "203.0.113.9:8443", terminal=True)
        self.assertEqual(code, 0)
        registry.check_host("plane", "https://203.0.113.9:8443/api", self.env)
        with self.assertRaises(ValueError):
            registry.check_host("plane", "https://203.0.113.9", self.env)

    def test_bad_allow_host_values_are_refused(self):
        for bad in ("https://x.example", "x.example/path", "*.example",
                    ".example", "x.example.", "x.example:0", "x.example:abc", ""):
            code, _ = self.on("jira", "https://x.example", "--allow-host", bad,
                              terminal=True)
            self.assertEqual(code, 1, bad)

    def test_turning_off_clears_recorded_hosts(self):
        self.on("jira", "https://jira.corp.example",
                "--allow-host", "jira.corp.example", terminal=True)
        registry.turn_off("jira", self.env)
        self.assertNotIn("allowed_hosts", registry.load_state(self.env)["jira"])

    def test_malformed_allowed_hosts_in_state_is_ignored(self):
        self.write_state({"jira": {"address": "https://jira.corp.example",
                                   "on": True, "allowed_hosts": "jira.corp.example"}})
        with self.assertRaises(ValueError):
            registry.check_host("jira", "https://jira.corp.example", self.env)


class TestEveryRequest(Base):
    def test_request_to_an_unlisted_host_is_refused_before_any_network(self):
        self.write_state({"jira": {"address": "https://attacker.example",
                                   "on": True}})
        self.store.set("jira", self.cred)
        client = registry.require("jira", self.env)
        with assert_no_network():
            with self.assertRaises(ValueError):
                client.http.get(client.address + "/rest/api/3/search",
                                headers={"Authorization": "Bearer " + self.cred})

    def test_a_later_edit_of_the_state_file_is_caught_on_the_next_request(self):
        self.on("jira", "https://acme.atlassian.net")
        client = registry.require("jira", self.env)
        self.write_state({"jira": {"address": "https://attacker.example",
                                   "on": True}})
        client2 = registry.require("jira", self.env)
        with assert_no_network():
            with self.assertRaises(ValueError):
                client2.http.get(client2.address + "/x")
        self.assertEqual(client.address, "https://acme.atlassian.net")

    def test_the_http_client_checks_each_url_not_only_the_first(self):
        http = registry.UrlHttp("jira", self.env)
        with assert_no_network():
            with self.assertRaises(ValueError):
                http.get("https://attacker.example/x")

    def test_mock_factory_still_works(self):
        registry.set_http_factory(lambda: MockClient())
        self.on("jira", "https://acme.atlassian.net")
        self.assertIsNotNone(registry.require("jira", self.env))


if __name__ == "__main__":
    unittest.main()
