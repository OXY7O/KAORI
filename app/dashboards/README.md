# KAORI Dashboard Architecture

This package is the permanent domain boundary for asset-specific dashboards.
Welcome is intentionally outside this package because it is a platform-wide landing workspace.

## Canonical ownership

| Workspace | Python package | Template root | Blueprint | Canonical URL |
|---|---|---|---|---|
| Welcome | `app/welcome` | `templates/welcome` | `welcome` | `/welcome` |
| Kubernetes Dashboard | `app/dashboards/kubernetes` | `templates/dashboards/kubernetes` | `kubernetes_dashboard` | `/dashboards/kubernetes` |
| Server Dashboard | `app/dashboards/server` | `templates/dashboards/server` | reserved | reserved |
| HCI Dashboard | `app/dashboards/hci` | `templates/dashboards/hci` | reserved | reserved |

Dashboard routing is canonical-only. Welcome is owned by `welcome.index`, while Kubernetes Dashboard is owned by `kubernetes_dashboard.index` and `kubernetes_dashboard.section`. Retired `dashboard.*` endpoints and alternate redirects must not be restored.

## Mandatory domain rules

- Never place Server or HCI queries, schemas, routes, or templates inside the Kubernetes package.
- Cross-domain helpers may be added only under `app/dashboards/common` after at least two dashboard domains require the same stable contract.
- Do not create speculative generic abstractions merely because Server and HCI are planned.
- Every domain owns its own route, schema, orchestration service, section builders, and templates.
- Shared visual components belong under `templates/dashboards/common`; data-bound section templates stay inside their asset domain.
- Domain permissions must remain explicit. Kubernetes currently uses `dashboard.view`; Server and HCI must receive separate permission keys before their routes are enabled.

## Kubernetes service structure

`app/dashboards/kubernetes/service.py` is only the overview orchestrator. Section-specific integration and transformation logic is separated into:

- `sections/cluster_health.py`
- `sections/capacity.py`
- `sections/alerts.py`
- `sections/top_consumers.py`
- `sections/forecast.py`
- `sections/reporting.py`
- `sections/freshness.py`
- `sections/recommendations.py`

Database loading and defensive queries are isolated in `repository.py`. Reusable Kubernetes dashboard formatting and normalization helpers are isolated in `utils.py`.

A new dashboard section must not be implemented directly in the orchestration function. Add a section builder module, return a typed schema object, and let the orchestrator compose it.

## Retired path guardrail

`app/dashboard`, `templates/dashboard`, and `app/dashboards/routes.py` are retired paths. New imports, endpoints, and template references must use the canonical packages above.
