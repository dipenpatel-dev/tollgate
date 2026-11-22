# Walkthrough: A Bug Ticket from Start to Close

Created by Dipen Patel.

All client names, ticket IDs, table names, and data values in this document are fictional. Replace them with your actual values when working a real ticket.

> Every command in this walkthrough starts with `tg-`, the fixed Tollgate prefix, for example `/tg-ticket` and `/tg-close`. This walkthrough assumes the vault git setting is `local`, so commands print vault git lines for you to run. With `none` they print no git lines; with `remote` they add a push line.

---

## The Scenario

You receive this Slack message at 9:15 AM:

> "Hey, the client's team is saying 22 records are missing from the Procedure X report this month. Can you look into it? The data submission was two weeks ago so I'm not sure what happened."

You open your ticket tracker. There is already a ticket. (In this sample the ticket details come from the optional tracker connector; with no connector set up, the commands work from the vault and say which source is missing.)

```
PROJ-200 | Bug | High
Title: Client A Procedure X records missing from monthly report
Status: Open
Reporter: client contact (Client A)
```

This is a bug ticket. The chain is:

```
/tg-start
/tg-ticket PROJ-200
/tg-support PROJ-200
/tg-spec PROJ-200
/tg-arch PROJ-200
[approve design]
/tg-dev PROJ-200
/tg-qa PROJ-200
/tg-close
```

---

## Step 1: Start the session

```
/tg-start ticket PROJ-200
```

The checklist runs. You see:

```
/tg-start - 2026-06-03

3 tickets in progress in the vault.
  PROJ-200  Client A Procedure X missing records  [OPEN / High]
  PROJ-195  Client B pipeline timeout  [IN PROGRESS]
  PROJ-188  Documentation update  [BLOCKED - waiting on a downstream team]

Vault health: 12 state files checked, 11 current. PROJ-188 state is stale (last updated 6 days ago).
Open blockers: PROJ-188 waiting on a downstream team schema decision.

Ready. Start with PROJ-200 or pick up PROJ-195?
```

You type: `PROJ-200`

---

## Step 2: Orient on the ticket

```
/tg-ticket PROJ-200
```

The skill reads the vault first, including the Client A client file. It goes to the tracker connector only if the vault has nothing or a stub. Then it produces the ORIENT block:

```
ORIENT - PROJ-200 - Client A Procedure X records missing from monthly report

CONTEXT
  Client reported 22 Procedure X records are missing from the monthly monthly report.
  Client A submitted source data 14 days ago. The gap was discovered by
  their reporting team during report review.

CLIENT CONTEXT
  Client:     Client A
  Catalog:    example_client_a_dev
  Schema:     bronze_client_a
  Pipeline:   client-a-tavr-ingest (Databricks Job ID: 4821)
  Notebook:   databricks/pipelines/clients/client_a/procedure_x_bronze.py
  Table(s):   raw_client_a_tavr, bronze_client_a.tavr, silver_std_procedure_x
  Git:        main (no active branch for this client)

KNOWN (verified from vault / Jira / code)
  - Client A submitted 500 Procedure X records on 2026-05-20  [Jira: the client contact comment]
  - Clinical report shows 478 records  [Jira: reporter]
  - 22 records are missing  [Jira: reporter]
  - Pipeline ran successfully - no job failure alerts  [Vault: client-a.md]

UNKNOWN
  - Where in the pipeline the 22 records dropped (Raw? Bronze? Silver?)
  - Whether the 22 records arrived in the source file
  - What distinguishes the missing 22 from the 478 that passed

ASSUMING
  - "Missing from monthly report" means missing from silver_std_procedure_x output
  - The 500 record count is from Client A, not independently verified
```

The skill then asks the explain back gate:

```
In two sentences: what is this ticket about, and what do you think needs to happen?
```

You respond: "22 records from Client A's Procedure X submission are not showing in the monthly report. I need to trace where they dropped out of the pipeline, figure out why, and fix it."

The skill classifies the ticket as a bug and routes to `/tg-support`.

---

## Step 3: Diagnose the bug

```
/tg-support PROJ-200
```

The skill reads the state file and begins the diagnostic trace.

**INTAKE**

