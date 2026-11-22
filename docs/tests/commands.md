# Command file tests

`bash tests/commands/run.sh` checks the command files in `commands/`. Set `TOLLGATE_REQUIRE_SCRIPTS=1` to make script paths required.

| Rule | Checks |
|------|--------|
| CMD-01 | No command holds a literal personal absolute path (`/Users/<name>`, `/home/<name>`, `/Volumes/...`). Folders come from variables. |
| CMD-02 | Every hook, standards or repo file a command names by path exists. Paths like `$TOLLGATE_HOME/scripts/...` are listed in the output and are listed in the output; set `TOLLGATE_REQUIRE_SCRIPTS=1` to make a missing script fail the run. |
| CMD-03 | Every `$TOLLGATE_*` or `$CLAUDE_DOTFILES` variable stays strict and must be defined in `docs/variables.md`. A `{marker}` passes if it is a defined placeholder (`prefix`, `KEY`, `INITIALS`), is lower case letters, digits and underscore, may end in `_NN` (for example `{block_NN}`), or is exactly `N`, `NN` or `TOTAL`. Any other upper case marker (for example `{PREFIX_UPPER}`) fails. |
| CMD-04 | The leak scanner finds zero CMD-04 hits in `commands/influence.md`, and a synthetic bad `influence.md` is flagged. |
| CMD-05 | The spec, arch, dev and qa commands contain the status words the gate reads (imported from `hooks/gate_rules.py`) on a status or state line. The arch drafting word `DESIGN_COMPLETE` is checked too. |

Scope: CMD-01 to CMD-03 run on the main command list (spec, arch, dev, qa, support, ticket, explain, influence, devops, sre, terraform, doc-gen, retrieve, sweep, think-calibrate, pr-review). Other command files are checked against `KNOWN_GAPS` in the test: a file that fails and is not on the list fails the run, so new gaps cannot slip in. The list is empty today.
