"""
module_name: test_bootstrap.py
description: Tests for the bootstrap scripts, run.sh, hook helpers, session_cost and memory enums.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial test.
"""
import json
import os
import pathlib
import stat
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests" / "harness"))
sys.path.insert(0, str(REPO / "scripts"))

from throwaway_home import throwaway_home  # noqa: E402

CORE = REPO / "scripts" / "core"
BOOT = CORE / "bootstrap"
ROLES = ["dispatch"] + ["%s-%d" % (t, i) for t in ("arch", "dev", "qa", "spec") for i in (1, 2)]


def make_env(home, env):
    """Point the scripts at the repo and put a fake claude first on PATH."""
    env["TOLLGATE_HOME"] = str(REPO)
    bindir = pathlib.Path(home) / "bin"
    bindir.mkdir(exist_ok=True)
    fake = bindir / "claude"
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$TG_FAKE_OUT"\n'
                    'printf "%s\\n" "$TOLLGATE_WORKER_ID" >> "$TG_FAKE_OUT"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
    env["TG_FAKE_OUT"] = str(pathlib.Path(home) / "claude_args.txt")
    tpl = pathlib.Path(home) / "templates"
    tpl.mkdir(exist_ok=True)
    for t in ("dispatch", "arch", "dev", "qa", "spec"):
        (tpl / ("%s-identity-template.md" % t)).write_text("I am {{WORKER_NAME}} of type %s\n" % t)
    env["TOLLGATE_WORKER_TEMPLATES"] = str(tpl)
    return env


def run(cmd, env, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, env=env, **kw)


class Bootstrap(unittest.TestCase):
    def test_all_scripts_present_and_executable(self):
        for role in ROLES:
            p = BOOT / ("bootstrap-%s.sh" % role)
            self.assertTrue(p.is_file(), role)
            self.assertTrue(os.access(p, os.X_OK), role)

    def test_each_role_launches_with_identity(self):
        for role in ROLES:
            with throwaway_home() as (home, env):
                make_env(home, env)
                proc = run(["bash", str(BOOT / ("bootstrap-%s.sh" % role))], env)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                state = pathlib.Path(env["TOLLGATE_STATE_DIR"])
                ident = state / "workers" / ("%s-identity.md" % role)
                self.assertIn("I am %s of type" % role, ident.read_text())
                out = pathlib.Path(env["TG_FAKE_OUT"]).read_text().split("\n")
                self.assertEqual(out[0], "--append-system-prompt-file")
                self.assertEqual(out[1], str(ident))
                self.assertEqual(out[2], role)
                reg = state / "worker-registry" / ("%s.json" % role)
                if role == "dispatch":
                    self.assertFalse(reg.exists())
                else:
                    rec = json.loads(reg.read_text())
                    self.assertEqual(rec["worker_name"], role)
                    self.assertEqual(rec["type"], role.split("-")[0])
                    self.assertEqual(rec["status"], "available")
                    self.assertFalse(reg.with_suffix(".json.tmp").exists())

    def test_missing_template_fails_clearly(self):
        with throwaway_home() as (home, env):
            make_env(home, env)
            env["TOLLGATE_WORKER_TEMPLATES"] = os.path.join(home, "empty")
            proc = run(["bash", str(BOOT / "bootstrap-arch-1.sh")], env)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("template not found", proc.stderr)

    def test_unset_home_says_not_set_up(self):
        with throwaway_home() as (home, env):
            make_env(home, env)
            env.pop("TOLLGATE_HOME")
            proc = run(["bash", str(BOOT / "bootstrap-dev-1.sh")], env)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not set up", proc.stderr)


