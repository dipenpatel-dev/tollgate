"""
module_name: test_paths.py
description: Tests for the path loader and the tg_path command.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial test.
"""
import os
import pathlib
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests" / "harness"))
sys.path.insert(0, str(REPO / "scripts"))

from throwaway_home import throwaway_home  # noqa: E402
from core import paths  # noqa: E402

TG_PATH = str(REPO / "scripts" / "core" / "tg_path")


def with_env(env):
    """Context helper: swap os.environ for env, restore after."""
    class _Ctx:
        def __enter__(self):
            self.saved = dict(os.environ)
            os.environ.clear()
            os.environ.update(env)

        def __exit__(self, *exc):
            os.environ.clear()
            os.environ.update(self.saved)
    return _Ctx()


def run_cli(env, *args):
    return subprocess.run([sys.executable, "-B", TG_PATH, *args],
                          capture_output=True, text=True, env=env)


class LoaderDefaults(unittest.TestCase):
    def test_defaults_from_knowledge(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_PATHS")
            with with_env(env):
                vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
                self.assertEqual(paths.get_path("vault"), vault)
                self.assertEqual(paths.get_path("tickets"), vault / "02-tickets")
                self.assertEqual(paths.get_path("output"), vault / "output")
                self.assertEqual(paths.get_path("meetings"), vault / "meetings")
                self.assertEqual(paths.get_path("conversations"), vault / "05-conversations")
                self.assertEqual(paths.get_path("references"), vault / "references")
                self.assertEqual(paths.get_path("state"), pathlib.Path(env["TOLLGATE_STATE_DIR"]))
                self.assertEqual(paths.get_path("repos"), pathlib.Path(env["TOLLGATE_CODE_DIR"]))
                base = pathlib.Path(home) / ".tollgate"
                self.assertEqual(paths.get_path("cache"), base / "cache")
                self.assertEqual(paths.get_path("logs"), base / "logs")
                self.assertEqual(paths.get_path("index"), base / "index")

    def test_state_default_without_env(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_STATE_DIR")
            with with_env(env):
                self.assertEqual(paths.get_path("state"),
                                 pathlib.Path(home) / ".tollgate" / "state")

    def test_get_all_lists_names(self):
        with throwaway_home() as (home, env):
            with with_env(env):
                result = paths.get_all()
                # `standards` has no default, so it is left out until the paths file sets it.
                self.assertEqual(set(result), set(paths.NAMES) - {"standards"})

    def test_unknown_name(self):
        with throwaway_home() as (home, env):
            with with_env(env):
                with self.assertRaises(KeyError):
                    paths.get_path("nope")


class LoaderFile(unittest.TestCase):
    def test_standards_has_no_default_and_follows_the_file(self):
        with throwaway_home() as (home, env):
            with with_env(env):
                with self.assertRaises(paths.NotSetUp):
                    paths.get_path("standards")
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text("standards: %s/std\n" % home)
            with with_env(env):
                self.assertEqual(paths.get_path("standards"), pathlib.Path(home) / "std")

    def test_references_line_moves_it_out_of_the_vault(self):
        with throwaway_home() as (home, env):
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text("references: %s/lib\n" % home)
            with with_env(env):
                self.assertEqual(paths.get_path("references"), pathlib.Path(home) / "lib")

    def test_file_overrides_default(self):
        with throwaway_home() as (home, env):
            target = os.path.join(home, "elsewhere")
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text(
                "# comment\ntickets: %s\n\noutput: '%s'  # note\n" % (target, target + "/out"))
            with with_env(env):
                self.assertEqual(paths.get_path("tickets"), pathlib.Path(target))
                self.assertEqual(paths.get_path("output"), pathlib.Path(target + "/out"))
                # name not in file falls back to default
                vault = pathlib.Path(env["TOLLGATE_KNOWLEDGE"])
                self.assertEqual(paths.get_path("meetings"), vault / "meetings")

    def test_tilde_and_var_expansion(self):
        with throwaway_home() as (home, env):
            env["TG_TEST_BASE"] = os.path.join(home, "base")
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text(
                "tickets: ~/tix\noutput: $TG_TEST_BASE/out\ncache: ${TG_TEST_BASE}/c\n")
            with with_env(env):
                self.assertEqual(paths.get_path("tickets"), pathlib.Path(home) / "tix")
                self.assertEqual(paths.get_path("output"), pathlib.Path(home) / "base" / "out")
                self.assertEqual(paths.get_path("cache"), pathlib.Path(home) / "base" / "c")

    def test_missing_file_is_ignored(self):
        with throwaway_home() as (home, env):
            env["TOLLGATE_PATHS"] = os.path.join(home, "does-not-exist")
            with with_env(env):
                self.assertEqual(paths.get_path("vault"),
                                 pathlib.Path(env["TOLLGATE_KNOWLEDGE"]))

    def test_file_can_supply_vault_when_env_unset(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_KNOWLEDGE")
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text("vault: %s/v\n" % home)
            with with_env(env):
                self.assertEqual(paths.get_path("vault"), pathlib.Path(home) / "v")
                self.assertEqual(paths.get_path("tickets"), pathlib.Path(home) / "v" / "02-tickets")


class LoaderLayout(unittest.TestCase):
    def test_folder_name_comes_from_the_one_table(self):
        with throwaway_home() as (home, env):
            with with_env(env):
                for key, name in paths.LAYOUT.items():
                    self.assertEqual(paths.folder_name(key), name)
                self.assertEqual(paths.folder_name("meetings"), "meetings")
                with self.assertRaises(KeyError):
                    paths.folder_name("nope")

    def test_paths_file_line_renames_a_folder(self):
        with throwaway_home() as (home, env):
            vault = env["TOLLGATE_KNOWLEDGE"]
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text("tickets: %s/work-items\n" % vault)
            with with_env(env):
                self.assertEqual(paths.folder_name("tickets"), "work-items")
                self.assertEqual(paths.folder_name("system_map"), paths.LAYOUT["system_map"])
                self.assertIn("work-items", paths.layout_dirs())

    def test_a_given_environment_is_used_instead_of_the_process_one(self):
        with throwaway_home() as (home, env):
            self.assertEqual(paths.get_path("tickets", env),
                             pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / paths.LAYOUT["tickets"])

    def test_layout_cli_lists_dirs(self):
        out = subprocess.run([sys.executable, str(REPO / "scripts" / "core" / "paths.py"), "dirs"],
                             capture_output=True, text=True, check=True).stdout.split()
        self.assertIn(paths.LAYOUT["tickets"], out)
        self.assertIn(paths.LAYOUT["knowledge"] + "/decisions", out)


class LoaderNotSetUp(unittest.TestCase):
    def test_vault_unset_raises(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_KNOWLEDGE")
            with with_env(env):
                for name in ("vault", "tickets", "output", "meetings"):
                    with self.assertRaises(paths.NotSetUp):
                        paths.get_path(name)

    def test_repos_unset_raises(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_CODE_DIR")
            with with_env(env):
                with self.assertRaises(paths.NotSetUp):
                    paths.get_path("repos")

    def test_get_all_skips_unresolved(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_KNOWLEDGE")
            with with_env(env):
                result = paths.get_all()
                self.assertNotIn("vault", result)
                self.assertIn("cache", result)


class TgPathCli(unittest.TestCase):
    def test_prints_path(self):
        with throwaway_home() as (home, env):
            proc = run_cli(env, "tickets")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout.strip(),
                             os.path.join(env["TOLLGATE_KNOWLEDGE"], "02-tickets"))
            self.assertEqual(proc.stderr, "")

    def test_not_set_up_exit_and_stderr(self):
        with throwaway_home() as (home, env):
            env.pop("TOLLGATE_KNOWLEDGE")
            proc = run_cli(env, "vault")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not set up", proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_unknown_name_exit(self):
        with throwaway_home() as (home, env):
            proc = run_cli(env, "nope")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not set up", proc.stderr)

    def test_usage_error(self):
        with throwaway_home() as (home, env):
            proc = run_cli(env)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("usage", proc.stderr)


class SessionCostSlug(unittest.TestCase):
    def test_project_slug_matches_the_rule_claude_code_uses(self):
        from core import session_cost
        self.assertEqual(session_cost.derive_project_slug(pathlib.Path("/a.b/c_d e")), "-a-b-c-d-e")


class TicketFolders(unittest.TestCase):
    """The shared helper that finds a ticket folder, flat or under its prefix folder."""

    def setUp(self):
        import tempfile
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name).resolve() / "tickets"
        self.root.mkdir()

    def test_flat_ticket(self):
        (self.root / "T-1").mkdir()
        self.assertEqual(paths.ticket_folder("T-1", self.root), self.root / "T-1")

    def test_nested_ticket(self):
        (self.root / "PROJ" / "PROJ-312").mkdir(parents=True)
        self.assertEqual(paths.ticket_folder("PROJ-312", self.root), self.root / "PROJ" / "PROJ-312")

    def test_flat_wins_over_nested(self):
        (self.root / "PROJ-5").mkdir()
        (self.root / "PROJ" / "PROJ-5").mkdir(parents=True)
        self.assertEqual(paths.ticket_folder("PROJ-5", self.root), self.root / "PROJ-5")

    def test_lowercase_prefix_folder_matches_an_uppercase_key(self):
        (self.root / "ex" / "EX-4").mkdir(parents=True)
        self.assertEqual(paths.ticket_folder("EX-4", self.root), self.root / "ex" / "EX-4")

    def test_missing_ticket_is_none(self):
        self.assertIsNone(paths.ticket_folder("PROJ-9", self.root))
        self.assertIsNone(paths.ticket_folder("PROJ-9", self.root / "absent"))

    def test_bad_keys_are_refused(self):
        (self.root / "x").mkdir()
        (self.root / "PROJ").mkdir()
        for key in ("", "PROJ", "PROJ-", "PROJ-x", "../x", "PROJ-1/..", "PROJ-1 ", "1-2", "PROJ-1-2", "..", None):
            self.assertIsNone(paths.ticket_folder(key, self.root), repr(key))

    def test_a_symlink_to_outside_the_root_is_refused(self):
        outside = self.root.parent / "outside"
        (outside / "PROJ-7").mkdir(parents=True)
        (self.root / "PROJ-7").symlink_to(outside / "PROJ-7", target_is_directory=True)
        self.assertIsNone(paths.ticket_folder("PROJ-7", self.root))
        (self.root / "Q").symlink_to(outside, target_is_directory=True)
        (outside / "Q-1").mkdir()
        self.assertIsNone(paths.ticket_folder("Q-1", self.root))
        self.assertEqual(list(paths.iter_ticket_folders(self.root)), [])

    def test_a_symlink_that_stays_inside_the_root_is_allowed(self):
        (self.root / "real" / "PROJ-8").mkdir(parents=True)
        (self.root / "PROJ").symlink_to(self.root / "real", target_is_directory=True)
        self.assertEqual(paths.ticket_folder("PROJ-8", self.root), self.root / "PROJ" / "PROJ-8")

    def test_iter_yields_both_depths_and_nothing_else(self):
        for name in ("T-1", "T-2", "notes", "sprints", "PROJ/PROJ-3", "PROJ/PROJ-4", "PROJ/archive", "ex/EX-9", "PROJ/T-5", "PROJ/readme"):
            (self.root / name).mkdir(parents=True)
        (self.root / "PROJ-6").write_text("a file")
        found = [p.relative_to(self.root).as_posix() for p in paths.iter_ticket_folders(self.root)]
        self.assertEqual(sorted(found), ["PROJ/PROJ-3", "PROJ/PROJ-4", "T-1", "T-2", "ex/EX-9"])

    def test_iter_on_a_missing_folder_is_empty(self):
        self.assertEqual(list(paths.iter_ticket_folders(self.root / "absent")), [])

    def test_the_default_root_is_the_tickets_path(self):
        with throwaway_home() as (home, env):
            tickets = pathlib.Path(env["TOLLGATE_KNOWLEDGE"]) / "02-tickets"
            (tickets / "PROJ" / "PROJ-1").mkdir(parents=True)
            with with_env(env):
                self.assertEqual(paths.ticket_folder("PROJ-1"), tickets / "PROJ" / "PROJ-1")
                self.assertEqual(list(paths.iter_ticket_folders()), [tickets / "PROJ" / "PROJ-1"])

    def test_a_paths_file_tickets_override_is_followed(self):
        with throwaway_home() as (home, env):
            moved = pathlib.Path(home) / "elsewhere"
            (moved / "PROJ" / "PROJ-2").mkdir(parents=True)
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text("tickets: %s\n" % moved)
            with with_env(env):
                self.assertEqual(paths.ticket_folder("PROJ-2"), moved / "PROJ" / "PROJ-2")

    def test_prefix_depth_tells_the_two_layouts_apart(self):
        self.assertEqual(paths.ticket_prefix_depth(("PROJ", "PROJ-312", "PROJ-312-state.md")), 1)
        self.assertEqual(paths.ticket_prefix_depth(("ex", "EX-1", "x.md")), 1)
        self.assertEqual(paths.ticket_prefix_depth(("PROJ-312", "PROJ-312-state.md")), 0)
        self.assertEqual(paths.ticket_prefix_depth(("PROJ-312", "archive", "x.md")), 0)
        self.assertEqual(paths.ticket_prefix_depth(("PROJ", "T-1", "x.md")), 0)
        self.assertEqual(paths.ticket_prefix_depth(("sprints", "plan.md")), 0)

    def test_subdir_prefixes_only_name_layout_folders(self):
        self.assertEqual(paths.subdir_prefixes("system_map", ("clients", "products")), ("01-system-map/clients/",))
        self.assertEqual(paths.subdir_prefixes("knowledge", ("decisions",)), ("03-knowledge-base/decisions/",))

    def test_file_value_reads_a_line_get_path_does_not_know(self):
        with throwaway_home() as (home, env):
            pathlib.Path(env["TOLLGATE_PATHS"]).write_text("sessions: /somewhere/else\n")
            with with_env(env):
                self.assertEqual(paths.file_value("sessions"), pathlib.Path("/somewhere/else"))
                self.assertIsNone(paths.file_value("nothing"))


if __name__ == "__main__":
    unittest.main()
