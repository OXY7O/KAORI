# Analytics Top Consumers Standard

Status: Canonical KAORI Analytics presentation, evidence, and snapshot contract

Implementation owners:

- `app/analytics/top_consumers/contracts.py`
- `app/analytics/top_consumers/evidence.py`
- `app/analytics/top_consumers/rows.py`
- `app/analytics/top_consumers/domain.py`
- `app/analytics/top_consumers/presentation.py`
- `app/analytics/top_consumers/recommendations.py`
- `app/analytics/top_consumers/service.py`
- `app/analytics/top_consumers/routes.py`
- `app/templates/analytics/top_consumers/`
- `app/templates/analytics/components/_ranked_evidence_panel.html`
- `app/templates/analytics/components/_record_pagination.html`

## Purpose

Top Consumers identifies the largest active consumers in a committed cluster or Namespace snapshot without treating CPU cores, memory bytes, Pod count, and PVC bytes as comparable raw units. The page separates absolute consumption, contribution, request and limit configuration, pressure against a valid denominator, and operational priority.

## Runtime Ownership

```text
Prometheus query registry
        ↓
TopConsumersEvidenceCollector
        ↓
Canonical row builders
        ↓
Domain coverage and posture
        ↓
Committed analytics.top_consumers snapshot
        ↓
Presentation-only filters and pagination
        ↓
Page, Analytics Overview, and report payload
```

Each Prometheus signal is queried once per snapshot variant. `service.py` owns orchestration only; query parsing, row construction, risk semantics, actionable recommendations, and presentation controls belong to their dedicated modules.

## Namespace Snapshot Ownership

The committed snapshot varies only by:

- Cluster;
- optional Namespace.

The following are presentation state and must never create another snapshot:

- active tab;
- resource;
- search;
- priority;
- focus;
- sort;
- page;
- rows per page.

A requested Namespace may only display a committed snapshot whose payload scope matches that exact Namespace. A cluster snapshot must never be silently projected into a Namespace view. A mismatch renders a refresh/materialization requirement.

## Evidence Boundary

### CPU and memory

CPU and memory consumer rows include only non-infrastructure containers from Pods in `Pending` or `Running` phase. Duplicate scrape series are normalized by:

```text
namespace + pod + container
```

before ranking or aggregation.

Requests and limits use the same active-Pod identity boundary. An empty request or limit query is treated as confirmed absence only when the corresponding `resource_requests_limits` capability evidence is available. When capability evidence is missing, an empty result is `Unavailable`, not zero and not a confirmed configuration gap.

### Pod density

Pod ranking counts distinct `Running` Pods by Namespace. Pod pressure uses total Ready-worker allocatable Pod capacity. Nodes with role `control-plane` or legacy `master` are excluded.

### PVC consumption

PVC ranking uses observed mounted-volume bytes:

```text
kubelet_volume_stats_used_bytes
/
kubelet_volume_stats_capacity_bytes
```

Duplicate series are normalized by:

```text
namespace + persistentvolumeclaim
```

Requested PVC storage is not a pressure denominator.

### Scope totals and capacity

CPU, memory, and Pod denominators use Ready-worker allocatable capacity. PVC capacity is the sum of observed claim capacities represented in the selected snapshot. Missing denominator evidence renders `N/A`; it never creates a synthetic `0%`, `100%`, Normal, or Healthy state.

## Workspace Composition

1. Hero with actual page posture, highest valid pressure, actionable count, and scope metadata.
2. Controls and readiness with Cluster and Namespace Snapshot only.
3. Top Consumer Summary with structured identities.
4. Canonical tabs: Consumer Rankings, Consumer Records, Recommendations.
5. Bright ranked and record evidence.
6. Darker interpretation and recommended-action regions.

## Canonical Consumer Identity

Never parse a display string to reconstruct identity. Payloads provide:

- entity type;
- Namespace;
- workload owner and kind when available;
- Pod;
- container;
- PVC.

