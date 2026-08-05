# Kubernetes Analytics Hero Extension

This document extends `HERO.md` for Kubernetes Analytics. It does not override shared hero geometry, typography, or action styling.

## Reference composition

Kubernetes Node Inventory is the content-density reference. Every Analytics hero uses `components/page_hero.html` and contains:

1. `Kubernetes Analytics` domain eyebrow;
2. one concise page title and description;
3. no more than three metadata labels in any rendered branch;
4. one compact posture context card;
5. exactly two posture metrics;
6. one full-width `Manage Clusters` action using `server-cog`.

## Canonical implementation

Normal Analytics pages use:

```jinja
page_hero.context_card(...)
```

Analytics Overview lazy posture uses:

```jinja
page_hero.context_card_body(...)
```

because the parent hero already owns the `<aside>` wrapper.

Domain templates provide only:

- posture label;
- semantic tone;
- metric labels and values;
- concise metric helpers;
- cluster-management URL.

They do not recreate posture headers, metric cards, value scales, or action geometry.

## Stable context titles

- Analytics Overview: `Analytics Status`
- Resource Utilization: `Resource Pressure`
- Capacity Analysis: `Capacity Headroom`
- Storage Analysis: `Storage Pressure`
- Workload Analysis: `Workload Governance`
- Top Consumers: `Consumer Pressure`
- Alerts & Anomalies: `Signal Readiness`
- Resource Forecast: `Forecast Outlook`

## Metadata ownership

Metadata must not duplicate the two posture metrics. Long technical identifiers remain in evidence and detail surfaces. Hero helper values use concise semantic context such as:

- `Node Filesystem`;
- `Ready-Worker Capacity`;
- `Namespace Scope`;
- a short resource display name.

Do not truncate technical identifiers into an ambiguous hero label.

## Prohibited patterns

- Analytics-only hero helper components that duplicate `page_hero`;
- `context_posture_header(...)`;
- `context_posture_note(...)`;
- `context_bottom_notice(...)`;
- local `text-xl`, `text-2xl`, or `value_classes` metric overrides;
- more than two posture metrics;
- a second interpretation paragraph inside the context card.

Interpretation and recommended action belong in the Analytics content surfaces below the hero.
