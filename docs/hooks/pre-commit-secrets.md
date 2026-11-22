---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "tollgate"
source_file: "hooks/pre-commit-secrets"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE     # ACTIVE or ARCHIVED
last_updated: 2026-11-21
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: "for loop over PATTERNS (line 37)"    # function or line that executes when the script runs
requires: [bash, git, awk, grep, head, sed, echo]       # external commands or tools this script depends on
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

`hooks/pre-commit-secrets` is a git pre-commit hook, not a Claude Code hook. Before a commit is recorded it looks at the lines being added and refuses the commit if any of them look like a real credential, such as an API token or a private key header. It exists so a secret cannot be committed by hand or by any tool, even where no Claude Code hook is running.

## Dependencies

**Depends on.**
- `bash`, `git`, `awk`, `grep`, `head`, `sed` {src:hooks/pre-commit-secrets:38} {src:hooks/pre-commit-secrets:47}.
- No environment variables and no files. The 23 patterns are written in the script {src:hooks/pre-commit-secrets:9-33}.

**Used by.**
- Product code: no `settings.json` entry. `install.sh` only prints a copy command for the user to run in each repo, and only when not in simple mode {src:install.sh:1697-1700}. Searched 2026-11-21: `install.sh` for `pre-commit`; that is the only line.
- The hook inventory check lists it as a helper that need not be wired {src:tests/hooks/check_hook_inventory.py:39} {src:tests/hooks/check_hook_inventory.py:46}.
- Tests: [test_security_fixes](../tests/hooks/test_security_fixes.md) runs it on staged files {src:tests/hooks/test_security_fixes.py:366} {src:tests/hooks/test_security_fixes.py:376} {src:tests/hooks/test_security_fixes.py:386} {src:tests/hooks/test_security_fixes.py:406}. [test_secret_shapes](../tests/hooks/test_secret_shapes.md) checks each added shape {src:tests/hooks/test_secret_shapes.py:171}.

## Behavior

1. Strict mode `-euo pipefail` is on {src:hooks/pre-commit-secrets:5}. The match pipeline ends in `|| true`, so "no match" does not abort the script {src:hooks/pre-commit-secrets:38}. The same `|| true` also hides a failure of `grep` itself.
2. `PATTERNS` holds 23 extended regular expressions {src:hooks/pre-commit-secrets:9-33}. The first group: Atlassian `ATATT`, Slack `xoxb-` and `xoxp-`, Anthropic `sk-ant-api03-`, Databricks `dapi`, GitHub `github_pat_` and `gh[pousr]_`, OpenAI `sk-`, Plane `plane_api_`, a JSON member such as `"token": "<20+ characters>"`, Azure `AccountKey=`, and a private key header {src:hooks/pre-commit-secrets:10-21}. The second group, added in v1: AWS access keys (`AKIA`, `ASIA`), OpenAI `sk-proj-`, `sk-svcacct-` and `sk-admin-`, Stripe live keys, Google API keys, npm, Hugging Face, GitLab, SendGrid, JWT, Slack webhook URLs, and credentials inside a URL {src:hooks/pre-commit-secrets:22-32}. Most of the second group start with `(^|[^A-Za-z0-9])`, so a key must not be glued to a longer word {src:hooks/pre-commit-secrets:22-30}.
3. For each pattern the script runs `git diff --cached --unified=0`, passes the output through an `awk` filter, and applies the pattern with `grep -E -e` {src:hooks/pre-commit-secrets:38}. The filter sets a flag at each `diff --git` line and clears it at the first `@@` line, so each file's header block is skipped; after that it keeps every line that starts with `+` {src:hooks/pre-commit-secrets:38}. An added line whose own text starts with `++` is therefore still scanned. The `-e` makes `grep` read a pattern that starts with a dash (the private key header) as a pattern, not an option {src:hooks/pre-commit-secrets:38}. This is 23 runs of `git diff`, one per pattern.
4. On the first hit it prints a banner that the commit is blocked and that credentials belong in environment variables or a secrets manager {src:hooks/pre-commit-secrets:40-44}. For every matching pattern it prints the pattern and up to three matching lines {src:hooks/pre-commit-secrets:46-47}.
5. If any pattern matched it prints the `--no-verify` hint and exits 1, which makes git abort the commit {src:hooks/pre-commit-secrets:53-56}. Otherwise it exits 0 {src:hooks/pre-commit-secrets:58}.
6. Git does not run pre-commit hooks when the commit uses `--no-verify` {src:docs:githooks(5)}. The script itself names that flag as the override {src:hooks/pre-commit-secrets:54}.

