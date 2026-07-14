# KAORI Welcome and Infrastructure Dashboard Architecture

This document defines the product boundary, access contract, current implementation, and target folder structure for KAORI Welcome and infrastructure dashboards.

Use this document as the baseline when changing:

- the authenticated landing experience;
- dashboard routes and blueprints;
- dashboard templates and HTMX partials;
- dashboard data aggregation;
- RBAC visibility and access;
- Kubernetes, Server, or HCI dashboard navigation; and
- shared dashboard UI components.

## 1. Platform Positioning

KAORI is a unified infrastructure operations platform for:

- observability;
- analytics;
- governance; and
- intelligent recommendations.

The primary infrastructure asset domains are:

1. Kubernetes;
2. Server; and
3. HCI.

A domain may be implemented before the others, but platform-level wording must preserve the unified KAORI identity. Do not position KAORI as only a Kubernetes product.

Domain-specific pages must clearly identify their asset scope. For example, the current operational dashboard is a **Kubernetes Dashboard**, not a generic KAORI dashboard.

## 2. Page and Domain Boundaries

### 2.1 Welcome

Welcome is KAORI's universal authenticated landing page.

Functional contract:

- It is the first page shown after a successful login.
- Every authenticated user can open it regardless of assigned role.
- It summarizes KAORI at platform level.
- It exposes role-aware shortcut cards to workspaces the user can access.
- It must remain useful when no Kubernetes cluster is registered.
- It must not depend on live Prometheus, Alertmanager, Kubernetes, Server, or HCI queries merely to render.
- Restricted shortcuts are omitted instead of displayed as disabled or `No access` cards.
- Account and personal settings remain the baseline destination available to every authenticated user.

Current route contract:

- URL: `/welcome`
- Endpoint: `dashboard.welcome`
- Access gate: `login_required`
- Feature permission: none

Current presentation:

- `app/templates/dashboard/welcome.html`

Welcome must not become an infrastructure operations dashboard. Its purpose is orientation and navigation, not detailed asset monitoring.

### 2.2 Kubernetes Dashboard

The current `K8s Dashboard` is the operational summary dashboard for registered Kubernetes clusters.

Functional contract:

- It summarizes registered Kubernetes clusters.
- It supports `All Clusters` and `Selected Cluster` scopes.
- It provides a compact view of resource, health, capacity, alert, inventory, reporting, freshness, and recommendation signals.
- It does not replace the detailed Kubernetes Inventory or Kubernetes Analytics pages.
- It acts as a command-center summary and drill-down starting point.
- It may aggregate data from inventory snapshots, Prometheus, Alertmanager, Reports, and the Intelligence engine.

Current route contract:

- URL: `/`
- Endpoint: `dashboard.index`
- Access gate: `dashboard.view`
- Lazy section URL: `/dashboard/section/<section>`
- Lazy section endpoint: `dashboard.section`

The route name is currently generic for backward compatibility, but the page itself is Kubernetes-specific.

### 2.3 Future Server Dashboard

The Server Dashboard will summarize registered or discovered server assets. It must have its own:

- route namespace;
- permission boundary;
- schema and data service;
- templates and partials;
- asset selector and scope behavior; and
- domain-specific data source contract.

Do not add Server-specific conditions, cards, models, or query branches directly into the existing Kubernetes dashboard service.

### 2.4 Future HCI Dashboard

The HCI Dashboard will summarize HCI clusters, hosts, virtual machines, storage, and other supported HCI assets. It must have its own:

- route namespace;
- permission boundary;
- schema and data service;
- templates and partials;
- asset selector and scope behavior; and
- HCI integration contract.

Do not add HCI-specific conditions, cards, models, or API calls directly into the existing Kubernetes dashboard service.

## 3. Kubernetes Dashboard Scope Semantics

### 3.1 All Clusters

`All Clusters` is primarily an aggregate view from persisted KAORI inventory snapshots.

Rules:

- Inventory totals may aggregate all registered clusters from the database.
- Reporting totals may aggregate persisted report records.
- Live Prometheus and Alertmanager blocks must not imply a single coherent cross-cluster live query when no global metrics layer is configured.
- Detailed live resource blocks require a selected cluster.
- Cluster Health may show per-cluster live signals because each row has an explicit cluster identity.
- Any unavailable live value must be shown as unavailable, not estimated from unrelated data.

This preserves the agreed KAORI guardrail:

> All-cluster inventory is DB-backed; detailed live signals require a selected cluster.

A future Thanos or other global-query implementation may extend this contract, but the UI must explicitly identify that source and query scope.

### 3.2 Selected Cluster

A selected cluster may combine:

- persisted Kubernetes inventory snapshots;
- Prometheus metrics for usage, capacity, consumers, and forecast inputs;
- Alertmanager or Prometheus alert signals;
- generated report and schedule context; and
- catalog-backed findings from the Intelligence engine.

