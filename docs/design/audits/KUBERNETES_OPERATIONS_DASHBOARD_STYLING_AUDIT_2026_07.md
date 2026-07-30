# Kubernetes Operations Dashboard Styling Audit — July 2026

## Scope

Reviewed `app/templates/dashboards/kubernetes/`, the dashboard route/service contract, shared dashboard components, and the duplicated forecast implementation in Kubernetes Analytics.

## Approved decisions

- Add a shared Operational Section Card.
- Add standalone Workspace Tabs with URL state.
- Document dashboard metric typography.
- Consolidate the Forecast Projection Chart across Dashboard and Analytics.
- Standardize the compact 36 px section-header action.
- Keep primary Info Flow content static and always visible.
- Use Context Guidance Card for secondary rail guidance.

## Before

- repeated page-local section shells across dashboard partials;
- custom tab geometry that lost state during HTMX scope refresh;
- duplicate forecast SVG implementations;
- custom status and metadata labels;
- card-inside-card tab composition;
- custom Cluster Health pagination with enabled controls styled as disabled;
- repeated manual empty and unavailable states;
- inconsistent card-title hierarchy and Title Case copy.

## After

- dashboard partials compose shared section, tab, chart, label, table, state, pagination, and rail components;
- active tab is preserved through `?tab=` and cluster changes;
- Cluster Health uses default 5 and choices 5/10/25/50;
- primary content and contextual guidance follow the 20rem rail contract;
- Forecast is full-width and shared with Analytics;
- Info Flow is static; secondary guidance remains expandable in the rail;
- page-local arbitrary font sizes and repeated standard card shells are removed from Kubernetes Dashboard templates.

## Data-boundary decision

The redesign remains presentation-only. The page continues to read committed KAORI database and worker snapshots. No live Kubernetes, Prometheus, Alertmanager, or storage query was added to a web request.
