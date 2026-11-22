"""
module_name: test_cache.py
description: cache_write, run_log, phi_guard and daily_brief. Synthetic data only; fake identifiers are built at run time.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[3]
CACHE = ROOT / "scripts" / "cache"
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(CACHE))
from throwaway_home import throwaway_home  # noqa: E402

import cache_write  # noqa: E402
import daily_brief  # noqa: E402
import phi_guard  # noqa: E402
import run_log  # noqa: E402


def fake_ssn():
    return "-".join(("%03d" % 123, "%02d" % 45, "%04d" % 6789))


def meta(result="success", when=None, reject=0):
    when = when or datetime.now(timezone.utc)
    return {"_meta": {"pulled_at": when.isoformat(), "result": result, "reason": "api_ok", "reject_count": reject},
            "data": [{"k": "v"}]}


class CacheWrite(unittest.TestCase):
    def test_writes_json_and_leaves_no_temp_file(self):
        with throwaway_home() as (home, _env):
            target = pathlib.Path(home) / "out.json"
            cache_write.atomic_replace(target, {"a": 1})
            self.assertEqual(json.loads(target.read_text()), {"a": 1})
            self.assertEqual([p.name for p in pathlib.Path(home).glob(".out.json*")], [])

    def test_failure_keeps_old_file_and_cleans_up(self):
        with throwaway_home() as (home, _env):
            target = pathlib.Path(home) / "out.json"
            cache_write.atomic_replace(target, {"a": 1})

            class Bad:
                def __repr__(self):
                    raise RuntimeError("no")
            with self.assertRaises(Exception):
                cache_write.atomic_replace(target, {"a": Bad()})
            self.assertEqual(json.loads(target.read_text()), {"a": 1})
            self.assertEqual([p.name for p in pathlib.Path(home).glob(".out.json*")], [])


class RunLog(unittest.TestCase):
    def record(self, **over):
        now = datetime.now(timezone.utc).isoformat()
        rec = {"script": "demo", "start_ts": now, "end_ts": now, "result": "success", "reason": "write_ok", "reject_count": 0}
        rec.update(over)
        return rec

    def test_append_goes_to_the_logs_folder(self):
        with throwaway_home() as (home, env):
            os.environ.update(env)
            try:
                run_log.append(self.record())
                run_log.append(self.record(result="failed", reason="api_timeout"))
            finally:
                for k in env:
                    os.environ.pop(k, None)
            lines = (pathlib.Path(home) / ".tollgate" / "logs" / "run_log.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["reason"], "api_timeout")

    def test_rejects_bad_records(self):
        with throwaway_home() as (home, _env):
            path = pathlib.Path(home) / "log.jsonl"
            for bad in (self.record(result="weird"), self.record(reason="raw error text"), self.record(reject_count=True),
                        self.record(reject_count=-1), self.record(script="a\nb"), self.record(start_ts="not a time")):
                with self.assertRaises(ValueError):
                    run_log.append(bad, path)
            missing = self.record()
            del missing["script"]
            with self.assertRaises(ValueError):
                run_log.append(missing, path)
            self.assertFalse(path.exists())

    def test_extra_keys_are_dropped(self):
        with throwaway_home() as (home, _env):
            path = pathlib.Path(home) / "log.jsonl"
            run_log.append(self.record(secret="x"), path)
            self.assertNotIn("secret", json.loads(path.read_text()))


class PhiGuard(unittest.TestCase):
    def test_drops_records_with_identifiers(self):
        rows = [{"note": "call about " + fake_ssn()}, {"note": "lunch at noon"},
                {"nested": {"deep": ["MRN 1234567 is due"]}}, {"who": "Dr. Smith"}, {"dob": "DOB: 1990-01-02"}]
        clean, rejected = phi_guard.scrub(rows, "demo")
        self.assertEqual(clean, [{"note": "lunch at noon"}])
        self.assertEqual(rejected, 4)

    def test_clean_input_passes_whole(self):
        rows = [{"title": "Review design", "n": 3}]
        self.assertEqual(phi_guard.scrub(rows, "demo"), (rows, 0))

    def test_extra_patterns(self):
        rows = [{"t": "badge ZX-9911"}, {"t": "fine"}]
        clean, rejected = phi_guard.scrub(rows, "demo", extra_patterns=[re.compile(r"ZX-\d{4}")])
        self.assertEqual((clean, rejected), ([{"t": "fine"}], 1))


class DailyBrief(unittest.TestCase):
    def status_of(self, payload, now=None):
        with throwaway_home() as (home, _env):
            cache = pathlib.Path(home) / "cache"
            cache.mkdir()
            if payload is not None:
                (cache / "src.json").write_text(json.dumps(payload))
            blocks = daily_brief.assemble_sources(daily_brief.discover_sources(cache, ["src"]), now or datetime.now().astimezone())
            return blocks["src"]

    def test_fresh(self):
        block = self.status_of(meta())
        self.assertEqual(block["status"], "fresh")
        self.assertEqual(block["data"], [{"k": "v"}])

    def test_missing(self):
        self.assertEqual(self.status_of(None)["status"], "missing")

    def test_stale_yesterday_future_and_naive(self):
        self.assertEqual(self.status_of(meta(when=datetime.now(timezone.utc) - timedelta(days=2)))["status"], "stale")
        self.assertEqual(self.status_of(meta(when=datetime.now(timezone.utc) + timedelta(hours=3)))["status"], "stale")
        naive = meta()
        naive["_meta"]["pulled_at"] = datetime.now().replace(tzinfo=None).isoformat()
        self.assertEqual(self.status_of(naive)["status"], "stale")
        self.assertEqual(self.status_of({"data": []})["status"], "stale")

    def test_degraded_failed_and_unknown_result(self):
        self.assertEqual(self.status_of(meta("degraded"))["status"], "degraded")
        self.assertEqual(self.status_of(meta("failed"))["status"], "failed")
        self.assertEqual(self.status_of(meta("odd"))["status"], "stale")

    def test_bool_reject_count_is_ignored(self):
        payload = meta()
        payload["_meta"]["reject_count"] = True
        self.assertEqual(self.status_of(payload)["reject_count"], 0)

    def test_unreadable_file_is_stale(self):
        with throwaway_home() as (home, _env):
            cache = pathlib.Path(home) / "cache"
            cache.mkdir()
            (cache / "src.json").write_text("{not json")
            (cache / "list.json").write_text("[1]")
            blocks = daily_brief.assemble_sources(daily_brief.discover_sources(cache), datetime.now().astimezone())
            self.assertEqual({b["status"] for b in blocks.values()}, {"stale"})

    def test_run_writes_the_brief_and_one_log_line(self):
        with throwaway_home() as (home, env):
            cache = pathlib.Path(home) / ".tollgate" / "cache"
            cache.mkdir(parents=True)
            (cache / "one.json").write_text(json.dumps(meta()))
            proc = subprocess.run([sys.executable, "-B", str(CACHE / "daily_brief.py"), "--source", "two"],
                                  env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            brief = json.loads((cache / "daily_brief.json").read_text())
            self.assertEqual(brief["sources"]["one"]["status"], "fresh")
            self.assertEqual(brief["sources"]["two"]["status"], "missing")
            self.assertNotIn("daily_brief", brief["sources"])
            log = (pathlib.Path(home) / ".tollgate" / "logs" / "run_log.jsonl").read_text().splitlines()
            self.assertEqual(len(log), 1)
            self.assertEqual(json.loads(log[0])["script"], "daily_brief")

    def test_not_set_up_without_a_vault_is_not_needed_for_cache(self):
        with throwaway_home() as (home, env):
            env = {k: v for k, v in env.items() if k != "TOLLGATE_KNOWLEDGE"}
            proc = subprocess.run([sys.executable, "-B", str(CACHE / "daily_brief.py")], env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((pathlib.Path(home) / ".tollgate" / "cache" / "daily_brief.json").exists())


if __name__ == "__main__":
    unittest.main()
