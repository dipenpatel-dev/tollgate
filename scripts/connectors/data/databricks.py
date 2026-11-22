#!/usr/bin/env python3
"""Databricks connector: read-only queries, schema export, notebook scan source.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Plug a Databricks workspace into the chart data seam and the
         notebook scan seam, and export table definitions. Read only.
Change log:
  - First version: query guard, warehouse data source, workspace notebook
    source, schema export, command line.

  databricks.py status
  databricks.py schemas --schema CATALOG.SCHEMA [--schema ...] [--out DIR]
  databricks.py scan-notebooks --path WORKSPACE_PATH [--path ...]
  databricks.py check --warehouse ID [--catalog NAME]

The address and key come from the connector's first-use flow (`connect.py on
databricks`). The warehouse and catalog come from flags, never from code.
Only a single SELECT, SHOW or DESCRIBE statement is ever sent. Results are
never logged: only counts are.
"""
import argparse
import base64
import json
import logging
import pathlib
import re
import sys
from datetime import date
from urllib.parse import urlencode, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from connectors import registry
from chart.data_source import DataSource, parse_sort, validate_identifier
from qa.scan_notebooks import NotebookSource, scan_source
from connectors.comms import comms_common as cc

NAME = "databricks"
MAX_ROWS = 500
ALLOWED_FIRST_WORDS = ("SELECT", "SHOW", "DESCRIBE")
COL_NAME_WIDTH = 40
COL_TYPE_WIDTH = 30
LABEL_LENGTH = 24
DATE_LINE_PREFIX = "-- extracted:"
LOOPBACK = ("127.0.0.1", "localhost", "::1")

log = logging.getLogger("tollgate.databricks")


class DatabricksError(Exception):
    """Raised for a refused statement or a failed call. Never holds row data."""


# ---- query guard ----

def check_read_only(statement):
    """Return the statement without a trailing semicolon, or raise.

    Allowed: exactly one SELECT, SHOW or DESCRIBE. Refused: a second
    statement, any comment marker outside a quoted string, any other first
    word. Quoted text (single, double, backtick) is skipped while checking.
    """
    if not isinstance(statement, str) or not statement.strip():
        raise DatabricksError("refused: empty statement")
    text = statement.strip()
    quote = None
    i, n = 0, len(text)
    cut = None
    while i < n:
        c = text[i]
        if quote:
            if c == "\\" and quote != "`":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in ("'", '"', "`"):
            quote = c
        elif c == ";":
            if text[i + 1:].strip():
                raise DatabricksError("refused: more than one statement")
            cut = i
            break
        elif text.startswith("--", i) or text.startswith("/*", i):
            raise DatabricksError("refused: comments are not allowed in a statement")
        i += 1
    if quote:
        raise DatabricksError("refused: unterminated quote")
    body = text[:cut] if cut is not None else text
    words = body.split(None, 1)
    first = words[0].upper() if words else ""
    if first not in ALLOWED_FIRST_WORDS:
        raise DatabricksError("refused: only SELECT, SHOW or DESCRIBE is allowed")
    return body.strip()


def _check_address(address):
    u = urlparse(address or "")
    if u.scheme == "https" and u.hostname:
        return address.rstrip("/")
    if u.scheme == "http" and u.hostname in LOOPBACK:
        return address.rstrip("/")
    raise registry.NotSetUp("%s: the address must start with https:// "
                            "(http is only allowed for 127.0.0.1)" % NAME)


# ---- client ----

