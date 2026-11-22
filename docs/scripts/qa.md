# QA helpers: `scripts/qa/`

The folder holds one script, `scan_notebooks.py`.

`scan_notebooks.py PATH` counts sensitive-looking patterns in notebooks. PATH is one `.ipynb` file or a folder of them {src:scripts/qa/scan_notebooks.py:15} {src:scripts/qa/scan_notebooks.py:64}.

It prints, per notebook, the code cell count, line count, how many cells hold saved output, and for each pattern a count and up to 12 line numbers {src:scripts/qa/scan_notebooks.py:26} {src:scripts/qa/scan_notebooks.py:100} {src:scripts/qa/scan_notebooks.py:103}. It never prints notebook text and writes nothing to disk {src:scripts/qa/scan_notebooks.py:4} {src:scripts/qa/scan_notebooks.py:5} {src:scripts/qa/scan_notebooks.py:90}. Saved outputs are counted, not read {src:scripts/qa/scan_notebooks.py:84} {src:scripts/qa/scan_notebooks.py:85}. A zero count is not proof a notebook is clean: the patterns cannot see names or plain-word lists {src:scripts/qa/scan_notebooks.py:7} {src:scripts/qa/scan_notebooks.py:8}.

Patterns: `email`, `ssn_like`, `digit_run_7_plus`, `digit_list_literal`, `date_literal`, `hardcoded_secret_literal`, `connection_string_marker`, `secret_store_call`, `uri_cloud_storage`, `uri_mount_or_volume` and `output_exposure_calls` (`print`, `display`, `show`, `collect`, `toPandas`) {src:scripts/qa/scan_notebooks.py:30} {src:scripts/qa/scan_notebooks.py:31} {src:scripts/qa/scan_notebooks.py:32} {src:scripts/qa/scan_notebooks.py:33} {src:scripts/qa/scan_notebooks.py:34} {src:scripts/qa/scan_notebooks.py:35} {src:scripts/qa/scan_notebooks.py:38} {src:scripts/qa/scan_notebooks.py:39} {src:scripts/qa/scan_notebooks.py:40} {src:scripts/qa/scan_notebooks.py:41} {src:scripts/qa/scan_notebooks.py:42}.

Exit 0 after a scan, 2 when the path does not exist. An unreadable file is listed as not scanned {src:scripts/qa/scan_notebooks.py:122} {src:scripts/qa/scan_notebooks.py:124} {src:scripts/qa/scan_notebooks.py:111}.

## The seam

`NotebookSource` is a small interface (`iter_notebooks()` yields a label and a notebook) {src:scripts/qa/scan_notebooks.py:46} {src:scripts/qa/scan_notebooks.py:53}. `LocalFolderSource` is the built-in one {src:scripts/qa/scan_notebooks.py:57}. A connector that exports notebooks from a remote workspace subclasses it. The Databricks connector does (see `docs/scripts/connectors-data.md`) {src:scripts/connectors/data/databricks.py:264}.

## Tests

`tests/scripts/qa/run.sh`.
