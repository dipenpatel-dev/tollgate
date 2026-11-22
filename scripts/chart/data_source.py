"""
module_name: data_source.py
description: The data source seam for the report generator. A small interface plus two
             sample implementations (CSV folder, SQLite file) used by tests and demos.
             Real database connectors plug in here later by implementing the same two methods.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Interface, identifier check, CSV and SQLite implementations.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sqlite3

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")
SORT_DIRECTIONS = ("ASC", "DESC")


def validate_identifier(value: str, context: str) -> str:
    """Allow letters, digits and underscores only. Raises ValueError otherwise."""
    if not isinstance(value, str) or not SAFE_IDENTIFIER.match(value):
        raise ValueError(f"Unsafe identifier in {context}. Only letters, digits and underscores are allowed.")
    return value


def parse_sort(sort):
    """Turn 'name DESC' into (name, 'DESC'). None stays None."""
    if not sort:
        return None
    parts = sort.split()
    name = validate_identifier(parts[0], "sort column")
    direction = parts[1].upper() if len(parts) > 1 else "ASC"
    if direction not in SORT_DIRECTIONS:
        raise ValueError("Sort direction must be ASC or DESC.")
    return name, direction


class DataSource:
    """What the report generator needs from any data source.

    A connector (a real database, an API) subclasses this and fills in both methods.
    Rows come back keyed by the id value as text, and each row is a dict keyed by the
    variable name (the right side of the column map).
    """

    label = "unnamed"

    def fetch_rows(self, table, id_column, columns, ids, sort=None, limit=None):
        """Return {id: [row, ...]} for a table. columns maps raw column to variable name."""
        raise NotImplementedError

    def fetch_summary(self, table, id_column, columns, ids):
        """Return {id: row} for a one-row-per-id table. columns is a list of column names."""
        raise NotImplementedError


def _sorted(rows, sort):
    parsed = parse_sort(sort)
    if parsed is None:
        return rows
    name, direction = parsed
    return sorted(rows, key=lambda r: (r.get(name) in (None, ""), str(r.get(name) or "")), reverse=(direction == "DESC"))


class CsvSource(DataSource):
    """Reads <folder>/<table>.csv. Good for tests and small exports."""

    def __init__(self, folder):
        self.folder = pathlib.Path(folder)
        self.label = "csv"

    def _read(self, table):
        validate_identifier(table, "table")
        path = self.folder / f"{table}.csv"
        if not path.is_file():
            return []
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def fetch_rows(self, table, id_column, columns, ids, sort=None, limit=None):
        validate_identifier(id_column, "id column")
        wanted = set(ids)
        grouped = {}
        for row in self._read(table):
            key = (row.get(id_column) or "").strip()
            if key in wanted:
                grouped.setdefault(key, []).append({var: row.get(raw) for raw, var in columns.items()})
        out = {}
        for key, rows in grouped.items():
            rows = _sorted(rows, sort)
            # limit + 1 rows let the caller see that rows were cut
            out[key] = rows[:limit + 1] if limit else rows
        return out

    def fetch_summary(self, table, id_column, columns, ids):
        validate_identifier(id_column, "id column")
        wanted = set(ids)
        out = {}
        for row in self._read(table):
            key = (row.get(id_column) or "").strip()
            if key in wanted:
                out[key] = {col: row.get(col) for col in columns}
        return out


class SqliteSource(DataSource):
    """Reads tables from a SQLite file with bound parameters. Read-only connection."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.label = "sqlite"

    def _connect(self):
        return sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)

    @staticmethod
    def _q(name, context):
        return '"' + validate_identifier(name, context) + '"'

    def fetch_rows(self, table, id_column, columns, ids, sort=None, limit=None):
        ids = list(dict.fromkeys(ids))
        if not ids:
            return {}
        selects = ", ".join(f"{self._q(raw, 'column')} AS {self._q(var, 'variable')}" for raw, var in columns.items())
        order = ""
        parsed = parse_sort(sort)
        if parsed:
            reverse = {v: k for k, v in columns.items()}
            if parsed[0] not in reverse:
                raise ValueError("Sort variable is not in the column map.")
            order = f" ORDER BY {self._q(reverse[parsed[0]], 'sort')} {parsed[1]}"
        marks = ", ".join("?" for _ in ids)
        sql = (f"SELECT {self._q(id_column, 'id column')} AS _id, {selects} FROM {self._q(table, 'table')} "
               f"WHERE {self._q(id_column, 'id column')} IN ({marks}){order}")
        out = {}
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(sql, ids):
                data = dict(row)
                key = str(data.pop("_id"))
                bucket = out.setdefault(key, [])
                if not limit or len(bucket) <= limit:
                    bucket.append(data)
        return out

    def fetch_summary(self, table, id_column, columns, ids):
        ids = list(dict.fromkeys(ids))
        if not ids:
            return {}
        selects = ", ".join(self._q(c, "column") for c in columns)
        marks = ", ".join("?" for _ in ids)
        sql = (f"SELECT {self._q(id_column, 'id column')} AS _id, {selects} FROM {self._q(table, 'table')} "
               f"WHERE {self._q(id_column, 'id column')} IN ({marks})")
        out = {}
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(sql, ids):
                data = dict(row)
                out[str(data.pop("_id"))] = data
        return out


def open_source(spec: str) -> DataSource:
    """Build a source from 'csv:<folder>' or 'sqlite:<file>'. Other kinds are connectors (later)."""
    kind, _, target = spec.partition(":")
    if kind == "csv" and target:
        return CsvSource(target)
    if kind == "sqlite" and target:
        return SqliteSource(target)
    raise ValueError("Unknown source. Use csv:<folder> or sqlite:<file>. Database connectors come later.")
