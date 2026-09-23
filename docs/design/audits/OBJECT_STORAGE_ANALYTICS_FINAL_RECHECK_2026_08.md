# Object Storage Analytics Final Recheck — August 2026

## Scope

Reviewed the Object Storage Analytics release surface end to end: Overview, Capacity & Usage, Performance, Forecast, Top Consumers, Alerts & Anomalies, dependency/readiness states, HTMX record fragments, dedicated RBAC, source-resolution boundaries, forecast materialization, and committed-inventory prerequisites.

## Final decisions

1. **Blocker design:** Object Storage Analytics reuses the same shared dependency blocker surface as Kubernetes Analytics. Non-alert pages expose `Object Storage → Metrics`; Alerts extends the route to `Object Storage → Metrics → Alert Evidence`. The Hero blocked posture keeps the same current-step/progress semantics and `Analytics Readiness` label used by Kubernetes Analytics.
2. **Committed inventory prerequisite:** `ObjectStorageSystem` registration alone is not enough. A system with no `inventory_observed_at` is blocked as `Object Storage Inventory Sync Required` before any operational analytics workspace is rendered. This aligns runtime behavior with the existing dependency copy and preserves Inventory as the committed asset authority.
3. **Provider-neutral runtime:** interactive capacity, performance, consumer, and alert-derived metric views resolve the provider-neutral `MetricsSource` contract. The service and routes do not import MinIO clients or direct Prometheus consumers. Runtime requests remain fail-fast with request-local source-circuit behavior.
4. **Forecast ownership:** long-range forecast history remains worker-owned through `object_storage.forecast.materialize` and `ObjectStorageForecastSnapshot`; Overview consumes committed 30d forecast posture and Forecast consumes the requested committed history window.
5. **Alerts evidence:** Alertmanager/Prometheus provider alert records and KAORI metric-derived signals remain independent evidence families. Failure of one path must not suppress evidence from the other.
6. **HTMX fail-closed behavior:** bucket and alert record fragments render a dependency notice when the selected system loses prerequisite eligibility rather than returning an apparently empty data table.
7. **RBAC:** every Object Storage Analytics full-page and fragment endpoint remains guarded by `object_storage_analytics.view`; Kubernetes `analytics.view` is not reused.
8. **Hero copy:** Capacity, Performance, Forecast, and Top Consumers descriptions follow the canonical #470 compact Hero contract: 89–96 characters as the executable density boundary, with semantic clarity preserved for each analytics workspace.

## Reviewed workspace semantics

### Analytics Overview

Consolidates capacity, request-path health, usage direction, bucket concentration, committed forecast posture, reconciliation, and evidence provenance. Overview does not embed the full bucket record table.

### Capacity & Usage

Separates physical usable capacity from bucket quota posture, usage trend, bucket concentration, and Inventory-vs-operational reconciliation. Optional quota absence remains `No Quota Evidence`; it is not treated as zero quota or healthy quota posture.

### Performance

Separates request demand from reliability. Request rate/in-flight demand and ingress/egress traffic are descriptive; error ratio, queue pressure, and availability evidence determine request-path posture.

### Forecast

Uses worker-committed 7d/30d/90d history windows and the current linear baseline planning model. Missing, stale, failed, and expired worker evidence remain explicit and do not trigger a long-range browser query.

### Top Consumers

Ranks bucket storage/object/request/error evidence while keeping detailed records in the owning paginated table. Operational metrics remain preferred and committed Inventory is only an explicit supported fallback.

### Alerts & Anomalies

Automatic alert source selection remains Alertmanager-first with scoped Prometheus `ALERTS` fallback. Provider alert lifecycle records and KAORI metric-derived operating signals are presented separately.

## Dependency lifecycle

```text
Object Storage system + committed Inventory
        ↓
Validated operational metrics binding
        ↓
Current runtime metric evidence
        ↓
Object Storage Analytics
```

Alerts additionally expose provider alert evidence when available:

```text
Object Storage + Inventory
        ↓
Metrics
        ↓
Alert Evidence
```

A missing alert source does not erase usable metric-derived signals, and a metrics-source outage does not erase a usable Alertmanager stream on the Alerts page.

## Lock recommendation

Object Storage Analytics can remain locked after runtime smoke testing in the KAORI devcontainer. No page redesign is required. The principal audit corrections were blocker standardization, committed-inventory prerequisite enforcement, fail-closed HTMX dependency notices, and Hero copy refinement.
