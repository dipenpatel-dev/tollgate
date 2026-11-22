# Installer tests

Run: `bash tests/installer/run.sh`. Every case uses a throwaway home made with `mktemp -d`, a user name that is not the real one, and a private copy of the repo. The real `~/.claude`, shell profile and keychain are never touched. The helper is `tests/installer/helpers.sh` and needs nothing else from the repo.

| ID | What it proves |
|---|---|
| INS-01 | A fresh install into an empty home exits 0 and creates the config, settings, `CLAUDE.md`, commands, vault folders, workspace file, shell block, and the empty paths and connectors files. The settings `env` block holds the new variables. |
| INS-02 | `--vault`, `--initials`, `--ticket-prefix` (with `--non-interactive`, stdin closed) give the same config, settings, shell block and `CLAUDE.md` as typing the answers. A bad flag exits 2 with nothing written. A bad typed answer is asked again. |
| INS-03 | A second install changes no file, adds no settings backup, leaves one shell block and one copy of each hook. The user's model, env, plugins, status line, permissions and own hooks survive both runs. |
| INS-04 | The config holds the vault folder, initials and ticket prefix as plain `NAME="value"` lines. Fake secrets set in the environment (built at run time) appear nowhere in the config, settings, profile, paths or connectors files. |
| INS-05 | A settings backup exists and equals the file as it was before the merge. `--restore-settings` brings that state back exactly and keeps a copy of the replaced file. A broken settings file is backed up byte for byte. |
| MRG | `tests/installer/test_merge_settings.py`: ownership rules, mixed groups, extra fragments, `--set`, `--backup`, `--restore`, file mode, symlinks. |

The old checks t1 to t4 (backup before clean, dry run changes nothing, no secret on a command line) still run first.

The snapshot used for INS-03 leaves out the backup copies the installer makes on purpose (`*.bak.*`, `~/.claude.backup.*`).
