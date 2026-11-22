# Charts: `scripts/chart/`

This folder checks the diagrams in your documents. It holds four things: the `chart_check` command, its rules (`chart_rules.json` and the loader `chart_rules.py`), the data source seam (`data_source.py`), and a small block copier (`mermaid_block.py`).

## chart_check

`scripts/chart/chart_check --role ROLE [--ticket KEY | --state FILE] [--require-chart] [--rules FILE] FILE...` {src:scripts/chart/chart_check:16}

It finds every closed `mermaid` block in each file, names its type from the first word, and reports the blocks that break a rule {src:scripts/chart/chart_check:67} {src:scripts/chart/chart_check:84} {src:scripts/chart/chart_check:104} {src:scripts/chart/chart_check:148}. The doc-gen command calls it with `--role document-writer` and the whiteboard command calls it with `--role idea-analyst --require-chart` {src:commands/tg-doc-gen.md:229} {src:commands/tg-whiteboard.md:141}.

| Exit | Meaning |
|---|---|
| 0 | No findings. Prints nothing {src:scripts/chart/chart_check:64} {src:scripts/chart/chart_check:268}. |
| 1 | Findings. Prints the file name, one line per finding (chart number, line, reason), the allowed types, and how to add an exception {src:scripts/chart/chart_check:177} {src:scripts/chart/chart_check:178} {src:scripts/chart/chart_check:179} {src:scripts/chart/chart_check:180} {src:scripts/chart/chart_check:270}. |
| 2 | It could not finish (bad arguments, unknown role, unreadable file or rules, ticket given but paths not set up). The reason is on stderr {src:scripts/chart/chart_check:252} {src:scripts/chart/chart_check:254} {src:scripts/chart/chart_check:260} {src:scripts/chart/chart_check:278}. |

Rules checked:

1. The chart type must be on the role's list in `chart_rules.json` {src:scripts/chart/chart_check:157} {src:scripts/chart/chart_check:163} {src:scripts/chart/chart_rules.json:63}. Nine types are known: flowchart, sequence, class, state, er, git_graph, requirement, architecture, folder_tree {src:scripts/chart/chart_rules.json:4} {src:scripts/chart/chart_rules.json:12} {src:scripts/chart/chart_rules.json:18} {src:scripts/chart/chart_rules.json:24} {src:scripts/chart/chart_rules.json:31} {src:scripts/chart/chart_rules.json:37} {src:scripts/chart/chart_rules.json:44} {src:scripts/chart/chart_rules.json:50} {src:scripts/chart/chart_rules.json:56}.
2. A flowchart may not use circle, hexagon or stadium shapes (`((`, `{{`, `([`), may not have more than 12 nodes, and may not use per-node `style` lines (use `classDef`) {src:scripts/chart/chart_check:165} {src:scripts/chart/chart_check:166} {src:scripts/chart/chart_check:168} {src:scripts/chart/chart_check:170} {src:scripts/chart/chart_rules.json:179} {src:scripts/chart/chart_rules.json:180} {src:scripts/chart/chart_rules.json:181} {src:scripts/chart/chart_rules.json:182} {src:scripts/chart/chart_rules.json:183}.
3. No chart may hold an IPv4 host address {src:scripts/chart/chart_check:48} {src:scripts/chart/chart_check:172} {src:scripts/chart/chart_check:173}.
4. `--require-chart` fails a document with no chart {src:scripts/chart/chart_check:151} {src:scripts/chart/chart_check:152}.
5. An allowed exception is a line `%% exception: <reason>` inside the chart. An empty reason is a finding {src:scripts/chart/chart_check:41} {src:scripts/chart/chart_check:121} {src:scripts/chart/chart_check:122} {src:scripts/chart/chart_check:160} {src:scripts/chart/chart_check:161}.

`--ticket KEY` finds the ticket folder with the shared `ticket_folder` lookup, so it works for `<tickets>/<PREFIX>/<KEY>/<KEY>-state.md` and for a flat folder {src:scripts/chart/chart_check:205} {src:scripts/chart/chart_check:207} {src:scripts/chart/chart_check:208} {src:scripts/chart/chart_check:211}. `--state FILE` names the state file directly {src:scripts/chart/chart_check:246} {src:scripts/chart/chart_check:247}. If its front matter says `touches_data_model: true` (the plain word, not quoted), `er` is added to the allowed list {src:scripts/chart/chart_rules.json:174} {src:scripts/chart/chart_rules.json:175} {src:scripts/chart/chart_check:199} {src:scripts/chart/chart_check:200} {src:scripts/chart/chart_check:201} {src:scripts/chart/chart_rules.py:86} {src:scripts/chart/chart_rules.py:87}. No state file means no widening {src:scripts/chart/chart_check:255}.

Findings never repeat text from the document {src:scripts/chart/chart_check:4} {src:scripts/chart/chart_check:5} {src:scripts/chart/chart_check:6}. To change a verdict, edit `chart_rules.json`; no code change is needed {src:scripts/chart/chart_rules.json:2}. `chart_rules.py` loads and checks that file and answers which types a role may use {src:scripts/chart/chart_rules.py:35} {src:scripts/chart/chart_rules.py:76}.

## The data source seam

`data_source.py` defines `DataSource` with two methods, `fetch_rows` and `fetch_summary` {src:scripts/chart/data_source.py:42} {src:scripts/chart/data_source.py:52} {src:scripts/chart/data_source.py:56}. `CsvSource` and `SqliteSource` are samples for tests and small exports {src:scripts/chart/data_source.py:69} {src:scripts/chart/data_source.py:110}. SQLite opens read-only and binds every value {src:scripts/chart/data_source.py:118} {src:scripts/chart/data_source.py:142}. Every table and column name is checked to letters, digits and underscores {src:scripts/chart/data_source.py:19} {src:scripts/chart/data_source.py:23}. `open_source("csv:FOLDER")` or `open_source("sqlite:FILE")` builds one {src:scripts/chart/data_source.py:167} {src:scripts/chart/data_source.py:168}. A real database connector subclasses `DataSource` (see `docs/scripts/connectors-data.md`) {src:scripts/connectors/data/databricks.py:212}.

## Also here

`mermaid_block.py FILE [N] [--stdout]` lists the mermaid blocks in a markdown file, or copies block N to the clipboard (it finds `pbcopy`, `wl-copy` or `xclip`, else prints) {src:scripts/chart/mermaid_block.py:25} {src:scripts/chart/mermaid_block.py:82} {src:scripts/chart/mermaid_block.py:83} {src:scripts/chart/mermaid_block.py:91} {src:scripts/chart/mermaid_block.py:95} {src:scripts/chart/mermaid_block.py:96} {src:scripts/chart/mermaid_block.py:97}.

## Tests

`tests/scripts/chart/run.sh`
