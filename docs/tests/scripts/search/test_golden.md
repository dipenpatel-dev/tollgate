---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/scripts/search/test_golden.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["scripts/search/build_index.py", "scripts/search/eval_rag.py", "scripts/search/eval_retrieval.py", "scripts/search/eval_judge.py"]         # source files under test, relative paths from repo root
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

This file builds one search index from the synthetic corpus with the fake (hash) embedder, runs the 57 golden questions against it, and checks the results: the build is clean, a second build changes nothing, ticket files are keyed relative to the vault, the seven basic questions all hit, no critical question misses, off-topic questions return nothing, and the overall hit rate stays above a floor. It also runs the two evaluation scripts end to end.

## Dependencies

**Depends on.**
- Standard library: `json`, `sys`, `unittest` {src:tests/scripts/search/test_golden.py:10-12}. Helper [[support]] and [support](support.md) for `CORPUS`, `GOLDEN`, `in_env`, `script_env`, `throwaway_home`, `run_script`, `HAVE_STORE` and `NOTE` {src:tests/scripts/search/test_golden.py:14-15}.
- Code under test: [[build_index]] and [build_index](../../../scripts/search/build_index.md) {src:tests/scripts/search/test_golden.py:31}, [[eval_rag]] and [eval_rag](../../../scripts/search/eval_rag.md) {src:tests/scripts/search/test_golden.py:35}, [[eval_judge]] and [eval_judge](../../../scripts/search/eval_judge.md) {src:tests/scripts/search/test_golden.py:93}, and the script [[eval_retrieval]] and [eval_retrieval](../../../scripts/search/eval_retrieval.md) run as a subprocess {src:tests/scripts/search/test_golden.py:81}.
- Data: the folder `tests/rag_eval/corpus` (4 top-level entries on 2026-11-20) and `tests/rag_eval/golden_questions.json` (57 questions, 3 marked critical, 11 marked expect-none, counted by a one-off read on 2026-11-20) {src:tests/scripts/search/support.py:20-21}.
- Environment: `TOLLGATE_KNOWLEDGE` set to the corpus {src:tests/scripts/search/test_golden.py:30}; `TOLLGATE_EVAL_CASES` removed for the CLI test {src:tests/scripts/search/test_golden.py:88}.
- Packages `chromadb` and PyYAML; the whole class is skipped without them {src:tests/scripts/search/test_golden.py:24}.

**Used by.** Searched with `git grep` for `test_golden` outside `docs/` on 2026-11-20: nothing names it; the folder runner [[run]] and [run](run.md) finds it by pattern {src:tests/scripts/search/run.sh:9}.

## Behavior

**Shared setup (once per class).** `setUpClass` makes a throwaway home, builds a full index of the corpus with the hash embedder (`summary`), builds again with no `full` (`again`), loads the golden file, and scores every question with `top_k=3` (`rows`) {src:tests/scripts/search/test_golden.py:28-37}. `tearDownClass` removes the home {src:tests/scripts/search/test_golden.py:39-41}. Six of the tests below read these shared results, one more (tickets) queries the shared index, and the other three (the two script runs and the judge) do not use it.

**Constants.** `MIN_HIT_RATE = 0.80`, the floor for the fake embedder {src:tests/scripts/search/test_golden.py:19}; `BASIC_PREFIX = "q0"` {src:tests/scripts/search/test_golden.py:20}; `OFFTOPIC` is the ids `d27` to `d32` {src:tests/scripts/search/test_golden.py:21}.

