# Search scripts

The search scripts index your vault, your tickets and your reference documents into one local store, and answer questions from it. Nothing leaves your machine. With no store they print `not set up` and the command that called them carries on. {src:scripts/search/query_index.py:54-56} {src:scripts/search/ground.py:40-41}

Folder: `scripts/search/`. Tests: `tests/scripts/search/run.sh`. This is the only search in Tollgate: the older `rag/` folder is gone (see the last section).

## Where things live

The scripts read folder names through the path loader: `vault`, `tickets`, `references` for the documents, and `index` for the store. Nothing is hard coded. {src:scripts/search/config.py:135-136} {src:scripts/search/build_index.py:262} {src:scripts/search/build_index.py:274-276} See `docs/variables.md`.

## The one command commands call

Commands do not call the Python scripts directly. They call the fixed wrapper `scripts/search/tg-search <query|ground|reference|health>`, so one permission rule covers all four. {src:scripts/search/tg-search:6} {src:scripts/search/tg-search:27-30} The wrapper picks the Python (`TOLLGATE_PYTHON`, else the state folder venv, else `python3`), passes every argument and standard input through, and returns the tool's exit code. {src:scripts/search/tg-search:40-50} Page: [tg-search](search/tg-search.md).

| Wrapper word | Script behind it | What it does | Exit |
|---|---|---|---|
| `tg-search query "words" --top 8` | `query_index.py` | JSON list of passages. Also `--min-score`, `--intent`, `--situation`, `--embedder`. `--stdin` (or `-` as the words) reads the query from standard input, so a prompt never shows in the process list and may start with dashes. There is no `--index`: the folder comes from the path loader. {src:scripts/search/query_index.py:39-45} {src:scripts/search/query_index.py:47-48} | 0 ok, 1 query failed, 2 `not set up` {src:scripts/search/query_index.py:56} {src:scripts/search/query_index.py:68} |
| `tg-search health --top 5` | `vault_health.py` | Counts dead `[[links]]` and checks the index age. Also `--json`. {src:scripts/search/vault_health.py:226-227} | 0 healthy, 1 degraded or stale, 2 `not set up` {src:scripts/search/vault_health.py:233} {src:scripts/search/vault_health.py:243} |
| `tg-search ground 'SKILL' 'QUERY'` | `ground.py` | Grounding for a command. First line `STATE: ok`, `partial`, `empty` or `unavailable`, then `COLLECTIONS:`, an optional `DETAIL:`, then passages. {src:scripts/search/ground.py:72-75} | always 0 {src:scripts/search/ground.py:80} |
| `tg-search reference --situation --stakes --skill --query --top` | `reference_query.py` | Passages from your reference store with source and tag. {src:scripts/search/reference_query.py:75} | 0 (also for `no match`), 2 `not set up` {src:scripts/search/reference_query.py:72} {src:scripts/search/reference_query.py:69} |

`reference_add.py PATH --tag NAME` is not behind the wrapper: it adds a file or folder to the reference store and exits 0 added, 1 nothing to add, 2 `not set up`. {src:scripts/search/reference_add.py:72-73} {src:scripts/search/reference_add.py:79} {src:scripts/search/reference_add.py:86}

`partial` appears only when passages came back but one collection failed. `ok` and `partial` always carry at least one passage. {src:scripts/search/ground.py:58-60}

## Reference store

You decide what goes in. Tollgate ships nothing.

1. `python3 scripts/search/reference_add.py ~/my-docs/design --tag design --tag patterns`
2. Optional: create `references.yaml` next to your paths file, one line per situation: `dev_implement: [patterns]`. With no file, or no line for a situation, every reference is searched. {src:scripts/search/refstore.py:29} {src:scripts/search/refstore.py:44} The shipped `situation_map` knows `arch_design`, `spec_define`, `dev_implement`, `qa_review` and `support_triage`. {src:scripts/search/routing.yaml:25-29}
3. `--stakes high` accepts weaker matches than `low`: the score floor moves by +0.1 for `low`, 0 for `medium` and -0.05 for `high`. {src:scripts/search/config.py:130} {src:scripts/search/reference_query.py:45}

Chunks added this way carry their tags and survive a full rebuild, because `--full` deletes only chunks whose origin is `build`. {src:scripts/search/build_index.py:455-457}

## Build and keep the index

