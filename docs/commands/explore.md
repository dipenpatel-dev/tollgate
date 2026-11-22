# /tg-explore

**It reads what already exists about a topic (vault, Confluence, Git, Slack), shows you what it found, and after you confirm writes a system-map note.** Use it to learn a client, pipeline or system area. It writes nothing until you confirm the findings {src:commands/tg-explore.md:5-6} {src:commands/tg-explore.md:162}.

The command name is fixed: `/tg-explore [topic / client name / pipeline name / Slack channel]`. If you give no topic it asks "What are we exploring?" {src:commands/tg-explore.md:13} {src:commands/tg-explore.md:15}.

## What it does

1. States its plan first: what it will read, which vault files it will create or update, where it assumes it should look, and whether Slack is connected. It waits for your confirmation {src:commands/tg-explore.md:21-27}.
2. Reads, with no writing. Deep codebase and document searches go through an Explore subagent to protect the main context {src:commands/tg-explore.md:31} {src:commands/tg-explore.md:33}.
   - Vault first: relevant files, existing docs in `{system_map}`, prior ticket work in `{tickets}`, decisions and patterns in `{knowledge}`. It prefers updating a note over creating one {src:commands/tg-explore.md:35}.
   - Confluence, through `mcp__atlassian__searchConfluenceUsingCql` or `searchAtlassian`, then full pages for relevant hits {src:commands/tg-explore.md:37-39}.
   - Git: pipeline code, configs and schema files in `$TOLLGATE_CODE_DIR`, read-only {src:commands/tg-explore.md:41-43}.
   - Slack, if connected: searches channels, reads threads, flags decisions never documented elsewhere {src:commands/tg-explore.md:45-49}.
3. If Slack is not connected it prints a one-line notice (re-run `install.sh` and paste a bot token to connect) and continues. Missing Slack is not a failure {src:commands/tg-explore.md:51-53} {src:commands/tg-explore.md:161}.
4. If the topic touches client data or patient pipelines it flags the PHI or PII implications and stops until you acknowledge {src:commands/tg-explore.md:55-56}.
5. Presents findings before writing: what it found, how things connect upstream and downstream, why things were done that way ("Decision found, rationale unknown" when no reason is found), gaps, every assumption, prioritized open questions, and any Databricks or Unity Catalog concepts met. It asks you to correct anything wrong and confirm {src:commands/tg-explore.md:62-84}.
6. After approval, writes the main note and, if new concepts came up, a learning note. It reports each file created or updated with its full path {src:commands/tg-explore.md:88} {src:commands/tg-explore.md:91} {src:commands/tg-explore.md:121-122} {src:commands/tg-explore.md:139}.
7. Lists what to explore next, questions to answer before acting, and a suggested next command (`/tg-ticket`, `/tg-arch` or another `/tg-explore`) {src:commands/tg-explore.md:145-154}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{vault}`, `{system_map}`, `{tickets}` and `{knowledge}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-explore.md:3}. All four names exist in the path loader {src:scripts/core/paths.py:33-36} {src:scripts/core/paths.py:56}.

- Reads: the vault folders above, Confluence, Slack when connected, and the company repos under `$TOLLGATE_CODE_DIR` {src:commands/tg-explore.md:35} {src:commands/tg-explore.md:37-45}.
- Writes: `{system_map}/[area]/[topic].md` (what it is, how it connects, key files, decisions found, open questions, related links) {src:commands/tg-explore.md:91-119}. Optionally `{system_map}/databricks-learning/[concept].md` {src:commands/tg-explore.md:121-137}.
- Scripts: only `$TOLLGATE_HOME/scripts/core/tg_path`, which exists {src:commands/tg-explore.md:3}. It calls no search script, no cost script and no vault git script.
- Vault git: the command has no commit or push step, so it commits nothing. Use `/tg-close` or the vault git lines other commands print; see [tg_vault_git](../scripts/core/tg_vault_git.md).

## Hooks and gate lines

The command writes no `Status:` gate line and touches no ticket state. It names no hook. Any vault frontmatter or PHI hooks that watch your vault writes still apply to the notes it creates.

## Stops

- Waits for your confirmation of the plan {src:commands/tg-explore.md:27}.
- Waits for acknowledgment on a PHI or PII flag {src:commands/tg-explore.md:55-56}.
- Waits for confirmation of the findings before any vault write {src:commands/tg-explore.md:84} {src:commands/tg-explore.md:162}.

## Notes

- The page template hard-codes vault paths in two of the three links in its Related list (`[[01-system-map/clients/client-name]]` and `[[03-knowledge-base/decisions/YYYY-MM-DD-topic]]`) even though the command tells itself to look folders up with `tg_path` {src:commands/tg-explore.md:116} {src:commands/tg-explore.md:118}. The ticket link is a bare name, `[[JIRA-ID-spec]]`, with no folder in it, so it works for both the flat and the nested `02-tickets/PREFIX/KEY/` layout {src:commands/tg-explore.md:117}.
- It reads `{tickets}/` only as "prior ticket work" with no pattern, so on a nested vault it relies on the model to look inside prefix folders {src:commands/tg-explore.md:35}.
- The command says Slack "if available". Its description line says "Confluence + Git + Slack", but Slack is optional and Confluence needs the Atlassian tools to be connected; the command has no fallback text for a missing Confluence connection {src:commands/tg-explore.md:5} {src:commands/tg-explore.md:37-39}.
- The "Meeting notes to process" next step says to handle them in this session; the command does not say how {src:commands/tg-explore.md:155}.

## What it never does

- It never writes to the vault before presenting findings and getting your confirmation {src:commands/tg-explore.md:162}.
- It never writes in the company repos; they are read-only {src:commands/tg-explore.md:42}.
- It does not duplicate vault entries; it reads what is there and builds on it {src:commands/tg-explore.md:164}.

## Example

```
/tg-explore client onboarding pipeline
```

It states the plan, reads the vault, Confluence, Git and Slack, shows what it found and the open questions, and after you confirm writes `{system_map}/[area]/[topic].md` {src:commands/tg-explore.md:21-27} {src:commands/tg-explore.md:62-84} {src:commands/tg-explore.md:91}.
