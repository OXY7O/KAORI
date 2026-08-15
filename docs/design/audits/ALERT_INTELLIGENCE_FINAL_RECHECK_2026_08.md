# Alert Intelligence Final Recheck — 2026-08

## Decision

Alert Intelligence is aligned to the current KAORI Intelligence workspace standard and uses the shared KAORI Content Tabs in server-owned link mode to control long-form content while preserving one asset-scoped operational context. Browser/runtime smoke in the full devcontainer remains the final visual confirmation.

## Canonical page hierarchy

1. Hero — permanent Alert Intelligence identity and provider posture.
2. Alert Intelligence Summary — matching alerts, critical, warning, and committed recommendation context; remains visible across tabs.
3. Alert Intelligence Workspace — shared Content Tabs first, followed by a compact Operational Context for domain, asset, and alert-source policy.
4. Active section content remains inside that same workspace surface:
   - **Alert Records** — record-only filters, source/runtime/lifecycle context, records, and canonical pagination.
   - **Correlation & Guidance** — active recommendation count, catalog-rule count, contextual-only boundary, detailed recommendations, and canonical rule guidance.
   - **Notification Delivery** — shared channel posture, operational-channel count, asset-scoped delivery journal, and Integrations handoff.
   - **Evidence & Ownership** — detection, lifecycle, interpretation, and execution authority with explicit KAORI/provider ownership details.

The tabs are the primary navigation inside the workspace, not a control that follows a filter form. Visual geometry is owned by `components/content_tabs.html`; selected section state remains URL/server-owned and does not use the Analytics client-side controller. The compact **Operational Context** sits below the tabs because domain, asset, and source policy define the shared evidence context rather than filtering one table. Search, severity, and state are separate record filters that exist only inside Alert Records. There is no Apply button; all controls refresh automatically. Reset Filters remains available inside Alert Records and preserves the selected alert-source context. Active section content is rendered inside the same outer workspace surface instead of creating a second standalone section card below it.

## Authority boundary

- Kubernetes uses the existing alert source contract; Automatic prefers Alertmanager and may fall back to Prometheus `ALERTS`.
- Object Storage uses the provider-neutral alert stream contract with the same source-policy semantics.
- Alertmanager retains raw grouping, inhibition, silences, routing, receiver delivery, and lifecycle authority.
- KAORI adds asset identity, committed recommendation context, catalog guidance, and enriched Notification Channel delivery evidence.
- Correlation is contextual and must never be presented as causal attribution without evidence.
- Automation Control remains a separately governed execution boundary.

## Audit findings closed

- Replaced the long sequential page with four section-owned tabs while keeping the global Summary visible.
- Replaced the page-local Intelligence underline tab treatment with the canonical shared KAORI Content Tabs component used by Analytics; Alert Intelligence uses `render_links()` because section state is server/URL-owned.
- Extended shared server-owned Content Tabs with backward-compatible `nowrap` and `hx-sync` support so long labels remain one row on the 14-inch target and concurrent HTMX scope/tab requests share one synchronization boundary.
- Moved canonical Content Tabs directly below the workspace header so section choice is visually primary.
- Renamed the global controls to **Operational Context** and compacted them below the tabs so they read as shared evidence context rather than a filter panel.
- Moved Alert Record search/severity/state controls into the Alert Records section itself; Reset Filters now preserves domain, asset, and alert-source context.
- Rendered the active tab inside the same workspace surface instead of stacking a second full section card below the workspace shell.
- Added informative tab context instead of label-only tabs: source/lifecycle context, recommendation/rule counts, delivery posture, and authority mapping.
- Kept full-page scope refresh for domain/asset/source changes so Hero, Summary, and active-tab context cannot drift apart.
- Kept record pagination local to the Alert Records table.
- Scoped recent delivery journal evidence by current domain + asset identity.
- Preserved explicit Alertmanager/Prometheus fallback status, errors, provider ownership semantics, and the contextual-not-causal correlation disclaimer.

## Ownership outside Alert Intelligence

Notification Channels remains under Integrations. Recommendations and Rule Catalog remain separate Intelligence workspaces; Alert Intelligence links to them rather than duplicating their full record/detail experiences. Automation Control remains the only governed execution surface.
