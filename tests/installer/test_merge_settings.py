#!/usr/bin/env python3
"""
Author: Dipen Patel (dipenpatel-dev)
Date:
Scope: unit tests for installer/merge_settings.py (merge rules, backup, restore)
Ticket: none
ChangeLog:
  - Tests for the "$$" literal escape, the two tg-search permission rules (absolute and literal), manifest
    ownership and uninstall of both, the removal of old search rules, and the old TOLLGATE_SKILL_PREFIX env.
  - Created.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "installer"))
import merge_settings  # noqa: E402


def cmd(path: str, interpreter: str = "") -> dict:
    return {"type": "command", "command": (interpreter + " " if interpreter else "") + f'"{path}"'}


TEMPLATE = {
    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [cmd("$CLAUDE_DOTFILES/hooks/guard.py", "python3")]}]},
    "permissions": {"allow": ["Read($CLAUDE_DOTFILES/**)"]},
}


class MergeRules(unittest.TestCase):
    def test_user_interpreter_hook_is_not_mistaken_for_ours(self) -> None:
        user = {"hooks": {"PreToolUse": [{"hooks": [cmd("/home/me/mine.py", "python3")]}]}}
        out = merge_settings.merge(user, TEMPLATE, {})
        cmds = [h["command"] for g in out["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertIn('python3 "/home/me/mine.py"', cmds)
        self.assertIn('python3 "$CLAUDE_DOTFILES/hooks/guard.py"', cmds)

    def test_stale_tollgate_path_replaced_and_mixed_group_keeps_user_hook(self) -> None:
        group = {"matcher": "Bash", "hooks": [cmd("/old/place/hooks/guard.py", "python3"), cmd("/home/me/mine.sh")]}
        merged = merge_settings.merge({"hooks": {"PreToolUse": [group]}}, TEMPLATE, {})
        cmds = [h["command"] for g in merged["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertEqual(cmds, ['"/home/me/mine.sh"', 'python3 "$CLAUDE_DOTFILES/hooks/guard.py"'])

    def test_user_keys_win_and_template_adds_missing(self) -> None:
        user = {"model": "mine", "statusLine": {"type": "command", "command": "x"}, "enabledPlugins": {"p": True}}
        out = merge_settings.merge(user, {**TEMPLATE, "model": "theirs", "extraKey": 1}, {})
        self.assertEqual(out["model"], "mine")
        self.assertEqual(out["extraKey"], 1)
        self.assertEqual(out["enabledPlugins"], {"p": True})
        self.assertEqual(out["statusLine"], user["statusLine"])

    def test_combine_templates_adds_new_hook_entries_once(self) -> None:
        extra = {"hooks": {"PreToolUse": [{"hooks": [cmd("$CLAUDE_DOTFILES/hooks/new.py", "python3")]}],
                           "Stop": [{"hooks": [cmd("$CLAUDE_DOTFILES/hooks/stop.sh")]}]},
                 "permissions": {"allow": ["Bash(ls)"]}, "env": {"A": "1"}}
        both = merge_settings.combine_templates(TEMPLATE, extra)
        both = merge_settings.combine_templates(both, extra)
        self.assertEqual(len(both["hooks"]["PreToolUse"]), 2)
        self.assertEqual(len(both["hooks"]["Stop"]), 1)
        self.assertEqual(both["permissions"]["allow"], ["Read($CLAUDE_DOTFILES/**)", "Bash(ls)"])
        self.assertEqual(both["env"], {"A": "1"})

    def test_non_command_hook_identity_is_its_whole_json(self) -> None:
        prompt = {"type": "prompt", "prompt": "check this"}
        template = {"hooks": {"Stop": [{"hooks": [prompt]}]}}
        user = {"hooks": {"Stop": [{"hooks": [prompt]}, {"hooks": [{"type": "prompt", "prompt": "mine"}]}]}}
        out = merge_settings.merge(user, template, {})
        self.assertEqual(len(out["hooks"]["Stop"]), 2)
        self.assertEqual(merge_settings.merge(out, template, {}), out)


class CommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = os.path.join(self.tmp.name, "settings.json")
        self.template = os.path.join(self.tmp.name, "template.json")
        with open(self.template, "w") as fh:
            json.dump(TEMPLATE, fh)
        self.args = [self.template, self.target, "/repo", "/vault", "/scripts", "/code"]

    def run_main(self, *extra: str) -> int:
        return merge_settings.main(["merge_settings.py", *extra, *self.args])

    def read(self) -> dict:
        with open(self.target) as fh:
            return json.load(fh)

    def backups(self) -> list[str]:
        return sorted(n for n in os.listdir(self.tmp.name) if n.startswith("settings.json.bak."))

    def test_set_writes_env_and_fills_placeholders(self) -> None:
        extra = os.path.join(self.tmp.name, "extra.json")
        with open(extra, "w") as fh:
            json.dump({"hooks": {"Stop": [{"hooks": [cmd("$TOLLGATE_HOME/hooks/stop.sh")]}]}}, fh)
        self.assertEqual(self.run_main("--set", "TOLLGATE_INITIALS=AB", "--set", "TOLLGATE_HOME=/th",
                                       "--template", extra), 0)
        out = self.read()
        self.assertEqual(out["env"]["TOLLGATE_INITIALS"], "AB")
        self.assertEqual(out["env"]["TOLLGATE_HOME"], "/th")
        self.assertEqual(out["hooks"]["Stop"][0]["hooks"][0]["command"], '"/th/hooks/stop.sh"')
        self.assertIn("/repo/hooks/guard.py", out["hooks"]["PreToolUse"][0]["hooks"][0]["command"])

    def test_backup_only_when_the_file_changes(self) -> None:
        with open(self.target, "w") as fh:
            json.dump({"model": "mine"}, fh)
        self.assertEqual(self.run_main("--backup"), 0)
        self.assertEqual(len(self.backups()), 1)
        first = self.read()
        self.assertEqual(self.run_main("--backup"), 0)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.read(), first)

    def test_no_backup_when_file_is_new(self) -> None:
        self.assertEqual(self.run_main("--backup"), 0)
        self.assertEqual(self.backups(), [])

    def test_restore_newest_backup_and_keep_replaced_file(self) -> None:
        with open(self.target, "w") as fh:
            json.dump({"model": "mine"}, fh)
        self.run_main("--backup")
        self.assertNotEqual(self.read(), {"model": "mine"})
        self.assertEqual(merge_settings.main(["merge_settings.py", "--restore", self.target]), 0)
        self.assertEqual(self.read(), {"model": "mine"})
        self.assertTrue(any(n.startswith("settings.json.before-restore.") for n in os.listdir(self.tmp.name)))

    def test_restore_without_backup_fails(self) -> None:
        self.assertEqual(merge_settings.main(["merge_settings.py", "--restore", self.target]), 1)

    def test_file_mode_is_kept(self) -> None:
        with open(self.target, "w") as fh:
            json.dump({}, fh)
        os.chmod(self.target, 0o644)
        self.run_main()
        self.assertEqual(os.stat(self.target).st_mode & 0o777, 0o644)

    def test_symlinked_settings_are_written_through(self) -> None:
        real = os.path.join(self.tmp.name, "real.json")
        with open(real, "w") as fh:
            json.dump({"model": "mine"}, fh)
        os.symlink(real, self.target)
        self.run_main("--backup")
        self.assertTrue(os.path.islink(self.target))
        with open(real) as fh:
            self.assertEqual(json.load(fh)["model"], "mine")
        self.assertEqual(len(self.backups()), 1)

    def test_wrong_argument_count_returns_2(self) -> None:
        self.assertEqual(merge_settings.main(["merge_settings.py", "only-one"]), 2)
        self.assertEqual(merge_settings.main(["merge_settings.py", *self.args, "old-skill-prefix"]), 2)


class SearchWrapperRules(unittest.TestCase):
    """The tg-search permission rules: an absolute form and a literal $TOLLGATE_HOME form."""

    ABS = "Bash(/th/scripts/search/tg-search:*)"
    LIT = "Bash($TOLLGATE_HOME/scripts/search/tg-search:*)"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = os.path.join(self.tmp.name, "settings.json")
        self.manifest = os.path.join(self.tmp.name, "manifest.json")
        self.template = os.path.join(REPO, "settings.json")

    def run_main(self, *extra: str, template: str = "") -> int:
        return merge_settings.main(["merge_settings.py", "--manifest", self.manifest, "--set", "TOLLGATE_HOME=/th",
                                    *extra, template or self.template, self.target, "/repo", "/vault", "/scripts", "/code"])

    def read(self) -> dict:
        with open(self.target) as fh:
            return json.load(fh)

    def test_double_dollar_stays_a_single_literal_dollar(self) -> None:
        tree = {"a": "$$TOLLGATE_HOME/x", "b": ["$TOLLGATE_HOME/x", "cost $$5"], "c": {"d": "$$$TOLLGATE_HOME"}}
        out = merge_settings.substitute(tree, {"$TOLLGATE_HOME": "/th"})
        self.assertEqual(out, {"a": "$TOLLGATE_HOME/x", "b": ["/th/x", "cost $5"], "c": {"d": "$/th"}})

    def test_both_rules_are_installed_and_owned(self) -> None:
        self.assertEqual(self.run_main(), 0)
        allow = self.read()["permissions"]["allow"]
        self.assertIn(self.ABS, allow)
        self.assertIn(self.LIT, allow)
        with open(self.manifest) as fh:
            owned = json.load(fh)["permissions"]["allow"]
        self.assertIn(self.ABS, owned)
        self.assertIn(self.LIT, owned)

    def test_no_interpreter_search_rules_remain(self) -> None:
        self.run_main()
        for rule in self.read()["permissions"]["allow"]:
            self.assertNotIn("query_index.py", rule)
            self.assertNotIn("TOLLGATE_PYTHON", rule)

    def test_uninstall_removes_both_and_keeps_user_rules(self) -> None:
        with open(self.target, "w") as fh:
            json.dump({"permissions": {"allow": ["Bash(echo mine)"]}}, fh)
        self.run_main()
        self.assertEqual(merge_settings.main(["merge_settings.py", "--uninstall", "--manifest", self.manifest,
                                              self.target]), 0)
        self.assertEqual(self.read()["permissions"]["allow"], ["Bash(echo mine)"])

    def test_update_drops_old_search_rules_and_old_prefix_env(self) -> None:
        old_rules = ["Bash(python3 /th/scripts/search/query_index.py:*)",
                     "Bash(${TOLLGATE_PYTHON:-python3} $TOLLGATE_HOME/scripts/search/ground.py:*)"]
        with open(self.target, "w") as fh:
            json.dump({"permissions": {"allow": ["Bash(echo mine)"] + old_rules},
                       "env": {"TOLLGATE_SKILL_PREFIX": "ah-", "MY_VAR": "1"}}, fh)
        with open(self.manifest, "w") as fh:
            json.dump({"permissions": {"allow": old_rules}, "env": ["TOLLGATE_SKILL_PREFIX"]}, fh)
        self.run_main()
        out = self.read()
        self.assertNotIn(old_rules[0], out["permissions"]["allow"])
        self.assertNotIn(old_rules[1], out["permissions"]["allow"])
        self.assertIn("Bash(echo mine)", out["permissions"]["allow"])
        self.assertIn(self.LIT, out["permissions"]["allow"])
        self.assertNotIn("TOLLGATE_SKILL_PREFIX", out["env"])
        self.assertEqual(out["env"]["MY_VAR"], "1")

    def test_update_drops_retired_rules_without_manifest_and_keeps_user_rules(self) -> None:
        retired = ["Bash(git config:*)", "Bash(python3 /repo/rag/query_index.py:*)",
                   "Bash(python3 $CLAUDE_DOTFILES/rag/query_index.py:*)"]
        mine = ["Bash(echo mine)", "Bash(git config --get user.name)", "Bash(git config:* extra)"]
        with open(self.target, "w") as fh:
            json.dump({"permissions": {"allow": mine + retired}}, fh)
        self.run_main()
        allow = self.read()["permissions"]["allow"]
        for rule in retired:
            self.assertNotIn(rule, allow)
        for rule in mine:
            self.assertIn(rule, allow)

    def test_second_run_writes_nothing(self) -> None:
        self.run_main()
        before = os.stat(self.target).st_mtime_ns
        self.run_main()
        self.assertEqual(os.stat(self.target).st_mtime_ns, before)

    def test_same_form_twice_is_listed_once(self) -> None:
        template = os.path.join(self.tmp.name, "t.json")
        with open(template, "w") as fh:
            json.dump({"permissions": {"allow": ["Bash($TOLLGATE_HOME/x:*)", "Bash($$TOLLGATE_HOME/x:*)"]}}, fh)
        self.run_main(template=template, )
        self.assertEqual(self.read()["permissions"]["allow"], ["Bash(/th/x:*)", "Bash($TOLLGATE_HOME/x:*)"])


if __name__ == "__main__":
    unittest.main()
