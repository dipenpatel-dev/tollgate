# Port tool

The port tool copies a file or folder into the Tollgate repo and cleans it on the way. It never changes the source. It never writes outside the destination you give it.

## What it does by itself

1. Personal absolute paths become variables from `docs/variables.md` (pairs in `tools/port/mappings.json`).
2. Ticket prefixes like `AB-12` become `${TOLLGATE_TICKET_PREFIX}-12`. Command prefixes like `ab-` (the `skill_prefixes` list in the mapping) become the fixed `tg-`; there is no per-install prefix variable. {src:tools/port/port.py:129} Initials become `${TOLLGATE_INITIALS}`.
3. Names on your private term file become `Client A` (or the word you write after `=>`).
4. A `Date:` field in the first 30 lines is emptied. Dates in change-log entries are removed. Dates elsewhere stay.
5. AI attribution lines are removed. Em dashes become a comma or a period.

Works on shell, Python, Markdown, JSON and YAML. Other text files get the same treatment. Binary files are copied as they are. File mode bits are kept. Running it twice gives the same result.

## Your private files

The real path pairs, prefixes and names are private. Pass them by flag or by environment variable. They are never stored in the repo.

| What | Flag | Environment variable | Format |
|---|---|---|---|
| Mapping | `--map` | `TOLLGATE_PORT_MAP` | JSON like `tools/port/mappings.json` |
| Term file | `--denylist` | `TOLLGATE_DENYLIST` | one term per line; `term => replacement` optional; `#` for comments |

## Leftovers

The tool writes `leftovers.md` inside the destination. It lists each line it could not safely rewrite, with file, line and reason: political words, names that look like people, hosts, IP addresses, email addresses, tokens, and personal paths with no mapping. It does not repeat the line itself. It also lists every em dash and attribution line it changed. Fix the leftovers by hand, then delete `leftovers.md` before you commit.

## Safety

The destination must be inside the Tollgate repo (`--root` changes that, for tests). Source and destination must not overlap. `--dry-run` prints what would change and writes nothing.

## Example

    export TOLLGATE_PORT_MAP=~/private/port-map.json
    export TOLLGATE_DENYLIST=~/private/terms.txt
    tools/port/run.sh /path/to/source/commands commands/ported --dry-run
    tools/port/run.sh /path/to/source/commands commands/ported
    cat commands/ported/leftovers.md

Run the tests with `python3 -m unittest discover -s tools/port/tests`.
