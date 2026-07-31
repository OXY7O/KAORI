# Analytics Workload Analysis

Status: Canonical KAORI Workload Analysis presentation and evidence contract

Implementation:

- `app/templates/analytics/workload/`
- `app/analytics/workload/service.py`
- `app/templates/analytics/components/_analysis_surfaces.html`
- `app/templates/analytics/components/_evidence_record_list.html`
- `app/templates/analytics/components/_record_filter_bar.html`

## Purpose

Workload Analysis combines Namespace ResourceQuota governance with workload request, limit, QoS, runtime-evidence, and right-sizing signals. It must distinguish configuration facts from health state and must never manufacture a right-sizing conclusion from missing observations.

## Workspace Composition

Use the Capacity reference grammar without forcing identical domain content:

```text
Hero
Controls & Data Readiness
Quick Workload Overview
Tabbed Detailed Workspace
├── Tenant Quota Analysis
├── Workload Resource Mapping
└── Workload Recommendations
```

Tenant Quota and Recommendations render with the page. Workload Resource Mapping loads on first tab activation. Hidden tabs do not request or poll.

## Scope Ownership

Top-level scope is:

```text
Cluster + Namespace + Time Range
```

Cluster and Time Range identify the committed worker snapshot. Namespace is a presentation filter applied to that snapshot. Local Search, Type, Configuration, QoS, Risk, and pagination filters update only the owning record panel.

Summary metrics follow the top-level active scope. Local filters do not change those summary metrics. The record footer reports both the filtered result count and the top-level scope count.

## Surface Hierarchy

- Summary metrics, scope context, quota evidence, workload mapping records, and expanded CPU/Memory evidence use bright surfaces.
- Operational Reading, Recommended Action, and interpretation guidance use the darker soft surface.
- Semantic status is carried by shared labels, not by tinting entire record rows.

## Extended Record Filter Bar

Workload Mapping uses the shared extended local filter pattern:

```text
Always Visible
├── Search
├── Workload Type
└── Risk

Advanced Filters — Closed By Default
├── Resource Configuration
├── QoS
└── Reset Filters
```

Advanced Filters may open initially only when an advanced filter is active. Do not keep five peer controls in one dense laptop-width row.

## Request and Limit Coverage

Request Coverage and Limit Coverage are separate evidence contracts.

Request Coverage:

- `Complete`
- `Partial`
- `Missing`
- `Unknown`

Limit Coverage:

- `Complete`
- `Memory Limit Missing`
- `CPU Limit Unset`
- `Limits Unset`
- `Partial`
- `Unknown`

Missing CPU or memory requests are high-risk because scheduling and right-sizing depend on them. Missing memory limits are warning-level governance evidence. `CPU Limit Unset` is factual information by default and must not be classified as a failure unless a separate governance policy requires CPU limits.

## QoS Semantics

Kubernetes QoS is factual metadata:

- `Guaranteed`
- `Burstable`
- `BestEffort`
- `Mixed`
- `Unknown`

QoS uses metadata-label treatment. Risk remains owned by Request Coverage, Limit Coverage, runtime evidence, and the dedicated Risk column. Do not use QoS as a duplicate semantic health badge.

## Analytics Evidence Coverage

Every workload record exposes runtime Evidence Coverage:

- `Complete`: every Pod has current CPU, current memory, selected-window CPU peak, and selected-window memory peak observations.
- `Partial`: at least one observation exists, but the complete four-signal set is not available for every Pod.
- `Unavailable`: no usable complete runtime and selected-window evidence is available.

Semantic ownership:

```text
Complete     → Normal
Partial      → Warning
Unavailable  → Unknown
```

Right-sizing is active only when Evidence Coverage is `Complete`. Partial evidence may produce review guidance, but it must not generate an automatic increase or reduction recommendation.

## Runtime Terminology

The instantaneous Prometheus signals are labeled `Current Usage`, not `Average Usage`.

The selected-window aggregate is labeled `Selected-Window Pod Peak Sum`. It is an upper-bound signal because individual Pod peaks may occur at different timestamps. Do not label it as a simultaneous workload peak or average.

## Request Fit

Do not calculate or display one averaged CPU/Memory `Efficiency` percentage. Show CPU Request Utilization and Memory Request Utilization separately so one resource bottleneck cannot be hidden by the other.

When evidence or the request denominator is unavailable:

- render `N/A`;
- use semantic `Unknown` when appropriate;
- suppress progress;
- defer right-sizing.

## ResourceQuota Semantics

A configured quota key with numeric value `0` remains configured. Missing-key detection checks key presence, not value truthiness.

Quota Pressure identifies the resource producing the highest valid used-to-hard ratio. Runtime Demand identifies the resource producing the highest valid current-to-limit ratio. Each value names its owning resource. Unavailable denominators render `N/A` rather than `0%`.

## Pagination and URL Ownership

Normal links always target the full Workload page:

```text
/analytics/workload?tab=quotas
/analytics/workload?tab=mapping
```

HTMX requests target the owning partial endpoint. Previous, numeric pages, Next, and 5/10/25/50 page-size changes retain Cluster, Namespace, Time Range, active tab, and local filters. Direct navigation must never open a fragment without the KAORI layout.

## Recommendation Destinations

Recommendations deep-link to the owning tab and filter context. Examples:

- missing ResourceQuota → Quotas / Missing;
- incomplete requests → Mapping / Requests Missing or Requests Partial;
- BestEffort → Mapping / BestEffort;
- right-sizing → Mapping / relevant Risk;
- general practice → Recommendations.

## Prohibited Patterns

- No composite page loading tracker outside Analytics Overview.
- No `Average Usage` label for current Prometheus observations.
- No composite CPU/Memory Efficiency value.
- No right-sizing recommendation when Evidence Coverage is not Complete.
- No CSS class in domain status payloads.
- No label parsing in Jinja to infer semantic tone.
- No QoS health coloring.
- No partial endpoint as a normal form action or pagination `href`.
- No compatibility aliases for retired workload filter or snapshot field names.
