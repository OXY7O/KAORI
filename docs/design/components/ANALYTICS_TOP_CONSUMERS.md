# Analytics Top Consumers Standard

Status: Canonical KAORI Analytics presentation and evidence contract

Implementation owners:

- `app/analytics/top_consumers/service.py`
- `app/templates/analytics/top_consumers/`
- `app/templates/analytics/components/_ranked_evidence_panel.html`
- `app/templates/analytics/components/_record_pagination.html`

## Purpose

Top Consumers identifies the largest consumers in a committed cluster or namespace snapshot without treating CPU, memory, pod count, and PVC bytes as one comparable unit. The page separates consumption, contribution, configuration boundaries, and operational pressure.

## Workspace Composition

1. Hero with page posture, highest valid pressure, actionable count, and bottom notice.
2. Controls and readiness with Cluster and Namespace Snapshot only.
3. Top Consumer Summary with structured identity.
4. Canonical tabs: Consumer Rankings, Consumer Records, Recommendations.
5. Bright ranked and record evidence.
6. Darker interpretation and recommended-action regions.

## Namespace Snapshot Ownership

Namespace is a worker snapshot dimension. Cluster scope reads the committed cluster snapshot; a selected Namespace reads a namespace-specific committed snapshot. Changing Namespace may require a new materialization. Search, Resource, Priority, Sort, Focus, and pagination are presentation-only controls.

## Canonical Consumer Identity

Never parse a display string to reconstruct identity. Payloads provide:

- entity type;
- namespace;
- workload owner and kind when available;
- pod;
- container;
- PVC.

CPU and memory consumers are containers within pods, optionally resolved to a workload owner. Pod density is a namespace entity. Storage consumers are PersistentVolumeClaims.

## Consumer Pressure Model

Keep these signals distinct:

- absolute consumption;
- contribution to selected-scope consumption;
- request utilization;
- limit utilization;
- configuration state;
- operational pressure.

Do not publish a blended usage ratio. Missing CPU or memory requests are Critical. Missing memory limits are Warning. An unset CPU limit is informational unless policy says otherwise. PVC pressure uses claim capacity. Pod pressure uses cluster pod capacity and must be labeled as namespace share of that capacity.

## Mixed-Resource Sort Contract

For All Resources, allow Operational Priority, Contribution to Scope, Namespace, and Resource Type. Do not sort heterogeneous raw units together.

For a single resource, allow Absolute Consumption, Pressure Ratio, Operational Priority, and Namespace.

## Multi-Resource Evidence Coverage

CPU, Memory, Pods, and PVC each report Complete, Partial, or Unavailable. The page posture is:

- Critical when critical pressure or a critical configuration gap exists;
- Evidence Incomplete when any resource evidence is partial or unavailable and there is no higher critical state;
- Review for warning pressure;
- Healthy only when all evidence is complete and no hotspot exists;
- Unknown when no consumer evidence exists.

Unavailable denominator evidence renders `N/A` and suppresses derived progress.

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

Consumer Records use `_evidence_record_list.html`, `_record_filter_bar.html`, and the shared `_record_pagination.html`.

Normal links always resolve to the full page. HTMX requests target the owning partial. Page size follows 5/10/25/50. Expanded records are closed by default and must retain a native `hidden` fallback so HTMX swaps cannot expose all detail bodies before Alpine initialization.

## Prohibited Patterns

- No display-string splitting for identity.
- No all-resource raw-value sort.
- No synthetic zero or Normal state for missing evidence.
- No red or amber progress fills for consumer pressure.
- No CSS classes in domain payloads.
- No domain-local record pagination copies.
- No direct fragment endpoint as a normal `href`.