```
INTAKE - PROJ-200

Reproducing the gap:
  silver_std_procedure_x WHERE client = 'client_a' AND report_period = '2026-05'
  Result: 478 rows
  Expected: 500 rows
  Gap confirmed: 22 records missing

Tier classification: Tier 2 (data gap, no pipeline failure)
  - Job completed successfully
  - No error logs
  - Records present in source but absent in output

PHI check: Query returns aggregate counts only. No patient-level data in this context.
```

**TROUBLESHOOT**

The skill traces Raw to Bronze to Silver:

```
LAYER TRACE - PROJ-200

Raw layer:
  raw_client_a_tavr WHERE load_date = '2026-05-20'
  Result: 500 rows confirmed
  All 500 records landed in Raw.

Bronze layer:
  bronze_client_a.tavr WHERE source_load_date = '2026-05-20'
  Result: 478 rows
  Gap appears here. 22 records did not pass from Raw to Bronze.

Null check on Raw:
  raw_client_a_tavr WHERE encounter_date IS NULL AND load_date = '2026-05-20'
  Result: 22 rows

Root cause confirmed:
  22 records have NULL encounter_date in the source file.
  The Bronze transform filters records WHERE encounter_date IS NOT NULL.
  Those 22 records were excluded at the Bronze filter and never reached Silver.
```

**HANDOFF PACKAGE**

```
ROOT CAUSE
  22 records filtered at Bronze ingestion due to NULL encounter_date.
  Filter is in procedure_x_bronze.py, line 47: df.filter(col("encounter_date").isNotNull())
  This filter was added 2026-03-10 (PROJ-157) to prevent downstream null propagation.

EVIDENCE
  Raw count: 500 - Bronze count: 478 - Silver count: 478
  Null records: 22 rows WHERE encounter_date IS NULL in raw_client_a_tavr

FIX OPTIONS (not a decision - passing to /tg-spec)
  Option A: Quarantine nulls to a holding table, alert client to provide corrected data
  Option B: Coalesce null encounter_date to a default value (e.g., load_date) and pass through
  Option C: Pass null records through with quarantine_ind = 1 for manual review

CROSS TEAM FLAG
  The filter in procedure_x_bronze.py was added per PROJ-157 (a downstream team decision).
  Any change to this filter requires the downstream team review before implementation.
```

---

## Step 4: Write the spec

```
/tg-spec PROJ-200
```

The skill reads the support handoff and produces requirements. The RESTATE gate fires first:

```
RESTATE - PROJ-200

Problem: 22 Client A Procedure X records have null encounter_date. The current Bronze
filter excludes them. They never reach Silver and are absent from the monthly report.

Fix scope: decide how to handle null encounter_date records at Bronze ingestion.
Three options from the support handoff. Choosing and implementing one.

Does this framing match yours?
```

You confirm. The skill produces the spec:

```
SPEC - PROJ-200

REQUIREMENTS
  R1  The fix handles null encounter_date records without silently dropping them.
  R2  The handling mechanism is the same for all clients, not Client A-specific.
  R3  The downstream team reviews and approves the approach before implementation.
  R4  A count of null-handled records is logged per pipeline run.

ACCEPTANCE CRITERIA
  AC1  0 records dropped silently at Bronze for null encounter_date. Pass: query
       raw count equals bronze count plus quarantine count. Fail: any other result.
  AC2  A quarantine_ind column exists on the Bronze table with value 1 for null
       records. Pass: column exists, 22 rows have value 1. Fail: column absent.
  AC3  The pipeline log for this run shows "22 records quarantined: null
       encounter_date." Pass: string present in run log. Fail: absent or wrong count.
  AC4  The downstream team has reviewed and approved the design. Pass: approval comment
       on PROJ-200 from the downstream team lead. Fail: no approval recorded.

SUCCESS METRICS
  SM1  Client A Procedure X monthly report shows 500 records for the 2026-05 period
       after the fix is applied and pipeline is rerun.
  SM2  No downstream pipeline failures introduced by the quarantine column.
```

---

## Step 5: Design the fix

```
/tg-arch PROJ-200
```

The skill reads the spec and produces design options.

