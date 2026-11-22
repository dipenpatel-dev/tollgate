#!/usr/bin/env python3
"""HAR-01..HAR-13: tests for the Tollgate test harness. Synthetic data only."""
import getpass
import os
import socket
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from throwaway_home import throwaway_home, run_in_home, fake_user_name  # noqa: E402
from real_guard import RealStateGuard, file_checksum  # noqa: E402
from connector_helpers import (MockClient, FakeSecretStore,  # noqa: E402
                               assert_no_network, NetworkAttempt)


def put(path, text):
    with open(path, "w") as f:
        f.write(text)


class HarnessTests(unittest.TestCase):
    def test_HAR_01_fake_user_not_real(self):
        with throwaway_home() as (home, _env):
            self.assertNotEqual(os.path.basename(home), getpass.getuser())
        self.assertNotEqual(fake_user_name(), getpass.getuser())

    def test_HAR_02_env_points_at_home(self):
        os.environ["TOLLGATE_KNOWLEDGE"] = "/real/looking/vault"
        os.environ["TOLLGATE_STRAY"] = "x"
        try:
            proc, home = run_in_home(
                [sys.executable, "-c",
                 "import os;print(os.environ['HOME']);"
                 "print(os.environ['TOLLGATE_KNOWLEDGE']);"
                 "print(os.environ.get('TOLLGATE_STRAY','unset'))"])
        finally:
            del os.environ["TOLLGATE_KNOWLEDGE"]
            del os.environ["TOLLGATE_STRAY"]
        out = proc.stdout.split()
        self.assertEqual(out[0], home)
        self.assertTrue(out[1].startswith(home))
        self.assertEqual(out[2], "unset")

    def test_HAR_03_cleanup_removes_home(self):
        with throwaway_home() as (home, _):
            root = os.path.dirname(home)
            self.assertTrue(os.path.isdir(home))
        self.assertFalse(os.path.exists(root))

    def test_HAR_04_cleanup_on_error(self):
        root = None
        with self.assertRaises(ValueError):
            with throwaway_home() as (home, _):
                root = os.path.dirname(home)
                raise ValueError("boom")
        self.assertFalse(os.path.exists(root))

    def test_HAR_05_guard_clean_run_passes(self):
        with tempfile.TemporaryDirectory() as d:
            s = os.path.join(d, "settings.json")
            v = os.path.join(d, "vault")
            os.makedirs(v)
            put(s, "{}")
            put(os.path.join(v, "a.md"), "a")
            with RealStateGuard(s, v):
                pass

    def test_HAR_06_guard_detects_settings_change(self):
        with tempfile.TemporaryDirectory() as d:
            s = os.path.join(d, "settings.json")
            put(s, "{}")
            g = RealStateGuard(s)
            g.record()
            put(s, '{"x":1}')
            with self.assertRaises(AssertionError):
                g.verify()

    def test_HAR_07_guard_detects_vault_change(self):
        with tempfile.TemporaryDirectory() as d:
            v = os.path.join(d, "vault")
            os.makedirs(v)
            g = RealStateGuard(os.path.join(d, "none.json"), v)
            g.record()
            put(os.path.join(v, "new.md"), "n")
            with self.assertRaises(AssertionError):
                g.verify()

    def test_HAR_08_guard_handles_missing(self):
        with tempfile.TemporaryDirectory() as d:
            s = os.path.join(d, "absent.json")
            v = os.path.join(d, "absent-vault")
            self.assertEqual(file_checksum(s), "MISSING")
            with RealStateGuard(s, v):
                pass  # missing before and after is clean
            g = RealStateGuard(s)
            g.record()
            put(s, "{}")
            with self.assertRaises(AssertionError):
                g.verify()

    def test_HAR_09_fake_secret_store_records(self):
        store = FakeSecretStore()
        fake_value = "fake" + "-" + "value" + "-123"
        store.set("conn/token", fake_value)
        store.get("conn/token")
        self.assertTrue(store.asked_to_store("conn/token"))
        self.assertEqual(store.stored_names(), ["conn/token"])
        self.assertNotIn(fake_value, repr(store.requests))

    def test_HAR_10_mock_client_records_no_network(self):
        c = MockClient({("GET", "https://example.invalid/x"): {"status": 204}})
        with assert_no_network():
            r = c.get("https://example.invalid/x")
        self.assertEqual(r["status"], 204)
        self.assertEqual(len(c.calls), 1)

    def test_HAR_11_no_network_catches_connect(self):
        with self.assertRaises(NetworkAttempt):
            with assert_no_network():
                try:
                    socket.create_connection(("127.0.0.1", 9), timeout=1)
                except NetworkAttempt:
                    pass  # swallowed here; the helper must still fail at exit
        s = socket.socket()  # patch restored afterwards
        s.close()

    def test_HAR_12_bash_lib_runs_in_home(self):
        lib = os.path.join(HERE, "throwaway_home.sh")
        script = (
            'source "%s"; tg_make_home; '
            'tg_run_in_home bash -c \'echo "$HOME|$TOLLGATE_KNOWLEDGE"\'; '
            'echo "ROOT=$TG_ROOT"; tg_clean_home' % lib)
        env = dict(os.environ, TOLLGATE_KNOWLEDGE="/real/looking/vault")
        p = subprocess.run(["bash", "-c", script], capture_output=True,
                           text=True, env=env)
        lines = p.stdout.strip().splitlines()
        home, kn = lines[0].split("|")
        root = lines[1].split("=", 1)[1]
        self.assertEqual(kn, home + "/vault")
        self.assertNotEqual(os.path.basename(home), getpass.getuser())
        self.assertFalse(os.path.exists(root))

    def test_HAR_13_bash_lib_with_no_tollgate_vars_under_set_u(self):
        # an empty unset_args array must not fail under set -u on bash 3.2
        lib = os.path.join(HERE, "throwaway_home.sh")
        script = ('set -u; source "%s"; tg_make_home; '
                  'tg_run_in_home bash -c \'echo "$TOLLGATE_KNOWLEDGE"\'; tg_clean_home' % lib)
        env = {k: v for k, v in os.environ.items() if not k.startswith("TOLLGATE_")}
        bash = "/bin/bash" if os.path.exists("/bin/bash") else "bash"
        p = subprocess.run([bash, "-c", script], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.strip().endswith("/vault"))


if __name__ == "__main__":
    unittest.main()
