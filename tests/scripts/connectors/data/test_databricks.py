#!/usr/bin/env python3
"""Databricks connector tests: CON-01 to CON-04, query guard, sources, export.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Prove the connector is off until first use, only sends read-only
         single statements, binds parameters, caps rows and logs counts only.
Change log:
  - First version.
"""
import base64
import contextlib
import io
import json
import logging
import os
import pathlib
import sys
import tempfile
import unittest
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "tests" / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from connector_helpers import MockClient, FakeSecretStore, assert_no_network
from throwaway_home import throwaway_home
from connectors import registry, connect
from connectors.data import databricks as dbx

ADDRESS = "https://ws.invalid"


class Stub(MockClient):
    """Mock http that answers the statements, export and tables calls."""

    def __init__(self, rows=None, state="SUCCEEDED", tables=None, notebooks=None):
        super().__init__()
        self.rows, self.state = rows or [], state
        self.tables, self.notebooks = tables or [], notebooks or {}

    def request(self, method, url, **kw):
        self.calls.append({"method": method, "url": url, "kwargs": kw})
        if url.endswith("/api/2.0/sql/statements"):
            sent = json.loads(kw["data"])
            cap = sent["row_limit"]
            rows = self.rows[:cap]
            body = {"status": {"state": self.state},
                    "manifest": {"schema": {"columns": [{"name": n} for n in
                                 (list(rows[0]) if rows else ["ok"])]}},
                    "result": {"data_array": [list(r.values()) for r in rows]}}
            return {"status": 200, "body": json.dumps(body)}
        if "/unity-catalog/tables" in url:
            return {"status": 200, "body": json.dumps({"tables": self.tables})}
        if "/workspace/export" in url:
            for path, nb in self.notebooks.items():
                if ("path=" + path.replace("/", "%2F")) in url:
                    enc = base64.b64encode(json.dumps(nb).encode()).decode()
                    return {"status": 200, "body": json.dumps({"content": enc})}
            return {"status": 404, "body": ""}
        return {"status": 404, "body": ""}


def client(stub, warehouse="wh1", catalog="cat1"):
    return dbx.DatabricksClient(ADDRESS, "k", stub, warehouse, catalog)