```
DESIGN - PROJ-200

OPTION A (recommended): Quarantine to bronze with quarantine_ind flag
  Add quarantine_ind column to bronze_client_a.tavr and silver_std_procedure_x.
  Records with null encounter_date pass through Bronze with quarantine_ind = 1.
  Silver excludes quarantine_ind = 1 records from the monthly report output.
  Client is notified and asked to resubmit corrected records.

  WHY: Preserves the record in the pipeline. Makes the gap visible and auditable.
  Gives the client a path to correction without losing the original submission.
  Consistent with how other null fields are handled (see pipeline-standards Rule 9).

OPTION B: Coalesce to load_date
  Replace null encounter_date with load_date at Bronze ingestion.
  Records pass through with a synthetic date.

  WHY NOT: A synthetic date is wrong data. The monthly report would show encounters
  on a date that is not the actual encounter date. Wrong data is worse than
  missing data (pipeline-standards Rule 18). Rejected.

OPTION C: Pass through with no flag
  Remove the filter entirely. Null records pass to Silver as-is.

  WHY NOT: Downstream logic that depends on encounter_date for date range filtering
  will produce unpredictable results on null values. The original filter (PROJ-157)
  existed for this reason. Rejected.

CROSS TEAM REQUIREMENT
  The downstream team must approve Option A before /tg-dev starts.
  The quarantine_ind column addition affects silver_std_procedure_x, which the downstream team owns.
  Flag: post the design to the downstream team on PROJ-200 and wait for sign off.

ASSUMPTION
  Dipen confirms: quarantine_ind is the right column name (not filter_ind or exclude_ind).
  Check pipeline-standards Rule 4 for where indicator columns live (Bronze and Silver, never Raw).
```

You review the design, agree with Option A, and post it to Jira for the downstream team review. The downstream team responds within the day: approved.

---

## Step 6: Implement

```
/tg-dev PROJ-200
```

The skill reads the approved design. The TEACHING gate fires:

```
TEACHING GATE - PROJ-200

Walk me through the approach before I write any code. Two sentences:
what are we changing and why does this approach satisfy the acceptance criteria?
```

You explain. The skill produces the implementation:

```python
# procedure_x_bronze.py
# Author: [YOUR NAME]
# Date:
# Scope: Add quarantine_ind for null encounter_date records (PROJ-200)
# Ticket: PROJ-200
# ChangeLog: 2026-06-03 - added quarantine_ind column per the downstream team approval

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, when, lit
import logging

logger = logging.getLogger(__name__)

NULL_ENCOUNTER_DATE_FLAG: int = 1
VALID_RECORD_FLAG: int = 0


def apply_quarantine_flags(df: DataFrame) -> DataFrame:
    """Flag records with null encounter_date for downstream exclusion."""
    flagged = df.withColumn(
        "quarantine_ind",
        when(col("encounter_date").isNull(), lit(NULL_ENCOUNTER_DATE_FLAG))
        .otherwise(lit(VALID_RECORD_FLAG))
    )
    null_count = flagged.filter(col("quarantine_ind") == NULL_ENCOUNTER_DATE_FLAG).count()
    logger.info("records quarantined: null encounter_date | count=%d", null_count)
    return flagged


def load_bronze_tavr(df: DataFrame) -> DataFrame:
    """Apply quarantine flags and write to Bronze. No records dropped silently."""
    return apply_quarantine_flags(df)
```

The skill also produces the Silver layer change:

```python
# silver_std_procedure_x.py - excerpt
# Filter quarantine records from monthly report output

def build_silver_tavr(df: DataFrame) -> DataFrame:
    """Exclude quarantined records from Silver output. Quarantine stays in Bronze."""
    return df.filter(col("quarantine_ind") == VALID_RECORD_FLAG)
```

The skill commits the code on a feature branch in the code repository, one commit per work block, and squash merges it onto the ticket branch. Notes in the vault are different. `/tg-dev` writes the session log and state file, then prints the vault git lines and stops. You run them:

```
git -C {vault} add <the paths written this run>
git -C {vault} commit -m "PROJ-200 B-01: dev complete"
```

---

## Step 7: QA review

```
/tg-qa PROJ-200
```

The adversary reads the spec, design, and implementation. It produces findings:

