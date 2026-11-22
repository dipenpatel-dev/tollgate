---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_embedder_profile.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/search/embedder.py", "scripts/search/build_index.py", "scripts/search/config.py"]         # source files under test, relative paths from repo root
tags: []
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
---

## Purpose

This file tests three settings of the local embedder without downloading a model: whether the model may run its own shipped code, which named prompt is used for search questions, and the guard that stops two different models from writing into one index. A fake `sentence_transformers` module stands in for the real model.

## Dependencies

**Depends on.**
- Standard library: `pathlib`, `sys`, `types`, `unittest` {src:tests/scripts/search/test_embedder_profile.py:10-13}.
- Helper module [[support]] and [support](support.md), for `in_env`, `script_env`, `throwaway_home` and `make_vault` {src:tests/scripts/search/test_embedder_profile.py:15-16}. Throwaway home factory [[throwaway_home]] and [throwaway_home](../../harness/throwaway_home.md).
- Code under test: [[embedder]] and [embedder](../../../scripts/search/embedder.md) (`LocalModelEmbedder`, `HashEmbedder`, `write_marker`, `read_marker`, `embedder_for_index`) {src:tests/scripts/search/test_embedder_profile.py:62-64}. [[build_index]] and [build_index](../../../scripts/search/build_index.md) (`build`) {src:tests/scripts/search/test_embedder_profile.py:119}. [[config]] and [config](../../../scripts/search/config.md) (`index_root`) {src:tests/scripts/search/test_embedder_profile.py:120}.
- Environment variables set by the tests: `TOLLGATE_EMBED_TRUST_REMOTE_CODE` {src:tests/scripts/search/test_embedder_profile.py:71}, `TOLLGATE_EMBED_QUERY_PROMPT` {src:tests/scripts/search/test_embedder_profile.py:75}, `TOLLGATE_EMBEDDER` {src:tests/scripts/search/test_embedder_profile.py:103}, `TOLLGATE_KNOWLEDGE` {src:tests/scripts/search/test_embedder_profile.py:113}.

**Used by.** Searched with `git grep` for `test_embedder_profile` outside `docs/` on 2026-11-20: nothing names it. The folder runner [[run]] and [run](run.md) finds it by the `test_*.py` pattern {src:tests/scripts/search/run.sh:9}.

## Behavior

**Fake model.** `FakeModel` records the keyword arguments it was loaded with {src:tests/scripts/search/test_embedder_profile.py:26-27}, records every `encode` call with the number of texts {src:tests/scripts/search/test_embedder_profile.py:29-30}, returns a fixed two-number vector per text {src:tests/scripts/search/test_embedder_profile.py:31}, and exposes one named prompt, `query` {src:tests/scripts/search/test_embedder_profile.py:24}. `install_fake_model` puts it in `sys.modules` as `sentence_transformers`, drops any cached `sentence_transformers.backend`, clears the records, and returns an undo function {src:tests/scripts/search/test_embedder_profile.py:41-53}. The real embedder imports `SentenceTransformer` inside its constructor, which is why this swap works {src:scripts/search/embedder.py:97}.

**Class `LocalEmbedderSettings`** (the fake is installed in `setUp` and undone by a cleanup {src:tests/scripts/search/test_embedder_profile.py:57-59}). Each `make` builds a `LocalModelEmbedder` for `Snowflake/snowflake-arctic-embed-l` inside `in_env`, so only the variables the test passes are visible {src:tests/scripts/search/test_embedder_profile.py:61-64}.
- `test_trust_remote_code_is_off_unless_asked`: with no variable, the model is loaded with `trust_remote_code` equal to `False` {src:tests/scripts/search/test_embedder_profile.py:67-68}. This holds because the code turns trust on only when the variable is exactly `1` {src:scripts/search/embedder.py:99}.
- `test_trust_remote_code_turns_on_with_the_setting`: with `TOLLGATE_EMBED_TRUST_REMOTE_CODE=1`, it is `True` {src:tests/scripts/search/test_embedder_profile.py:71-72}.
- `test_questions_use_the_query_prompt_and_documents_do_not`: with the prompt set to `query`, a document encode carries no `prompt_name` and a question encode carries `prompt_name == "query"` {src:tests/scripts/search/test_embedder_profile.py:75-79}. The code adds `prompt_name` only in `encode_query` {src:scripts/search/embedder.py:112-113}.
- `test_without_the_setting_questions_are_plain`: with no setting, a question encode has no `prompt_name` {src:tests/scripts/search/test_embedder_profile.py:82-84}.
- `test_a_prompt_name_the_model_does_not_have_is_refused_with_the_choices`: a prompt name `nope` raises `ValueError`, and the message holds the lowercase word `query`, which is the model's real choice {src:tests/scripts/search/test_embedder_profile.py:87-89}. The environment variable name is upper case, so the lowercase match can only come from the list of choices in the message {src:scripts/search/embedder.py:105-108}.
- `test_hash_embedder_questions_match_documents`: for the hash embedder, `encode_query` returns the same vectors as `encode` {src:tests/scripts/search/test_embedder_profile.py:92-94}, matching the code {src:scripts/search/embedder.py:77-79}.
- `test_index_questions_use_the_model_that_built_the_index`: it writes a marker for a model named `Some/other-model`, clears `TOLLGATE_EMBEDDER`, and checks that `embedder_for_index` returns an embedder with that model name {src:tests/scripts/search/test_embedder_profile.py:98-105}. The code reads the marker and rebuilds the local embedder from it only when no override is set {src:scripts/search/embedder.py:165-173}.