class DatabricksClient:
    """Thin REST client. Every request goes through the given http object."""

    def __init__(self, address, key, http, warehouse=None, catalog=None):
        self.address = _check_address(address)
        self._key = key
        self.http = http
        self.warehouse = warehouse
        self.catalog = catalog

    def _headers(self):
        return {"Authorization": "Bearer " + self._key,
                "Content-Type": "application/json"}

    def _call(self, method, path, payload=None):
        data = json.dumps(payload) if payload is not None else None
        resp = self.http.request(method, self.address + path,
                                 headers=self._headers(), data=data)
        status = resp.get("status", 0)
        if status >= 400:
            raise DatabricksError("%s %s failed: HTTP %s" % (method, path.split("?")[0], status))
        body = resp.get("body")
        if isinstance(body, (str, bytes)):
            try:
                body = json.loads(body) if body else {}
            except ValueError:
                raise DatabricksError("unreadable response from the workspace")
        return body or {}

    # -- SQL --

    def query(self, statement, params=None, limit=MAX_ROWS):
        """Run one read-only statement. Returns (columns, rows, truncated).

        params maps a name to a text value and is sent as bound parameters
        (:name in the statement). Rows are capped at MAX_ROWS.
        """
        body_sql = check_read_only(statement)
        if not self.warehouse:
            raise registry.NotSetUp("%s: pass --warehouse ID" % NAME)
        cap = max(1, min(int(limit or MAX_ROWS), MAX_ROWS))
        payload = {"warehouse_id": self.warehouse, "statement": body_sql,
                   "wait_timeout": "30s", "on_wait_timeout": "CANCEL",
                   "disposition": "INLINE", "format": "JSON_ARRAY",
                   "row_limit": cap + 1}
        if self.catalog:
            payload["catalog"] = self.catalog
        if params:
            payload["parameters"] = [
                {"name": validate_identifier(k, "parameter name"),
                 "value": None if v is None else str(v), "type": "STRING"}
                for k, v in params.items()]
        out = self._call("POST", "/api/2.0/sql/statements", payload)
        state = (out.get("status") or {}).get("state")
        if state != "SUCCEEDED":
            raise DatabricksError("statement did not finish: state %s" % state)
        cols = [c.get("name") for c in
                ((out.get("manifest") or {}).get("schema") or {}).get("columns") or []]
        rows = [dict(zip(cols, r)) for r in (out.get("result") or {}).get("data_array") or []]
        truncated = len(rows) > cap or bool((out.get("manifest") or {}).get("truncated"))
        rows = rows[:cap]
        log.info("query done: %d rows, truncated=%s", len(rows), truncated)
        return cols, rows, truncated

    # -- Unity Catalog --

    def list_tables(self, catalog, schema):
        tables, token = [], None
        while True:
            q = {"catalog_name": catalog, "schema_name": schema}
            if token:
                q["page_token"] = token
            out = self._call("GET", "/api/2.1/unity-catalog/tables?" + urlencode(q))
            tables.extend(out.get("tables") or [])
            token = out.get("next_page_token")
            if not token:
                return tables

    # -- workspace --

    def export_notebook(self, path):
        """Return the notebook as a dict, or {"_unreadable": True}."""
        q = urlencode({"path": path, "format": "JUPYTER"})
        try:
            out = self._call("GET", "/api/2.0/workspace/export?" + q)
            return json.loads(base64.b64decode(out.get("content", "")).decode("utf-8"))
        except (DatabricksError, ValueError):
            return {"_unreadable": True}


# ---- chart data seam ----

def _table_ref(table):
    parts = table.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Table must be name, schema.name or catalog.schema.name.")
    return ".".join("`" + validate_identifier(p, "table") + "`" for p in parts)


def _q(name, context):
    return "`" + validate_identifier(name, context) + "`"


class WarehouseSource(DataSource):
    """Reads tables through a SQL warehouse. Bound parameters, read only."""

    def __init__(self, client):
        self.client = client
        self.label = "databricks"
        self.truncated = False

    def _ids(self, ids):
        ids = list(dict.fromkeys(ids))
        marks = ", ".join(":p%d" % i for i in range(len(ids)))
        return ids, marks, {"p%d" % i: v for i, v in enumerate(ids)}

    def fetch_rows(self, table, id_column, columns, ids, sort=None, limit=None):
        ids, marks, params = self._ids(ids)
        if not ids:
            return {}
        selects = ", ".join("%s AS %s" % (_q(raw, "column"), _q(var, "variable"))
                            for raw, var in columns.items())
        order = ""
        parsed = parse_sort(sort)
        if parsed:
            reverse = {v: k for k, v in columns.items()}
            if parsed[0] not in reverse:
                raise ValueError("Sort variable is not in the column map.")
            order = " ORDER BY %s %s" % (_q(reverse[parsed[0]], "sort"), parsed[1])
        sql = ("SELECT CAST(%s AS STRING) AS `_id`, %s FROM %s WHERE CAST(%s AS STRING) IN (%s)%s"
               % (_q(id_column, "id column"), selects, _table_ref(table),
                  _q(id_column, "id column"), marks, order))
        _, rows, self.truncated = self.client.query(sql, params, MAX_ROWS)
        out = {}
        for row in rows:
            key = str(row.pop("_id"))
            bucket = out.setdefault(key, [])
            if not limit or len(bucket) <= limit:   # limit + 1 shows a cut
                bucket.append(row)
        return out

    def fetch_summary(self, table, id_column, columns, ids):
        ids, marks, params = self._ids(ids)
        if not ids:
            return {}
        selects = ", ".join(_q(c, "column") for c in columns)
        sql = ("SELECT CAST(%s AS STRING) AS `_id`, %s FROM %s WHERE CAST(%s AS STRING) IN (%s)"
               % (_q(id_column, "id column"), selects, _table_ref(table),
                  _q(id_column, "id column"), marks))
        _, rows, self.truncated = self.client.query(sql, params, MAX_ROWS)
        return {str(r.pop("_id")): r for r in rows}


# ---- notebook scan seam ----

