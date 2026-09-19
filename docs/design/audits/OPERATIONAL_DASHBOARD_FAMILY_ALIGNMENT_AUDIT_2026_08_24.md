# Operational Dashboard Family Alignment Audit — 2026-08-24

## Result

PASS. The **Kubernetes Operations Dashboard** and **Object Storage Operations Dashboard** now use one KAORI operational-dashboard grammar and are the paired reference for future operational dashboards.

## Canonical composition

Both dashboards preserve the same sequence:

1. canonical Page Hero;
2. Operational Signal Overview with active scope, committed-snapshot time context, scope selector, and KPI grid;
3. the same four workspace tabs: **Operations Overview**, **Capacity & Demand**, **Signals & Actions**, and **Reporting**;
4. peer analysis using the shared `peer_content_grid` pattern;
5. evidence before interpretation and action;
6. section-owned loading and failure states.

The domain changes the evidence noun only: Kubernetes uses clusters/nodes/workloads while Object Storage uses systems/buckets/storage signals. The layout grammar does not change.

## Visual standardization

- Palette remains semantic and token-driven: `bg-surface-*`, `text-content-*`, `border-outline-*`, KAORI Violet identity tokens, and semantic status tokens.
- No dashboard-owned hex colors or dark-mode overrides are introduced.
- Major section titles remain owned by `operational_section_card`; peer and nested content use the canonical `text-base`, `text-sm`, and `text-xs` hierarchy.
- Both dashboards use `space-y-5` between major blocks and the same `rounded-xl` / `rounded-lg` hierarchy from shared components.
- Integrated tabs remain horizontally scrollable on narrow screens and keyboard accessible.

## Wording review

Verbose operational copy was shortened without changing evidence meaning. The dashboard favors one-sentence descriptions and short action verbs. Snapshot wording remains explicit and does not imply request-time provider access.

The generic **What This Summary Means** callout is removed from both Alert Response and Reporting guidance. The section title, description, status, evidence, and controlled flow already establish interpretation; repeating a generic explanation added visual weight without adding a new decision boundary.

Both Reporting guidance panels now place a compact **Reporting Control** information block immediately before the controlled flow. It clarifies scope and committed-evidence review without introducing another tip-style surface.

## Structural code review

Object Storage now mirrors the Kubernetes composition more directly through dedicated `_hero.html`, `_signal_overview.html`, and `_content.html` partial ownership. This avoids an oversized content template and makes the family contract obvious for future maintainers.

Existing shared components remain authoritative:

- `page_hero.html`
- `workspace_tabs.html`
- `operational_section_card.html`
- `peer_content_grid.html`
- `operational_metric_card.html`
- `operational_flow_steps.html`
- `operational_callout.html`
- canonical table, label, progress, empty, and loading components.

No new page-local visual component system was created.

## Data and operational boundary

Both dashboards remain read-only projections over committed database rows and worker snapshots. Kubernetes does not query Kubernetes API, Metrics Source, or Alertmanager at request time. Object Storage does not query its provider API or metrics provider at request time. Missing evidence remains explicit.

## Accessibility and interaction

Both dashboards retain URL-backed active tabs, `role=tablist/tab/tabpanel`, keyboard Arrow/Home/End behavior, scope selector labels, canonical focus states, responsive stacking, and section-owned HTMX loading.

## Future operational dashboards

Server/VM, HCI, Network, Backup, and other future operational dashboards must begin from this family pattern: the **same four workspace tabs**, Hero geometry, Operational Signal Overview placement, peer-grid rhythm, typography, color semantics, and committed-snapshot boundary. Domain-specific content may change; the shell must not fork into a new page-local dashboard style.
