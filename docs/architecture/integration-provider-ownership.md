# Integration Provider Ownership

KAORI separates provider-neutral orchestration from presentation and backend-specific implementations.

## Metrics Source

```text
app/integrations/observability/metrics_source/application/                       web/forms/presentation and application-facing Metrics Source service
app/integrations/observability/metrics_source/          provider-neutral metrics adapter registry and backend implementations
app/models/metrics_source.py       provider-neutral persisted Metrics Source record
```

The public category is `metrics_source`. Concrete products are provider catalog entries, currently including Prometheus and Thanos Query.

The backend registry owns adapter dispatch. The current `prometheus_http` adapter contains Prometheus HTTP/PromQL-specific transport/runtime validation. A future adapter can be added without changing consumer domains.

Public application operations include connection testing, runtime validation/health, generic query sessions, validation sessions, and binding validation. Consumers do not build provider-specific clients.

## Alertmanager

```text
app/integrations/observability/alert_source/providers/alertmanager/application/                  web/forms/presentation
app/integrations/observability/alert_source/providers/alertmanager/     provider transport/runtime/binding operations
```

## Dependency direction

- provider backend code may not import its web/domain package;
- provider-neutral binding orchestration may not import provider web/domain modules;
- service modules must not depend on WTForms when a provider-neutral input contract can be used;
- analytics/report/intelligence consumers depend on integration contracts, not concrete provider clients.

`scripts/verify_architecture_boundaries.py` enforces these boundaries. Metrics Source currently translates validated form state into `MetricsSourceConfigurationInput` before calling its service layer.

## Bounded Observability evidence projections

The Metrics Source and Alertmanager provider registries and consumer-binding
tables retain the standard SQL-backed `5 / 10 / 25 / 50` pagination contract.
They count the complete canonical fleet and page source/binding records **before**
hydrating visible operational evidence. A source-detail binding page computes
Effective Consumer Resolution only for its displayed bindings; the summary
counters remain full-fleet SQL aggregates, not page counts.

Observability Connection Coverage computes cross-asset status, filters, and
aggregate posture in SQL, then resolves provider and binding details for the
visible managed-asset page. The provider-neutral integration registry exposes
an optional `record_model` on each provider implementation solely for batched
read-model loading; adapter/provider ownership of runtime operations and
external configuration remains unchanged. A disabled or non-active canonical
source, a missing provider record, or an unvalidated consumer binding must
never be counted Ready just because a historical provider readiness value exists.

Prometheus HTTP core validation requires operation-appropriate successful API
envelopes, with a usable provider-neutral `vector(1)` result for query probes.
Empty discovery results are valid where the endpoint contract permits them.
Alertmanager API v2 must preserve genuine empty alert/silence responses while
failing closed on malformed individual records or missing status version identity.
Consumer payload correctness and provider readiness remain separately owned.
