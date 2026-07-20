# Inventory and Operational Page Patterns

This document defines reusable structures. It does not define domain-specific fields, metrics, routes, or actions.

## Inventory list pattern

1. Shared hero.
2. One filter-and-table content block.
3. Default pagination of 5 with 5/10/25/50 options.
4. Left-aligned operational columns and right-aligned final action column.
5. Expandable details when row-level context cannot fit without harming scanability.
6. Shared loading, empty, unavailable, and permission states.

## Expandable detail pattern

- Standard cards use 12 px radius.
- Icon surfaces use 8 px radius.
- Key/value rows use consistent sans-serif typography.
- Dynamic status uses semantic labels.
- Identity and descriptive values use metadata or neutral treatment.
- Empty nested sections use a compact dashed information box rather than an empty object card.
- Secondary summaries may be anchored in a bottom stack above one concise informational tip.

## Operational workspace pattern

1. Workspace Hero.
2. Compact readiness or authority context.
3. Primary configuration or operation card.
4. Supporting guidance rail where useful.
5. Runtime, validation, history, and audit evidence in separate sections or tabs.
6. HTMX updates target the affected content region and preserve hero stability.

## Selector pattern

- Labels use sentence case.
- Standard controls are 44 px high with 8 px radius.
- Focus uses KAORI Violet.
- Live lookup failures display a concise in-page state; full technical evidence belongs in Activity Audit Log.
- A selector must not trigger a full-page reload when an HTMX interaction is appropriate.

## Integration landing workspace pattern

1. Provider overview remains above the workspace switcher.
2. Integration Coverage and Connection Registry use one shared Violet tab bar. The selected tab uses solid KAORI Violet with white text; unselected tabs remain Violet outlined/soft rather than neutral gray.
3. Coverage and Registry title boxes use the same icon, title, description, spacing, border, and loading-bar hierarchy. Provider-specific wording may differ, but the visual shell must not.
4. Registry tables use explicit column widths. The final Action column is compact, right-aligned, and must not be the cause of horizontal overflow.
5. Horizontal scrolling is allowed only when the available viewport is genuinely narrower than the compact technical table contract. Do not force an oversized minimum width by default.

## Kubernetes integration landing overview

1. The Kubernetes Integrations landing page uses the same overview-box hierarchy as Prometheus and Alertmanager directly below the hero.
2. The overview header contains the provider icon, `Kubernetes Integration Overview`, and one concise description.
3. Summary metrics are presented in four compact cards: Registered Connections, Validated Connections, Needs Attention, and Scope Bindings.
4. The lower contract row contains Integration Contract, Capability Resolution, and Authority Boundary.
5. Do not split these three contracts into separate standalone cards above the registry; they belong inside the shared overview box.

