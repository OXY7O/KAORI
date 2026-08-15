# Alert Intelligence Final Recheck — 2026-08

## Decision

Alert Intelligence is redesigned to the current KAORI Intelligence workspace standard and can be treated as visually locked pending browser/runtime smoke in the full devcontainer.

## Canonical page hierarchy

1. Hero — permanent Alert Intelligence identity and provider posture.
2. Alert Intelligence Summary — matching alerts, critical, warning, and committed recommendation context.
3. Alert Records Workspace — two-row auto-refresh filters, source-runtime context, records, and canonical pagination.
4. Correlation & Guidance — committed Recommendations beside canonical Rule Catalog enrichment definitions.
5. Notification Delivery — Integrations-owned channel posture and delivery journal scoped to the current domain + asset.
6. Evidence & Ownership Boundaries — explicit KAORI versus provider authority.

Page-level Alert Intelligence tabs are removed. Alert filters do not have an Apply button. Search and select changes refresh automatically; Reset Filters remains the only filter action.

## Authority boundary

- Kubernetes uses the existing alert source contract; Automatic prefers Alertmanager and may fall back to Prometheus `ALERTS`.
- Object Storage uses the provider-neutral alert stream contract with the same source-policy semantics.
- Alertmanager retains raw grouping, inhibition, silences, routing, receiver delivery, and lifecycle authority.
- KAORI adds asset identity, committed recommendation context, catalog guidance, and enriched Notification Channel delivery evidence.
- Correlation is contextual and must never be presented as causal attribution without evidence.
- Automation Control remains a separately governed execution boundary.

## Audit findings closed

- Removed five page tabs that fragmented one asset-scoped review workflow.
- Removed the Apply filter button; filters now use canonical HTMX auto-refresh behavior.
- Preserved Reset Filters and changed desktop filter geometry to two rows.
- Added a standalone Alert Intelligence Summary above the records workspace.
- Kept full-page scope refresh for domain/asset/source changes so Hero and dependent sections remain synchronized.
- Kept record pagination local to the table.
- Scoped recent delivery journal evidence by current domain + asset identity.
- Prevented a missing asset from producing an unusable Analytics action; Hero action points to the owning Integration setup instead.
- Preserved explicit Alertmanager/Prometheus fallback status, errors, and provider ownership semantics.

## No redesign required elsewhere

Notification Channels remains under Integrations. Recommendations and Rule Catalog remain separate Intelligence workspaces; Alert Intelligence links to them rather than duplicating their full record/detail experiences.