CPU and memory consumers are containers within Pods, optionally resolved to a workload owner. Pod density is a Namespace entity. Storage consumers are PersistentVolumeClaims.

## Consumer Pressure Model

Keep these signals distinct:

- absolute consumption;
- contribution to selected-scope consumption;
- request utilization;
- limit utilization;
- configuration state;
- operational pressure.

Do not publish a blended usage ratio.

Configuration policy:

- confirmed missing CPU or memory request: Critical;
- confirmed missing memory limit: Warning;
- confirmed unset CPU limit: Info unless policy says otherwise;
- request or limit capability unavailable: Unknown / Evidence Incomplete;
- PVC pressure: observed usage versus observed volume capacity;
- Pod pressure: Namespace running Pod count versus Ready-worker Pod capacity.

## Mixed-Resource Sort Contract

For All Resources, allow:

- Operational Priority;
- Contribution to Scope;
- Namespace;
- Resource Type.

Never sort heterogeneous raw units together.

For a single resource, allow:

- Absolute Consumption;
- Pressure Ratio;
- Operational Priority;
- Namespace.

Rows without an optional pressure or contribution value sort after rows with valid evidence.

## Multi-Resource Evidence Coverage

CPU, Memory, Pods, and PVC each report Complete, Partial, or Unavailable. Page posture is:

- Critical when critical pressure or a confirmed critical configuration gap exists;
- Limited Evidence when any resource evidence is partial or unavailable and no higher critical state exists;
- Watch for warning pressure with complete evidence;
- Healthy only when all four resource evidence sets are complete and no hotspot exists;
- Unknown when no eligible consumer evidence exists.

Provider capability observations are advisory. The exact dataset query remains the authoritative runtime probe. When a capability is already known missing and its query returns no rows, the result remains unavailable rather than being converted to confirmed zero.

## Ranked Consumer Evidence

Use `_ranked_evidence_panel.html` for ranked consumer panels. Each panel owns:

- resource title and icon;
- selected-scope total;
- capacity or denominator context;
- structured identity;
- absolute consumption;
- contribution to selected scope;
- semantic priority.

Progress represents contribution and remains KAORI Violet. Severity belongs to the semantic badge and copy.

## Record Collection and Pagination

Consumer Records use `_evidence_record_list.html`, `_record_filter_bar.html`, and shared `_record_pagination.html`.

Normal links always resolve to the full page. `/analytics/top-consumers/table` is HTMX-only; direct navigation redirects to the full workspace with `tab=records`. Fragment responses are `no-store`, vary on `HX-Request`, and push the canonical full-page URL.

Page size follows 5/10/25/50. Consumer record actions use the shared Analytics record-detail modal and the canonical `View More` label. Record evidence must not expand inline inside the collection; the modal is teleported to `body` so table and HTMX overflow boundaries cannot clip the detail surface. Top Consumers explicitly uses the shared modal `wide` variant (`max-w-5xl`) because its evidence matrix is denser than alert/anomaly triage. The modal remains content-sized with a viewport-safe maximum height; short record evidence must not stretch to full-screen height.

## Report Contract

The Top Consumers report uses `TopConsumersSelection` and the same service/domain pipeline as the page. Its period is the canonical `current` snapshot, not an inherited `24h` history label. Report collection uses Operational Priority for mixed resources and must not reintroduce an invalid `usage_percent` sort or a different PVC denominator.

## Prohibited Patterns

- No display-string splitting for identity.
- No all-resource raw-value sort.
- No synthetic zero or Normal state for missing evidence.
- No requested PVC capacity as usage denominator.
- No control-plane or NotReady node capacity in worker pressure.
- No terminal Pod consumption in active rankings.
- No red or amber progress fills for consumer pressure.
- No CSS classes in domain payloads.
- No domain-local record pagination copies.
- No direct fragment endpoint as a normal `href`.
- No compatibility `/top-consumers/section` route.
- No inline expandable Consumer Record detail bodies; `View More` must open the shared Analytics modal.