`rebuild.sh` (or `build_index.py`) indexes new and changed files, removes the chunks of a file that now yields none, and removes chunks of deleted files, one collection at a time (a collection whose folders could not all be read is left alone). {src:scripts/search/rebuild.sh:22} {src:scripts/search/build_index.py:470} {src:scripts/search/build_index.py:488-491} {src:scripts/search/build_index.py:501-504} `rebuild.sh` picks the Python the same way as `tg-search`: `TOLLGATE_PYTHON`, else the state folder venv, else `python3`. {src:scripts/search/rebuild.sh:14-16} Files that are links pointing outside their folder are skipped in the vault walk; `reference_add.py` is documented to do the same. {src:scripts/search/build_index.py:343-345} `--full` re-embeds everything. `--source` limits it to one collection: `vault`, `tickets`, `references`, `code` or `standards`. {src:scripts/search/build_index.py:526} Tickets are indexed once, under the `tickets` collection, and left out of the vault pass. {src:scripts/search/build_index.py:315} {src:scripts/search/build_index.py:337}

## Embeddings

Embeddings are injectable. `TOLLGATE_EMBEDDER=hash` uses a built in word and trigram embedder: no model, no network, same vector every run. `local` loads a sentence-transformers model that is already on disk and never downloads. The default `auto` uses the local model when present, else `hash`. {src:scripts/search/embedder.py:140-148} {src:scripts/search/embedder.py:94} {src:scripts/search/embedder.py:100} The index remembers which one built it and queries use the same one. {src:scripts/search/embedder.py:153} {src:scripts/search/embedder.py:163-174} A named embedder (the `--embedder` option or `TOLLGATE_EMBEDDER`) overrides the marker when querying. {src:scripts/search/embedder.py:165-166} A build refuses to mix two embedders unless `--full` is given for all collections; a `--full` run limited with `--source` still refuses, and leaves an existing marker as it was. {src:scripts/search/embedder.py:184-187} {src:scripts/search/build_index.py:441-442} {src:scripts/search/build_index.py:459} Every reader of the index, including `sweep` when it writes the `knowledge` collection, picks its embedder through `embedder_for_index`. {src:scripts/sync/sweep:237} {src:scripts/search/query_index.py:59} {src:scripts/search/ground.py:43} `download_model.py --yes-download` is the only place a model is fetched, and only when you run it. {src:scripts/search/download_model.py:27-28} `TOLLGATE_RERANK=1` adds an optional local re-ranker. {src:scripts/search/router.py:62} Chunk context generation (`build_index.py --context`) is off by default and needs a provider you set up. {src:scripts/search/build_index.py:528}

`hash` cannot read meaning. The test holds it to at least 80 percent of the 57 shipped golden questions in the top three, with no critical miss. {src:tests/scripts/search/test_golden.py:19} {src:tests/scripts/search/test_golden.py:67-69} {src:tests/scripts/search/test_golden.py:75-78} The measured rate was not rerun for this page (unverified). A real model does better.

## Search layout and optional collections

