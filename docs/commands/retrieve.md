# /tg-retrieve

Looks up passages from the search index and hands them to the conversation as context {src:commands/tg-retrieve.md:6}.

The command name is fixed: `/tg-retrieve <query>` {src:commands/tg-retrieve.md:8}.

## When to use

When a keyword search of the vault would miss and you want meaning-based lookup. Look in the vault first when the answer is a known ticket or note {src:commands/tg-retrieve.md:10}.

## What it does

1. Runs `$TOLLGATE_HOME/scripts/search/tg-search query --stdin --top 8`, with the query passed on standard input and never as an argument, so any character in it is safe {src:commands/tg-retrieve.md:18} {src:commands/tg-retrieve.md:25}. It adds `--intent teach|verify|build|decide|draft` only when you say what the answer is for {src:commands/tg-retrieve.md:30}.
2. Handles the outcomes {src:commands/tg-retrieve.md:32-35}:
   - `not set up` (exit 2): it prints how to build the index and stops.
   - A JSON object with an `error` key: it says the search failed in one line, without the error text, and stops.
   - `[]`: it says no results were found, and suggests rebuilding the index if it is out of date.
3. Returns the passages as session context, each with its file, heading and tier label. A passage is an excerpt, not the full file {src:commands/tg-retrieve.md:37}.

Empty results are a valid outcome, not an error {src:commands/tg-retrieve.md:16}.

## What it reads and writes

- Reads: the search index only, through `$TOLLGATE_HOME/scripts/search/tg-search query`. It searches the vault, tickets, references and knowledge collections, plus code and standards when they are on {src:commands/tg-retrieve.md:10} {src:commands/tg-retrieve.md:30}. The embedder and vector store are local and optional; with no index the script prints `not set up` {src:commands/tg-retrieve.md:17}.
- Writes: nothing. Passages stay in the conversation, are not written to any file and no log is written for the call {src:commands/tg-retrieve.md:15} {src:commands/tg-retrieve.md:37}.
- It uses no folder lookup and no vault git line.

## Hooks and gate lines

No gate line applies. It is not part of the spec, arch, dev, qa chain, so the gate does not read it. The normal write guards still apply to any file it writes.

## Example

`/tg-retrieve how did we handle the T-001 retry bug` returns the best matching passages. If the index was never built it tells you to run `./install.sh` with the search step, or `bash $TOLLGATE_HOME/scripts/search/rebuild.sh`, to build it {src:commands/tg-retrieve.md:33}.
