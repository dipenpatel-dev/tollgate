#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: unit tests for the owned-entries manifest (installer/manifest.py) and the manifest rules in
       installer/merge_settings.py: stale entries removed, user entries kept, uninstall, backup pruning
Ticket: none
ChangeLog:
  - Created.
"""

from __future__ import annotations

import glob
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "installer"))
import manifest  # noqa: E402
import merge_settings  # noqa: E402


def hook(path: str) -> dict:
    return {"type": "command", "command": 'python3 "%s"' % path}


def template(*scripts: str, allow=()) -> dict:
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [hook("/repo/hooks/" + s) for s in scripts]}]},
            "permissions": {"allow": list(allow)}}


USER = {"hooks": {"PreToolUse": [{"hooks": [hook("/home/me/mine.py")]}]},
        "permissions": {"allow": ["Bash(echo mine)"]}}


def commands(settings: dict) -> list:
    return [h["command"] for g in settings["hooks"].get("PreToolUse", []) for h in g["hooks"]]


class ManifestRules(unittest.TestCase):
    def two_runs(self, first: dict, second: dict):
        run1, owned1 = merge_settings.merge_full(USER, first, {})
        run2, owned2 = merge_settings.merge_full(run1, second, {}, owned1)
        return run1, run2, owned2

    def test_hook_removed_upstream_is_removed_and_user_hook_kept(self) -> None:
        run1, run2, _ = self.two_runs(template("a.py", "b.py"), template("a.py"))
        self.assertTrue(any("b.py" in c for c in commands(run1)))
        self.assertFalse(any("b.py" in c for c in commands(run2)))
        self.assertTrue(any("a.py" in c for c in commands(run2)))
        self.assertTrue(any("mine.py" in c for c in commands(run2)))

    def test_hook_renamed_upstream_is_old_removed_new_added(self) -> None:
        _, run2, owned = self.two_runs(template("old.py"), template("tg-new.py"))
        text = " ".join(commands(run2))
        self.assertNotIn("old.py", text)
        self.assertIn("tg-new.py", text)
        self.assertEqual(owned["hooks"], ["cmd:tg-new.py"])

    def test_permission_removed_upstream_is_removed_and_user_rule_kept(self) -> None:
        run1, run2, owned = self.two_runs(template("a.py", allow=["Read(/x)", "Read(/y)"]),
                                          template("a.py", allow=["Read(/x)"]))
        self.assertIn("Read(/y)", run1["permissions"]["allow"])
        self.assertNotIn("Read(/y)", run2["permissions"]["allow"])
        self.assertIn("Read(/x)", run2["permissions"]["allow"])
        self.assertIn("Bash(echo mine)", run2["permissions"]["allow"])
        self.assertEqual(owned["permissions"]["allow"], ["Read(/x)"])

    def test_rule_the_user_already_had_is_never_removed(self) -> None:
        user = {"permissions": {"allow": ["Read(/y)"]}}
        run1, owned1 = merge_settings.merge_full(user, template("a.py", allow=["Read(/y)", "Read(/x)"]), {})
        self.assertEqual(owned1["permissions"]["allow"], ["Read(/x)"])
        run2, _ = merge_settings.merge_full(run1, template("a.py"), {}, owned1)
        self.assertIn("Read(/y)", run2["permissions"]["allow"])
        self.assertNotIn("Read(/x)", run2["permissions"]["allow"])

    def test_second_merge_with_same_template_changes_nothing(self) -> None:
        run1, run2, _ = self.two_runs(template("a.py", allow=["Read(/x)"]), template("a.py", allow=["Read(/x)"]))
        self.assertEqual(run1, run2)

    def test_strip_owned_keeps_user_entries(self) -> None:
        run1, owned = merge_settings.merge_full(USER, template("a.py", allow=["Read(/x)"]), {"TOLLGATE_HOME": "/r"})
        out = merge_settings.strip_owned(run1, owned)
        self.assertEqual(commands(out), ['python3 "/home/me/mine.py"'])
        self.assertEqual(out["permissions"]["allow"], ["Bash(echo mine)"])
        self.assertNotIn("env", out)


class SettingsBackups(unittest.TestCase):
    def test_settings_backups_are_pruned_to_three(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "settings.json")
            with open(target, "w") as fh:
                fh.write("{}")
            for n in range(1, 7):
                with open("%s.bak.2020010100000%d" % (target, n), "w") as fh:
                    fh.write("{}")
            merge_settings.make_backup(target)
            left = sorted(os.path.basename(p) for p in glob.glob(target + ".bak.*"))
            self.assertEqual(len(left), 3)
            self.assertNotIn("settings.json.bak.20200101000001", left)


class ManifestFile(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cmds = os.path.join(self.tmp.name, "commands")
        os.makedirs(self.cmds)
        self.manifest = os.path.join(self.tmp.name, "tollgate", "manifest.json")
        self.backup = os.path.join(self.tmp.name, "tollgate", "removed", "removed.1")

    def touch(self, name: str) -> None:
        with open(os.path.join(self.cmds, name), "w") as fh:
            fh.write(name)

    def sync(self, *names: str) -> None:
        manifest.sync_commands(self.manifest, self.cmds, self.backup, list(names), "0.2.0")

    def test_rename_is_remove_old_plus_add_new(self) -> None:
        self.touch("start.md")
        self.touch("mine.md")
        self.sync("start.md")
        self.touch("tg-start.md")
        self.sync("tg-start.md")
        self.assertFalse(os.path.exists(os.path.join(self.cmds, "start.md")))
        self.assertTrue(os.path.exists(os.path.join(self.backup, "start.md")))
        self.assertTrue(os.path.exists(os.path.join(self.cmds, "tg-start.md")))
        self.assertTrue(os.path.exists(os.path.join(self.cmds, "mine.md")), "a file not in the manifest is never touched")
        self.assertEqual(manifest.load(self.manifest)["commands"], ["tg-start.md"])

    def test_names_with_a_folder_part_are_never_removed(self) -> None:
        outside = os.path.join(self.tmp.name, "keep.md")
        with open(outside, "w") as fh:
            fh.write("x")
        manifest.save(self.manifest, {"commands": ["../keep.md", "/etc/hosts", ".hidden.md"]})
        self.sync("a.md")
        self.assertTrue(os.path.exists(outside))

    def test_save_writes_only_on_change(self) -> None:
        self.assertTrue(manifest.save(self.manifest, {"a": 1}))
        self.assertFalse(manifest.save(self.manifest, {"a": 1}))

    def test_removed_backup_folders_are_pruned_to_three(self) -> None:
        parent = os.path.join(self.tmp.name, "tollgate", "removed")
        for n in range(1, 6):
            os.makedirs(os.path.join(parent, "removed.%d" % n))
        self.touch("old.md")
        manifest.save(self.manifest, {"commands": ["old.md"]})
        manifest.sync_commands(self.manifest, self.cmds, os.path.join(parent, "removed.9"), [], "0.2.0")
        self.assertEqual(len(os.listdir(parent)), 3)


if __name__ == "__main__":
    unittest.main()
