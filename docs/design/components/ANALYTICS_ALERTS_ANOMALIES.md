# Analytics Alerts & Anomalies Standard

Status: Canonical KAORI Analytics presentation and signal-evidence contract

Implementation owners:

- `app/analytics/alerts/`
- `app/templates/analytics/alerts/`
- `app/templates/analytics/components/_analysis_surfaces.html`
- `app/templates/analytics/components/_evidence_record_list.html`
- `app/templates/analytics/components/_record_pagination.html`

## Purpose

Alerts & Anomalies presents committed alert, anomaly, routing, suppression, ownership, and readiness evidence without treating a disconnected or partially available source as a healthy state. The page separates raw operational evidence from interpretation and recommended action.

## Workspace Composition

1. Hero with page posture, Critical Alerts, Source Health, and a full-width bottom notice.
2. Controls and Data Readiness with Cluster, Source, committed snapshot metadata, and source warnings.
3. Cluster Signal Overview as one integrated signal workspace: compact Signal Snapshot, alert severity profile, Investigation Focus, and a dedicated Operational Reading rail. Avoid a six-column wall of peer metrics; primary volume, severity, and investigation guidance must read as separate evidence layers.
4. Canonical tabs: Alerts, Anomalies, Routing & Suppression, Ownership & Runbooks, Incident Readiness, Recommendations, and Operational Resources.
5. Bright record and operational evidence.
6. Darker interpretation, attention, suppression boundary, and recommended-action regions.

## Signal Evidence Semantics

Source and anomaly evidence are independent. Page posture follows the strongest applicable state:

- `Blocked` when a dependency blocker prevents analysis;
- `Unknown` when no alert source is connected;
- `Critical` when critical alerts are active;
- `Review` when warning alerts or anomaly candidates require investigation;
- `Evidence Incomplete` when one or more optional sources are partial or unavailable;
- `Healthy` only when required evidence is connected, optional collection is complete, and no active signal requires review.

Missing evidence is never converted into zero, Normal, or Healthy.

## Source Readiness and Committed Snapshot

Source Readiness describes current Alertmanager or Prometheus connectivity. Committed Snapshot describes the worker-produced dataset being viewed. These are related but separate evidence boundaries. A currently degraded source does not invalidate already committed evidence, but it must be shown as a warning for future refreshes.

Prometheus fallback may provide alert records while Alertmanager-specific routing, silence, and inhibition evidence remains limited. The page must state this limitation explicitly.

## Snapshot and Presentation Dimensions

The committed `analytics.alerts` dataset is keyed only by `cluster_id` and `source`. Severity, status, Namespace, search, active tab, alerts pagination, and anomalies pagination are local presentation state. These controls must never generate additional worker snapshots.

The full committed record set owns page posture, source health, incident readiness, and recommendations. Local filters only change record tables and their local result summary; filtering out a critical alert must not rewrite the global posture to Healthy. Incomplete anomaly evidence must generate a recovery recommendation; it cannot produce the Normal no-action baseline.


## Normalization and Deduplication

- Alertmanager fingerprint is the preferred stable identity when present.
- Prometheus HA replica labels such as `__replica__` and `prometheus_replica` are excluded from fallback identity.
- Severity aliases such as `P1`, `page`, `error`, and `fatal` normalize to Critical; `P2` and `warn` normalize to Warning.
- Namespace filters use exact normalized equality rather than substring matching.
- Duplicate anomaly candidates use signal name, Namespace, and target identity, retaining the strongest observation.

## Anomaly Query Boundary

Restart and readiness anomaly queries execute independently. A failure in one query family must not erase successful evidence from the other. The source-status payload exposes available and failed query families and marks the result partial.

Both anomaly families are limited to active Pods in `Pending|Running`. Restart counters are normalized with `max by(namespace,pod,container)` before Pod aggregation so duplicate kube-state-metrics scrape targets do not inflate the signal.

## Semantic Status Ownership

Domain payloads provide semantic levels such as `healthy`, `fallback`, `degraded`, `available`, `limited`, `ready`, `partial`, `weak`, `watch`, and `incident_risk`. Templates normalize these through `table_label.semantic_tone(...)`.

Domain services do not emit CSS classes. Visual geometry and color remain owned by shared components.

## Alerts and Anomalies Record Collection

Alerts and Anomalies use the shared Evidence Record Collection and shared Record Pagination.

The two collections use independent page state: `alerts_page`/`alerts_per_page` and `anomalies_page`/`anomalies_per_page`. Fragment routes require HTMX, use `Cache-Control: no-store`, vary on `HX-Request`, and push the canonical full-page URL. Direct navigation to a fragment redirects to `/analytics/alerts` with the corresponding tab.

- Normal links resolve to `/analytics/alerts` with the canonical `tab` parameter.
- HTMX requests use the owning partial endpoint.
- Filters retain Cluster, Source, Severity, State, Namespace, Search, active tab, and both page-size values.
- Default page size is 5 with 5/10/25/50 options.
- Alert and anomaly record actions use the shared Analytics record-detail modal with the canonical `View More` label. Detail evidence must not expand inline inside either record collection. The shared modal is content-sized on desktop (`max-w-5xl`) and uses viewport height only as a maximum bound; it must never force a near-full-screen empty body when the detail content is short.
- Long labels and technical identifiers use controlled wrapping, not unconditional `break-all`.

## Routing, Suppression, Ownership, and Readiness

Routing, silence, inhibition, ownership, runbook, and readiness records are primary operational evidence and use bright surfaces. Review boundaries and recommended actions use darker soft surfaces.

Silence and inhibition evidence must not be interpreted as automatically good or bad. The UI shows matched scope and operational impact; the operator decides whether the suppression is intended.

## Progress and Severity

Readiness and ownership progress fills remain KAORI Violet. Alert severity belongs to semantic badges, icons, and copy. Do not recolor progress bars red or amber unless a separate visualization contract is approved.

## Report and Overview Consumers

The Alerts & Anomalies report reads the committed `analytics.alerts` snapshot and never performs live provider calls during rendering. When committed evidence is unavailable, the report renders an explicit unavailable evidence boundary.

Analytics Overview consumes the snapshot evidence-completeness fields. It may show Stable only when alert-source and anomaly evidence are complete and no active signal requires review.

## Canonical Navigation

Use:

- `?tab=alerts`
- `?tab=anomalies`
- `?tab=routing`
- `?tab=ownership`
- `?tab=readiness`
- `?tab=recommendations`
- `?tab=resources`

The legacy `/analytics/alerts-anomalies` route is not part of the canonical contract.

## Prohibited Patterns

- No CSS classes in alert-domain payloads.
- No page-local workspace tab shell.
- No domain-local pagination partial.
- No direct fragment endpoint as a normal `href`.
- No Healthy posture when evidence is incomplete.
- No dark fill around primary signal records or metrics.
- No red or amber readiness progress fill.
- No arbitrary micro typography in Alerts templates.
- No inline expandable Alert or Anomaly evidence rows; `View More` must open the shared Analytics modal.
- No fixed viewport-height Analytics record modal. Content should determine modal height until the viewport-safe maximum is reached.
- No six-column Cluster Signal Overview metric wall. Use the integrated Signal Snapshot + severity profile + Investigation Focus + Operational Reading composition.