Every section must preserve source status and unavailable states. Missing live data must not be silently replaced with stale or fabricated values.

## 4. Dashboard Information Boundary

The Kubernetes Dashboard provides a summary. Detailed workflows belong to their owning domains.

| Dashboard information | Detailed owner |
|---|---|
| Registered cluster health and identity | Kubernetes Cluster |
| Nodes, namespaces, workloads, pods, services, ingress, and storage | Kubernetes Inventory |
| Utilization, capacity, storage, workload, forecast, consumers, alerts, and anomalies | Kubernetes Analytics |
| Prioritized findings and recommended actions | Intelligence |
| Generated reports, templates, schedules, and storage | Reports |
| Integration configuration and source readiness | Settings, Prometheus, and Alertmanager |

Dashboard cards should link or guide the user to the owning detailed page instead of duplicating the entire workflow.

## 5. Current Implementation Structure

The current package is:

```text
app/dashboard/
├── __init__.py
├── routes.py
├── schema.py
├── service.py
└── README.md

app/templates/dashboard/
├── welcome.html
├── index.html
└── partials/
    ├── _content.html
    ├── _hero.html
    ├── _loading_bar.html
    ├── _section_loading.html
    ├── _kpi_cards.html
    ├── _cluster_health.html
    ├── _capacity_snapshot.html
    ├── _alerts_summary.html
    ├── _top_consumers.html
    ├── _forecast_risk.html
    ├── _inventory_summary.html
    ├── _reporting_summary.html
    ├── _data_freshness.html
    └── _recommended_actions.html
```

### 5.1 Current file responsibilities

`app/dashboard/routes.py`

- owns the universal Welcome route;
- owns Kubernetes Dashboard full-page and lazy-section routes;
- maps lazy section identifiers to templates; and
- applies the cluster onboarding guardrail.

`app/dashboard/schema.py`

- defines the view models used by the Kubernetes Dashboard;
- must remain presentation-oriented and must not contain infrastructure queries.

`app/dashboard/service.py`

- aggregates Kubernetes inventory, metrics, alerts, reports, and recommendations;
- builds the `DashboardOverview` view model; and
- contains source normalization and section builder logic.

`app/templates/dashboard/welcome.html`

- renders the platform-wide Welcome page only.

`app/templates/dashboard/index.html`

- is the Kubernetes Dashboard page shell.

`app/templates/dashboard/partials/_content.html`

- defines Kubernetes Dashboard section composition and HTMX lazy-loading behavior.

`app/templates/dashboard/partials/*.html`

- render Kubernetes-specific dashboard sections.

## 6. Current Structural Assessment

The current implementation is functional, but the package name `dashboard` now contains two different architectural scopes:

1. platform-wide Welcome; and
2. Kubernetes-specific operational dashboard.

This is acceptable while Kubernetes is the only implemented infrastructure dashboard, but it is not the final maintainable structure for multiple asset domains.

The strongest maintenance signals are:

- `app/dashboard/service.py` is already a large Kubernetes aggregation module;
- `dashboard.index` is generic in name while its data and UI are Kubernetes-specific;
- `app/templates/dashboard/partials` contains only Kubernetes components but has a generic path;
- future Server or HCI conditions inside the same service would produce cross-domain coupling; and
- one generic blueprint would make permissions, URLs, onboarding rules, and lazy-section identifiers increasingly ambiguous.

### Decision

Do **not** perform a route or folder migration only for cosmetic consistency while Kubernetes is the sole dashboard. Existing behavior and endpoint compatibility should remain stable.

A structural refactor becomes mandatory **before implementation of the first Server Dashboard or HCI Dashboard feature**.

## 7. Target Multi-Domain Structure

The recommended target is:

```text
app/
├── welcome/
│   ├── __init__.py
│   ├── routes.py
│   └── service.py                 # optional: shortcut resolution only
│
└── dashboards/
    ├── __init__.py
    ├── common/
    │   ├── schema.py              # only genuinely shared view primitives
    │   └── helpers.py             # source-neutral helpers only
    │
    ├── kubernetes/
    │   ├── __init__.py
    │   ├── routes.py
    │   ├── schema.py
    │   ├── service.py
    │   └── sections/
    │       ├── cluster_health.py
    │       ├── capacity.py
    │       ├── alerts.py
    │       ├── consumers.py
    │       ├── forecast.py
    │       ├── inventory.py
    │       ├── reporting.py
    │       ├── freshness.py
    │       └── recommendations.py
    │
    ├── server/
    │   ├── __init__.py
    │   ├── routes.py
    │   ├── schema.py
    │   ├── service.py
    │   └── sections/
    │
    └── hci/
        ├── __init__.py
        ├── routes.py
        ├── schema.py
        ├── service.py
        └── sections/
```

Recommended template structure:

