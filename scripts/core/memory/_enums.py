"""
module_name: _enums.py
description: Single source of truth for memory enum values and shared constants.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Initial port.
"""

# ── Applicable scope values ───────────────────────────────────────────────────

APPLICABLE_SCOPE_VALUES: frozenset[str] = frozenset({
    "all",
    "restricted-topic",
    "internal-only",
    "comms-restricted",
    "code-restricted",
})

RESTRICTED_SCOPES: frozenset[str] = APPLICABLE_SCOPE_VALUES - {"all"}

# ── Confidence values ─────────────────────────────────────────────────────────

CONFIDENCE_VALUES: frozenset[str] = frozenset({
    "hypothesis",
    "observed",
    "validated",
})

# ── Status values ─────────────────────────────────────────────────────────────

STATUS_VALUES_MEMORY: frozenset[str] = frozenset({
    "active",
    "draft",
    "deprecated",
    "superseded",
})

# Standards tier does not use "superseded", that is memory-tier only.
STATUS_VALUES_STANDARDS: frozenset[str] = frozenset({
    "active",
    "draft",
    "deprecated",
})

# ── Data domain values ─────────────────────────────

DATA_DOMAIN_VALUES: frozenset[str] = frozenset({
    "general",
    "client-a",
    "client-b",
    "client-c",
    "client-d",
    "internal",
})

# ── Lifecycle quarantine directories ──────────────────────────────────────────

LIFECYCLE_QUARANTINE_DIRS: dict[str, str] = {
    "draft":      "memory-quarantine/draft",
    "deprecated": "memory-quarantine/deprecated",
    "superseded": "memory-quarantine/superseded",
}

# ── Manifest health reasons ───────────────────────────────────────────────────

MANIFEST_HEALTH_REASONS: frozenset[str] = frozenset({
    "status-draft-excluded-from-conflict-surface",
    "status-deprecated-excluded",
    "status-superseded-excluded",
    "parse-error-quarantined-separately",
})

# ── Cascade warnings reasons ──────────────────────────────────────────────────

CASCADE_WARNINGS_REASONS: frozenset[str] = frozenset({
    "source-file-missing",
    "source-frontmatter-parse-error",
    "standards-file-missing-status",
    "standards-file-uses-superseded",
})

# ── Tier-specific defensive defaults ─────────────────────────────────────────
# Callers MUST select the tier-appropriate dict. No single global default.
# "DROP" is a typed sentinel: callers check `value == DROP_SENTINEL` to detect
# the drop signal without relying on a stringly-typed magic string.

DROP_SENTINEL: str = "DROP"

# Memory tier: missing fields read as the most restrictive safe value.
MEMORY_DEFENSIVE_DEFAULTS: dict[str, str] = {
    "missing_scope":       "internal-only",
    "missing_confidence":  "hypothesis",
    "missing_status":      "active",
    "missing_data_domain": "general",
}

# Standards tier: missing status on a standards-allowlist file → drop the passage.
# Files in the standards-status-required list MUST carry a valid status field.
STANDARDS_DEFENSIVE_DEFAULTS: dict[str, str] = {
    "missing_status": DROP_SENTINEL,
}

# Foundation tier: foundation files use supersedes: instead of status:.
# Missing status on a foundation file is by design, treat as active.
FOUNDATION_DEFENSIVE_DEFAULTS: dict[str, str] = {
    "missing_status": "active",
}

# ── Score thresholds ──────────────────────────────────────────────────────────

CASCADE_MIN_SCORE: float = 0.3   # cascade mode: per-passage threshold , lowered from 0.5 (current embedding model produces lower cosine similarities than the earlier one)
MIN_SCORE: float = 0.3           # non-cascade mode: legacy threshold (unchanged behavior)
