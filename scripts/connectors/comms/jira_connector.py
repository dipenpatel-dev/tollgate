#!/usr/bin/env python3
"""Tracker connector `jira`: pull recently updated tickets into the cache.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Write jira.json (the daily brief seam) from a Jira style search API.
Change log:
  - First version, ported from the Jira cache puller. The site address, the
    login and the query now come from the connector entry and flags.

  jira_connector.py [--jql QUERY] [--dry-run]

Address: the site base URL, set at first use. Key: either `login:token`
(sent as Basic auth) or a single token (sent as Bearer). The key lives in the
secret store only. The query is a flag; the default is "mine, updated in the
last day". Ticket titles are never printed or logged, only counts.
Pagination follows nextPageToken until isLast, with a page and a size cap.
"""
import argparse
import base64
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from connectors.registry import register, ensure, run_cli  # noqa: E402
from connectors.comms import comms_common as cc  # noqa: E402

NAME = "jira"
SCRIPT_NAME = "jira_pull"
SEARCH_PATH = "/rest/api/3/search/jql"
DEFAULT_JQL = ("(assignee = currentUser() OR reporter = currentUser()) "
               "AND updated >= -1d ORDER BY updated DESC")
FIELDS = ["summary", "status", "priority", "updated", "assignee", "reporter"]
PAGE_SIZE = 50
MAX_PAGES = 10
MAX_TOTAL = 500
TIMEOUT = 15

DRY_RUN_FIXTURE = [
    {"key": "FIXTURE-1", "summary": "Dry run fixture one", "status": "In Progress",
     "priority": "Medium", "updated": "2026-01-01T08:00:00.000+0000", "assignee": "Fixture User"},
    {"key": "FIXTURE-2", "summary": "Dry run fixture two", "status": "To Do",
     "priority": "High", "updated": "2026-01-01T07:30:00.000+0000", "assignee": "Fixture User"},
]


def project_issue(raw):
    """Lean projection of one issue; None on a wrong shape (a schema failure).

    Drops email addresses and account ids; keeps display names only.
    """
    if not isinstance(raw, dict) or "key" not in raw or not isinstance(raw.get("fields"), dict):
        return None
    f = raw["fields"]
    parts = {}
    for k in ("status", "priority", "assignee"):
        v = f.get(k)
        if v is not None and not isinstance(v, dict):
            return None
        parts[k] = v or {}
    return {"key": raw["key"], "summary": f.get("summary", ""),
            "status": parts["status"].get("name", ""),
            "priority": parts["priority"].get("name", ""),
            "updated": f.get("updated", ""),
            "assignee": parts["assignee"].get("displayName", "")}


class JiraClient:
    def __init__(self, address, key, http):
        self.address, self.key, self.http = address.rstrip("/"), key, http

    def _auth(self):
        if ":" in self.key:
            return "Basic " + base64.b64encode(self.key.encode()).decode("ascii")
        return "Bearer " + self.key

    def _page(self, jql, token):
        body = {"jql": jql, "maxResults": PAGE_SIZE, "fields": FIELDS}
        if token:
            body["nextPageToken"] = token
        resp, reason = cc.call(
            self.http, "POST", self.address + SEARCH_PATH, timeout=TIMEOUT,
            headers={"Authorization": self._auth(), "Accept": "application/json",
                     "Content-Type": "application/json"},
            data=json.dumps(body))
        if resp is None:
            return None, reason
        data = cc.body_of(resp)
        if (not isinstance(data, dict) or not isinstance(data.get("issues"), list)
                or not isinstance(data.get("isLast"), bool)):
            return None, cc.LogReason.SCHEMA_INVALID
        return data, cc.LogReason.API_OK

    def fetch(self, jql=DEFAULT_JQL):
        """Return (issues, result, reason). Caps give DEGRADED, not failure."""
        issues, token = [], None
        for _ in range(MAX_PAGES):
            page, reason = self._page(jql, token)
            if page is None:
                return [], cc.LogResult.FAILED, reason
            for raw in page["issues"]:
                rec = project_issue(raw)
                if rec is None:
                    return [], cc.LogResult.FAILED, cc.LogReason.SCHEMA_INVALID
                issues.append(rec)
                if len(issues) >= MAX_TOTAL:
                    return issues, cc.LogResult.DEGRADED, cc.LogReason.API_OK
            if page["isLast"]:
                return issues, cc.LogResult.SUCCESS, cc.LogReason.API_OK
            token = page.get("nextPageToken")
            if not isinstance(token, str) or not token:
                return [], cc.LogResult.FAILED, cc.LogReason.SCHEMA_INVALID
        return issues, cc.LogResult.DEGRADED, cc.LogReason.API_OK


register(NAME, lambda address, key, http: JiraClient(address, key, http))


def classify(issues, fetch_result, fetch_reason):
    """Apply the privacy filter and decide the final result. Returns 4 values."""
    clean, rejected = cc.scrub(issues, source="jira")
    if issues and not clean:
        return [], cc.LogResult.DEGRADED, cc.LogReason.PHI_REJECTED_ALL, rejected
    if fetch_result == cc.LogResult.DEGRADED:
        return clean, cc.LogResult.DEGRADED, fetch_reason, rejected
    if rejected:
        return clean, cc.LogResult.DEGRADED, cc.LogReason.PHI_REJECTED, rejected
    return clean, cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK, rejected


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pull recent tracker tickets to the cache.")
    ap.add_argument("--jql", default=DEFAULT_JQL, help="search query")
    ap.add_argument("--dry-run", action="store_true", help="write a fixture, no network")
    args = ap.parse_args(argv)
    client = ensure(NAME)
    start = cc.now_iso()
    tally = {}
    if args.dry_run:
        clean, rejected = cc.scrub(DRY_RUN_FIXTURE, source="jira")
        res, reason = cc.LogResult.SUCCESS, cc.LogReason.WRITE_OK
    else:
        issues, fres, freason = client.fetch(args.jql)
        if fres == cc.LogResult.FAILED:
            clean, res, reason, rejected = [], fres, freason, 0
        else:
            clean, res, reason, rejected = classify(issues, fres, freason)
            clean = cc.redact_records(clean, tally)
    return cc.finish(SCRIPT_NAME, "jira", start, clean, res, reason, rejected, tally)


if __name__ == "__main__":
    sys.exit(run_cli(main) or 0)
