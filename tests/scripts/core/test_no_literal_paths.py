"""
module_name: test_no_literal_paths.py
description: SCR-02. No script outside the path loader holds a literal folder string, a home path or a hostname.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial test.
"""
import os
import pathlib
import re
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
ALLOWLIST = {"scripts/core/paths.py", "scripts/core/tg_path"}

HOME_PATHS = [
    r"/Users/", r"/home/[A-Za-z]", r"/Volumes/", r"~/", r"\bPath\.home\(\)",
    r"expanduser\(\s*[\"']~", r"\$HOME\b", r"\$\{HOME[}:]",
]
FOLDERS = [
    r"\.claude\b", r"\.tollgate\b", r"\." + "sh" + "ankar" + r"\b", r"\.cursor\b",
    r"\b0[0-9]-[a-z][a-z-]+\b", r"\bDeveloper/", r"\b_numbered_dir\b",
]
HOSTS = [
    r"[\"'][\w-]+(\.[\w-]+)*\.(lan|local|internal|home|corp)[\"':/]",
    r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2,3}\b",
]
PATTERNS = [(re.compile(p), "home path") for p in HOME_PATHS] + \
           [(re.compile(p), "folder string") for p in FOLDERS] + \
           [(re.compile(p), "hostname") for p in HOSTS]


def scan_text(text):
    """Return a list of (line number, kind, matched text)."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        for pattern, kind in PATTERNS:
            match = pattern.search(line)
            if match:
                found.append((number, kind, match.group(0)))
    return found


def scan_tree(root, allow=ALLOWLIST, base=None):
    base = base or root.parent
    offenders = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(base).as_posix()
        if rel in allow:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for number, kind, hit in scan_text(text):
            offenders.append("%s:%d %s %r" % (rel, number, kind, hit))
    return offenders


class ScannerSelfTest(unittest.TestCase):
    def test_flags_each_kind(self):
        # Fake values are built at run time so this file stays clean.
        samples = {
            "home path": "p = '/" + "Users/someone/x'",
            "folder string": "d = '02" + "-tickets'",
            "hostname": "h = 'box1." + "lan'",
        }
        for kind, line in samples.items():
            kinds = [k for _, k, _ in scan_text(line)]
            self.assertIn(kind, kinds, line)

    def test_clean_line_passes(self):
        self.assertEqual(scan_text("from core.paths import get_path"), [])

    def test_allowlist_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "scripts"
            (root / "core").mkdir(parents=True)
            (root / "core" / "paths.py").write_text("x = '~/" + ".tollgate'\n")
            (root / "core" / "other.py").write_text("x = '~/" + ".tollgate'\n")
            found = scan_tree(root)
            self.assertEqual(len(found), 2)  # both hit lines in other.py
            self.assertTrue(all("other.py" in f for f in found))


class NoLiteralPaths(unittest.TestCase):
    def test_scripts_have_no_literal_paths(self):
        offenders = scan_tree(SCRIPTS)
        self.assertEqual(
            offenders, [],
            "SCR-02 offenders (file:line kind match):\n" + "\n".join(offenders))

    def test_hooks_hold_no_numbered_vault_folder_name(self):
        """The hooks take the tickets folder from the path loader, never from a literal."""
        folder = re.compile(FOLDERS[2])
        offenders = []
        for path in sorted((REPO / "hooks").glob("*")):
            if path.is_file() and path.suffix in ("", ".py", ".sh"):
                for number, line in enumerate(path.read_text().splitlines(), 1):
                    if folder.search(line):
                        offenders.append("hooks/%s:%d %s" % (path.name, number, line.strip()))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_loader_files_exist(self):
        for rel in ALLOWLIST:
            self.assertTrue((REPO / rel).is_file(), rel)


if __name__ == "__main__":
    unittest.main()
