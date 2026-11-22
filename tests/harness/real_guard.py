#!/usr/bin/env python3
"""Real-settings checksum guard (read only).

Records a checksum of the REAL ~/.claude/settings.json and of a given real
vault folder before a run, and fails if either changed afterwards. A missing
file or folder is a valid state: missing before must be missing after.
"""
import hashlib
import os


def file_checksum(path):
    """sha256 of a file, or 'MISSING' if absent. Read only."""
    if not os.path.isfile(path):
        return "MISSING"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def folder_checksum(path):
    """sha256 over relative paths, sizes, mtimes (ns) and file bytes. Read only."""
    if not os.path.isdir(path):
        return "MISSING"
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, path)
            try:
                st = os.stat(full)
                h.update(("%s|%d|%d\n" % (rel, st.st_size, st.st_mtime_ns)).encode())
                h.update(file_checksum(full).encode())
            except OSError:
                h.update(("%s|unreadable\n" % rel).encode())
    return h.hexdigest()


class RealStateGuard:
    """Use as a context manager or call record() then verify()."""

    def __init__(self, settings_path=None, vault_path=None):
        self.settings_path = settings_path or os.path.join(
            os.path.expanduser("~"), ".claude", "settings.json")
        self.vault_path = vault_path
        self.before = None

    def snapshot(self):
        snap = {"settings": file_checksum(self.settings_path)}
        if self.vault_path:
            snap["vault"] = folder_checksum(self.vault_path)
        return snap

    def record(self):
        self.before = self.snapshot()
        return self.before

    def verify(self):
        """Raise AssertionError naming what changed. Returns True when clean."""
        if self.before is None:
            raise RuntimeError("record() was not called")
        after = self.snapshot()
        changed = [k for k in self.before if self.before[k] != after[k]]
        if changed:
            raise AssertionError("real state changed: " + ", ".join(changed))
        return True

    def __enter__(self):
        self.record()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.verify()
        return False
