# KAORI Operational Dashboard Architecture

This package owns **domain-neutral Operational Dashboard application contracts** and reserved standalone dashboard domains. Dashboard implementation remains capability/domain-first: a dashboard may live inside its owning capability package when that is the canonical domain boundary.

## Current consumers

| Operational Dashboard | Python owner | Template root | Blueprint / route | Permission |
|---|---|---|---|---|
| Kubernetes | `app/kubernetes/dashboard` | `templates/kubernetes/dashboard` | `kubernetes_dashboard` / `/dashboards/kubernetes` | `dashboard.view` |
| Object Storage | `app/storage/object_storage/dashboard` | `templates/storage/object_storage/dashboard` | `object_storage_dashboard` / `/dashboards/object-storage` | `dashboard.view` |
| Artifact Registry Overview | `app/artifact_registry` | `templates/artifact_registry` | `artifact_registry.overview` / `/artifact-registry/` | `artifact_registry.view` |
| Server | `app/dashboards/server` | `templates/dashboards/server` | reserved | dedicated permission required |
| HCI | `app/dashboards/hci` | `templates/dashboards/hci` | reserved | dedicated permission required |

Artifact Registry intentionally remains inside the Registry capability instead of being moved under `/dashboards`. Capability/domain ownership is primary; the Operational Dashboard pattern standardizes the operational presentation and request contract without flattening domain architecture.

## Shared application contract

`app/dashboards/common/operational.py` owns only stable domain-neutral mechanics proven across current consumers:

- canonical tabs: `overview → capacity → signals → reporting`;
- invalid-tab fallback to `overview`;
- dashboard page-size facade over the canonical `app/common/pagination.py` contract;
- HTMX request detection.

`app/common/pagination.py` remains the pagination authority. Operational Dashboard code must not define a second 5/10/25/50 parser or page-size taxonomy.

## Shared presentation contract

Canonical visual primitives live under `app/templates/components`, including:

- `states/_empty_state.html` with the dashed `panel` variant for section-local missing/unavailable/no-findings evidence;
- `operational_dashboard_workspace.html`;
- `operational_signal_overview.html`;
- `operational_evidence_tile.html`;
- `operational_alert_summary.html`;
- `operational_alert_response.html`;
- `operational_recommendation_cards.html`;
- `operational_section_card.html`;
- `operational_section_loading.html` for canonical KPI and bounded-section loading placeholders;
- `peer_content_grid.html`;
- `reporting_dashboard_workspace.html`.

`app/templates/dashboards/common` is not a second component library. New shared presentation primitives belong in `templates/components` when they are product-wide KAORI components. A missing setup or required scope is a prerequisite blocker; once scope exists, missing section evidence in Capacity & Demand or Signals & Actions uses the shared dashed empty-state panel rather than a blocked-state variant.

## Domain ownership rules

Every dashboard domain keeps explicit ownership of:

- Blueprint and URL;
- permission decorators;
- scope query names;
- onboarding/readiness behavior;
- section map and lazy-loading boundaries;
- schema/presentation projection;
- orchestration service and section builders;
- committed evidence queries;
- provider-specific semantics and actions.

Do not create a universal dashboard route factory, service base class, ORM repository, or provider abstraction only to reduce line count. Extract a shared application/data contract only after at least two real consumers demonstrate the same stable semantics.

## Section architecture

Kubernetes currently demonstrates the preferred decomposition for a growing operational domain: overview orchestration in `service.py`, section builders under `sections/`, typed presentation objects in `schema.py`, and database reads isolated from request presentation.

Every Operational Dashboard now follows **Fast Shell & Bounded Section Loading**:

```text
Fast Shell
→ bounded KPI projection
→ bounded visible/active section projection
→ committed KAORI state / materialized snapshots
```

The canonical invariant is **one HTTP request → one bounded presentation projection**. Initial requests render readiness/scope/active-tab/minimal context plus placeholders. KPI and tab sections load independently. A section endpoint must not rebuild the complete dashboard or project unrelated sections.

Loading presentation is also shared. Current and future consumers use `components/operational_section_loading.html` instead of page-local pulse markup:

- KPI placeholders use `section_loading.kpis(...)` and `hx-trigger="load"`;
- bounded tab/section placeholders use `section_loading.section(...)` and `hx-trigger="revealed"`;
- both replace their own container with `hx-target="this"` + `hx-swap="outerHTML"`;
- no global dashboard loading overlay is allowed.

Projection granularity stays domain-owned. A growing domain such as Kubernetes may split a canonical tab into finer bounded sub-projections when latency or failure isolation justifies it; another domain may keep one bounded projection per canonical tab. The visible loading grammar and request triggers do not fork.

Domain services remain explicit. This contract does not authorize a universal route factory, generic service base class, or shared ORM repository. Future Server/VM, HCI, Source Control/GitHub, Backup, Network, and other dashboard implementations must begin with this loading boundary rather than copying a monolithic builder.

## Request boundary

Operational Dashboard web requests read committed KAORI state. Provider engines remain authoritative, but provider APIs are not queried directly during ordinary dashboard rendering.

Permissions must resolve before authorization-sensitive readiness/data access. Unknown lazy-section identifiers return `404` before provider/readiness work.

## Retired paths

`app/dashboard`, `templates/dashboard`, and `app/dashboards/routes.py` are retired. Do not restore alternate generic dashboard endpoints.
