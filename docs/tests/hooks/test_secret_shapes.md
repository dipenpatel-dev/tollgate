---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "tests/hooks/test_secret_shapes.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: ["hooks/scrub_secrets.py", "hooks/post-tool-bash-scan-secrets.py", "hooks/pre-commit-secrets", "hooks/phi_patterns.py"]         # source files under test, relative paths from repo root
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

This file tests that the secret scanners catch the key shapes added after the first release, and that ordinary text is left alone. The scanners are the check before a tool runs and the redaction after it in `scrub_secrets.py`, its `scrub_text` helper, the output scanner `post-tool-bash-scan-secrets.py`, and the commit hook `pre-commit-secrets` {src:tests/hooks/test_secret_shapes.py:5-7}. It builds 14 fake values of the new shapes at run time, by joining pieces, so no whole key sits in the source {src:tests/hooks/test_secret_shapes.py:13} {src:tests/hooks/test_secret_shapes.py:34-51}. It has 17 tests in 3 classes. It was not run while this page was written, so each claim says what a test asserts.

## Dependencies

**Depends on.**
- The scrubber `hooks/scrub_secrets.py`: [[scrub_secrets]] and [scrub_secrets](../../hooks/scrub_secrets.md). It is started as a child process and also imported, for `scrub_text` {src:tests/hooks/test_secret_shapes.py:29} {src:tests/hooks/test_secret_shapes.py:55}.
- The output scanner [[post-tool-bash-scan-secrets]] and [post-tool-bash-scan-secrets](../../hooks/post-tool-bash-scan-secrets.md) {src:tests/hooks/test_secret_shapes.py:140}, and the commit hook [[pre-commit-secrets]] and [pre-commit-secrets](../../hooks/pre-commit-secrets.md), run with `bash` {src:tests/hooks/test_secret_shapes.py:171}.
- `hooks/phi_patterns.py` (no doc yet): [[phi_patterns]] and [phi_patterns](../../hooks/phi_patterns.md). The scrubber's text folding calls `normalize_text` from it for any text that is not plain ASCII {src:hooks/scrub_secrets.py:114-117}.
- The `git` program, used by the commit hook tests {src:tests/hooks/test_secret_shapes.py:167}.
- Standard library only: `json`, `os`, `subprocess`, `sys`, `tempfile`, `unittest` {src:tests/hooks/test_secret_shapes.py:18-23}.
- Environment: the hook child processes get the developer's whole environment {src:tests/hooks/test_secret_shapes.py:55}.

**Used by.** Product code: none. Tests: the unit test step of the hook runner finds it by the pattern `test_*.py` {src:tests/hooks/run.sh:198}, and CI runs the same command {src:.github/workflows/tests.yml:35}. Its header gives the command `python3 tests/hooks/test_secret_shapes.py` {src:tests/hooks/test_secret_shapes.py:12}. Searched 2026-11-21: the whole worktree except `.git`, `docs/`, caches and virtual environments for `test_secret_shapes`; no other file names it.

## Behavior

**Setup.** `fakes` returns a label-to-value map of 14 entries: `AWS_ACCESS_KEY` (with a `KEY_` prefix), `OPENAI_KEY` (the `proj` form), `STRIPE_KEY` and a second `STRIPE_RK` value, `GOOGLE_API_KEY`, `NPM_TOKEN`, `HUGGINGFACE_TOKEN`, `GITLAB_TOKEN`, `SENDGRID_KEY`, `JWT`, `URL_CREDENTIAL`, `SLACK_WEBHOOK`, `CURL_CREDENTIAL` and `BEARER_TOKEN` {src:tests/hooks/test_secret_shapes.py:36-51}. `run` starts a hook with the payload as JSON on stdin {src:tests/hooks/test_secret_shapes.py:54-55}. `pre` builds a before-tool payload {src:tests/hooks/test_secret_shapes.py:58-59}. `deny_text` returns an empty string when the hook printed nothing and otherwise asserts the decision is `deny` and returns the reason {src:tests/hooks/test_secret_shapes.py:62-68}.