class Base(unittest.TestCase):
    def setUp(self):
        self.cm = throwaway_home()
        self.home, self.env = self.cm.__enter__()
        self._old = os.environ.copy()
        os.environ.update(self.env)
        self.store = FakeSecretStore()
        self.mock = Stub()
        registry.set_store(self.store)
        registry.set_http_factory(lambda: self.mock)
        registry.register("databricks", dbx._factory)
        self.secret = "tgfake-" + uuid.uuid4().hex

    def tearDown(self):
        registry.set_store(None)
        registry.set_http_factory(None)
        os.environ.clear()
        os.environ.update(self._old)
        self.cm.__exit__(None, None, None)

    def turn_on(self):
        os.environ["TG_TEST_KEY"] = self.secret
        try:
            return connect.main(["on", "databricks", "--address", ADDRESS,
                                 "--key-from-env", "TG_TEST_KEY"], env=self.env)
        finally:
            del os.environ["TG_TEST_KEY"]

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = dbx.registry.run_cli(lambda: dbx.main(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()


class TestCon(Base):
    def test_con01_not_set_up(self):
        with assert_no_network():
            code, _, err = self.run_cli(["check", "--warehouse", "w"])
        self.assertNotIn(code, (0, None))
        self.assertIn("databricks: not set up", err)
        self.assertEqual(self.mock.calls, [])

    def test_con02_first_use_secret_nowhere_on_disk(self):
        with assert_no_network():
            self.assertEqual(self.turn_on(), 0)
        self.assertTrue(self.store.asked_to_store("databricks"))
        needle = self.secret.encode()
        for root in (ROOT, pathlib.Path(self.home)):
            for dp, dn, fn in os.walk(root):
                dn[:] = [d for d in dn if d != ".git"]
                for f in fn:
                    try:
                        with open(os.path.join(dp, f), "rb") as fh:
                            data = fh.read()
                    except OSError:
                        continue
                    self.assertNotIn(needle, data)

    def test_con03_on_reaches_client_after_restart(self):
        self.turn_on()
        registry._FACTORIES.clear()
        registry.register("databricks", dbx._factory)
        self.mock.rows = [{"ok": "1"}]
        code, out, _ = self.run_cli(["check", "--warehouse", "wh1"])
        self.assertEqual(code, 0)
        self.assertIn("reachable", out)
        self.assertEqual(len(self.mock.calls), 1)
        sent = self.mock.calls[0]
        self.assertEqual(sent["url"], ADDRESS + "/api/2.0/sql/statements")
        self.assertEqual(sent["kwargs"]["headers"]["Authorization"], "Bearer " + self.secret)
        self.assertEqual(json.loads(sent["kwargs"]["data"])["warehouse_id"], "wh1")

    def test_con04_off_returns_to_not_set_up(self):
        self.turn_on()
        self.assertEqual(connect.main(["off", "databricks"], env=self.env), 0)
        with assert_no_network():
            code, _, err = self.run_cli(["check", "--warehouse", "w"])
        self.assertNotIn(code, (0, None))
        self.assertIn("databricks: not set up", err)
        self.assertEqual(self.mock.calls, [])


class TestGuard(unittest.TestCase):
    def test_allowed(self):
        for s in ("SELECT 1", "select a from t where x = :p;", "SHOW TABLES IN a.b",
                  "DESCRIBE a.b.c", "SELECT ';' AS semi", "SELECT 'a--b' AS x"):
            dbx.check_read_only(s)

    def test_refused(self):
        for s in ("DROP TABLE t", "DELETE FROM t", "INSERT INTO t VALUES (1)",
                  "UPDATE t SET a=1", "SELECT 1; DROP TABLE t", "SELECT 1; SELECT 2",
                  "SELECT 1 -- x", "SELECT /* x */ 1", "WITH a AS (SELECT 1) SELECT * FROM a",
                  "", "   ", "SELECT 'open", "CREATE TABLE t (a INT)", "MERGE INTO t"):
            with self.assertRaises(dbx.DatabricksError, msg=s):
                dbx.check_read_only(s)

    def test_refused_statement_makes_no_call(self):
        stub = Stub()
        with self.assertRaises(dbx.DatabricksError):
            client(stub).query("DROP TABLE t")
        self.assertEqual(stub.calls, [])

    def test_address_must_be_https_or_loopback(self):
        with self.assertRaises(registry.NotSetUp):
            dbx.DatabricksClient("http://example.invalid", "k", Stub())
        dbx.DatabricksClient("http://127.0.0.1:9", "k", Stub())


class TestQuery(unittest.TestCase):
    def test_bound_parameters_and_no_value_in_sql(self):
        stub = Stub(rows=[{"a": "1"}])
        client(stub).query("SELECT a FROM t WHERE id = :p0", {"p0": "SECRET-ID-77"})
        sent = json.loads(stub.calls[0]["kwargs"]["data"])
        self.assertNotIn("SECRET-ID-77", sent["statement"])
        self.assertEqual(sent["parameters"][0]["value"], "SECRET-ID-77")
        self.assertEqual(sent["catalog"], "cat1")

    def test_row_cap_500(self):
        stub = Stub(rows=[{"a": str(i)} for i in range(900)])
        cols, rows, truncated = client(stub).query("SELECT a FROM t", limit=10000)
        self.assertEqual(len(rows), 500)
        self.assertTrue(truncated)
        self.assertEqual(json.loads(stub.calls[0]["kwargs"]["data"])["row_limit"], 501)

    def test_not_finished_raises_without_data(self):
        with self.assertRaises(dbx.DatabricksError) as cm:
            client(Stub(state="FAILED")).query("SELECT 1")
        self.assertIn("FAILED", str(cm.exception))

    def test_missing_warehouse(self):
        with self.assertRaises(registry.NotSetUp):
            client(Stub(), warehouse=None).query("SELECT 1")

    def test_logs_counts_only(self):
        stub = Stub(rows=[{"a": "VALUE-XYZ-123"}])
        with self.assertLogs("tollgate.databricks", level="INFO") as cm:
            client(stub).query("SELECT a FROM t")
        text = "\n".join(cm.output)
        self.assertIn("1 rows", text)
        self.assertNotIn("VALUE-XYZ-123", text)


class TestWarehouseSource(unittest.TestCase):
    def test_fetch_rows_shape_and_binding(self):
        stub = Stub(rows=[{"_id": "7", "v": "x"}, {"_id": "7", "v": "y"},
                          {"_id": "8", "v": "z"}])
        src = dbx.WarehouseSource(client(stub))
        out = src.fetch_rows("sch.tbl", "pid", {"raw_v": "v"}, ["7", "8", "7"], sort="v DESC", limit=1)
        self.assertEqual(out, {"7": [{"v": "x"}, {"v": "y"}], "8": [{"v": "z"}]})
        sent = json.loads(stub.calls[0]["kwargs"]["data"])
        self.assertNotIn("'7'", sent["statement"])
        self.assertEqual({p["value"] for p in sent["parameters"]}, {"7", "8"})
        self.assertIn("ORDER BY `raw_v` DESC", sent["statement"])
        self.assertIn("`sch`.`tbl`", sent["statement"])

    def test_unsafe_identifiers_refused_before_any_call(self):
        stub = Stub()
        src = dbx.WarehouseSource(client(stub))
        for bad in ({"table": "t; DROP", "id_column": "id"},
                    {"table": "t", "id_column": "id`x"}):
            with self.assertRaises(ValueError):
                src.fetch_rows(bad["table"], bad["id_column"], {"a": "a"}, ["1"])
        with self.assertRaises(ValueError):
            src.fetch_rows("t", "id", {"a`b": "a"}, ["1"])
        self.assertEqual(stub.calls, [])

    def test_empty_ids_no_call(self):
        stub = Stub()
        self.assertEqual(dbx.WarehouseSource(client(stub)).fetch_rows("t", "id", {"a": "a"}, []), {})
        self.assertEqual(stub.calls, [])

    def test_fetch_summary(self):
        stub = Stub(rows=[{"_id": "7", "a": "1"}])
        out = dbx.WarehouseSource(client(stub)).fetch_summary("t", "id", ["a"], ["7"])
        self.assertEqual(out, {"7": {"a": "1"}})


class TestNotebooksAndSchemas(unittest.TestCase):
    def test_notebook_source_feeds_scanner(self):
        nb = {"cells": [{"cell_type": "code", "source": ["x = 1\n", "a@b.co\n"], "outputs": []}]}
        stub = Stub(notebooks={"/Shared/nb1": nb})
        src = dbx.WorkspaceNotebookSource(client(stub), ["/Shared/nb1", "/Shared/gone"])
        report = "\n".join(dbx.scan_source(src))
        self.assertIn("nb1", report)
        self.assertIn("email", report)
        self.assertIn("gone: not readable", report)
        self.assertNotIn("a@b.co", report)

    def test_render_ddl_and_write_if_changed(self):
        t = {"catalog_name": "c", "schema_name": "s", "name": "t",
             "columns": [{"name": "b", "type_text": "int", "position": 1, "nullable": False},
                         {"name": "a", "type_text": "string", "position": 0, "comment": "it's"}]}
        d1 = dbx.render_ddl(t, today="2000-01-01")
        self.assertLess(d1.index(" a "), d1.index(" b "))
        self.assertIn("NOT NULL", d1)
        self.assertIn("COMMENT 'it''s'", d1)
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "t.sql"
            self.assertTrue(dbx.write_if_changed(p, d1))
            self.assertFalse(dbx.write_if_changed(p, dbx.render_ddl(t, today="2001-02-02")))
            t["columns"].append({"name": "c", "type_text": "int", "position": 2})
            self.assertTrue(dbx.write_if_changed(p, dbx.render_ddl(t)))

    def test_export_schemas_redacts_secrets_in_comments_and_counts_them(self):
        tok = "xo" + "xb-" + "1234567890" + "-" + "abcdefghij"
        t = {"catalog_name": "c", "schema_name": "s", "name": "tbl", "comment": "owner key " + tok,
             "columns": [{"name": "a", "type_text": "string", "position": 0}]}
        stub = Stub(tables=[t])
        tally = {}
        with tempfile.TemporaryDirectory() as tmp:
            w, u, e = dbx.export_schemas(client(stub), [("c", "s")], tmp, tally)
            self.assertEqual((w, u, len(e)), (1, 0, 0))
            text = (pathlib.Path(tmp) / "c" / "s" / "tbl.sql").read_text()
            self.assertIn("-- comment:   owner key [REDACTED:SLACK_TOKEN]", text)
            self.assertNotIn(tok, text)
            self.assertIn("CREATE TABLE IF NOT EXISTS c.s.tbl", text)
            self.assertEqual(tally, {"SLACK_TOKEN": 1})
            w2, u2, e2 = dbx.export_schemas(client(stub), [("c", "s")], tmp, {})
            self.assertEqual((w2, u2), (0, 1))

    def test_export_schemas(self):
        t = {"catalog_name": "c", "schema_name": "s", "name": "tbl", "columns": []}
        bad = {"catalog_name": "c", "schema_name": "s", "name": "../evil"}
        stub = Stub(tables=[t, bad])
        with tempfile.TemporaryDirectory() as tmp:
            w, u, e = dbx.export_schemas(client(stub), [("c", "s")], tmp)
            self.assertEqual((w, u, len(e)), (1, 0, 1))
            self.assertTrue((pathlib.Path(tmp) / "c" / "s" / "tbl.sql").exists())
            self.assertEqual(sorted(p.name for p in pathlib.Path(tmp).rglob("*.sql")), ["tbl.sql"])


if __name__ == "__main__":
    unittest.main()
