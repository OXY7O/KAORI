# Prometheus Domain Boundary

`app/prometheus` owns KAORI's Prometheus registration workflow, instance
workspace, scope binding policy, source resolution, presentation, Activity
Audit integration, and HTTP routes.

The provider implementation is exclusively owned by
`app/integrations/prometheus/`. Transport, query profiles, capability
declarations, validation evidence, compatibility profiles, and the runtime
adapter must not be duplicated in this domain package.

Domain services call the Integration Registry for provider operations.
Persistence uses `PrometheusInstance`, `IntegrationInstance`, and
`IntegrationBinding` only. No alternate Python import path remains for retired provider packages, and no
bookmark redirects remain for replaced routes.

## Prometheus Manage UI and lifecycle contract

Prometheus and Prometheus-compatible query endpoints are registered as reusable provider instances. Each instance has one canonical manage workspace containing
Configuration, Validation & Capabilities, Runtime & History, and Scope &
Resolution. Provider-local configuration pages and cluster-scoped routes are not
part of the active contract.

### Instance deletion

Instance deletion is a governed database lifecycle action and has no live
Prometheus or Thanos dependency. Every provider-neutral scope binding must be removed first, including disabled bindings. Active provider jobs also block the
operation. KAORI repeats these checks in the service boundary before deleting
the provider record and its canonical integration identity atomically.

Historical runtime observations and Activity Audit records remain available.
The Delete Instance control is shown only in the contextual Scope & Resolution
workspace, adjacent to its binding and job blockers.

## Provider invocation

The domain facade preserves route, analytics, and report call sites, but all
provider runtime and binding operations are dispatched through the Integration
Registry. Provider compatibility, query validation, binding mutation, and scope
probe logic must not be reimplemented in this package.

## Analytics query runtime contract

Kubernetes Analytics uses `PrometheusConsumer` as the canonical query boundary.
The consumer creates clients lazily, reuses one HTTP session within a dataset,
and records only bounded query fingerprints and aggregate telemetry; raw PromQL
is not persisted in snapshot metadata.

An Integration Runtime observation such as `unhealthy` or `disconnected` is
advisory for a later analytics worker attempt when the binding, selector,
readiness, and instant/range query transport remain eligible. The real dataset
query is the authoritative runtime probe. Analytics-specific code must not add
an extra `vector(1)` preflight query. Generic provider validation may still use
a lightweight query as part of Integration Runtime evidence.

Transient connection and HTTP 429/500/502/503/504 failures receive bounded
retries. Heavy queries are serialized by selected provider instance in the
analytics materialization layer so clusters sharing one Prometheus or Thanos
Query endpoint do not bypass the same concurrency boundary.