**Class `OneModelPerIndex`** builds a throwaway home and a synthetic vault in `setUp`, and removes the home in `tearDown` {src:tests/scripts/search/test_embedder_profile.py:109-116}.
- `test_switching_models_without_full_is_refused_and_full_is_allowed`: build a full index with the hash embedder; a second build with an injected embedder named `local:Other/model` and no `full` raises `ValueError` mentioning `--full`; the marker is still `hash-v1`; a build with `full=True` succeeds and the marker becomes `local:Other/model` {src:tests/scripts/search/test_embedder_profile.py:123-133}. The refusal comes from `check_marker` {src:scripts/search/embedder.py:183-187}, which `build` runs unless the run is a full rebuild with no single source named {src:scripts/search/build_index.py:441-442}.
- `test_same_model_again_is_fine`: two builds with the hash embedder, the second without `full`, report zero errors {src:tests/scripts/search/test_embedder_profile.py:136-140}.

## Diagram

None: the setup is one fake module and one throwaway home, with no chain of mocks.

## Notes

- Code and description agree: the header says it covers the query prompt, the trust setting and the switch guard {src:tests/scripts/search/test_embedder_profile.py:8}, and the tests do. The header says "nothing is downloaded" {src:tests/scripts/search/test_embedder_profile.py:3}: true for the `LocalEmbedderSettings` tests, which use the fake, and the embedder is told to use local files only {src:scripts/search/embedder.py:100}. `test_switching_models...` uses the hash embedder and a subclass, so it loads no model either {src:tests/scripts/search/test_embedder_profile.py:123-124}.
- The header `date:` field is empty {src:tests/scripts/search/test_embedder_profile.py:5}.
- Environment leak: `test_index_questions_use_the_model_that_built_the_index` builds `LocalModelEmbedder("Some/other-model")` outside `in_env` {src:tests/scripts/search/test_embedder_profile.py:101}. The constructor calls `os.environ.setdefault` for `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE` {src:scripts/search/embedder.py:94-95}, so those two values stay set in the real process after the test, and the constructor also reads the developer's real `TOLLGATE_EMBED_QUERY_PROMPT` and `TOLLGATE_EMBED_TRUST_REMOTE_CODE` {src:scripts/search/embedder.py:99-103}. If the real prompt name is set to something the fake does not have, that test would fail on a machine for a reason that has nothing to do with the code.
- `OneModelPerIndex` has no `skipUnless(HAVE_STORE)` marker {src:tests/scripts/search/test_embedder_profile.py:108}, so without `chromadb` it would be expected to error, not skip (read, not run). The `LocalEmbedderSettings` tests need neither `chromadb` nor a model.
- Weak assertion: `test_hash_embedder_questions_match_documents` compares two calls to the same pure function {src:tests/scripts/search/test_embedder_profile.py:94}, so it fails only if `encode_query` stops delegating to `encode`.
- No test here depends on a machine path or on the Python version. The throwaway home is a temp folder {src:tests/scripts/search/test_embedder_profile.py:98}.
- Not tested: `embedder_for_index` when the marker is the hash name, a marker with no model after the colon, and `trust_remote_code` values other than `1` (for example `true`).
- Inputs to paths, commands, network or outbound text without a check: none in this file; every value is a literal or a temp path. The test does reach `embedder_for_index`, whose marker file content becomes a model name passed to the model loader with no check on its value {src:scripts/search/embedder.py:172-173}.
- Shared-file writes: `write_marker` writes `embedder.json` with a plain `write_text`, not atomic {src:scripts/search/embedder.py:151-153}, and nothing stops two writers; here each test has its own temp folder.
