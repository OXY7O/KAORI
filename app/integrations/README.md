# Integrations domain

The Integrations domain owns cross-platform integration discovery, compatibility presentation, and canonical navigation. Integration-specific validation remains in each driver domain, such as `app/prometheus` and `app/alertmanager`.

## Page structure

- `Overview` presents ecosystem posture, category coverage, the supported/planned catalog, and configured targets.
- `Prometheus` presents endpoint identity, Prometheus source profile, PromQL profile, metric schema, retention, and Kubernetes Analytics readiness.
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
- supported filters are endpoint compatibility, cluster environment, and analytics readiness;
- pagination defaults to 5 rows and supports 5, 10, 25, and 50 rows;
- filter and pagination responses render only the inventory content partial;
- the full page owns the single table loading indicator;
- endpoint presentation must continue to use `safe_endpoint()` and must never render credentials or URL query parameters.

Filtering and pagination are presentation concerns in `app.integrations.service`. Prometheus connectivity, compatibility, PromQL validation, and credential handling remain owned by `app.prometheus`.

## Compatibility domain ownership

- Kubernetes compatibility validates Kubernetes version, API resources, and RBAC for Inventory, Operations, and Governance.
- Prometheus compatibility validates direct Prometheus or Thanos Query endpoint identity plus the Prometheus source/PromQL contract for Kubernetes Analytics.
- Alertmanager compatibility validates the direct Alertmanager runtime and API v2 capabilities for alert analytics and alert-management workflows.

Do not reuse a runtime-version field across products. In particular, a Thanos Query version is endpoint evidence for Thanos and never a detected Prometheus version.

## Alertmanager instance inventory

Alertmanager inventory is instance-first. One row represents one reusable
Alertmanager deployment, not one Kubernetes cluster. Connection configuration,
validation, detected version, readiness, and capabilities belong to the
instance. Asset consumption belongs to explicit bindings.

```text
AlertmanagerInstance
        ↓
AlertmanagerBinding(scope_type, scope_key, role, priority)
        ↓
Kubernetes / Server / HCI / Storage consumer
```

The list defaults to 5 items and supports 5, 10, 25, and 50. It may filter by
query, deployment type, and readiness. Cluster Management may link to a bound
instance, but must not recreate cluster-owned Alertmanager configuration.
Legacy cluster URLs are compatibility redirects only.

## Integration Runtime Framework

Shared runtime contracts live in `app/integrations/runtime/`. Provider packages implement an adapter while the framework owns the common runtime lifecycle and UI vocabulary.

- `contracts.py` defines provider-neutral runtime state, diagnostics, health factors, and capability snapshots.
- `scoring.py` converts weighted health factors into a stable `healthy`, `degraded`, or `unhealthy` state.
- `refresh.py` orchestrates provider refresh without importing provider internals.
- `presentation.py` converts runtime state into a template-safe view model.

Provider-specific endpoint, authentication, API probing, compatibility mapping, and capability discovery remain inside the provider package. The first adapter is `app/alertmanager/runtime_adapter.py`.

Readiness and health are intentionally separate: readiness describes whether configuration and compatibility permit use; health describes the latest observed runtime condition.


## Canonical architecture references

All new provider integrations must follow the shared standards in:

- `docs/architecture/integration-lifecycle.md`;
- `docs/architecture/integration-runtime.md`;
- `docs/architecture/provider-adapter.md`;
- `docs/architecture/capability-framework.md`;
- `docs/architecture/compatibility-framework.md`; and
- `docs/architecture/consumer-pattern.md`.

The simplified operational rule is:

```text
Register provider once
        ↓
Validate and discover capabilities
        ↓
Bind it to an asset scope
        ↓
Resolver selects the healthiest eligible source
        ↓
Consumer returns canonical data to analytics
```

Primary, secondary, and fallback are preference levels only. They do not mean
that every source is processed at the same time. A secondary source is selected
when it is healthier or when the primary source lacks a capability required by
the requested operation.