**Tests.**
- `test_index_builds_on_the_corpus`: zero errors, embedder name `hash-v1`, at least 20 files indexed, and more than zero chunks in both the `vault` and `tickets` collections {src:tests/scripts/search/test_golden.py:44-48}.
- `test_second_build_changes_nothing`: the second build indexes 0 files, adds 0 chunks, and skips exactly as many files as the first build indexed {src:tests/scripts/search/test_golden.py:51-53}.
- `test_tickets_use_vault_relative_keys`: a search for "duplicate rows after the nightly retry" returns at least one file key that starts with `02-tickets/EX-101/` {src:tests/scripts/search/test_golden.py:58-59}. `default_retrieve` returns the file keys above the embedder's score floor {src:scripts/search/eval_rag.py:40-41}.
- `test_basic_questions_all_return_the_expected_file`: the rows whose id starts with `q0` number exactly 7, and every one has verdict `PASS` {src:tests/scripts/search/test_golden.py:62-65}. A row passes when the expected file ranks within the top 3 and any file that must be outranked is outranked {src:scripts/search/eval_rag.py:58-65}.
- `test_no_critical_question_misses`: no row has verdict `HALLUCINATION_RISK`, which is what a failing row gets when it is marked critical {src:tests/scripts/search/test_golden.py:68-69} {src:scripts/search/eval_rag.py:65}.
- `test_off_topic_questions_return_nothing`: for the ids `d27` to `d32`, `returned` must be 0 {src:tests/scripts/search/test_golden.py:72-73}.
- `test_hit_rate_floor`: the summary `hit_rate` is at least 0.80 {src:tests/scripts/search/test_golden.py:77-78}. The rate counts a row as found when it expected nothing and returned nothing, or its expected file ranked within `top_k` {src:scripts/search/eval_rag.py:90-93}.
- `test_eval_retrieval_runs_end_to_end`: runs `eval_retrieval.py` with the corpus, golden file, `hash` and `--min-hit-rate 0.0`, and checks the text `hit@3` is in stdout {src:tests/scripts/search/test_golden.py:81-84}. The report line prints `hit@{top_k}` {src:scripts/search/eval_rag.py:106}.
- `test_eval_rag_cli_needs_a_question_file`: with no `--golden` and no `TOLLGATE_EVAL_CASES`, `eval_rag.py` exits with code 2 {src:tests/scripts/search/test_golden.py:87-90}, matching the check in the script {src:scripts/search/eval_rag.py:118-120}.
- `test_eval_judge_scores_relevance`: two questions with a fake search and the word-overlap judge at threshold 0.3. The first returns one passage and counts 1 relevant, the second returns nothing, and precision is 1.0 {src:tests/scripts/search/test_golden.py:94-100}. The judge scores the share of question words of 4 or more letters found in the passage {src:scripts/search/eval_judge.py:31-37}, and precision averages relevant over returned for questions that expected results and got some {src:scripts/search/eval_judge.py:68-72}.

## Diagram

None: one shared index and a plain list of checks, no chain of mocks.

## Notes

- Code and description: the header says the golden questions "return the expected files" {src:tests/scripts/search/test_golden.py:3}. That is only enforced for the seven `q0` questions and the 0.80 overall floor. The other 50 can miss, and the comment says so on purpose {src:tests/scripts/search/test_golden.py:17-18}. The header names "SCR-03" {src:tests/scripts/search/test_golden.py:3}, a label that appears nowhere else in the repo (searched with `git grep` outside `docs/`, 2026-11-20, one hit: this line). The `date:` field is empty {src:tests/scripts/search/test_golden.py:5}.
- Weak assertions: `test_eval_retrieval_runs_end_to_end` uses `--min-hit-rate 0.0` and checks only that `hit@3` is printed {src:tests/scripts/search/test_golden.py:83-84}, so it proves the script runs and prints, not that results are good. `test_eval_rag_cli_needs_a_question_file` pops `TOLLGATE_EVAL_CASES` {src:tests/scripts/search/test_golden.py:88}, but the throwaway env already strips every `TOLLGATE_*` key {src:tests/harness/throwaway_home.py:31-33}, so the pop is redundant.
- The off-topic test names only 6 of the 11 questions marked expect-none; the five `d33` to `d37` "absent" questions are covered by the hit-rate floor only {src:tests/scripts/search/test_golden.py:21}.
- Hard-coded counts depend on the data files: exactly 7 ids with prefix `q0` {src:tests/scripts/search/test_golden.py:63}, at least 20 indexed files {src:tests/scripts/search/test_golden.py:46}, and the ticket key `EX-101` {src:tests/scripts/search/test_golden.py:59}. Adding a `q0x` question or trimming the corpus breaks them.
- The tests share state through the class (one index for all), so test order does not matter, but one failed setup fails every test in the class. No test depends on a machine path or the Python version; the corpus path comes from the repo root {src:tests/scripts/search/support.py:20}.
- Unchecked inputs: the corpus path is written into a paths file by `eval_retrieval.py` with no quoting or check {src:scripts/search/eval_retrieval.py:31}; here it is a repo path, so it is safe in practice. No other input in this file reaches a path, command, address or outbound text without a check.
- Shared-file writes: the build writes the index into the throwaway home; `eval_retrieval.py` writes its own paths file in a temp folder {src:scripts/search/eval_retrieval.py:29-31}. Nothing is atomic and nothing locks, but there is one writer at a time.
- Not tested: `eval_judge.ollama_judge` (network call to a model server) and the `--json` output of `eval_rag.py`.
