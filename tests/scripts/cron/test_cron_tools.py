#!/usr/bin/env python3
"""Tests for the cron scripts: setup_cron (SCR-05), nightly_index, write_nightly_health,
vault_staleness, backup_vault, think_calibrate_reminder and the launchers.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove the cron setup writes only into the home passed to it and never loads a job
without --yes-install-job (the launcher is a stub), and that the nightly scripts write
only inside folders the path loader returns.
Change log:
  - First version.
"""
import json
import os
import pathlib
import plistlib
import re
import subprocess
import sys
import unittest
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CRON = ROOT / "scripts" / "cron"
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from throwaway_home import throwaway_home  # noqa: E402
from core import paths  # noqa: E402
from real_guard import RealStateGuard  # noqa: E402

LOADER_NAMES = ("vault", "tickets", "output", "meetings", "conversations", "references",
                "state", "cache", "logs", "index", "repos")


def run(args, env, input_text=None, timeout=180):
    return subprocess.run(args, env=dict(env, PYTHONDONTWRITEBYTECODE="1"), input=input_text,
                          capture_output=True, text=True, timeout=timeout)


def files_under(folder):
    return {str(p) for p in pathlib.Path(folder).rglob("*") if p.is_file()}


def loader_folders(env):
    out = []
    for name in LOADER_NAMES:
        proc = run([str(ROOT / "scripts" / "core" / "tg_path"), name], env)
        if proc.returncode == 0:
            out.append(pathlib.Path(proc.stdout.strip()).resolve())
    return out


def make_stub_launcher(home):
    """A fake launchctl: records its arguments in a log file and never calls the real one."""
    log = pathlib.Path(home) / "stub-launcher.log"
    stub = pathlib.Path(home) / "stub-launcher"
    stub.write_text('#!/bin/bash\necho "$@" >> "{}"\nexit 0\n'.format(log))
    stub.chmod(0o755)
    return stub, log


