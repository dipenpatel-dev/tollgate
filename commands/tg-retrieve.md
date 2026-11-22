# /tg-retrieve

Author: {INITIALS}
Date:

Query the search index and return grounded passages as session context.

Usage: `/tg-retrieve <query>`

The search index is the only place this command reads. Look in the vault first when the answer is a known ticket or note; use this command when a keyword lookup would miss.

## Rules

- Accept the query as the argument passed to this command.
- Return passages as session context only. Write nothing to any log for this call.
- Empty results are a valid outcome, not an error.
- The embedder and the vector store are local and optional. With no index the script prints `not set up`. Treat that as "not available", never as a crash.
- Pass the query on standard input, never as an argument, so any character in it is safe.

## Steps

1. Run the search script with the query on standard input (replace the words between the markers with the user's query; keep the quotes on the marker line):

   ```bash
   $TOLLGATE_HOME/scripts/search/tg-search query --stdin --top 8 2>/dev/null <<'TG_QUERY'
   {the query}
   TG_QUERY
   ```

   The script searches the vault, tickets, references and knowledge collections (plus code and standards when they are on) and prints a JSON list of `{file, heading, excerpt, score, tier, tier_label, collection}`. Add `--intent teach|verify|build|decide|draft` only when the user says what the answer is for.

2. Handle the outcomes:
   - The output is `not set up` (exit 2): print "Search is not set up. Run ./install.sh with the search step, or `bash $TOLLGATE_HOME/scripts/search/rebuild.sh`, to build the index." and stop.
   - The output is a JSON object with an `error` key: say the search failed in one line, without the error text, and stop.
   - The output is `[]`: print "No results found. If the index is out of date, run `bash $TOLLGATE_HOME/scripts/search/rebuild.sh`." and stop.

3. Return results as session context. Surface each passage with its file, heading and tier label. A passage carries an excerpt, not the full file; open the file when more is needed. Do not write passage content to any file.
