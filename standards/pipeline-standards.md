# Pipeline Standards

**What this is:** Your rule book for pipeline architecture — the layered medallion design, write semantics, layer boundaries, ingestion patterns, schema lineage. Read by every Tier 5 skill in Step 0 alongside `technical-standards.md`.

**Audience:** You and Claude. Companion to `technical-standards.md`.

**When it updates:** When a pipeline pattern proves itself across a second client, or when a correction generates the same fix twice, harden it. Rules stay in the team's language.

---

## The Frame

Every pipeline your team runs delivers data that a person will act on. A wrong record is worse than a missing record. A pipeline that drops the wrong record silently is worse than one that fails loudly. Every rule below exists to make failures loud, recoverable, and explainable.

---

## Layer Boundaries

**Rule 1 — Raw, Bronze, Silver each have one responsibility.** Raw lands source data unchanged. Bronze standardizes and validates. Silver shapes the data for the product. A skill proposing a change states which layer it touches. Mixing responsibilities across layers is the most common cause of pipelines that work in dev and break in production.

**Rule 2 — Use "layer" not "stage" in all docs and folder names.** Drift in vocabulary becomes drift in the mental model.

**Rule 3 — Raw is append-only and immutable.** No deletes, no updates, no overwrites. Every load is an append. The Raw layer is the source of truth for what arrived and when. If the source needs correction, the Raw record stands — the correction happens in Bronze.

**Rule 4 — Indicator columns live on Bronze and Silver, never on Raw.** `quarantine_ind`, `delete_ind`, `process_ind`, `filter_ind` are Bronze/Silver concerns. Raw is the immutable ledger. See memory `[feedback_indicator_columns_layer]`.

**Rule 5 — Source-bound ingestion, not product-bound.** Raw tables serve all products. Never name an ingestion path after a product (no `raw_[procedure]` — it is `raw_[client]` and [PROCEDURE]-specific logic starts at Bronze). See memory `[feedback_source_bound_ingestion]`.

---

## Write Semantics

**Rule 6 — Every write mode is stated explicitly at the call site.** No defaults. `mode("append")`, `mode("overwrite")` with `replaceWhere`, or `MERGE INTO` with explicit match conditions. A write without an explicit mode is rejected at QA.

**Rule 7 — `overwrite` without `replaceWhere` replaces the entire table.** Know this every time you write it. If the intent is partition-level replacement, `replaceWhere` is required. Tier 5 skills are extra careful here.

**Rule 8 — Idempotency at every layer.** Every layer survives a rerun without producing duplicates or wrong totals. The pipeline can be replayed from any starting point without breaking downstream. Design states the idempotency mechanism: append + deduplication key, MERGE with match condition, or `replaceWhere` on a partition.

**Rule 9 — Null handling is explicit at every join, filter, and `withColumn`.** Joins state what happens to null keys. Filters state what happens to null values. `withColumn` states the null behavior of the expression. Implicit null handling is the most common cause of patients silently disappearing from the output.

---

## Ingestion Patterns

**Rule 10 — Ingestion notebooks contain no DDL.** No `CREATE TABLE`. No `CREATE SCHEMA`. No `ALTER`. Provisioning is a separate setup script. Cell 6 of an ingestion notebook is DESCRIBE checks only. See memory `[feedback_ingestion_notebook_no_ddl]`, `[feedback_pipelines_must_not_create_schemas]`.

**Rule 11 — One pipeline YAML drives all layers.** One YAML per client, all layers configured in it. Job parameters are two only: environment + config_path. See memory `[feedback_pipeline_yaml_all_layers]`.

**Rule 12 — Master schema is separate from data schemas.** `file_registry`, `ingestion_runs`, `table_metrics`, and similar metadata tables live in `{client}_master`, never in `raw_*` or `bronze_*`. See memory `[feedback_master_schema_separate]`.

**Rule 13 — Pipeline handles compressed files transparently.** ZIP, GZ, or any other compression is extracted by the pipeline. Never asking the user to extract manually. The Azure SDK does this in the notebook. See memory `[feedback_pipeline_handle_zips]`.

**Rule 14 — Connect to the existing pipeline framework.** All new work integrates with the existing YAML framework. No parallel systems. See memory `[feedback_connect_to_existing_pipeline]`.

---

## Schema Lineage and Integrity

**Rule 15 — Schema lineage from source through Silver.** Every Silver column traces back to a specific Raw column (or a documented derivation). The chain is explicit and verifiable. When a Silver field is wrong, the trace is how the diagnosis starts.

**Rule 16 — Verify the Silver schema before any change, not the Raw view.** Pipelines use `silver_std_*` tables; Raw `_vw` columns differ.

**Rule 17 — End-to-end layer validation before any fix.** Always trace Raw → Bronze → Silver → Output. Never assume the data flows cleanly between layers.

**Rule 18 — Record integrity is non-negotiable.** Missing data is acceptable. Wrong data is never acceptable. Semi-join every source branch, verify the record key on every join.

**Rule 19 — Anchor column varies by view.** [CLIENT] views use several different ID column names for the same entity. Run dual-anchor profiling before configuring any join.

---

## Validation and QA

**Rule 20 — Validator must use independent logic.** Never copy pipeline SQL into the validator. Raw-to-final-output analysis only. Test sharing implementation has zero detection power.

**Rule 21 — Accuracy validation targets raw columns only.** Raw validation rules always target source views. Silver comparison is a separate workstream.

**Rule 22 — Use `CURRENT_DATE()` for historical date upper bounds.** Never hardcoded year.

**Rule 23 — Internal procedure codes are not CPT.** Never group a source system's internal procedure codes with CPT in any analysis.

**Rule 24 — pandas strips leading zeros from MRN columns.** Use `dtype=str` on any MRN read.

---

## Cross-Client Design

**Rule 25 — Every architecture choice must work across all clients and interface types.** No one-client special cases without writing down the constraint.

**Rule 26 — Cost-aware data sharing.** Shared-data queries can cost money per query. Prefer persisting Raw locally with hash-based delta detection.

**Rule 27 — Tables before logic.** DDL first, notebooks second. Structures before processes.

---

## When This File Updates

When a pipeline pattern proves itself across two clients, harden it. When a correction generates the same fix twice, harden it. Rules stay in the team's language.
