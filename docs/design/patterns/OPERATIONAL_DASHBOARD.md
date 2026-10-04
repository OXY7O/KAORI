# KAORI Operational Dashboard Pattern v1.7

**Status:** Locked reference pattern  
**Reference implementations:** Kubernetes Operations Dashboard and Object Storage Operations Dashboard  
**Canonical framework:** `app/templates/components/operational_dashboard_workspace.html`  
**Reference consumers:** `app/templates/kubernetes/dashboard/partials/_content.html` and `app/templates/storage/object_storage/dashboard/partials/_content.html`  
**Additional conforming consumer:** `Artifact Registry → Overview` through `app/templates/artifact_registry/partials/_overview_content.html`

## Purpose

This pattern defines a read-only, snapshot-backed operational dashboard that combines scope, operational indicators, peer workspace tabs, tables, charts, and visible action guidance without creating page-local styling systems.

Kubernetes Operations Dashboard and Object Storage Operations Dashboard are the paired references. The shared `operational_dashboard_workspace.html` component owns workspace tabs, URL-backed active state, keyboard navigation, panel ARIA/visibility geometry, and the canonical four-tab information architecture. Domain implementations change data, nouns, evidence, actions, and section content only.

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

The profile action role is **operational source/readiness management**. Kubernetes Dashboard uses `Open Cluster Integrations` routed to `integrations.kubernetes`; `Add Cluster` is not an approved Dashboard Hero action label. Other domains may use an equivalent source-management label and route, but the action role does not change. A generic inventory/navigation shortcut must not replace the readiness/source-management action.

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
- Use `components/operational_metric_card.html` for KPI cards and `components/operational_signal_overview.html` for the shared scope/status/update/selector shell around them.
- Consume `components/operational_dashboard_workspace.html` for canonical four-tab navigation, URL state, keyboard behavior, and panel geometry. It delegates tab rendering to `components/workspace_tabs.html` with semantic key `integrated-workspace`.
- Use `components/operational_section_card.html` for repeated section shells and `components/operational_evidence_tile.html` for the repeated Inventory Snapshot / Data Freshness evidence-tile geometry.
- Use `components/peer_content_grid.html` for equal-height peer content.
- Use `components/operational_flow_steps.html` for capacity and other directional action flows where arrow-connected progression remains meaningful.
- Use `components/operational_alert_summary.html` for the bounded AlertCase summary/insight presentation.
- Use `components/operational_alert_response.html` for **Alert Interpretation & Response**; it delegates the six-step flow to `components/numbered_governance_steps.html` and accepts domain-specific response wording plus optional handoff content.
- Use `components/operational_recommendation_cards.html` for central Intelligence recommendation cards.
- Reporting uses the shared compact `components/reporting_dashboard_workspace.html` presentation so dashboard consumers cannot drift.
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

### Controlled dashboard flow contract

`Alert Interpretation & Response` keeps the shared six-step sequence `Validate → Triage → Investigate → Respond → Verify → Record`, rendered through `components/numbered_governance_steps.html`.

`Governed Reporting Flow` remains `Validate → Select → Create → Generate → Schedule → Retain`, but its geometry is owned by `components/reporting_dashboard_workspace.html`. Domain wrappers provide scope/evidence wording only. Capacity remains on `components/operational_flow_steps.html` where directional action progression is the intended semantic.

### Alerts Summary preview contract

`Alerts Summary` is a bounded dashboard preview, not an alert registry. Kubernetes, Object Storage, and Artifact Registry consume `components/operational_alert_summary.html`, which renders at most **five** projected recent AlertCase records while severity totals continue to represent the complete selected scope. Domain services remain responsible for bounded committed projections, and the full case set remains available through **Open Alert Intelligence**.

### Recent Report Activity preview contract

`Recent Report Activity` is a bounded dashboard preview of generated report artifacts. Kubernetes and Object Storage query and render at most **four** latest generated report records. The Reports workspace remains authoritative for full report history, filtering, scheduling, and retained-artifact review; dashboard summaries must not add local pagination.

## Data-boundary contract

- Web requests read committed database rows and worker snapshots only.
- Web requests must not query Kubernetes API, Metrics Source, Alertmanager, Object Storage API, or another provider directly.
- Missing, pending, failed, stale, or expired snapshots are explicit.
- All-scope modes may summarize inventory and committed evidence.
- Detailed capacity, forecast, consumer, and alert signals may require a selected domain scope.
- UI copy uses `snapshot`, `committed`, `available`, or `detailed signals`; it must not imply request-time provider queries.
- Reporting guidance remains format-neutral.
- Reporting guardrails state selected scope, committed-evidence authority, and review requirement before the governed reporting flow.

