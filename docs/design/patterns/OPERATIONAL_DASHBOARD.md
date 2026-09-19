# KAORI Operational Dashboard Pattern v1.5

**Status:** Locked reference pattern  
**Reference implementations:** Kubernetes Operations Dashboard and Object Storage Operations Dashboard  
**Canonical pages:** `app/templates/kubernetes/dashboard/partials/_content.html` and `app/templates/storage/object_storage/dashboard/partials/_content.html`

## Purpose

This pattern defines a read-only, snapshot-backed operational dashboard that combines scope, operational indicators, peer workspace tabs, tables, charts, and visible action guidance without creating page-local styling systems.

Kubernetes Operations Dashboard and Object Storage Operations Dashboard are the paired references. Domain content may change nouns and evidence values; Hero grammar, Operational Signal Overview placement, workspace tabs, peer-grid composition, data boundaries, interaction, accessibility, wording discipline, and style ownership remain shared.

## Operational Dashboard Hero Profile

Both paired dashboards must render through:

```jinja
page_hero.operational_dashboard(...)
```

The profile owns the complete Hero shell and context structure. Dashboard templates provide semantic values only and must not locally compose `shell_classes()`, `layout_classes()`, `content_classes()`, or `context_panel_classes()`.

Normal Dashboard metadata has exactly three semantic slots in this order:

1. inventory evidence;
2. metrics/analytics evidence;
3. alert evidence.

The right-side Dashboard context has exactly two semantic metrics in this order:

1. **Active Scope** — selected cluster/system or aggregate scope;
2. **Data Authority** — request-time evidence authority. Current paired dashboards use `Committed Snapshots`.

The profile action role is **operational source/readiness management**. Domain labels and routes may vary, but the action role does not. A generic inventory/navigation shortcut must not replace the readiness/source-management action.

Blocked Dashboard state retains the same profile geometry, changes the right-side context to readiness semantics, and does not fabricate normal operational evidence.

### Dashboard Readiness blocked contract

A blocked Operational Dashboard uses the same canonical right-side grammar in every domain:

1. context eyebrow `Dashboard Readiness`;
2. domain setup title, for example `Cluster Setup Required` or `Object Storage Setup Required`;
3. semantic `Blocked` status badge;
4. **Active Scope** as the first context metric;
5. **Data Authority** as the second context metric;
6. one concise information strip that states the next setup requirement.

The blocked Dashboard body immediately below the Hero uses the shared section blocked-state grammar: setup title/status, concise explanation, ordered setup steps when useful, and one permission-aware primary action. Kubernetes and Object Storage must not maintain separate local blocker geometry.

## Canonical composition

```text
Operational Dashboard Hero Profile
Operational Signal Overview
├── Scope selector
├── Snapshot update context
└── Operational KPI grid
Tab Style 1 — Integrated Workspace Tabs
├── Operations Overview
│   ├── Domain health table
│   └── Inventory / Data Freshness peer grid
├── Capacity & Demand
│   ├── Capacity / Forecast peer grid
│   └── Top Consumers
├── Signals & Actions
│   ├── Alerts / Response Guidance peer grid
│   └── Recommended Actions
└── Reporting
    └── Reporting Summary / Guidance peer grid
```

Kubernetes maps the health table to clusters and Object Storage maps it to registered systems. Future dashboards may substitute a domain-specific health register, but page hierarchy and peer relationships stay the same.

## Visual contract

- Use `components/page_hero.html` and the `operational_dashboard(...)` profile renderer for the Hero.
- Use `components/operational_metric_card.html` for the KPI grid.
- Use `components/workspace_tabs.html` with semantic key `integrated-workspace`.
- Use `components/operational_section_card.html` for repeated section shells.
- Use `components/peer_content_grid.html` for equal-height peer content.
- Use `components/operational_flow_steps.html` for visible action and response flows.
- Use `components/operational_callout.html` for interpretation/supporting guidance.
- Use `components/forecast_projection_chart.html` for historical/projected utilization.
- Use canonical table, label, empty-state, loading, and pagination components.
- Do not introduce page-local Hero/card/tab/label/pagination/chart geometry, arbitrary typography, or dark-mode colors.
- The dashboard remains neutral-first in dark mode. Violet is limited to identity, active state, focus, links, progress, and primary actions.

