#!/usr/bin/env python3
"""Git connector `git-commits`: collect recent commits into the cache.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Write commits.json (the daily brief seam) from local git history.
Change log:
  - First version, ported from the commits cache puller. The repo folders
    come from the connector entry or --root flags, not from a fixed list.

  commits_connector.py [--root PATH ...] [--since "24 hours ago"] [--dry-run]

This reads local git history only, so it needs no key and makes no network
call. It is a connector anyway so it stays off until you ask. The framework
wants a key, so setup stores the non-secret word `local`:

    printf local | python3 scripts/connectors/connect.py on git-commits \\
        --address /path/to/repos --key-stdin

The address is one or more folders (separated by the path separator). With the
word `local` as the address the `repos` folder from the path loader is used.
A folder that is a repo counts as one repo; otherwise each child that is a repo
counts. Commit subjects are never printed or logged, only counts.
"""
import argparse
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from connectors.registry import register, ensure, run_cli  # noqa: E402
from connectors.comms import comms_common as cc  # noqa: E402

NAME = "git-commits"
SCRIPT_NAME = "commits_pull"
SEP = "\x1f"
PRETTY = "%H" + SEP + "%aI" + SEP + "%an" + SEP + "%s"
GIT_TIMEOUT = 10
MAX_PER_REPO = 200

DRY_RUN_FIXTURE = [
    {"repo": "fixture-repo", "sha": "abc1234567890abcdef1234567890abcdef12345",
     "timestamp": "2026-01-01T08:00:00+00:00", "author": "Fixture User", "subject": "Fixture commit one"},
    {"repo": "fixture-repo", "sha": "def4567890abcdef1234567890abcdef123456ab",
     "timestamp": "2026-01-01T07:30:00+00:00", "author": "Fixture User", "subject": "Fixture commit two"},
]


def resolve_repos(root):
    """Repos under root: root itself if it has .git, else its children that do."""
    root = pathlib.Path(root)
    if not root.is_dir():
        return []
    if (root / ".git").exists():
        return [root]
    return [c for c in sorted(root.iterdir()) if c.is_dir() and (c / ".git").exists()]


def parse_line(line, repo_name):
    parts = line.split(SEP)
    if len(parts) != 4:
        return None
    sha, ts, author, subject = parts
    return {"repo": repo_name, "sha": sha, "timestamp": ts, "author": author, "subject": subject}


class CommitsClient:
    def __init__(self, address, key, http, runner=subprocess.run):
        self.address, self.runner = address, runner   # key and http unused: local only

    def roots(self, flags):
        if flags:
            return list(flags)
        if self.address and self.address != "local":
            return [r for r in self.address.split(os.pathsep) if r]
        return [str(cc.get_path("repos"))]

    def log_repo(self, repo, since):
        try:
            r = self.runner(["git", "-C", str(repo), "log", "--since=" + since,
                             "--pretty=format:" + PRETTY, "--no-merges", "-n%d" % MAX_PER_REPO],
                            capture_output=True, text=True, timeout=GIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            return [], cc.LogReason.API_TIMEOUT
        except OSError:
            return [], cc.LogReason.API_5XX
        if r.returncode != 0:
            return [], cc.LogReason.API_4XX
        out = []
        for line in r.stdout.splitlines():
            rec = parse_line(line, repo.name)
            if rec is None:
                return [], cc.LogReason.SCHEMA_INVALID
            out.append(rec)
        return out, cc.LogReason.API_OK

    def collect(self, roots, since):
        """Return (commits, result, reason). The first bad reason is kept."""
        allc, bad, ok = [], None, 0
        for root in roots:
            repos = resolve_repos(root)
            if not repos:
                bad = bad or cc.LogReason.API_5XX
                continue
            for repo in repos:
                commits, reason = self.log_repo(repo, since)
                if reason != cc.LogReason.API_OK:
                    bad = bad or reason
                    continue
                allc.extend(commits)
                ok += 1
        if bad is None:
            return allc, cc.LogResult.SUCCESS, cc.LogReason.API_OK
        if ok == 0:
            return [], cc.LogResult.FAILED, bad
        return allc, cc.LogResult.DEGRADED, bad


register(NAME, lambda address, key, http: CommitsClient(address, key, http))


def main(argv=None, runner=None):
    ap = argparse.ArgumentParser(description="Collect recent commits to the cache.")
    ap.add_argument("--root", action="append", default=[], help="repo folder (repeat)")
    ap.add_argument("--since", default="24 hours ago")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    client = ensure(NAME)
    if runner:
        client.runner = runner
    start = cc.now_iso()
    tally = {}
    if args.dry_run:
        clean, rejected = cc.scrub(DRY_RUN_FIXTURE, source="commits")
        res, reason = cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK
    else:
        commits, cres, creason = client.collect(client.roots(args.root), args.since)
        if cres == cc.LogResult.FAILED:
            clean, res, reason, rejected = [], cres, creason, 0
        else:
            clean, rejected = cc.scrub(commits, source="commits")
            clean = cc.redact_records(clean, tally)
            if commits and not clean:
                clean, res, reason = [], cc.LogResult.DEGRADED, cc.LogReason.PHI_REJECTED_ALL
            elif cres == cc.LogResult.DEGRADED:
                res, reason = cres, creason
            elif rejected:
                res, reason = cc.LogResult.DEGRADED, cc.LogReason.PHI_REJECTED
            else:
                res, reason = cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK
    return cc.finish(SCRIPT_NAME, "commits", start, clean, res, reason, rejected, tally)


if __name__ == "__main__":
    sys.exit(run_cli(main) or 0)
