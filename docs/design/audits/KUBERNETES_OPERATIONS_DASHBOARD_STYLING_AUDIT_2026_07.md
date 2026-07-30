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
- Use Context Guidance Card for reusable ordered guidance.
- Keep peer dashboard content in a shared 6/6 or 7/5 content grid; do not treat it as a fixed sidebar.
- Use section skeletons for dashboard loading instead of one global loading bar.

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

- dashboard partials compose shared section, tab, chart, label, table, state, pagination, and peer-grid components;
- active tab is preserved through `?tab=` and cluster changes;
- Cluster Health uses default 5 and choices 5/10/25/50;
- primary dashboard blocks use peer 6/6 or 7/5 content grids;
- the 20rem context rail remains reserved for genuinely secondary page content outside this dashboard layout;
- Forecast remains shared with Analytics and is paired with Capacity in the dashboard content grid;
- Info Flow is static; reusable secondary guidance remains expandable without being treated as a sidebar;
- asynchronous dashboard sections use local skeleton placeholders and no global dashboard loading bar;
- page-local arbitrary font sizes and repeated standard card shells are removed from Kubernetes Dashboard templates.

## Data-boundary decision

The redesign remains presentation-only. The page continues to read committed KAORI database and worker snapshots. No live Kubernetes, Prometheus, Alertmanager, or storage query was added to a web request.
