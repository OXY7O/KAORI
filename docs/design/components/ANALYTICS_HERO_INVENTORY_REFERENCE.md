# Kubernetes Analytics Hero — Inventory Reference Contract

The accepted visual reference is the Kubernetes Node Inventory hero.

## Required composition

Every Kubernetes Analytics hero uses the shared `components/page_hero.html` contract:

- `shell_classes()` and `layout_classes()` for the violet hero shell;
- `intro()` for eyebrow, leading icon, title, and description;
- at most three metadata labels in the left content region;
- `context_card()` for normal right-side posture panels;
- `context_card_body()` only when a lazy-loaded partial already owns the `<aside>` wrapper;
- a stable domain title in the context card, with status shown once in the badge;
- exactly two compact metrics at most;
- `text-lg` metric values owned by `context_metric()`;
- one full-width `Manage Clusters` action using the `server-cog` icon.

## Prohibited page-level overrides

Analytics templates must not recreate the context panel, posture header, metric cards, metric value sizes, or action button. They must not import an Analytics-only hero action helper. Domain templates provide data and semantics only.

## Stable right-panel titles

- Analytics Overview: Analytics Status
- Resource Utilization: Resource Pressure
- Capacity Analysis: Capacity Headroom
- Storage Analysis: Storage Pressure
- Workload Analysis: Workload Governance
- Top Consumers: Consumer Pressure
- Alerts & Anomalies: Signal Readiness
- Resource Forecast: Forecast Outlook