class RunScript(unittest.TestCase):
    def test_bad_option(self):
        with throwaway_home() as (home, env):
            env["TOLLGATE_HOME"] = str(REPO)
            proc = run(["bash", str(CORE / "run.sh"), "bogus"], env)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Usage", proc.stderr)

    def test_missing_job_scripts_are_skipped(self):
        with throwaway_home() as (home, env):
            env["TOLLGATE_HOME"] = home  # no scripts folder here
            proc = run(["bash", str(CORE / "run.sh"), "all"], env)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("skipped", proc.stdout)

    def test_runs_job_and_reports_failure(self):
        with throwaway_home() as (home, env):
            fake = pathlib.Path(home) / "scripts" / "sync"
            fake.mkdir(parents=True)
            s = fake / "sweep"
            s.write_text("#!/bin/sh\nexit 3\n")
            s.chmod(0o755)
            env["TOLLGATE_HOME"] = home
            proc = run(["bash", str(CORE / "run.sh"), "sweep"], env)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("failed", proc.stdout)

    def test_no_home_says_not_set_up(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_HOME", None)
            proc = run(["bash", str(CORE / "run.sh")], env)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not set up", proc.stderr)


class Hooks(unittest.TestCase):
    def test_precompact_prints_warning(self):
        proc = run(["bash", str(CORE / "hooks" / "precompact_hook.sh")], os.environ.copy())
        self.assertEqual(proc.returncode, 0)
        self.assertIn("<precompact_warning>", proc.stdout)

    def test_session_state_logs_when_unconfigured(self):
        with throwaway_home() as (home, env):
            env["TOLLGATE_HOME"] = str(REPO)
            proc = run(["bash", str(CORE / "hooks" / "session_state_hook.sh")], env)
            self.assertEqual(proc.returncode, 0)
            log = pathlib.Path(home) / ".tollgate" / "logs" / "session_state_hook.log"
            self.assertIn("not configured", log.read_text())

    def test_session_state_runs_writer(self):
        with throwaway_home() as (home, env):
            env["TOLLGATE_HOME"] = str(REPO)
            w = pathlib.Path(home) / "writer.py"
            w.write_text("print('writer ran')\n")
            env["TOLLGATE_SESSION_STATE_WRITER"] = str(w)
            proc = run(["bash", str(CORE / "hooks" / "session_state_hook.sh")], env)
            self.assertEqual(proc.returncode, 0)
            log = pathlib.Path(home) / ".tollgate" / "logs" / "session_state_hook.log"
            self.assertIn("writer ran", log.read_text())


class SessionCost(unittest.TestCase):
    def _session(self, home):
        base = pathlib.Path(home) / "claude" / "projects" / "proj"
        base.mkdir(parents=True)
        f = base / "s1.jsonl"
        lines = [
            {"sessionId": "abc", "timestamp": "2026-01-01T10:00:00Z", "type": "user"},
            {"sessionId": "abc", "type": "assistant", "message": {"usage": {
                "input_tokens": 1000000, "output_tokens": 1000000,
                "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}},
        ]
        f.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        return f

    def test_close_writes_ledger_in_output(self):
        with throwaway_home() as (home, env):
            sf = self._session(home)
            cmd = [sys.executable, "-B", str(CORE / "session_cost.py"),
                   "--mode", "close", "--tasks", "demo", "--session-file", str(sf)]
            proc = run(cmd, env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            ledger = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "output" / "session-costs.jsonl"
            entry = json.loads(ledger.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["status"], "closed")
            self.assertEqual(entry["input_tokens"], 1000000)
            self.assertAlmostEqual(entry["cost_usd"], 18.0)
            self.assertIn("demo", proc.stdout)

    def test_not_set_up_without_vault(self):
        with throwaway_home() as (home, env):
            sf = self._session(home)
            env.pop("TOLLGATE_KNOWLEDGE")
            proc = run([sys.executable, "-B", str(CORE / "session_cost.py"),
                        "--mode", "close", "--tasks", "x", "--session-file", str(sf)], env)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("not set up", proc.stderr)

    def test_needs_sessions_dir_when_no_override(self):
        with throwaway_home() as (home, env):
            env.pop("CLAUDE_CONFIG_DIR", None)
            proc = run([sys.executable, "-B", str(CORE / "session_cost.py"),
                        "--mode", "start"], env)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("not set up", proc.stderr)


class MemoryEnums(unittest.TestCase):
    def test_enums(self):
        from core.memory import _enums as e
        self.assertIn("all", e.APPLICABLE_SCOPE_VALUES)
        self.assertNotIn("all", e.RESTRICTED_SCOPES)
        self.assertEqual(e.STANDARDS_DEFENSIVE_DEFAULTS["missing_status"], e.DROP_SENTINEL)
        self.assertIn("general", e.DATA_DOMAIN_VALUES)
        self.assertEqual(set(e.LIFECYCLE_QUARANTINE_DIRS),
                         {"draft", "deprecated", "superseded"})


if __name__ == "__main__":
    unittest.main()
