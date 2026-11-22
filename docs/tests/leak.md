# Leak scanner

The scanner checks a repo folder before release and fails if anything personal, secret or political is in it. Exit code 0 means clean, 1 means hits, 2 means bad usage.

    tests/leak/run.sh scan <repo-folder> --denylist <file>
    python3 tests/leak/scan_leaks.py <repo-folder>      # denylist from TOLLGATE_DENYLIST

`tests/leak/run.sh` with no argument runs the scanner's own tests.

It reads every file except `.git`. Text, JSON and HTML are read as text. Images and any other binary give their printable strings (4 or more characters, ASCII and UTF-16), which covers image metadata. The report shows rule, file, line and a masked excerpt. A matched value is never printed in full.

## Rules

| Rule | Flags |
|------|-------|
| LEK-01 | Any term from the denylist, case-insensitive, in content or file name. The denylist is one term per line, `#` for comments. The real list is private and is never in the repo. |
| LEK-02 | An absolute personal path: `/Users/<name>` or `/home/<name>`. Generic names (`user`, `you`, `runner`, `shared`, and the test name `tgtester`) pass. |
| LEK-03 | Key or token patterns (cloud keys, GitHub, Slack, Google, `sk-` style, private key blocks, JWTs, quoted `api_key = "..."` values), an AI attribution line (Co-Authored-By or "generated with"), and a `Date:` field with a value in the file header (the first 30 lines only). An empty `Date:` passes, and dates further down (templates, test data, body text) are not checked. |
| LEK-04 | `LICENSE` missing, no copyright line, a holder that has company wording (Inc, LLC, Ltd, Labs, Health, Contributors, Team and similar), a one-word holder, or an email or URL in the holder line. |
| CMD-04 | Applies only to files named `influence.md`. Flags trust ratings (`trust level`, `trust score`), influence strategy wording (`influence strategy`, `power map`, `stakeholder analysis`, `manipulate`, `ally`, `adversary`, `political`), a sentence about a named person (`Name seems / wants / is ...`), and personality wording (`personality`, `agenda`, `loyalty`, `defensive`). |

## Allowlist

`tests/leak/allowed_fixtures.txt` lists files the scanner skips, by name.

    name_or_relative_path              skip for every rule
    name_or_relative_path : LEK-02     skip for the listed rules only

A name with no `/` matches the base name anywhere. The scanner's own rule file, its tests and the allowlist itself are listed so they do not flag themselves. Add a fixture here only when it must hold fake data on purpose.

## Tests

`tests/leak/test_leak.py` uses only synthetic data. Fake secrets and fake names are built at run time. Cases are named `LEK_01a` and up, through `LEK_04e`, plus `CMD_04a` to `CMD_04e` and a command-line exit-code check.

## Known limits

- Compiled `__pycache__` files carry source strings and are scanned, so they can add hits. Delete them before a release scan.
- CMD-04 is keyword based. It catches obvious cases, not clever wording.
