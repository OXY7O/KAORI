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

## Overview page boundary

The Integrations Overview is a domain landing page, not a duplicate target inventory. It contains the shared hero posture, category coverage, and integration catalog only. Per-target runtime version, compatibility, readiness, and configuration details remain on the dedicated Prometheus and Alertmanager pages. This prevents the overview from becoming a second operational table as additional integrations are introduced.

The Overview hero follows the same structural pattern as Kubernetes Inventory: icon and context badge, title and description, posture pills, and a right-side posture card. New integration landing pages should reuse this hierarchy instead of introducing a separate hero style.

## Prometheus Inventory presentation

The Prometheus list follows the shared Inventory interaction pattern:

- filters submit through HTMX without a separate Run button;
- supported filters are readiness status, cluster environment, and matched compatibility profile;
- pagination defaults to 5 rows and supports 5, 10, 25, and 50 rows;
- filter and pagination responses render only the inventory content partial;
- the full page owns the single table loading indicator;
- endpoint presentation must continue to use `safe_endpoint()` and must never render credentials or URL query parameters.

Filtering and pagination are presentation concerns in `app.integrations.service`. Prometheus connectivity, compatibility, PromQL validation, and credential handling remain owned by `app.prometheus`.
