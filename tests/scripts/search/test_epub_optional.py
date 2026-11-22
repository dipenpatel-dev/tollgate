"""
module_name: test_epub_optional.py
description: The search index works without ebooklib: epub files are skipped with one log line and a hint, nothing else fails.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version.
"""
import pathlib
import sys
import unittest
from unittest import mock

import support
from support import in_env, script_env, throwaway_home, write


class _BlockEpub:
    """Make `import ebooklib` fail even when the library is installed."""

    def __enter__(self):
        self._patch = mock.patch.dict(sys.modules, {"ebooklib": None, "ebooklib.epub": None})
        self._patch.start()

    def __exit__(self, *exc):
        self._patch.stop()


@unittest.skipUnless(support.HAVE_STORE, support.NOTE)
class EpubIsOptional(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.vault = support.make_vault(pathlib.Path(self.home) / "vault")
        self.env = script_env(env, TOLLGATE_KNOWLEDGE=str(self.vault))
        self.book = write(pathlib.Path(self.home) / "book.epub", "not a real epub")

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def test_missing_library_gives_a_hint_to_the_epub_requirements_file(self):
        import build_index
        with _BlockEpub(), self.assertRaises(ImportError) as ctx:
            build_index.chunk_epub(self.book, "book.epub")
        self.assertIn("requirements-epub.txt", str(ctx.exception))

    def test_build_skips_epub_with_one_log_line_and_keeps_other_files(self):
        import build_index
        import config
        import router
        found = [(self.book, "refs/one.epub", "vault"), (self.book, "refs/two.epub", "vault")]
        real = build_index.find_source_files

        def with_epubs(*args, **kwargs):
            return list(real(*args, **kwargs)) + found

        with in_env(self.env), _BlockEpub(), mock.patch.object(build_index, "find_source_files", with_epubs):
            with self.assertLogs(build_index.logger, level="WARNING") as logs:
                build_index.build(full=True, embedder_name="hash")
            files = {m["file"] for m in router.open_collections(config.index_root())["vault"].get()["metadatas"]}
        epub_lines = [ln for ln in logs.output if "epub" in ln.lower()]
        self.assertEqual(1, len(epub_lines), logs.output)
        self.assertIn("requirements-epub.txt", epub_lines[0])
        self.assertIn("notes/alpha.md", files)
        self.assertNotIn("refs/one.epub", files)


if __name__ == "__main__":
    unittest.main()
