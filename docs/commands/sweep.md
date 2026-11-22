# /tg-sweep

Moves everything waiting in the knowledge staging area into the vault and the search index, then prints one count line {src:commands/tg-sweep.md:6} {src:commands/tg-sweep.md:20}.

The command name is fixed: `/tg-sweep`.

## When to use

After a session that captured notes, or when the staging area has built up.

## What it does

The vector index is shared live state, so the command runs a preview first {src:commands/tg-sweep.md:8}:

1. Preview: `$TOLLGATE_HOME/scripts/sync/sweep` writes nothing and does not open the index {src:commands/tg-sweep.md:8-11}.
2. It states in one line what the sweep will write and where, then asks you to confirm {src:commands/tg-sweep.md:14}.
3. Only after your yes does it run `$TOLLGATE_HOME/scripts/sync/sweep --yes` {src:commands/tg-sweep.md:17}.
4. It reports the one summary line as is: counts processed, written, synced, partial and skipped {src:commands/tg-sweep.md:20}.

## What it reads and writes

- Reads: staged knowledge record files {src:commands/tg-sweep.md:6}.
- Writes: vault markdown documents by type, search index entries, and it clears staged files that synced. A file whose index sync failed is marked as vault-written and retried on the next sweep {src:commands/tg-sweep.md:6}.
- It runs no vault git line and makes no commit. It uses no folder lookup of its own; the script resolves its folders.

## Hooks and gate lines

No gate line applies. The index is shared live state, so the command says what it will write and waits for your yes before the real run {src:commands/tg-sweep.md:14}.

## Example

`/tg-sweep` prints `processed=4 written=4 synced=4 partial=0 skipped=0`. Records that failed to sync stay marked for the next sweep {src:commands/tg-sweep.md:6} {src:commands/tg-sweep.md:20}.
