# Kubernetes Operations Dashboard Styling Audit — July 2026

## Scope

Reviewed `app/templates/dashboards/kubernetes/`, the dashboard route/service contract, shared dashboard components, and the duplicated forecast implementation in Kubernetes Analytics.

## Approved decisions

- Register the integrated dashboard navigation as **Tab Style 1 — Integrated Workspace Tabs** (`integrated-workspace`) with URL state; the tab bar is not a separate card.
- Add a shared Operational Section Card.
- Add a static Operational Flow Steps component for peer main-content flows.
- Keep peer dashboard content in a shared 6/6 or 7/5 content grid and stretch both boxes to the tallest peer.
- Restore the card-grid Data Freshness presentation.
- Add a controlled capacity action flow derived from the current recommendation.
- Restore static box-based Alert Response and Reporting flows without expandable behavior. Reporting guidance ends with a visible operational tip callout.
- Consolidate the Forecast Projection Chart across Dashboard and Analytics.
- Standardize the compact 36 px section-header action.
- Keep primary Info Flow content static and always visible.
- Use section skeletons for initial loading and a section-owned loading bar for Cluster Health pagination and refresh.

## Before

- repeated page-local section shells across dashboard partials;
- custom tab geometry that lost state during HTMX scope refresh;
- tab navigation rendered as a separate floating block;
- duplicate forecast SVG implementations;
- custom status and metadata labels;
- card-inside-card tab composition;
- peer content incorrectly treated as a fixed sidebar;
- expandable flow guidance replacing the earlier actionable box flows;
- Cluster Health missing its own loading-bar feedback;
- pagination copy used lowercase resource naming;
- inconsistent card-title hierarchy and Title Case copy.

## After

- dashboard partials compose shared section, integrated-tab, flow, chart, label, table, state, pagination, and peer-grid components;
- active tab is preserved through `?tab=` and cluster changes, and the style is registered for reuse as Tab Style 1;
- Cluster Health uses default 5 and choices 5/10/25/50;
- Cluster Health owns its loading bar and uses `Showing X–Y of Z Clusters` copy;
- primary dashboard blocks use equal-height peer 6/6 or 7/5 content grids;
- the 20rem context rail remains reserved for genuinely secondary page content;
- Data Freshness again uses a compact card grid;
- Capacity Snapshot includes a visible recommendation-to-action flow;
- Alert Response and Reporting flows use static boxes and remain fully visible; Reporting includes a visible tip below the controlled flow;
- Forecast remains shared with Analytics;
- page-local arbitrary font sizes and repeated standard card shells remain removed.

## Data-boundary decision

The redesign remains presentation-only. The page continues to read committed KAORI database and worker snapshots. No live Kubernetes, Prometheus, Alertmanager, or storage query was added to a web request.
