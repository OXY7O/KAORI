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
5. Metrics Source and Alertmanager landing registries omit the Endpoint column. Endpoint details belong in the connection manage workspace, while the landing registry prioritizes runtime, compatibility, readiness, bindings, and validation state.
6. Horizontal scrolling is allowed only when the available viewport is genuinely narrower than the compact technical table contract. Do not force an oversized minimum width by default.

## Kubernetes integration landing overview

1. The Kubernetes Integrations landing page uses the same overview-box hierarchy as Metrics Source and Alertmanager directly below the hero.
2. The overview header contains the provider icon, `Kubernetes Integration Overview`, and one concise description.
3. Summary metrics are presented in four compact cards: Registered Connections, Validated Connections, Needs Attention, and Scope Bindings.
4. The lower contract row contains Integration Contract, Capability Resolution, and Authority Boundary.
5. Do not split these three contracts into separate standalone cards above the registry; they belong inside the shared overview box.

## Integrations overview portfolio pattern

1. The Integrations domain landing page places an Integration Portfolio Snapshot directly below the hero.
2. The Hero reports implemented Provider Workspaces plus persisted configured/ready target counts; it must not imply that an implemented provider is already configured.
3. Portfolio metrics are Configured Targets, Ready for Use, Readiness Review, and Not Configured. Disabled targets are never counted as Ready for Use.
4. The lower contract row is one concise Connection and Authority Boundary; do not recreate multiple contract mini-cards below the four portfolio metrics.
5. Provider Catalog, Runtime Overview, and Domain Coverage use shared server-owned Violet workspace navigation. Switching uses URL/HTMX ownership and replaces only the Integration workspace rather than eagerly rendering client-hidden deep panels.
6. Runtime filters and pagination update only the Runtime Overview region through HTMX and preserve `tab=runtime` in the URL.
7. Runtime pagination keeps the result summary and compact numeric page-size selector together on the left; Previous, numeric pages, and Next remain grouped on the right.
8. Available domains with zero registered targets are Not Configured, never Ready. Planned domains remain visible as compact roadmap entries and do not expose configuration actions.
9. Runtime Overview is persisted-evidence presentation, not a live validation trigger. Its empty state follows the shared KAORI state contract and its provider-neutral history is governed by Data Lifecycle.

## Pagination interaction contract

1. A disabled Previous or Next control must be rendered as a non-interactive element, never as an anchor with an `href`.
2. Disabled controls use `aria-disabled="true"` and the shared disabled navigation classes.
3. Active pagination and page-size changes should update only the owning table or workspace region through HTMX when practical.
4. The loading bar belongs inside the owning block header, directly below the title/action row, and must target the same partial region. Use the Activity Audit Table rounded Violet track and pulsing one-third segment.


## Kubernetes registry action-density contract

1. The Kubernetes Connection Registry reserves its text width for connection identity, environment, readiness, compatibility, and validation time.
2. Row actions use 36 px icon-only controls with `title`, `aria-label`, and screen-reader text.
3. Manage, Configure, Metrics Source binding, Alertmanager binding, and Delete use distinct provider or lifecycle icons; semantic color is reserved for binding state and destructive action.
4. Icon-only actions remain right-aligned in the final compact column. Do not reintroduce provider names or long action labels into the registry row.
5. Full action wording and context belong in tooltips and the destination workspace.

## Hero contextual-density contract

1. Hero descriptions use the same 14–16 px medium-weight supporting-text hierarchy across Integrations Overview and provider workspaces.
2. The right context panel contains a concise title, at most two compact metrics, and at most two actions.
3. Do not place paragraph-length workflow explanation in the context panel. Detailed guidance belongs in the overview box, Info Flow, or content workspace.
4. Add and Edit Kubernetes pages use the shared Hero Context Panel with two metrics and one Back to Registry action; their wider contextual rail uses an 8:4 main-to-side grid.

### Dense Registry Action Width

When a registry uses icon-only actions, the Actions column width must include icon width, inter-action gaps, and cell padding. Do not force five 32 px controls into a 150 px cell. The Kubernetes Connection Registry uses a dedicated 208 px right-aligned Actions column and explicit table width so controls never clip or leave an unexplained trailing surface.

### Shared-source binding workspace

- Scope Bindings must occupy a full-width block before resolver and creation panels.
- Do not use horizontally scrolling binding tables for selector-heavy content. Use responsive binding cards with standard KAORI typography.
- Metrics Identity and Alert Identity values use normal KAORI table/body typography; monospace is reserved for executable commands or code-oriented evidence.
- Provider registry Connection columns remain proportional and must not push Runtime, Compatibility, Readiness, or Last Validated off-screen.
- Metrics Source and Alertmanager registries reserve the largest column for Connection identity. Readiness and Action remain compact; Action may use a smaller labeled Manage control as long as accessibility and focus treatment remain intact.

## Jobs & Executions Workspace

Jobs & Executions is a cross-domain **Platform Operations** workspace. Do not place it inside a provider-specific Integrations submenu because it covers validation, runtime, analytics, forecasting, reporting, lifecycle, and future background work.

Required hierarchy:

1. Standard KAORI hero with compact execution posture.
2. Execution Overview with Active, Running, Needs Attention, and Completed-in-24-hours metrics.
3. Top-level tabs separate **Executions** from **Job Configuration**.
4. Executions retains violet inner tabs for Active Work, Execution Registry, and Queue Activity.
5. Active jobs use responsive cards with progress, queue, requester, timing, and cancellation boundary.
6. Execution Registry uses a compact six-column table: Job, Execution Context, Status, Progress, Timing, Action.
7. Queue Activity describes canonical database-backed execution demand and must not claim worker process liveness.
8. Job Configuration uses a searchable registered-job catalog and one selected definition workspace. It must show policy, scope, queue, last/next run, manual execution, recent executions, and the domain safety boundary without moving domain business logic into `app.jobs`.

The registry remains server-paginated with default 5 and options 5/10/25/50. The visible page-size control is numeric only. Refresh, filters, pagination, and cancellation use HTMX without reloading the hero.

## Runtime observation detail pattern

1. Recent Runtime Observations uses compact expandable observation cards rather than forcing long health evidence into a horizontal table row.
2. The collapsed summary shows observed time, health/readiness, score, capability profile, transition, and a clear `View Detail` affordance.
3. The expanded detail owns health narrative, latency, compatibility, capability changes, immutable diagnostics, and recommended action.
4. Kubernetes observations show both the KAORI current lifecycle band and the wider accepted compatibility contract. A version may be technically accepted while still classified as legacy.
5. Kubernetes detail also lists stable APIs selected by discovery and any legacy fallbacks recorded in that observation.
6. Scheduled Runtime Health and Full Capability Validation must be described separately: scheduled refresh is lightweight and automatic; full validation is worker-based and on demand after registration or contract changes.


### Jobs progress and action presentation

- Active Work uses one full-width execution row per job, not a two-column card grid.
- Workload icons are semantic and consistent: activity for runtime, scan-search for validation, analytics chart for batch analytics, chart-spline for forecasting, and workflow for general work.
- Show a determinate percentage only when the worker has published a valid total. Otherwise use an indeterminate moving bar and the label `In Progress`; queued work uses `Queued` without false percentage precision.
- Queued and cooperative heavy jobs may show `Cancel` when the user has `jobs.cancel`.
- Running provider validation/runtime work shows `Protected Run` because provider requests are not force-terminated mid-flight.
- Block loading indicators sit directly below the corresponding block header before filters or data content.
