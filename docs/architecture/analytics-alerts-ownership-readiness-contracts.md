# Analytics Alerts Ownership and Readiness Contracts

## Purpose

This Batch 3 slice completes the focused presentation contracts for ownership
metadata and incident readiness in KAORI Alerts & Anomalies. It removes the
remaining broad summary dictionaries from `AlertsSnapshot` while preserving the
ordinary dictionary and list values already consumed by templates, dashboards,
reports, and recommendation logic.

This is a contract-only refactor. It does not change owner, runbook, or contact
precedence; metadata coverage scoring; incident-readiness penalties; severity
thresholds; labels; descriptions; icons; or semantic CSS classes.

## Canonical Contracts

The source of truth is `app/analytics/kubernetes/alerts/contracts.py`.

### Ownership boundary

- `AlertOwnershipGroup` describes one owner coverage row.
- `AlertRunbookItem` describes one alert with a runbook link.
- `AlertMissingMetadataItem` describes one alert and its missing operational
  metadata.
- `AlertOwnershipSummary` describes the complete ownership and runbook
  readiness block.

`AlertOwnershipSummary` preserves these runtime keys:

```text
score
level
label
description
class
icon
source
alert_count
owner_count
runbook_count
contact_count
missing_owner_count
missing_runbook_count
missing_contact_count
owner_groups
runbook_items
missing_metadata_items
```

### Incident-readiness boundary

- `AlertIncidentReadinessCheck` describes one scoring check.
- `AlertIncidentReadinessSummary` describes the complete incident-readiness
  score and presentation block.

`AlertIncidentReadinessSummary` preserves these runtime keys:

```text
score
level
label
description
class
icon
critical_signals
warning_signals
anomaly_signals
ownership_score
source_score
silence_risk
inhibition_risk
routing_ready
recommended_action
checks
```

## Updated Ownership

`app/analytics/kubernetes/alerts/ownership.py` now returns focused ownership contracts for
both populated and empty states. Internal owner groups, runbook rows, and
missing-metadata rows are also typed without introducing runtime objects.

`app/analytics/kubernetes/alerts/readiness.py` now accepts the established source-health,
routing, silence, inhibition, and ownership summary contracts and returns a
focused incident-readiness contract. The selected-cluster signal overview
remains a separate boundary and is intentionally not redesigned in this slice.

`AlertsSnapshot` now references `AlertOwnershipSummary` and
`AlertIncidentReadinessSummary` directly instead of `dict[str, Any]`.

## Behavior Preserved

The following behavior is unchanged:

- explicit normalized owner, runbook, and contact values remain authoritative;
- label metadata precedes annotation metadata for owner and contact lookup;
- namespace remains the final owner fallback when it is meaningful;
- ownership score remains the rounded coverage of owner, runbook, and contact
  across all loaded alerts;
- owner groups remain sorted by count and label in descending order;
- runbook items remain limited to five and missing-metadata items to six;
- incident readiness starts at 100 and applies the existing eight penalties;
- readiness thresholds remain ready at 80, watch at 60, degraded at 40, and
  incident risk below 40;
- all eight readiness checks retain their current status and wording;
- empty states retain their existing labels, keys, and operational guidance.

All runtime values remain ordinary Python dictionaries and lists. No Jinja
consumer, report, dashboard, or recommendation function receives a class
instance.

## Validation

Contract tests verify:

- focused contracts exist and are consumed through canonical focused modules;
- ownership and readiness builders use focused return annotations;
- readiness inputs use the existing focused summary contracts;
- `AlertsSnapshot` references the focused ownership and readiness contracts;
- empty runtime dictionaries have exactly the typed contract keys.

Functional characterization tests verify:

- empty ownership and readiness states preserve their dictionary shapes;
- owner, runbook, and contact coverage produces the existing score, level,
  grouping, and missing-metadata rows;
- owner/runbook/contact precedence remains unchanged;
- the existing incident-readiness penalty model still produces the same score,
  level, risks, routing state, and eight checks.

## Follow-On Slice

The selected-cluster signal overview, priority, insight, and bar dictionaries
are covered by Batch 3 Slice 8 in
`docs/architecture/analytics-alerts-signal-overview-contracts.md`. That slice
remains separate from signal counting, anomaly classification, recommendation
behavior, and UI wording changes.