```text
app/templates/
├── welcome/
│   └── index.html
│
└── dashboards/
    ├── common/
    │   ├── _loading_bar.html
    │   └── _section_loading.html
    │
    ├── kubernetes/
    │   ├── index.html
    │   └── partials/
    │       ├── _content.html
    │       ├── _hero.html
    │       └── ...
    │
    ├── server/
    │   ├── index.html
    │   └── partials/
    │
    └── hci/
        ├── index.html
        └── partials/
```

Recommended endpoint and URL names:

| Workspace | Endpoint | URL |
|---|---|---|
| Welcome | `welcome.index` | `/welcome` |
| Kubernetes Dashboard | `kubernetes_dashboard.index` | `/dashboards/kubernetes` |
| Server Dashboard | `server_dashboard.index` | `/dashboards/server` |
| HCI Dashboard | `hci_dashboard.index` | `/dashboards/hci` |

The exact URL may be adjusted during implementation, but endpoint names must remain domain-explicit.

## 8. Safe Refactor Sequence

When the multi-domain refactor is started, apply it in phases.

### Phase 1 — Introduce explicit packages

- Create `app/welcome` and `app/dashboards/kubernetes`.
- Move code without changing behavior or data semantics.
- Move Kubernetes templates to `templates/dashboards/kubernetes`.
- Keep shared UI partials limited to components that are truly domain-neutral.

### Phase 2 — Preserve compatibility

- Update login redirect, sidebar, navbar, quick actions, tests, and documentation.
- Keep a temporary compatibility redirect from the previous Kubernetes Dashboard URL if needed.
- Do not keep two independent implementations of the same dashboard.

### Phase 3 — Split the Kubernetes service

- Keep one orchestration function that returns the dashboard overview.
- Move section-specific aggregation into `sections/` modules.
- Keep Prometheus, Alertmanager, inventory, report, and recommendation failures isolated per section.
- Avoid circular imports between dashboard sections and detailed domains.

### Phase 4 — Add Server or HCI

- Add the new domain only after the explicit dashboard package structure exists.
- Reuse design primitives, not Kubernetes data contracts.
- Give the new domain its own permission, onboarding state, selector behavior, and source readiness model.

## 9. Template Maintenance Rules

- `index.html` is a page shell, not a data-processing template.
- `_content.html` controls section order and HTMX composition.
- Each major dashboard block has one owning partial.
- Section partials receive a prepared view model and must not perform database or integration queries.
- Shared partials may contain visual primitives only; they must not assume Kubernetes field names.
- Do not copy an entire Kubernetes partial into Server or HCI and hide irrelevant fields with conditions.
- Use domain-specific hero text and selector labels.
- Preserve the agreed KAORI visual language: blue-to-cyan hero, consistent rounded cards, restrained borders, aligned labels, and unified loading behavior.

## 10. Service and Data Rules

- Routes parse request scope and delegate aggregation to a service.
- Services return typed view models from `schema.py`.
- Data-source exceptions must be converted into explicit source status and user-safe messages.
- A failure in one live integration must not prevent database-backed dashboard sections from rendering.
- `All Clusters` and `Selected Cluster` semantics must be implemented in services, not inferred ad hoc inside templates.
- The Intelligence engine remains the source of recommendation findings; do not recreate recommendation logic inside dashboard templates or section builders.
- Inventory is snapshot context. Prometheus and Alertmanager are live-signal sources for selected Kubernetes clusters.

## 11. RBAC Rules

- Welcome is available to every authenticated user.
- Kubernetes Dashboard access is controlled by `dashboard.view` in the current implementation.
- Future Server and HCI dashboards must receive domain-explicit permissions instead of reusing `dashboard.view` indefinitely.
- Sidebar visibility and route enforcement must use the same permission contract.
- A visible shortcut must always resolve to a route the user can open.

Suggested future permission names:

```text
dashboards.kubernetes.view
dashboards.server.view
dashboards.hci.view
```

Permission migration must include compatibility handling for roles currently using `dashboard.view`.

## 12. Naming Rules

Use explicit user-facing names:

- `Welcome`
- `Kubernetes Dashboard` or `K8s Dashboard`
- `Server Dashboard`
- `HCI Dashboard`

Use `Dashboard` without an asset prefix only for architecture-level discussion covering every dashboard domain.

Avoid ambiguous implementation names such as:

- `dashboard_service` for a domain-specific service;
- `dashboard_data` without an asset type;
- `generic_dashboard` containing domain branches; or
- one template with `if kubernetes`, `if server`, and `if hci` blocks.

## 13. Current No-Refactor Decision

For the current review:

- no route is changed;
- no blueprint is renamed;
- no Python module is moved;
- no template is moved;
- no RBAC permission is changed; and
- no UI behavior is changed.

Only this architecture document is updated.

The current Kubernetes Dashboard remains valid for the existing MVP. The documented package refactor must be scheduled before Server Dashboard or HCI Dashboard development begins.
