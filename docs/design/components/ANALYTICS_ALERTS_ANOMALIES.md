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
3. Cluster Signal Overview as one integrated decision workspace: Signal Posture, Alert Severity Profile, Investigation Focus, and a dedicated Operator Decision + Evidence Boundary rail. Avoid a six-column wall of peer metrics; primary volume, severity, dominant evidence, and operator action must read as separate layers.
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
- Alert and anomaly record actions use the shared Analytics record-detail modal with the canonical `View Details` label. Detail evidence must not expand inline inside either record collection. The shared modal is content-sized and defaults to `max-w-4xl`; dense Workload and Top Consumers evidence explicitly opt into the `wide` (`max-w-5xl`) variant. Viewport height is only a maximum guardrail, never a forced height. Alert details use Signal Context + Routing Metadata + Triage Decision/Readiness; Anomaly details use Observed Deviation + Review Decision + Investigation Sequence.
- Long labels and technical identifiers use controlled wrapping, not unconditional `break-all`.

## Routing, Suppression, Ownership, and Readiness

Routing, silence, inhibition, ownership, runbook, and readiness records are primary operational evidence and use bright surfaces. Review boundaries and recommended actions use darker soft surfaces.

Silence and inhibition evidence must not be interpreted as automatically good or bad. The UI shows matched scope and operational impact; the operator decides whether the suppression is intended.


## Incident Readiness Decision Workspace

Incident Readiness is not a six-metric dashboard. It is a decision workspace with four ordered layers:

1. `Readiness Posture`: one score plus the semantic readiness label.
2. `Response Control Readiness`: source health, ownership readiness, and routing context remain separate controls.
3. `Signal Pressure`: Critical, Warning, and Anomaly counts remain factual signal-load evidence.
4. `Incident Decision` and `Escalation Gate`: recommended action, silence/inhibition exposure, and pass/watch/fail check summary guide escalation.

The detailed `Readiness Checks` collection uses repeated semantic-dot status labels. The score may use a semantic progress bar because it represents an actual readiness state; signal-volume bars are not used.

## Progress and Severity

Status-related readiness and ownership progress bars use the shared semantic renderer because they represent operational state. Composition and contribution bars remain KAORI Violet; alert severity itself remains expressed through semantic labels and status evidence rather than recoloring quantitative contribution bars.

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
- No inline expandable Alert or Anomaly evidence rows; `View Details` must open the shared Analytics modal.
- No fixed viewport-height Analytics record modal. Content should determine modal height until the viewport-safe maximum is reached.
- No six-column Cluster Signal Overview metric wall. Use Signal Posture + Alert Severity Profile + Investigation Focus + Operator Decision/Evidence Boundary.
- No six-column Incident Readiness metric wall. Use Readiness Posture + Response Control Readiness + Signal Pressure + Incident Decision/Escalation Gate.
- No alert/anomaly modal that merely moves the inline detail block into an oversized dialog; modal information architecture must be purpose-built for triage.
