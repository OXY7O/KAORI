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

`service.py` owns the safe, read-only presentation context used by the Integrations landing page. Provider catalog, coverage, and runtime rows are built from persisted provider-native records. Driver validation, live endpoint access, resolver selection, and persistence remain in the integration-specific domains.

The overview must not derive Prometheus or Alertmanager existence from Kubernetes cluster bindings. An unbound provider instance remains a registered provider instance and must appear in its provider count and runtime inventory.

Planned catalog entries must not expose actions until their driver, model, permission, route, and compatibility contract exist. Integration-specific configuration pages return to their canonical list pages (`integrations.prometheus` or `integrations.alertmanager`), not to Kubernetes Cluster Management.

## Overview page boundary

The Integrations Overview is a resilient domain landing page. It contains the shared hero posture, Provider Catalog, persisted Runtime Overview, and category coverage. It does not perform live provider calls or replace provider-specific configuration and evidence workspaces.

Zero registered integrations is a supported state. The page must still render its hero, catalog, runtime empty state, and zero-value coverage without requiring a cluster, binding, runtime observation, validation result, or external endpoint.

Runtime navigation uses an explicit mapping for Kubernetes, Prometheus, and Alertmanager. Do not pass provider-owned endpoint names and argument dictionaries into `url_for()` from a template. Unknown or incomplete runtime rows render no navigation action instead of raising `BuildError`.

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

## Runtime persistence and monitoring

Every manual or scheduled runtime refresh must append one
`IntegrationRuntimeObservation`. The shared record stores provider identity,
readiness, health score, diagnostics, compatibility, and the capability
snapshot observed during that run. Provider configuration remains in the
provider-owned model; historical runtime evidence remains in the shared model.

Runtime persistence uses rolling per-instance retention. The shared repository
keeps the latest **100 observations for each provider and provider-native instance
ID** and deletes older rows in the same transaction as the new observation. This
also prunes legacy rows that do not yet carry a canonical integration-instance
foreign key.

Celery Beat invokes `app.integrations.runtime.tasks.refresh_integration_runtime` as a dispatcher only. The dispatcher performs no provider I/O; it fans out one lightweight runtime-health job per provider instance to the dedicated `integration-validation` queue. One slow or unreachable source therefore cannot block the remaining integration portfolio. The default interval is five minutes and can be controlled with `INTEGRATION_RUNTIME_MONITORING_*` environment variables.

## Validation execution boundary

KAORI separates fast registration probes from durable operational validation:

```text
Test Connection
→ synchronous Flask request
→ lightweight reachability, authentication, TLS, and basic API proof

Runtime Health Refresh
→ dedicated Celery validation worker
→ lightweight endpoint health and latency evidence
→ preserves the latest full capability evidence

Full Capability Validation
→ dedicated Celery validation worker
→ provider compatibility, capabilities, query/API contracts, retention, and readiness

Scope Binding Validation
→ dedicated Celery validation worker
→ validates the binding selector against the selected reusable source
```

Manual actions return immediately after a job is queued. The provider workspace polls task status through HTMX and renders the completed worker result without reloading the page. Queue, already-running, enqueue-failure, completion, and validation-failure events are recorded in Activity Audit Log; user-triggered completion feedback is also surfaced as the persistent KAORI toast. Redis owns short-lived job locks and polling metadata, while Celery's result backend owns task state.

The dedicated worker queue is configured through `INTEGRATION_VALIDATION_CELERY_QUEUE` and is intentionally separate from the `inventory` queue. Full validation and runtime refresh cannot overlap for the same provider instance. Scheduled refreshes are fan-out tasks and never execute full Prometheus or Alertmanager capability discovery every five minutes.

## Runtime history presentation

Provider detail pages may render shared runtime history through the provider-neutral
history repository and presentation mapper. The standard view defaults to 5 rows
with 5, 10, 25, and 50 options and uses HTMX for pagination and refresh. Pagination
must keep the result summary and page-size selector together on the left, with page
navigation grouped on the right.

Each observation may expose:

- health and score at the observation time;
- manual or scheduled trigger source;
- latency and readiness;
- recovery, degradation, and unhealthy transition markers; and
- capability additions or removals compared with the immediately older snapshot.

The history UI must not calculate provider health or capability support. It only
presents retained append-only runtime evidence already produced by the adapter and
shared runtime framework.

## Shared runtime overview

The Integrations Overview includes a shared runtime table for every provider that implements the Integration Runtime contract. The table uses the latest retained observation for health and score, while provider configuration remains authoritative for readiness and capability remediation. Prometheus/Thanos and Alertmanager are the first providers included.

The overview is intentionally diagnostic rather than a second configuration surface. It supports provider, health, and readiness filters; defaults to 5 rows with 5/10/25/50 choices; and links to the provider detail page where configuration and remediation are performed.

## Consumer facade standard

Provider configuration, validation, runtime monitoring, and analytics reads are
separate responsibilities. Asset analytics must not instantiate provider HTTP
clients directly. It consumes provider data through a canonical consumer facade:

```text
asset analytics
    -> provider consumer facade
    -> readiness and capability gate
    -> provider client
    -> normalized result and diagnostics
```

The shared contract lives in `app/integrations/consumer/`. Every consumer result
identifies the selected provider source, required capabilities, safe diagnostics,
and whether the operation completed. Low-level error detail is retained for
controlled toast and Activity Audit usage; it must not be rendered directly in
inline analytics blockers.

Prometheus-compatible reads are owned by `app/prometheus/consumer.py`.
`PrometheusService` remains a compatibility facade for existing analytics while
internally delegating runtime reads to `PrometheusConsumer`. Validation and
configuration workflows continue to use the provider service and client because
they intentionally test capabilities rather than consume validated data.

### Presentation-ready integration view models

Integration templates do not format raw datetimes or derive display labels.
Services/presenters must supply fields such as `observed_at_display`,
`latency_display`, and `capability_attention_display`. This keeps full-page and
HTMX rendering consistent with the authenticated user's timezone, locale, date
format, and time format.