**PreScanShapes (9 tests).** These run `scrub_secrets.py` in its before-tool mode.
- Each of the 14 values in a Bash command is denied, and the reason never repeats the value {src:tests/hooks/test_secret_shapes.py:72-77}. The curl value is sent as the command itself, the others after `echo` {src:tests/hooks/test_secret_shapes.py:74}. The reason is built from the label names only {src:hooks/scrub_secrets.py:211-213}, and the Bash command goes through the shape list plus any registry names {src:hooks/scrub_secrets.py:202} {src:hooks/scrub_secrets.py:207}.
- Each value in a Write payload is denied {src:tests/hooks/test_secret_shapes.py:79-81}. A write is scanned with the shape list and the assignment list {src:hooks/scrub_secrets.py:214-217}.
- The reason names the right label for each value, with the `STRIPE_RK` value expected to carry `STRIPE_KEY` {src:tests/hooks/test_secret_shapes.py:83-87}. One Stripe pattern covers the `sk_live_` and `rk_live_` forms {src:hooks/scrub_secrets.py:61}. The test checks that the label is present, not that it is the only one.
- An AWS key that follows an underscore (`export X=KEY_...`) is caught {src:tests/hooks/test_secret_shapes.py:89-90}, because the pattern checks only that the characters before and after are not letters or digits {src:hooks/scrub_secrets.py:52}.
- Four written texts are denied with the label `ASSIGNED_SECRET`: `password = "<value>"`, `db_token: '<value>'`, a JSON `"api_key": "<value>"` member, and `SECRET = "<value>"` {src:tests/hooks/test_secret_shapes.py:92-96}. The pattern wants a name ending in password, passwd, secret, token or api key, then `:` or `=`, then a quoted value of 8 or more characters {src:hooks/scrub_secrets.py:81-88}. The JSON member here has 12 characters, so the JSON shape, which needs 20, does not match; the assignment check is what catches it {src:hooks/scrub_secrets.py:43-46}.
- A Stripe-shaped value with a zero-width space after its fourth character is denied, and so is one whose underscore is replaced by the full-width underscore {src:tests/hooks/test_secret_shapes.py:98-103}. Before matching, the text is folded: zero-width characters are dropped and compatibility forms are normalised {src:hooks/scrub_secrets.py:112-117} {src:hooks/scrub_secrets.py:167} {src:hooks/phi_patterns.py:243}.
- Ordinary text is allowed: 18 written texts and 4 commands give an empty verdict {src:tests/hooks/test_secret_shapes.py:105-115}. The written texts include a password read from the environment, a `<your password>` placeholder, `${TOKEN}`, a `changeme` value, `token_url`, `max_tokens`, a short `sk-` word, a `Bearer <token>` placeholder, `curl -u $USER:$PASS`, a URL with `$PASS` or with the word `pass` as the password, a host-and-colon git address, an `eyJ` word with no dots, an all-capitals value, and `secret_name = "db"` {src:tests/hooks/test_secret_shapes.py:106-112}. The code that lets these through: the URL pattern refuses a `$` or bracket start and the words `pass`, `password`, `secret`, `changeme` {src:hooks/scrub_secrets.py:68}; the curl pattern does not allow `$` in the user part and refuses a `$` or bracket start for the password {src:hooks/scrub_secrets.py:70-71}, and the Bearer pattern refuses a `$` or bracket start {src:hooks/scrub_secrets.py:72}; the assignment pattern refuses a placeholder start, words such as `your`, `change`, `example`, and an all-capitals name value {src:hooks/scrub_secrets.py:83-86}.
- The assignment check is not applied to a Bash command: a command that holds `password = "<value>"` inside `python3 -c` gives an empty verdict {src:tests/hooks/test_secret_shapes.py:117-119}. Only the write branch adds the assignment list {src:hooks/scrub_secrets.py:207} {src:hooks/scrub_secrets.py:217}.
- Input that is not JSON exits 2 {src:tests/hooks/test_secret_shapes.py:121-123} {src:hooks/scrub_secrets.py:258-261}.

**PostAndHelperShapes (6 tests).**
- `scrub_text` redacts all 14 shapes: labels come back, the text holds `[REDACTED:` and the value is gone (for the curl value, the password part is checked) {src:tests/hooks/test_secret_shapes.py:127-132} {src:hooks/scrub_secrets.py:272-287}.
- `scrub_text` returns the input unchanged, with no labels, for an existing `[REDACTED:...]` marker, plain text, and a text holding an accented letter and a zero-width space {src:tests/hooks/test_secret_shapes.py:134-137}. When nothing is found the function hands back the original text, not the folded copy {src:hooks/scrub_secrets.py:285-286}.
- Both `scrub_secrets.py` and `post-tool-bash-scan-secrets.py`, given a Bash result that holds each value, exit 0 and print context holding `[REDACTED:` {src:tests/hooks/test_secret_shapes.py:139-146}. The output scanner gets the 12 newer labels and the `proj` OpenAI shape from the scrubber's list and puts them first {src:hooks/post-tool-bash-scan-secrets.py:72-77}.
- A `NPM_TOKEN` value with a zero-width joiner after its sixth character is still named in the output scanner's context {src:tests/hooks/test_secret_shapes.py:148-152}, because the scanner folds the output before matching {src:hooks/post-tool-bash-scan-secrets.py:103}.
- Clean output (`all good`) gives exit 0 and empty stdout {src:tests/hooks/test_secret_shapes.py:154-156} {src:hooks/post-tool-bash-scan-secrets.py:113-114}.
- Input `x` exits 2 {src:tests/hooks/test_secret_shapes.py:158-160} {src:hooks/post-tool-bash-scan-secrets.py:84-86}.