## Information hierarchy

```text
Identity → Scope → Indicators → Peer analysis → Interpretation → Action
```

The Hero establishes identity, evidence boundary, and readiness. Operational Signal Overview owns scope and high-level indicators. Tabs are peer perspectives of the same dashboard scope. Evidence precedes interpretation and action.

## Data-boundary contract

- Web requests read committed database rows and worker snapshots only.
- Web requests must not query Kubernetes API, Metrics Source, Alertmanager, Object Storage API, or another provider directly.
- Missing, pending, failed, stale, or expired snapshots are explicit.
- All-scope modes may summarize inventory and committed evidence.
- Detailed capacity, forecast, consumer, and alert signals may require a selected domain scope.
- UI copy uses `snapshot`, `committed`, `available`, or `detailed signals`; it must not imply request-time provider queries.
- Reporting guidance remains format-neutral.
- Reporting Control states selected scope, committed-evidence boundary, and review requirement before the controlled reporting flow.

## Request authorization contract

- Dashboard page and lazy-section views require `dashboard.view` where applicable.
- Authorization completes before readiness checks or dashboard data access.
- Unknown section identifiers return `404` before readiness checks/data reads.
- Unauthorized requests must not probe readiness, repositories, or onboarding state.

## Request and loading contract

- First request renders shell, Hero, scope, inventory aggregate, reporting summary, and local placeholders.
- Heavy sections load independently through HTMX.
- Hidden tab sections load when revealed.
- Loading and failures remain section-owned.
- Do not add a global dashboard loading overlay.
- One unavailable section must not prevent the rest of the dashboard from rendering.

## Tab interaction contract

Tab Style 1 remains URL-backed and accessible:

- active state is stored in `?tab=`;
- scope changes preserve active tab;
- invalid values resolve to `overview`;
- `role="tablist"`, `role="tab"`, and `role="tabpanel"` are required;
- only the active tab has `tabindex="0"`;
- Arrow Left/Right wrap; Home selects first; End selects last;
- keyboard selection moves focus and updates the URL.

## Responsive contract

- Tabs scroll horizontally on narrow screens.
- KPI cards progress from one to two to four columns.
- Peer content stacks on smaller screens and becomes equal-height peer content at desktop sizes.
- Tables retain canonical horizontal overflow behavior.
- Primary interactive targets remain at least 44 px high where required by the component contract.

## Operational wording

Use consistent evidence terminology such as `Cluster Signals Available`, `Select a Cluster for Detailed Signals`, `Alertmanager`, `approved output`, and `stored artifact`. Do not use wording that implies live request-time provider access.

## Dashboard family consistency

- Kubernetes and Object Storage share the same Hero profile, four workspace tabs, outer `space-y-5` rhythm, Operational Signal Overview placement, peer-grid proportions, and section-card hierarchy.
- Domain-specific wording changes nouns/evidence semantics only; it does not create a different visual grammar.
- Future Server/VM, HCI, network, backup, and other operational dashboards begin from this pattern and the shared Hero profile.
- Reusable layout changes happen through shared components/canonical structure and family-level contract tests.

## Maintainability and performance contract

- Dashboard web code owns no provider clients or request-time provider access.
- Internal naming distinguishes selected database scope from actual live/provider state.
- Heavy analytical evidence loads through bounded/lazy sections.
- Empty snapshot messaging describes committed worker evidence rather than provider request results.

## Layered release evidence

The reference Dashboard keeps evidence for Static Quality, Contract, Unit, Functional, Integration, Security Regression, Rendering/UI Contract, and End-to-End Smoke. `scripts/verify_feature_test_coverage.py` protects committed modules and `scripts/quality_gate.sh` executes the project gates.

## Change control

A dashboard-family change must update, in the same work item:

1. shared component/canonical dashboard implementation;
2. this document;
3. domain README when data/request boundaries change;
4. `scripts/verify_operational_dashboard_standard.py` when its protected contract changes;
5. dashboard/Hero contract tests;
6. the latest alignment audit for material decisions.

Run the operational dashboard verifier and its focused dashboard characterization/contract suites before UAT.
