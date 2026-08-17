# KAORI Operational Dashboard Pattern v1.3

**Status:** Locked reference pattern
**Reference implementation:** Kubernetes Operations Dashboard
**Canonical page:** `app/templates/dashboards/kubernetes/partials/_content.html`

## Purpose

This pattern defines a read-only, snapshot-backed operational dashboard that combines scope, operational indicators, peer workspace tabs, tables, charts, and visible action guidance without creating page-local styling systems.

The Kubernetes Operations Dashboard is the visual and technical reference for future KAORI operational dashboards. New dashboards may change domain content, but they must preserve the composition, data-boundary, interaction, accessibility, and style-ownership rules in this document.

## Canonical composition

```text
Canonical Hero
Operational Signal Overview
├── Scope selector
├── Snapshot update context
└── Operational KPI grid
Tab Style 1 — Integrated Workspace Tabs
├── Operations Overview
│   ├── Cluster Health table
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

## Visual contract

- Use `components/page_hero.html` for the page Hero. The Kubernetes reference uses the canonical **Context Icon Box** in the Hero right-side context header; do not invent a fourth Hero accessory type.
- Use `components/operational_metric_card.html` for the KPI grid.
- Use `components/workspace_tabs.html` with semantic key `integrated-workspace`.
- Use `components/operational_section_card.html` for repeated section shells.
- Use `components/peer_content_grid.html` for equal-height peer content.
- Use `components/operational_flow_steps.html` for visible action and response flows.
- Use `components/operational_callout.html` for interpretation and supporting guidance.
- Use `components/forecast_projection_chart.html` for historical and projected utilization.
- Use canonical table, label, empty-state, loading, and pagination components.
- Do not introduce page-local card shells, tab geometry, label geometry, pagination, chart SVGs, arbitrary typography, or dark-mode colors.
- The dashboard remains neutral-first in dark mode. Violet is limited to identity, active state, focus, links, progress, and primary actions.

## Information hierarchy

The page follows this sequence:

```text
Identity → Scope → Indicators → Peer analysis → Interpretation → Action
```

The Hero establishes identity and readiness. The Operational Signal Overview owns scope and high-level indicators. Tabs represent peer perspectives of the same dashboard scope. Each section presents evidence before guidance or action.

## Data-boundary contract

- Web requests read committed database rows and worker snapshots only.
- Web requests must not query Kubernetes API, Metrics Source, Alertmanager, Object Storage API, or another provider directly.
- Missing, pending, failed, stale, or expired snapshots are rendered explicitly.
- All-cluster mode may summarize inventory and per-cluster evidence.
- Detailed capacity, forecast, consumer, and alert signals require a selected cluster.
- UI copy must use `snapshot`, `committed`, `available`, or `detailed signals`; it must not imply that the page performs live provider queries.
- Reporting guidance must remain format-neutral because Analytics supports PDF/CSV and Inventory supports XLSX/CSV.

## Cluster setup blocker

The Kubernetes Operations Dashboard is the canonical visual reference for cluster setup blocking. Its Hero right panel is implemented through `components/cluster/_hero_blocked_context.html` and is shared by Kubernetes Inventory, Operations, and Governance. Blocked pages preserve Hero geometry, show readiness rather than normal posture evidence, and place the registration CTA in the onboarding banner below the Hero.

## Request authorization contract

- Dashboard page and lazy-section views require `dashboard.view`.
- Authorization must complete before clusterless onboarding, dependency blockers, or dashboard data access.
- A protected lazy section must not return an authorization-sensitive response from Blueprint `before_request`; clusterless rendering belongs inside the decorated view.
- Unknown section identifiers return `404` before cluster readiness checks or data reads.
- Unauthorized requests must not probe cluster readiness, query dashboard repositories, or render onboarding state.

## Request and loading contract

- The first request renders the shell, Hero, scope, inventory aggregate, reporting summary, and local placeholders.
- Heavy sections load independently through `get_dashboard_section()` and HTMX.
- Hidden tab sections load when revealed.
- Initial async sections use local skeletons.
- Tables with pagination or filtering own their loading bar.
- Do not add a global dashboard loading overlay.
- An unavailable section must not prevent the rest of the dashboard from rendering.

## Tab interaction contract

Tab Style 1 is URL-backed and accessible:

- active state is stored in `?tab=`;
- scope changes preserve the active tab;
- invalid values resolve to `overview`;
- `role="tablist"`, `role="tab"`, and `role="tabpanel"` are required;
- only the active tab has `tabindex="0"`;
- Arrow Left/Right wrap through tabs;
- Home selects the first tab;
- End selects the last tab;
- keyboard selection moves focus and updates the URL.

## Responsive contract

- Tabs scroll horizontally on narrow screens.
- KPI cards progress from one to two to four columns.
- Peer content stacks on smaller screens and becomes equal-height 6/6 or 7/5 content at desktop sizes.
- Tables retain canonical horizontal overflow behavior.
- Controls remain at least 44 px high where they act as primary interactive targets.

## Operational wording

Use these terms consistently:

- `Cluster Signals Available`
- `Select a Cluster for Detailed Signals`
- `Alertmanager`
- `approved output`
- `stored artifact`

Do not use:

- `Live Signals Enabled`
- `Select a Cluster for Live Signals`
- `AlertManager`
- generic reporting guidance that assumes every artifact is PDF

## Maintainability and performance contract

- Dashboard web code owns no provider clients, compatibility catch-all arguments, orphan public exports, or unused presentation fields.
- Internal naming must distinguish selected database scope from actual live/provider state.
- The overview shell does not read analytics snapshots; heavy evidence loads through lazy sections.
- Cluster Health paginates before inventory and committed-snapshot reads, so work is bounded to the visible page (`5/10/25/50`) rather than the complete cluster fleet.
- Empty snapshot messaging must describe committed worker evidence; wording such as `the metrics provider returned ...` is prohibited in the web presentation because it implies a direct request-time provider call.

## Layered release evidence

The reference Dashboard must keep permanent evidence for Static Quality, Contract, Unit, Functional, Integration, Security Regression, Rendering/UI Contract, and End-to-End Smoke. `scripts/verify_feature_test_coverage.py` protects the committed modules, while `scripts/quality_gate.sh` executes the same gates locally and in CI.

## Change control

The reference dashboard may evolve only when the change improves a reusable KAORI pattern. A visual change must update, in the same commit:

1. shared component or canonical dashboard implementation;
2. this document;
3. `app/dashboards/kubernetes/README.md` when the data or request boundary changes;
4. `scripts/verify_operational_dashboard_standard.py`;
5. dashboard contract tests;
6. the latest alignment audit when the decision is material.
7. behavioral characterization when authorization, request ordering, or failure isolation changes.

Run:

```bash
python3 scripts/verify_operational_dashboard_standard.py
python3 -m pytest -q tests/dashboards/test_kubernetes_dashboard_characterization.py
python3 -m pytest -q tests/dashboards/test_kubernetes_dashboard_snapshot_flow.py
python3 -m pytest -q tests/contracts/kubernetes/test_operations_dashboard_styling_guide_contract.py
```