class WorkspaceNotebookSource(NotebookSource):
    """Exports notebooks by workspace path and yields them to the scanner."""

    def __init__(self, client, paths):
        self.client = client
        self.paths = list(paths)

    def iter_notebooks(self):
        for path in self.paths:
            label = path.rstrip("/").rsplit("/", 1)[-1][:LABEL_LENGTH]
            yield label, self.client.export_notebook(path)


# ---- schema export ----

def _render_column(col):
    type_text = str(col.get("type_text", col.get("type_name", "STRING"))).upper()
    line = "    %-*s %-*s" % (COL_NAME_WIDTH, col.get("name", ""), COL_TYPE_WIDTH, type_text)
    if col.get("nullable") is False:
        line += " NOT NULL"
    if col.get("comment"):
        line += " COMMENT '%s'" % col["comment"].replace("'", "''")
    return line


def render_ddl(table, today=None):
    cat, sch, name = (table.get("catalog_name", ""), table.get("schema_name", ""),
                      table.get("name", ""))
    cols = sorted(table.get("columns") or [], key=lambda c: c.get("position", 0))
    lines = ["-- catalog:   " + cat, "-- schema:    " + sch, "-- table:     " + name,
             "-- type:      " + str(table.get("table_type", "MANAGED")),
             "%s %s" % (DATE_LINE_PREFIX, today or date.today().isoformat())]
    if table.get("comment"):
        lines.append("-- comment:   " + table["comment"])
    lines += ["", "CREATE TABLE IF NOT EXISTS %s.%s.%s (" % (cat, sch, name),
              ",\n".join(_render_column(c) for c in cols), ");", ""]
    return "\n".join(lines)


def _body(ddl):
    return "\n".join(l for l in ddl.splitlines() if not l.startswith(DATE_LINE_PREFIX))


def write_if_changed(path, ddl):
    """Write only when the definition changed (the date line is ignored)."""
    if path.exists() and _body(path.read_text()) == _body(ddl):
        return False
    path.write_text(ddl)
    return True


def export_schemas(client, targets, out_root, tally=None):
    """targets: list of (catalog, schema). Returns (written, unchanged, errors).

    Secrets in a table or column comment are redacted before the write; `tally`
    (a dict of label -> count) is updated when given.
    """
    tally = tally if tally is not None else {}
    written = unchanged = 0
    errors = []
    for catalog, schema in targets:
        validate_identifier(catalog, "catalog")
        validate_identifier(schema, "schema")
        try:
            tables = client.list_tables(catalog, schema)
        except DatabricksError:
            errors.append("%s.%s" % (catalog, schema))
            continue
        folder = pathlib.Path(out_root) / catalog / schema
        folder.mkdir(parents=True, exist_ok=True)
        log.info("%s.%s: %d tables", catalog, schema, len(tables))
        for t in tables:
            name = t.get("name", "")
            if not re.match(r"^[A-Za-z0-9_]+$", name):
                errors.append("%s.%s (name)" % (catalog, schema))
                continue
            if write_if_changed(folder / (name + ".sql"), cc.redact_text(render_ddl(t), tally)):
                written += 1
            else:
                unchanged += 1
    return written, unchanged, errors


# ---- connector registration and command line ----

def _factory(address, key, http):
    return DatabricksClient(address, key, http)


registry.register(NAME, _factory)


def _client(args):
    c = registry.ensure(NAME)
    c.warehouse = getattr(args, "warehouse", None)
    c.catalog = getattr(args, "catalog", None)
    return c


def main(argv=None):
    p = argparse.ArgumentParser(prog="databricks.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    ck = sub.add_parser("check")
    ck.add_argument("--warehouse", required=True)
    ck.add_argument("--catalog")
    sc = sub.add_parser("schemas")
    sc.add_argument("--schema", action="append", required=True, metavar="CATALOG.SCHEMA")
    sc.add_argument("--out")
    nb = sub.add_parser("scan-notebooks")
    nb.add_argument("--path", action="append", required=True)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    client = _client(args)
    try:
        if args.cmd == "status":
            print("databricks: on (%s)" % client.address)
        elif args.cmd == "check":
            _, rows, _ = client.query("SELECT 1 AS ok")
            print("databricks: reachable, %d row" % len(rows))
        elif args.cmd == "schemas":
            from core.paths import get_path
            targets = [tuple(s.split(".", 1)) for s in args.schema]
            if any(len(t) != 2 for t in targets):
                raise DatabricksError("use --schema CATALOG.SCHEMA")
            out = pathlib.Path(args.out) if args.out else get_path("references") / "schemas"
            tally = {}
            w, u, e = export_schemas(client, targets, out, tally)
            print("schemas: %d written, %d unchanged, %d errors, %s" % (
                w, u, len(e), cc.secrets_line(tally)))
            return 1 if e else 0
        else:
            for line in scan_source(WorkspaceNotebookSource(client, args.path)):
                print(line)
    except DatabricksError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(registry.run_cli(main) or 0)