## Application contract

All Operational Dashboard consumers use `app/dashboards/common/operational.py` for the stable request-level contract:

- canonical tab order is `overview → capacity → signals → reporting`;
- invalid or missing tabs normalize to `overview`;
- dashboard page-size normalization delegates to `app/common/pagination.py`, whose canonical options are `5 / 10 / 25 / 50` with default `5`;
- HTMX partial detection uses one shared predicate rather than domain-local header truthiness.

The common module is intentionally narrow. Blueprints, permission decorators, readiness checks, scope parameters, section maps, service/schema composition, provider evidence, and mutation boundaries remain domain-owned. A universal route factory or service base class is not part of the Operational Dashboard standard.

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

- Kubernetes and Object Storage consume the same `components/operational_dashboard_workspace.html` framework and therefore share the four workspace tabs, active-tab state, URL synchronization, keyboard navigation, panel semantics, outer `space-y-5` rhythm, and section hierarchy.
- Domain-specific templates own Hero values/readiness, Operational Signal semantics/KPI content, section data, and domain-specific copy/actions. Shared Signal Overview, evidence-tile, alert-summary, response-wrapper, recommendation-card, and reporting geometry remains component-owned.
- Artifact Registry Overview is a conforming operational-domain consumer: it uses the same Hero profile, Operational Signal Overview, four workspace tabs, provider scope, committed-snapshot boundary, and shared section/peer-grid components while keeping detailed Inventory, Security, Runtime Usage, Governance, and Analytics in their owning workspaces.
- Its Operations Overview follows the same reference composition: Registry Provider Health Summary → Inventory Snapshot / Data Freshness peer grid. Registry-specific evidence changes the nouns and source planes, not the layout grammar.
- Artifact Registry keeps the four Data Freshness identities stable across aggregate and provider scopes: `Inventory Snapshot`, `Metrics Snapshot`, `Security Snapshot`, and `Analytics Snapshot`. Scope changes values and detail, not the evidence-plane name.
- Artifact Registry security summaries must distinguish absent scan evidence from a clean scan result; missing evidence is `N/A` / not collected, never an inferred zero-finding posture.
- Artifact Registry **Capacity & Demand** uses the same semantic composition as the references: `Capacity Snapshot → Forecast & Growth Risk → Top Consumers`. Registry-specific evidence comes from committed inventory and Registry Analytics snapshots; unsupported quota or forecast evidence remains explicit rather than inferred.
- Artifact Registry **Signals & Actions** uses `Alerts Summary → Alert Interpretation & Response → Recommended Actions`. Active cases come from KAORI Alert Intelligence; recommendation cards come from central Intelligence and the Registry rule catalog. The dashboard does not define local recommendation rules.
- Artifact Registry **Reporting** uses the shared `reporting_dashboard_workspace.summary(...) + guidance(...)` contract and canonical Reports state. Report definitions, generation, schedules, retained artifacts, storage, and audit remain owned by Reports.
- A retained committed Registry inventory snapshot remains available even when the latest refresh attempt fails. Freshness is derived from `last_committed_at`; a stale retained snapshot is presented as stale/attention, never as `Not Collected`.
- Future capability dashboards—including Registry/Harbor and Source Control/GitHub, plus Server/VM, HCI, network, backup, and other operational domains—must start by consuming `operational_dashboard_workspace.html`; copying Alpine tab state or local panel geometry is prohibited.
- Reusable layout changes happen in shared components first, then all dashboard consumers inherit the change. Family-level contract tests and `scripts/verify_operational_dashboard_standard.py` protect this invariant.

## New dashboard implementation contract

A new operational dashboard is a **content implementation of the shared framework**, not a new page design.

Required sequence:

1. render the domain Hero with `page_hero.operational_dashboard(...)`;
2. render the domain onboarding/readiness blocker when required;
3. enter `operational_dashboard_workspace.controller(...)`;
4. render the domain Operational Signal Overview through `operational_signal_overview.render(...)`;
5. render `operational_dashboard_workspace.navigation(...)`;
6. provide content for the canonical `overview`, `capacity`, `signals`, and `reporting` panels through `operational_dashboard_workspace.panel(...)`;
7. use shared section-card, peer-grid, table, label, loading, chart, and reporting components rather than page-local geometry.

A future framework-level redesign updates the shared components and this standard once; individual dashboard domains should not fork the layout.

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