## Diagram

```mermaid
flowchart TD
  Start["Commit starts"] --> Next["Take next pattern"]
  Next --> Diff["Read staged added lines"]
  Diff --> Hit{"Any match?"}
  Hit -- yes --> Note["Print pattern and lines"]
  Hit -- no --> More
  Note --> More{"More patterns?"}
  More -- yes --> Next
  More -- no --> Found{"Any hit?"}
  Found -- yes --> Block["Exit 1, block commit"]
  Found -- no --> Allow["Exit 0, allow commit"]
```

## Notes

**Code and description disagree.**
- The header says "install.sh installs it" {src:hooks/pre-commit-secrets:4}. `install.sh` does not install it. It prints a copy command, and prints it only when simple mode is off {src:install.sh:1697-1700}.
- The header says the minimum lengths prevent false positives on the pattern strings in this file {src:hooks/pre-commit-secrets:7-8}. That holds: a test commits the hook file itself and expects exit 0 {src:tests/hooks/test_security_fixes.py:399-407}.

**What the filter and `-e` fix.** The private key pattern starts with five dashes {src:hooks/pre-commit-secrets:21}. Without `-e`, BSD `grep` can read such a pattern as an option and fail, and the `|| true` would hide the failure. The call uses `-e` {src:hooks/pre-commit-secrets:38}, and a test stages a private key header and expects exit 1 {src:tests/hooks/test_security_fixes.py:389-393}. Two tests cover added lines that look like file headers {src:tests/hooks/test_security_fixes.py:370-378} {src:tests/hooks/test_security_fixes.py:395-397}.

**Coverage and limits.**
- The list is shorter than the Claude-side scanner. It has no pattern for Bearer or `Authorization` lines, `export NAME_KEY=` lines, `curl -u` passwords, Azure SAS strings, quoted `password = "..."` assignments, or the variable-name registry {src:hooks/pre-commit-secrets:9-33} {src:hooks/scrub_secrets.py:72} {src:hooks/scrub_secrets.py:75} {src:hooks/scrub_secrets.py:70-71} {src:hooks/scrub_secrets.py:81-89}.
- Slack tokens are matched only as `xoxb-` and `xoxp-`, and Anthropic keys only as `sk-ant-api03-` {src:hooks/pre-commit-secrets:11-13}. The Claude-side list takes `xox[baprs]-` and any `sk-ant-` key {src:hooks/scrub_secrets.py:51} {src:hooks/scrub_secrets.py:57}.
- Matching is case sensitive and does no zero-width or look-alike folding, so a JSON member written as `"API_KEY"`, or a key with hidden characters inside, is not caught {src:hooks/pre-commit-secrets:19} {src:hooks/pre-commit-secrets:38}.
- A URL credential here has no placeholder exclusion, so `https://user:password@host` is flagged; the Claude-side shape skips that word {src:hooks/pre-commit-secrets:32} {src:hooks/scrub_secrets.py:68}.
- Only added lines of the staged diff are checked. Binary files appear in a diff only as a "differ" line, so their content is not scanned {src:docs:git-diff(1)}.
- Matching is on text shape only; nothing checks whether a value is a real credential.

**Inputs that reach a path, command, address or outbound text.** The patterns are constants, the pattern variable is quoted in the `grep` call {src:hooks/pre-commit-secrets:38}, and no input reaches a file path, a shell command or a network address. The outbound text is the problem: the script prints up to three matching lines per pattern, and those lines contain the secret in full {src:hooks/pre-commit-secrets:47}. A blocked commit therefore copies the secret to the terminal and to any log or transcript that records it.

**Writes to shared files.** None. The hook reads the index through `git diff` and prints to stdout. Searched 2026-11-21: `hooks/pre-commit-secrets` for `>` redirects to a file and `tee`; no match.
