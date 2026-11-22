"""
module_name: test_reference.py
description: reference_add.py and reference_query.py: tags, situation to tag map, no match, not set up, no network.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. Documents are synthetic and name nothing real.
"""
import pathlib
import unittest

import support
from support import in_env, run_script, script_env, throwaway_home, write

DESIGN_DOC = ("# Seams\n\nA seam is a place where you can change behavior without editing the code around it.\n"
              "Put a boundary between the parts that change often and the parts that stay put, so a change stays local.\n")
SECURITY_DOC = ("# Secrets\n\nNever write a credential to disk. Keep keys in a secret store and read them at run time.\n"
                "Rotate any key that was shown in a log, and treat a leaked key as exposed from that moment.\n")


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class ReferenceStore(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.env = script_env(env)
        self.docs = pathlib.Path(self.home) / "docs-to-add"
        write(self.docs / "design" / "seams.md", DESIGN_DOC)
        write(self.docs / "security" / "secrets.md", SECURITY_DOC)

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def query(self, *args):
        return run_script("reference_query.py", list(args), self.env)

    def add(self, sub, *tags):
        flags = [x for t in tags for x in ("--tag", t)]
        return run_script("reference_add.py", [str(self.docs / sub), *flags], self.env)

    def test_not_set_up_without_a_store(self):
        proc = self.query("--query", "seam boundary", "--situation", "arch_design", "--stakes", "high", "--top", "3")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "not set up")

    def test_add_then_match_prints_source_and_tag(self):
        proc = self.add("design", "design", "patterns")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tags: design,patterns", proc.stdout)
        out = self.query("--query", "place to change behavior without editing code", "--top", "2")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("source: design/seams.md", out.stdout)
        self.assertIn("tag: design,patterns", out.stdout)

    def test_no_match_exits_zero(self):
        self.add("design", "design")
        out = self.query("--query", "pizza topping weather forecast cricket", "--top", "3")
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "no match")

    def test_situation_maps_to_tags_from_references_yaml(self):
        self.add("design", "design")
        self.add("security", "security")
        write(pathlib.Path(self.home) / ".tollgate" / "references.yaml",
              "# situation to tag map\ndev_implement: [security]\nspec_define: [design]\n")
        out = self.query("--query", "credential key secret store", "--situation", "dev_implement", "--top", "3")
        self.assertIn("secrets.md", out.stdout)
        self.assertNotIn("seams.md", out.stdout)
        out = self.query("--query", "boundary change behavior code", "--situation", "dev_implement", "--top", "3")
        self.assertEqual(out.stdout.strip(), "no match")  # design chunks carry the other tag
        out = self.query("--query", "boundary change behavior code", "--situation", "spec_define", "--top", "3")
        self.assertIn("seams.md", out.stdout)

    def test_missing_map_searches_all_references(self):
        self.add("design", "design")
        self.add("security", "security")
        out = self.query("--query", "credential key secret store", "--situation", "qa_review", "--top", "3")
        self.assertIn("secrets.md", out.stdout)

    def test_stakes_changes_the_floor(self):
        self.add("design", "design")
        low = self.query("--query", "boundary", "--stakes", "low", "--top", "3")
        high = self.query("--query", "boundary", "--stakes", "high", "--top", "3")
        self.assertEqual(high.returncode, 0)
        self.assertEqual(low.returncode, 0)

    def test_re_adding_replaces_instead_of_duplicating(self):
        self.add("design", "design")
        self.add("design", "design")
        import refstore
        with in_env(self.env):
            self.assertEqual(refstore.open_references().count(), 1)

    def test_a_single_file_can_be_added(self):
        proc = run_script("reference_add.py", [str(self.docs / "security" / "secrets.md"), "--tag", "Security Basics"], self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("security-basics", proc.stdout)

    def test_bad_path_and_empty_folder(self):
        self.assertEqual(run_script("reference_add.py", [str(self.docs / "nope")], self.env).returncode, 1)
        empty = pathlib.Path(self.home) / "empty"
        empty.mkdir()
        self.assertEqual(run_script("reference_add.py", [str(empty)], self.env).returncode, 1)

    def test_rebuild_keeps_added_references(self):
        self.add("design", "design")
        import build_index
        import refstore
        with in_env(self.env):
            before = refstore.open_references().count()
            build_index.build(full=True, embedder_name="hash")
            self.assertEqual(refstore.open_references().count(), before)

    def library_chunks(self, name_part):
        """Metadata of every references chunk whose file key holds name_part, read in the throwaway home."""
        import refstore
        with in_env(self.env):
            metas = refstore.open_references().get(include=["metadatas"])["metadatas"]
        return [m for m in metas if name_part in m["file"]]

    def make_library(self):
        lib = pathlib.Path(self.home) / "vault" / "references"
        write(lib / "design" / "seams.md", DESIGN_DOC)
        write(lib / "plain.md", SECURITY_DOC)
        return lib

    def test_rebuild_does_not_duplicate_a_file_added_with_tags(self):
        # TG-1: a file in the library folder is read by the rebuild (no tags) and by the add (tags).
        # Only the tagged copy may stay.
        import build_index
        lib = self.make_library()
        self.assertEqual(run_script("reference_add.py", [str(lib / "design"), "--tag", "design"], self.env).returncode, 0)
        with in_env(self.env):
            build_index.build(embedder_name="hash")
            build_index.build(full=True, embedder_name="hash")
        seams = self.library_chunks("seams.md")
        self.assertTrue(seams)
        self.assertEqual({m["origin"] for m in seams}, {"add"})
        self.assertEqual({m["tags"] for m in seams}, {"|design|"})
        plain = self.library_chunks("plain.md")  # never added: the rebuild still indexes it, untagged
        self.assertTrue(plain)
        self.assertEqual({m["origin"] for m in plain}, {"build"})

    def test_add_after_rebuild_replaces_the_untagged_copy(self):
        import build_index
        lib = self.make_library()
        with in_env(self.env):
            build_index.build(embedder_name="hash")
        self.assertEqual({m["origin"] for m in self.library_chunks("seams.md")}, {"build"})
        self.assertEqual(run_script("reference_add.py", [str(lib / "design"), "--tag", "design"], self.env).returncode, 0)
        seams = self.library_chunks("seams.md")
        self.assertEqual({m["origin"] for m in seams}, {"add"})
        self.assertEqual(len(seams), 1)

    def test_tag_filter_finds_a_library_file_once(self):
        lib = self.make_library()
        run_script("reference_add.py", [str(lib), "--tag", "design"], self.env)
        write(pathlib.Path(self.home) / ".tollgate" / "references.yaml", "arch_design: [design]\n")
        import build_index
        with in_env(self.env):
            build_index.build(embedder_name="hash")
        out = self.query("--query", "place to change behavior without editing code", "--situation", "arch_design", "--top", "5")
        self.assertEqual(out.stdout.count("seams.md"), 1, out.stdout)

    def test_no_network_in_add_and_query(self):
        from connector_helpers import assert_no_network
        import reference_add
        import reference_query
        with in_env(self.env), assert_no_network() as attempts:
            reference_add.add(self.docs / "design", ["design"])
            found = reference_query.search("boundary change behavior", None, "medium", 3)
        self.assertEqual(attempts, [])
        self.assertTrue(found)

    def test_situation_file_parser(self):
        import refstore
        path = pathlib.Path(self.home) / "map.yaml"
        write(path, "a: [x, y]\nb: z   # note\n# c: [skipped]\nd: []\n")
        self.assertEqual(refstore.load_situation_tags(path), {"a": ["x", "y"], "b": ["z"]})
        self.assertEqual(refstore.load_situation_tags(pathlib.Path(self.home) / "none.yaml"), {})


if __name__ == "__main__":
    unittest.main()