- The vault walk skips the top-level folders `archive`, `work` and `history`, plus the landing and output folders named in the layout (`folder_name("landing")`, `folder_name("output")`). {src:scripts/search/config.py:42} {src:scripts/search/config.py:44} The match is on the exact path relative to the vault root, lower-cased, so a folder of the same name deeper down is indexed (a ticket may keep its own `work` folder). {src:scripts/search/build_index.py:338} {src:scripts/search/config.py:40-41} `TOLLGATE_INDEX_SKIP` still adds more names, which apply at any depth. {src:scripts/search/config.py:148-149} {src:scripts/search/build_index.py:336}
- Files under the `meetings` path are split by size, because a transcript has one heading. A meetings folder outside the vault is indexed in the vault collection under the key prefix `meetings/`. {src:scripts/search/build_index.py:46-48} {src:scripts/search/build_index.py:270-271}
- Tier (the confidence label) comes from the layout folders first: conversations, chat threads, meetings and landing are observed (tier 3); the `decisions` and `patterns` folders of the knowledge folder are verified (tier 1). After that, whole words in a path segment count (`chat`, `thread`, `meeting`, `conversation`, `landing`, `slack` for tier 3; `rca`, `decision`, `pattern` for tier 1; a trailing `s` is allowed). `threadpool`, `chatter` and `circa` match nothing. Tier 3 wins over tier 1. {src:scripts/search/config.py:102} {src:scripts/search/config.py:104-105} {src:scripts/search/config.py:98-101} {src:scripts/search/config.py:218} {src:scripts/search/config.py:227-235}
- Tier is only a tie-breaker, added after similarity: observed loses 0.05, verified and documented stay level at 0.0 (a bonus for verified pushed on-point notes out of the golden top three). It no longer hides chat or meeting notes. {src:scripts/search/config.py:89} {src:scripts/search/router.py:141}
- Each collection keeps its own best 20 candidates before the lists are merged, so a large collection cannot push a small one out. {src:scripts/search/router.py:144-146} {src:scripts/search/config.py:76} The final order is the `score` field. {src:scripts/search/router.py:169} A named intent tilts a collection by at most 10 percent; no intent means no tilt. {src:scripts/search/config.py:90} {src:scripts/search/router.py:112-113} {src:scripts/search/router.py:115} A ticket ID in the query (for example `TG-210`) that appears in a file path as a whole token adds 0.1 to the similarity, so the ticket's own state file leads; `TG-21` does not boost a file under `TG-210`. {src:scripts/search/router.py:139} {src:scripts/search/router.py:123-125} {src:scripts/search/config.py:91} With no intent, no single collection may fill more than its share of the final list (at least 2 results). {src:scripts/search/router.py:185} {src:scripts/search/router.py:250-251}
- With `TOLLGATE_RERANK=1`, `score` is half the re-ranker score (squeezed into 0 to 1) and half the weighted similarity score, so many re-ranker results at 1.0 still sort. {src:scripts/search/router.py:163-164} {src:scripts/search/config.py:92}
- The `knowledge` collection (facts written by `sweep`) is queried when its folder exists. `build_index.py` never writes or prunes it. {src:scripts/search/router.py:34} {src:scripts/search/router.py:54-55} {src:scripts/search/config.py:33-34}
- A collection that is switched off (`code` or `standards` with no folder set) is not queried, even if an old index folder is still on disk. {src:scripts/search/router.py:49-52}
- `code` is on only when the `repos` path (`TOLLGATE_CODE_DIR`) is a non-empty folder outside the vault. It indexes `.md .py .sql .ipynb .yaml .yml` and skips `__pycache__`, `.git`, `.venv`, `node_modules`, `.mypy_cache`, `.terraform` and similar folders. Keys start with `repos/`. {src:scripts/search/build_index.py:285-288} {src:scripts/search/build_index.py:53} {src:scripts/search/config.py:46-49} {src:scripts/search/build_index.py:280}
- `standards` is on only when the paths file has a `standards: <folder>` line. It indexes `.md` and skips `.git`, `__pycache__` and `commands`. Keys start with `standards/` (or the vault path if the folder is inside the vault). {src:scripts/search/build_index.py:280-289} {src:scripts/search/config.py:50} {src:scripts/search/build_index.py:224-230}
- When off, no folder is made and nothing is said. `build_index.py --source code` while off stops with a clear message and exit 2. {src:scripts/search/build_index.py:288} {src:scripts/search/build_index.py:444-445} {src:scripts/search/build_index.py:539-541}

## Other scripts

| Script | Purpose |
|---|---|
| `check_index_health.py` | Runs your probe queries from `index_health.json` next to the paths file: `[{"label", "file_contains", "query"}]`. With none, it only checks the index has chunks. {src:scripts/search/check_index_health.py:30} {src:scripts/search/check_index_health.py:9} |
| `eval_rag.py --golden FILE` | Scores search against a question file (hit rate, rank, critical misses). {src:scripts/search/eval_rag.py:113-115} |
| `eval_retrieval.py --corpus DIR --golden FILE` | Builds a throwaway index from a folder, then scores it. Your real index is untouched. {src:scripts/search/eval_retrieval.py:53-54} |
| `eval_judge.py --golden FILE` | Judges how relevant each returned passage is. The default judge counts shared words; `--judge ollama` uses a local service you name. {src:scripts/search/eval_judge.py:86-87} |
| `router.py`, `intent.py`, `routing.yaml` | Tilts the collections by intent (three core ones, plus `knowledge`, and `code` and `standards` when they are on). Intent comes only from `--intent`, `--situation` or a command name; there is no keyword guess and no question asked. Edit `routing.yaml` to retune; no Python change. {src:scripts/search/intent.py:34-42} {src:scripts/search/intent.py:9-10} {src:scripts/search/routing.yaml:15} |
| `context_generator.py` | Optional chunk context at index time. |
| `config.py`, `embedder.py`, `refstore.py` | Shared settings, embedders, reference helpers. |

## The older `rag/` folder

It is gone. `scripts/search/` is the only search. The session hook `hooks/pre-submit-vault-inject.sh` calls `query_index.py --stdin` with the python in `TOLLGATE_PYTHON`, asking for 3 results at a score of at least 0.40. {src:hooks/pre-submit-vault-inject.sh:17-18} {src:hooks/pre-submit-vault-inject.sh:55-57} {src:hooks/pre-submit-vault-inject.sh:19-20} The golden questions and sample notes in `tests/rag_eval/` are still used by `tests/scripts/search/` and `eval_retrieval.py`. {src:tests/scripts/search/support.py:20-21}

## Test

`TOLLGATE_TEST_PYTHON=<python with chromadb and PyYAML> tests/scripts/search/run.sh`. Without that variable the tests fall back to `python3` and skip when chromadb is missing. {src:tests/scripts/search/run.sh:9}