class SetupCron(unittest.TestCase):
    def _args(self, home, *extra):
        return [sys.executable, str(CRON / "setup_cron.py"), "--home", str(home), "--job", "nightly-index", *extra]

    def test_dry_run_prints_and_writes_nothing(self):
        with throwaway_home() as (home, env):
            stub, log = make_stub_launcher(home)
            before = files_under(home)
            proc = run(self._args(home, "--dry-run", "--yes-install-job", "--launcher", str(stub)), env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("would write:", proc.stdout)
            self.assertIn("nightly_index.sh", proc.stdout)
            self.assertEqual(files_under(home), before)
            self.assertFalse(log.exists())                 # even with the flag, a dry run loads nothing

    def test_write_without_the_flag_never_calls_the_launcher(self):
        with throwaway_home() as (home, env):
            stub, log = make_stub_launcher(home)
            before = files_under(home)
            proc = run(self._args(home, "--launcher", str(stub)), env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("not loaded", proc.stdout)
            self.assertFalse(log.exists())
            new = files_under(home) - before
            plist_path = pathlib.Path(home) / "Library" / "LaunchAgents" / "tg-job-nightly-index.plist"
            self.assertEqual(new, {str(plist_path)})       # exactly one file, inside the given home
            data = plistlib.loads(plist_path.read_bytes())
            self.assertEqual(data["Label"], "tg-job-nightly-index")
            self.assertEqual(data["ProgramArguments"][0], "/bin/bash")
            self.assertTrue(data["ProgramArguments"][1].endswith("nightly_index.sh"))
            self.assertEqual(data["StartCalendarInterval"], {"Hour": 2, "Minute": 0})
            self.assertFalse(data["RunAtLoad"])
            self.assertNotIn("@", plist_path.read_text())  # every marker was filled

    def test_flag_loads_through_the_stub_only(self):
        with throwaway_home() as (home, env):
            stub, log = make_stub_launcher(home)
            proc = run(self._args(home, "--yes-install-job", "--launcher", str(stub)), env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("loaded", proc.stdout)
            calls = log.read_text().splitlines()
            self.assertEqual(len(calls), 1)
            self.assertIn("bootstrap", calls[0])
            self.assertIn("tg-job-nightly-index.plist", calls[0])

    def test_real_launcher_is_refused_for_a_foreign_home(self):
        with throwaway_home() as (home, env):
            other = pathlib.Path(home) / "elsewhere"
            other.mkdir()
            # A PATH with a fake launchctl in front proves the real one is not reached either.
            stubdir = pathlib.Path(home) / "bin"
            stubdir.mkdir()
            marker = pathlib.Path(home) / "launchctl-was-called"
            fake = stubdir / "launchctl"
            fake.write_text('#!/bin/bash\ntouch "{}"\n'.format(marker))
            fake.chmod(0o755)
            env2 = dict(env, PATH=str(stubdir) + os.pathsep + env.get("PATH", os.environ["PATH"]))
            proc = run(self._args(other, "--yes-install-job"), env2)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("refused", proc.stderr)
            self.assertFalse(marker.exists())

    def test_bad_input_is_refused(self):
        with throwaway_home() as (home, env):
            base = [sys.executable, str(CRON / "setup_cron.py"), "--home", str(home)]
            self.assertEqual(run(base, env).returncode, 2)                                   # no job
            self.assertEqual(run(base + ["--job", "nightly-index", "--label", "../evil"], env).returncode, 2)
            self.assertEqual(run(base + ["--job", "nightly-index", "--hour", "25"], env).returncode, 2)
            self.assertEqual(run(base[:3] + [str(pathlib.Path(home) / "nope"), "--job", "nightly-index"], env).returncode, 2)

    def test_remove_deletes_only_the_job_file(self):
        with throwaway_home() as (home, env):
            stub, log = make_stub_launcher(home)
            run(self._args(home, "--launcher", str(stub)), env)
            plist_path = pathlib.Path(home) / "Library" / "LaunchAgents" / "tg-job-nightly-index.plist"
            self.assertTrue(plist_path.exists())
            proc = run(self._args(home, "--remove", "--launcher", str(stub)), env)
            self.assertEqual(proc.returncode, 0)
            self.assertFalse(plist_path.exists())
            self.assertFalse(log.exists())                 # no unload without the flag

    def test_weekly_reminder_has_a_weekday(self):
        with throwaway_home() as (home, env):
            run([sys.executable, str(CRON / "setup_cron.py"), "--home", str(home), "--job", "weekly-reminder"], env)
            data = plistlib.loads((pathlib.Path(home) / "Library/LaunchAgents/tg-job-weekly-reminder.plist").read_bytes())
            self.assertEqual(data["StartCalendarInterval"], {"Weekday": 0, "Hour": 9, "Minute": 0})

    def test_a_custom_program_and_the_carried_variables(self):
        with throwaway_home() as (home, env):
            proc = run([sys.executable, str(CRON / "setup_cron.py"), "--home", str(home),
                        "--program", str(CRON / "backup_vault.sh"), "--arg=--dry-run", "--hour", "3"], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = list((pathlib.Path(home) / "Library/LaunchAgents").glob("*.plist"))
            self.assertEqual(len(written), 1)
            data = plistlib.loads(written[0].read_bytes())
            self.assertEqual(data["ProgramArguments"][2], "--dry-run")
            self.assertEqual(data["EnvironmentVariables"]["TOLLGATE_KNOWLEDGE"], env["TOLLGATE_KNOWLEDGE"])
            self.assertNotIn("secret", json.dumps(data).lower())


class SetupCronCarriesPathsAndNightlyChecks(unittest.TestCase):
    def test_the_job_file_carries_home_and_paths_and_says_what_to_do_if_the_vault_moves(self):
        with throwaway_home() as (home, env):
            proc = run([sys.executable, str(CRON / "setup_cron.py"), "--home", str(home),
                        "--job", "nightly-index"], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("not loaded", proc.stdout)                  # setup never loads a job by itself
            self.assertIn("vault:", proc.stdout)                      # the note about a moved vault
            plist = pathlib.Path(home) / "Library/LaunchAgents/tg-job-nightly-index.plist"
            variables = plistlib.loads(plist.read_bytes())["EnvironmentVariables"]
            self.assertEqual(variables["TOLLGATE_HOME"], env["TOLLGATE_HOME"])
            self.assertEqual(variables["TOLLGATE_PATHS"], env["TOLLGATE_PATHS"])

    def test_nightly_index_stops_with_a_clear_message_when_the_vault_is_gone(self):
        with throwaway_home() as (home, env):
            gone = pathlib.Path(home) / "moved-away"
            env2 = dict(env, TOLLGATE_KNOWLEDGE=str(gone))
            proc = run(["bash", str(CRON / "nightly_index.sh"), "--skip-index"], env2)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("the vault folder does not exist", proc.stderr)
            logs = list((pathlib.Path(home) / ".tollgate" / "logs" / "nightly").glob("*.log"))
            self.assertEqual(len(logs), 1)
            self.assertIn("ABORT: the vault folder does not exist", logs[0].read_text())
            self.assertFalse(gone.exists())

    def test_vault_staleness_skips_memory_by_whole_folder_name(self):
        sys.path.insert(0, str(CRON))
        import vault_staleness
        self.assertTrue(vault_staleness.under_folder("memory/a.md", "memory"))
        self.assertTrue(vault_staleness.under_folder("memory", "memory"))
        self.assertFalse(vault_staleness.under_folder("03-knowledge-base/decisions/memory-notes.md", "memory"))
        self.assertFalse(vault_staleness.under_folder("memory2/a.md", "memory"))
        self.assertFalse(vault_staleness.under_folder("a/memory/b.md", "memory"))

    def test_vault_staleness_rules_come_from_the_layout(self):
        sys.path.insert(0, str(CRON))
        import vault_staleness
        names = sorted(vault_staleness.STALENESS_RULES)
        self.assertIn("01-system-map/platform-learning", names)
        self.assertIn("01-system-map/clients", names)
        self.assertFalse([n for n in names if "products" in n or "databricks" in n])


class NightlyAndHelpers(unittest.TestCase):
    def _sessions_dir(self, home, env):
        vault = env["TOLLGATE_KNOWLEDGE"]
        project = pathlib.Path(home) / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", vault)
        project.mkdir(parents=True)
        return project

    def test_dry_run_runs_and_writes_nothing(self):
        with throwaway_home() as (home, env):
            before = files_under(home)
            proc = run(["bash", str(CRON / "nightly_index.sh"), "--dry-run"], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("sync_conversations", proc.stdout)
            self.assertIn("build_index", proc.stdout)
            self.assertEqual(files_under(home), before)

    def test_run_writes_only_inside_loader_folders_and_records_health(self):
        with throwaway_home() as (home, env):
            self._sessions_dir(home, env)
            vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
            (vault / "a.md").write_text("link [b](b.md)\n")
            (vault / "b.md").write_text("body\n")
            settings = pathlib.Path(home) / ".claude" / "settings.json"
            settings.write_text("{}")
            before = files_under(home)
            osascript_marker = pathlib.Path(home) / "osascript-called"
            bindir = pathlib.Path(home) / "bin"
            bindir.mkdir()
            fake = bindir / "osascript"
            fake.write_text('#!/bin/bash\ntouch "{}"\n'.format(osascript_marker))
            fake.chmod(0o755)
            env2 = dict(env, PATH=str(bindir) + os.pathsep + os.environ["PATH"],
                        CLAUDE_CONFIG_DIR=str(pathlib.Path(home) / ".claude"))
            with RealStateGuard(vault_path=None):
                proc = run(["bash", str(CRON / "nightly_index.sh"), "--skip-index"], env2)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("[[b]]", (vault / "a.md").read_text())
            new = files_under(home) - before - {str(fake)}
            allowed = loader_folders(env)
            self.assertTrue(new)
            for path in new:
                self.assertTrue(any(pathlib.Path(path).resolve().is_relative_to(a) for a in allowed), path)
            self.assertEqual(settings.read_text(), "{}")
            health = json.loads((pathlib.Path(env["TOLLGATE_STATE_DIR"]) / "nightly-health.json").read_text())
            names = [s["name"] for s in health["steps"]]
            self.assertEqual(names, ["sync_conversations", "lint_wikilinks", "vault_staleness"])
            self.assertEqual(health["overall"], "PASS", health)
            self.assertFalse(osascript_marker.exists())     # no notification without --notify
            logs = list((pathlib.Path(home) / ".tollgate" / "logs" / "nightly").glob("*.log"))
            self.assertEqual(len(logs), 1)

    def test_a_failed_step_is_recorded_and_the_rest_still_run(self):
        with throwaway_home() as (home, env):
            # no sessions folder: sync_conversations fails, the other steps must still run
            proc = run(["bash", str(CRON / "nightly_index.sh"), "--skip-index"], env)
            self.assertEqual(proc.returncode, 0)
            health = json.loads((pathlib.Path(env["TOLLGATE_STATE_DIR"]) / "nightly-health.json").read_text())
            status = {s["name"]: s["status"] for s in health["steps"]}
            self.assertEqual(status["sync_conversations"], "FAIL")
            self.assertEqual(status["lint_wikilinks"], "PASS")
            self.assertEqual(health["overall"], "FAIL")

    def test_not_set_up(self):
        with throwaway_home() as (home, env):
            bare = {k: v for k, v in env.items() if k not in ("TOLLGATE_KNOWLEDGE", "TOLLGATE_PATHS")}
            proc = run(["bash", str(CRON / "nightly_index.sh")], bare)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not set up", proc.stderr)

    def test_health_notifies_only_with_the_flag(self):
        with throwaway_home() as (home, env):
            bindir = pathlib.Path(home) / "bin"
            bindir.mkdir()
            marker = pathlib.Path(home) / "osascript-called"
            fake = bindir / "osascript"
            fake.write_text('#!/bin/bash\ntouch "{}"\n'.format(marker))
            fake.chmod(0o755)
            env2 = dict(env, PATH=str(bindir) + os.pathsep + os.environ["PATH"])
            script = str(CRON / "write_nightly_health.py")
            run([sys.executable, script, "a:FAIL:1"], env2)
            self.assertFalse(marker.exists())
            run([sys.executable, script, "--notify", "a:FAIL:1"], env2)
            self.assertTrue(marker.exists())

    def test_vault_staleness_writes_one_report_into_output(self):
        with throwaway_home() as (home, env):
            vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
            scanned = vault / paths.folder_name("system_map")
            scanned.mkdir(parents=True, exist_ok=True)
            (scanned / "w.md").write_text("- [ ] open item\nsee [[missing-note]]\n")
            before = files_under(vault)
            proc = run([sys.executable, str(CRON / "vault_staleness.py")], env)
            self.assertEqual(proc.returncode, 2, proc.stderr)           # issues found
            report = vault / "output" / "vault-health-report.md"
            self.assertTrue(report.exists())
            self.assertEqual(files_under(vault) - before, {str(report)})
            self.assertIn("missing-note", report.read_text())
            self.assertEqual(run([sys.executable, str(CRON / "vault_staleness.py"), "--report-only"], env).returncode, 0)

    def test_think_calibrate_reminder_dry_run(self):
        proc = run(["bash", str(CRON / "think_calibrate_reminder.sh"), "--dry-run"], os.environ.copy())
        self.assertEqual(proc.returncode, 0)
        self.assertIn("think-calibrate", proc.stdout)

    def test_launchers_dry_run(self):
        with throwaway_home() as (home, env):
            before = files_under(home)
            proc = run(["bash", str(CRON / "launchers" / "run_task.sh"), "all", "--dry-run"], env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("sync_conversations", proc.stdout)
            self.assertEqual(files_under(home), before)
            self.assertEqual(run(["bash", str(CRON / "launchers" / "run_task.sh"), "nope"], env).returncode, 2)


class BackupVault(unittest.TestCase):
    def test_backup_encrypts_rotates_and_never_prints_the_key(self):
        with throwaway_home() as (home, env):
            fake_key = "tgfake-" + uuid.uuid4().hex
            keyfile = pathlib.Path(home) / "keyprinter"
            keyfile.write_text('#!/bin/bash\nprintf "%s" "{}"\n'.format(fake_key))
            keyfile.chmod(0o755)
            vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
            (vault / "note.md").write_text("hello backup\n")
            copy_to = pathlib.Path(home) / "second-folder"
            copy_to.mkdir()
            proc = run(["bash", str(CRON / "backup_vault.sh"), "--key-cmd", str(keyfile), "--copy-to", str(copy_to)], env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertNotIn(fake_key, proc.stdout + proc.stderr)
            archives = list((vault / "output" / "backups").glob("vault-*.enc"))
            self.assertEqual(len(archives), 1)
            self.assertEqual(len(list(copy_to.glob("vault-*.enc"))), 1)
            self.assertNotIn(b"hello backup", archives[0].read_bytes())      # really encrypted
            dec = subprocess.run(
                "openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -pass env:TGKEY -in '{}' | tar -tzf -".format(archives[0]),
                shell=True, capture_output=True, text=True, env=dict(os.environ, TGKEY=fake_key))
            self.assertIn("note.md", dec.stdout)
            self.assertFalse(list((vault / "output" / "backups").glob(".vault-enc-tmp-*")))

    def test_missing_key_and_missing_copy_folder_are_refused(self):
        with throwaway_home() as (home, env):
            empty = pathlib.Path(home) / "nokey"
            empty.write_text("#!/bin/bash\nexit 0\n")
            empty.chmod(0o755)
            script = str(CRON / "backup_vault.sh")
            self.assertEqual(run(["bash", script], env).returncode, 1)
            self.assertEqual(run(["bash", script, "--key-cmd", str(empty)], env).returncode, 1)
            gone = pathlib.Path(home) / "not-mounted"
            proc = run(["bash", script, "--key-cmd", "echo x", "--copy-to", str(gone)], env)
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(gone.exists())                                  # never created
            self.assertFalse((pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "output" / "backups").exists())

    def test_dry_run_writes_nothing(self):
        with throwaway_home() as (home, env):
            before = files_under(home)
            proc = run(["bash", str(CRON / "backup_vault.sh"), "--dry-run"], env)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("would write", proc.stdout)
            self.assertEqual(files_under(home), before)

    def test_option_without_a_value_fails_instead_of_looping(self):
        with throwaway_home() as (home, env):
            for option in ("--key-cmd", "--copy-to"):
                proc = run(["bash", str(CRON / "backup_vault.sh"), option], env, timeout=20)
                self.assertEqual(proc.returncode, 2, option)
                self.assertIn("missing value", proc.stderr)


if __name__ == "__main__":
    unittest.main()