**PreCommitShapes (2 tests).** `commit_status` makes a temp repo, with global and system git config pointed at the null device, writes one line to `f.txt`, stages it, runs the hook with `bash` in that repo and returns the exit code {src:tests/hooks/test_secret_shapes.py:164-172}.
- Twelve of the 14 values, each as `v = <value>`, give exit 1; the curl and Bearer values are skipped because the hook scans staged file text for value shapes only {src:tests/hooks/test_secret_shapes.py:174-178}. The hook holds 11 patterns for these 12 values, because one Stripe pattern covers both Stripe values, in its list {src:hooks/pre-commit-secrets:22-32} and exits 1 when any matches a staged added line {src:hooks/pre-commit-secrets:38} {src:hooks/pre-commit-secrets:53-55}.
- Four plain texts give exit 0: `hello world`, a URL with `$PASS`, a host-and-colon git address and a URL whose password is `pass` {src:tests/hooks/test_secret_shapes.py:180-183}. The hook's URL pattern needs a password of 6 or more characters that does not hold `$`, `%`, `<`, `{` or `[` {src:hooks/pre-commit-secrets:32}, so `pass` and `$PASS` do not match.

## Diagram

No diagram: each case is one process with one payload, or one temp repo, and there is no mock chain.

## Notes

**Gaps.**
- The commit hook is not tested with zero-width or full-width characters; the shell hook has no folding step (searched `hooks/pre-commit-secrets` for `normal` and for zero-width characters, 2026-11-21: no hits), so a key split by a zero-width character in a staged file would pass it. The output scanner and the scrubber are tested for this; the commit hook is not.
- Header scope says "all four places", but the commit hook is tested with 12 of the 14 shapes {src:tests/hooks/test_secret_shapes.py:5-7} {src:tests/hooks/test_secret_shapes.py:176-177}.
- The zero-width test for the scrubber uses one shape (Stripe), and for the output scanner one shape (npm) {src:tests/hooks/test_secret_shapes.py:99} {src:tests/hooks/test_secret_shapes.py:149}. The normalisation is shared by all shapes {src:hooks/scrub_secrets.py:167}.
- No test covers the older shapes (Anthropic, Databricks, GitHub, Slack) in this file; they are in [test_scrub_secrets](test_scrub_secrets.md) and [test_security_fixes](test_security_fixes.md).
- `test_label_names` and the denied-in-command test pass when the reason holds extra labels as well {src:tests/hooks/test_secret_shapes.py:87}.

**Machine dependence.**
- The scrubber children inherit the developer's environment {src:tests/hooks/test_secret_shapes.py:55}. A `SCRUB_REGISTRY_PATH` set in the shell would add names to the denied list {src:hooks/scrub_secrets.py:121-123}; that changes only what is denied extra, and the allowed-text tests use none of the registry names.
- The commit test sets `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` to the null device so the developer's git config cannot change the result {src:tests/hooks/test_secret_shapes.py:166}.
- Needs `git` and `bash` on the path, and the execute bit on the Python hooks {src:tests/hooks/test_secret_shapes.py:55}.

**Description against code.** The test header says each secret-shaped string is built by concatenation {src:tests/hooks/test_secret_shapes.py:13}. The labels differ between scanners for the Atlassian shape (`ATLASSIAN_TOKEN` against `JIRA_TOKEN`) {src:hooks/scrub_secrets.py:53} {src:hooks/post-tool-bash-scan-secrets.py:40}; no test in this file checks that label.

**Inputs without a check, and shared writes.** The fake values are constants and reach no path, command or network address. The commit test runs `git` and the hook only inside a temp repo {src:tests/hooks/test_secret_shapes.py:165-172}. Importing `scrub_secrets` with `hooks/` on the module path makes Python write `hooks/__pycache__`, which is not atomic and not locked against a second run {src:tests/hooks/test_secret_shapes.py:27} {src:tests/hooks/test_secret_shapes.py:29}. Everything else is under temp folders removed on exit.
