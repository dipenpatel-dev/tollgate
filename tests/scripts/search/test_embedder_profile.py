"""
module_name: test_embedder_profile.py
description: The query prompt, the trust setting and the one-model-per-index guard of the local embedder. A fake model stands in, so nothing is downloaded.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial version. Covers TOLLGATE_EMBED_QUERY_PROMPT, TOLLGATE_EMBED_TRUST_REMOTE_CODE and the switch-needs-full guard.
"""
import pathlib
import sys
import types
import unittest

import support
from support import in_env, script_env, throwaway_home


class FakeModel:
    """Records how it was loaded and called. Mimics the parts of SentenceTransformer we use."""

    loaded_with = {}
    calls = []
    prompts = {"query": "Represent this sentence for searching relevant passages: "}

    def __init__(self, name, **kwargs):
        FakeModel.loaded_with = dict(kwargs, name=name)

    def encode(self, texts, **kwargs):
        FakeModel.calls.append(dict(kwargs, n=len(texts)))
        return _Array([[0.0, 1.0] for _ in texts])


class _Array(list):
    def tolist(self):
        return list(self)


def install_fake_model():
    """Put a fake sentence_transformers module in place. Returns a function that undoes it."""
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeModel
    saved = sys.modules.get("sentence_transformers")
    sys.modules["sentence_transformers"] = module
    sys.modules.pop("sentence_transformers.backend", None)
    FakeModel.loaded_with, FakeModel.calls = {}, []

    def undo():
        if saved is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = saved
    return undo


class LocalEmbedderSettings(unittest.TestCase):
    def setUp(self):
        self.undo = install_fake_model()
        self.addCleanup(self.undo)

    def make(self, **env):
        import embedder
        with in_env(env):
            return embedder.LocalModelEmbedder("Snowflake/snowflake-arctic-embed-l")

    def test_trust_remote_code_is_off_unless_asked(self):
        self.make()
        self.assertIs(FakeModel.loaded_with["trust_remote_code"], False)

    def test_trust_remote_code_turns_on_with_the_setting(self):
        self.make(TOLLGATE_EMBED_TRUST_REMOTE_CODE="1")
        self.assertIs(FakeModel.loaded_with["trust_remote_code"], True)

    def test_questions_use_the_query_prompt_and_documents_do_not(self):
        emb = self.make(TOLLGATE_EMBED_QUERY_PROMPT="query")
        emb.encode(["a document"])
        emb.encode_query(["a question"])
        self.assertNotIn("prompt_name", FakeModel.calls[0])
        self.assertEqual(FakeModel.calls[1]["prompt_name"], "query")

    def test_without_the_setting_questions_are_plain(self):
        emb = self.make()
        emb.encode_query(["a question"])
        self.assertNotIn("prompt_name", FakeModel.calls[0])

    def test_a_prompt_name_the_model_does_not_have_is_refused_with_the_choices(self):
        with self.assertRaises(ValueError) as caught:
            self.make(TOLLGATE_EMBED_QUERY_PROMPT="nope")
        self.assertIn("query", str(caught.exception))

    def test_hash_embedder_questions_match_documents(self):
        import embedder
        e = embedder.HashEmbedder()
        self.assertEqual(e.encode_query(["retry the load"]), e.encode(["retry the load"]))

    def test_index_questions_use_the_model_that_built_the_index(self):
        import embedder
        with throwaway_home() as (home, _env):
            root = pathlib.Path(home) / "idx"
            root.mkdir()
            emb = embedder.LocalModelEmbedder("Some/other-model")
            embedder.write_marker(root, emb)
            with in_env({"TOLLGATE_EMBEDDER": ""}):
                chosen = embedder.embedder_for_index(root)
        self.assertEqual(chosen.model_name, "Some/other-model")


class OneModelPerIndex(unittest.TestCase):
    def setUp(self):
        self._home = throwaway_home()
        self.home, env = self._home.__enter__()
        self.vault = support.make_vault(pathlib.Path(self.home) / "vault")
        self.env = script_env(env, TOLLGATE_KNOWLEDGE=str(self.vault))

    def tearDown(self):
        self._home.__exit__(None, None, None)

    def test_switching_models_without_full_is_refused_and_full_is_allowed(self):
        import build_index
        import config
        import embedder

        class Other(embedder.HashEmbedder):
            name = "local:Other/model"

        with in_env(self.env):
            build_index.build(full=True, embedder_name="hash")
            with self.assertRaises(ValueError) as caught:
                build_index.build(emb=Other())
            self.assertIn("--full", str(caught.exception))
            self.assertEqual(embedder.read_marker(config.index_root()), "hash-v1")
            build_index.build(full=True, emb=Other())
            self.assertEqual(embedder.read_marker(config.index_root()), "local:Other/model")

    def test_same_model_again_is_fine(self):
        import build_index
        with in_env(self.env):
            build_index.build(full=True, embedder_name="hash")
            summary = build_index.build(embedder_name="hash")
        self.assertEqual(summary["errors"], 0)


if __name__ == "__main__":
    unittest.main()
