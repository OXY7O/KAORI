# Alert Intelligence Final Recheck — 2026-08

## Decision

Alert Intelligence is aligned to the current KAORI Intelligence workspace standard and uses the shared KAORI Content Tabs in server-owned link mode to control long-form content while preserving one asset-scoped operational context. Browser/runtime smoke in the full devcontainer remains the final visual confirmation.

## Canonical page hierarchy

1. Hero — permanent Alert Intelligence identity and provider posture.
2. Alert Intelligence Summary — matching alerts, critical, warning, and committed recommendation context; remains visible across tabs.
3. Alert Intelligence Workspace — shared Operational Scope for domain, asset, and alert-source policy.
4. Section-owned tabs:
   - **Alert Records** — record-only filters, source/runtime/lifecycle context, records, and canonical pagination.
   - **Correlation & Guidance** — active recommendation count, catalog-rule count, contextual-only boundary, detailed recommendations, and canonical rule guidance.
   - **Notification Delivery** — shared channel posture, operational-channel count, asset-scoped delivery journal, and Integrations handoff.
   - **Evidence & Ownership** — detection, lifecycle, interpretation, and execution authority with explicit KAORI/provider ownership details.

The tabs are content-density controls, not separate operational scopes. Visual geometry is owned by `components/content_tabs.html`; selected section state remains URL/server-owned and does not use the Analytics client-side controller. Domain, asset, and source policy remain shared across every tab. Search, severity, and state filters exist only on Alert Records. There is no Apply button; all filters refresh automatically. Reset Filters remains available on Alert Records.

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
- Kept shared domain/asset/source controls outside tab-specific semantics so switching sections never changes operational scope.
- Kept Alert Records filters auto-refreshing and removed any Apply action; Reset Filters remains.
- Added informative tab context instead of label-only tabs: source/lifecycle context, recommendation/rule counts, delivery posture, and authority mapping.
- Kept full-page scope refresh for domain/asset/source changes so Hero, Summary, and active-tab context cannot drift apart.
- Kept record pagination local to the Alert Records table.
- Scoped recent delivery journal evidence by current domain + asset identity.
- Preserved explicit Alertmanager/Prometheus fallback status, errors, provider ownership semantics, and the contextual-not-causal correlation disclaimer.

## Ownership outside Alert Intelligence

Notification Channels remains under Integrations. Recommendations and Rule Catalog remain separate Intelligence workspaces; Alert Intelligence links to them rather than duplicating their full record/detail experiences. Automation Control remains the only governed execution surface.
