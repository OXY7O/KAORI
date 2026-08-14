# Analytics Alerts Typed Contracts

## Status

Implemented in Batch 3, Slice 2.

This slice introduces explicit internal contracts without changing the runtime
representation consumed by Jinja templates, reports, dashboards, or recommendation
logic. Alerts and snapshots remain ordinary dictionaries at runtime.

## Canonical Contracts

The source of truth is:

```text
app/analytics/kubernetes/alerts/contracts.py
```

It defines:

- `NormalizedAlert` — common normalized alert shape shared by Alertmanager and Prometheus fallback;
- `AlertSourceStatus` — source-selection, connectivity, fallback, latency, and diagnostic state;
- `AlertLoadResult` — canonical source loader result;
- `AlertsSnapshot` — stable dashboard/report snapshot boundary;
- focused source-health, routing, silence, inhibition, ownership, incident-readiness, selected-cluster signal, multi-cluster comparison, and resource-link presentation summaries;
- `AlertsPagination` — pagination state for the interactive page.

## Dependency Direction

```text
Provider payload
    ↓
sources.py normalization
    ↓
NormalizedAlert + AlertSourceStatus
    ↓
health / routing / silences / inhibition / ownership / typed signals
    ↓
application.py or snapshots.py
    ↓
Jinja / dashboard / report / intelligence
```

Focused alert modules must not redefine provider payload shapes or introduce a
second normalized alert contract.

## Compatibility

The compatibility cutover is complete. Typed contracts are imported directly from
`app.analytics.kubernetes.alerts.contracts`. Both `app.analytics.kubernetes.alerts.service` and the
legacy query export module are retired and blocked by the architecture gate.

## Behavior Boundary

This slice intentionally does not change:

- alert severity or state normalization;
- source preference and Prometheus fallback behavior;
- silence or inhibition matching;
- routing grouping;
- ownership precedence;
- readiness scoring;
- template/report dictionary keys.

## Guardrails

Contract tests enforce that:

- source normalizers return `NormalizedAlert`;
- source loaders return `AlertLoadResult`;
- snapshot orchestration returns `AlertsSnapshot`;
- focused summary builders return their canonical presentation contracts;
- focused consumers import canonical types;
- no compatibility façade or aggregate service import remains;
- runtime outputs retain the existing dictionary key sets.


## Runtime TypedDict Metadata

`contracts.py` intentionally does not enable postponed annotations. Python must
evaluate `NotRequired[...]` while constructing each `TypedDict`; otherwise
provider-specific fields such as `route` and `value` are incorrectly exposed in
`__required_keys__`.

The contract gate verifies that these fields remain optional at runtime, not only
in the source annotation syntax.
