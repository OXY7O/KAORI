# KAORI Dashboard Architecture

This package is the permanent domain boundary for asset-specific dashboards.
Welcome is intentionally outside this package because it is a platform-wide landing workspace.

## Canonical ownership

| Workspace | Python package | Template root | Blueprint | Canonical URL |
|---|---|---|---|---|
| Welcome | `app/welcome` | `templates/welcome` | `welcome` | `/` and `/welcome` |
| Kubernetes Dashboard | `app/dashboards/kubernetes` | `templates/dashboards/kubernetes` | `kubernetes_dashboard` | `/dashboards/kubernetes` |
| Server Dashboard | `app/dashboards/server` | `templates/dashboards/server` | reserved | reserved |
| HCI Dashboard | `app/dashboards/hci` | `templates/dashboards/hci` | reserved | reserved |

The application now uses canonical routes only. The removed `dashboard` compatibility blueprint, `app/dashboard` package, and `templates/dashboard` tree must not be recreated. Internal links, redirects, tests, and extensions must use `welcome.*` or the relevant asset-dashboard blueprint directly.

## Mandatory domain rules

- Never place Server or HCI queries, schemas, routes, or templates inside the Kubernetes package.
- Cross-domain helpers may be added only under `app/dashboards/common` after at least two dashboard domains require the same stable contract.
- Do not create speculative generic abstractions merely because Server and HCI are planned.
- Every domain owns its own route, schema, orchestration service, section builders, and templates.
- Shared visual components belong under `templates/dashboards/common`; data-bound section templates stay inside their asset domain.
- Domain permissions must remain explicit. Kubernetes currently uses `dashboard.view`; Server and HCI must receive separate permission keys before their routes are enabled.
- Welcome is the universal authenticated landing page and must remain outside asset-dashboard permissions.

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

## Removed legacy surface

The following locations and endpoints are retired and must not be referenced:

```text
app/dashboard/
app/templates/dashboard/
app/dashboards/routes.py
dashboard.index
dashboard.section
dashboard.welcome
/dashboard/section/<section>
/dashboard/welcome
```

Use these canonical surfaces instead:

```text
welcome.index                       -> / or /welcome
kubernetes_dashboard.index          -> /dashboards/kubernetes
kubernetes_dashboard.section        -> /dashboards/kubernetes/section/<section>
```
