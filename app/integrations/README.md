# Integrations domain

The Integrations domain owns cross-platform integration discovery, compatibility presentation, and canonical navigation. Integration-specific validation remains in each driver domain, such as `app/prometheus` and `app/alertmanager`.

## Page structure

- `Overview` presents ecosystem posture, category coverage, the supported/planned catalog, and configured targets.
- `Prometheus` presents Prometheus-specific runtime, query profile, metric schema, and readiness information.
- `Alertmanager` presents Alertmanager API v2 and capability readiness.

Planned catalog entries are presentation-only and must not expose routes or configuration actions until their driver, model, validation contract, and permissions exist.

## Navigation ownership

Dashboard navigation is grouped under the `Dashboards` submenu so future Kubernetes, Server, and HCI dashboards can be added without promoting each dashboard to a separate top-level link.

Kubernetes Cluster Management displays only a compact integration summary and links into this domain. It does not own integration-specific configuration.

## Maintenance boundaries

- Keep compatibility profiles in `compatibility.py`.
- Keep deprecated API/metric mappings in `deprecations.py`.
- Keep safe presentation aggregation in `service.py`.
- Keep route handlers thin in `routes.py`.
- Never render credentials, bearer tokens, URL query strings, or raw validation payloads.

## Overview presentation builders

`service.py` owns the safe, read-only presentation context used by the Integrations landing page. The `_coverage()` and `_catalog()` helpers aggregate sanitized integration rows only; driver validation and persistence remain in the integration-specific domains. Planned catalog entries must not expose actions until their driver, model, permission, route, and compatibility contract exist.

Integration-specific configuration pages return to their canonical list pages (`integrations.prometheus` or `integrations.alertmanager`), not to Kubernetes Cluster Management.