```
QA FINDINGS - PROJ-200

CRITICAL (must fix before merge)
  None.

HIGH
  Finding 1: Silver filter uses == comparison on integer flag.
    Risk: If quarantine_ind is cast to string anywhere in the pipeline, == 0 fails
    silently and all records are excluded.
    Evidence: silver_std_procedure_x.py line 8 - no explicit cast.
    Route to: /tg-dev
    Fix: Cast to IntegerType() before comparison, or use col("quarantine_ind").isin([0]).

MEDIUM
  Finding 2: No test for the case where ALL records in a batch have null encounter_date.
    Risk: A full batch quarantine would pass the log check but the reporting team
    would receive an empty report with no alert.
    Route to: /tg-dev
    Fix: Add a check - if null_count equals total batch count, raise an alert.

LOW
  Finding 3: quarantine_ind column not yet documented in the schema registry.
    Route to: you (vault update, not a code change)

APPROVED WITH CONDITIONS
  Merge after High finding is resolved. Medium finding can be addressed in a
  follow on ticket (PROJ-201) if the downstream team agrees it is out of scope for PROJ-200.
```

You review the findings. The High finding is valid. You route it back to `/tg-dev` for the fix. The fix is applied. QA runs the review again and approves.

---

## Step 8: Draft the Jira resolution comment

```
/tg-draft jira PROJ-200
```

```
VOICE: Internal / Data team
TYPE: Jira resolution comment
STAKES: Medium

---
Resolved. Root cause: 22 Client A Procedure X records had null encounter_date in the
2026-05-20 source file. The Bronze filter (added PROJ-157) excluded them before
Silver. They never reached the monthly report.

Fix: added quarantine_ind column to bronze_client_a.tavr and silver_std_procedure_x.
Null records now pass through Bronze flagged as quarantine_ind = 1 and are
excluded from Silver output. Pipeline rerun for 2026-05-20 batch confirmed
500 records in silver_std_procedure_x, 22 with quarantine_ind = 1.

Next: notify Client A that 22 records require a corrected encounter_date
resubmission. Client message drafted separately.

The downstream team approved the quarantine_ind approach on 2026-06-02. No downstream
schema changes required beyond silver_std_procedure_x.
---

NOTES:
Assumes pipeline rerun has been completed and count verified before posting.
Client message ready separately - see /tg-draft slack client Client A.
```

You also draft the client message:

```
VOICE: Client
TYPE: Slack message to Client A data contact
STAKES: Medium

---
Your Procedure X data is complete. We identified 22 records from your May submission
that were missing an encounter date. Those records are currently held for
correction. No action needed from you today.

To get all 500 records into the June monthly report, please resubmit those
22 records with the correct encounter dates. Let me know if you need the list
of which records are affected and I can send it over.
---
```

---

## Step 9: Close the session

```
/tg-close
```

```
SESSION LOG - 2026-06-03 - PROJ-200

Done
  - Oriented on PROJ-200 (Client A Procedure X missing records)
  - Traced root cause: null encounter_date filtered at Bronze
  - Designed, implemented, and QA reviewed quarantine_ind fix
  - Downstream team approval obtained
  - Jira resolution comment drafted
  - Client message drafted

Decided
  - Option A (quarantine flag) over coalesce and pass-through.
    Wrong data is worse than flagged data.
  - Medium QA finding (full batch alert) deferred to PROJ-201.

Pending
  - You post Jira comment and client Slack message
  - Client A to resubmit 22 corrected records
  - PROJ-201 to be created for full batch quarantine alert

State file updated: PROJ-200-state.md, Status: QA_APPROVED

Vault commit: commit text printed. You run it:
  git -C {vault} add <the paths written this run>
  git -C {vault} commit -m "session: 2026-06-03 PROJ-200 quarantine fix"

Memory candidate:
  [feedback] quarantine_ind is the standard column name for null-excluded records
  at Bronze. Do not use filter_ind or exclude_ind.
  Save? [yes/no]
```

---

## What the Walkthrough Shows

The ticket took nine skill invocations across (realistically) two or three sessions. Each skill handed off cleanly. The Slack message from the client contact became a root cause trace, a design decision, implemented code, QA findings, and two drafted communications, all with your judgment at every gate.

Nothing was sent automatically. No vault commit was made for you: the skills printed the lines and you ran them. Nothing was merged without your review. The 22 missing records have a clear path to resolution and the system has a memory of how this class of problem was handled.

That is the chain working as designed.
