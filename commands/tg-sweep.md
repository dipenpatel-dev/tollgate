# /tg-sweep: Flush knowledge staging to vault and index

Author: {INITIALS}
Date:

Execute the knowledge sweep: process all staged knowledge record JSON files, write them to vault markdown documents by type, synchronize each to the search index, and report a summary. Staging files are cleared on successful sync; files with sync failures are marked as vault-written for retry on the next sweep.

The vector index is shared live state. Run the preview first. It writes nothing and does not open the index:

```bash
$TOLLGATE_HOME/scripts/sync/sweep
```

State in one line what the sweep will write and where, then ask the owner to confirm. Only after a yes, run it for real:

```bash
$TOLLGATE_HOME/scripts/sync/sweep --yes
```

The script prints one summary line with the counts processed, written, synced, partial and skipped. Report it as is.
