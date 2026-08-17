# Integration Provider Ownership

KAORI separates provider-neutral orchestration from presentation and backend-specific implementations.

## Metrics Source

```text
app/metrics/                       web/forms/presentation and application-facing Metrics Source service
app/integrations/metrics/          provider-neutral metrics adapter registry and backend implementations
app/models/metrics_source.py       provider-neutral persisted Metrics Source record
```

The public category is `metrics_source`. Concrete products are provider catalog entries, currently including Prometheus and Thanos Query.

The backend registry owns adapter dispatch. The current `prometheus_http` adapter contains Prometheus HTTP/PromQL-specific transport/runtime validation. A future adapter can be added without changing consumer domains.

Public application operations include connection testing, runtime validation/health, generic query sessions, validation sessions, and binding validation. Consumers do not build provider-specific clients.

## Alertmanager

```text
app/alertmanager/                  web/forms/presentation
app/integrations/alertmanager/     provider transport/runtime/binding operations
```

## Dependency direction

- provider backend code may not import its web/domain package;
- provider-neutral binding orchestration may not import provider web/domain modules;
- service modules must not depend on WTForms when a provider-neutral input contract can be used;
- analytics/report/intelligence consumers depend on integration contracts, not concrete provider clients.

`scripts/verify_architecture_boundaries.py` enforces these boundaries. Metrics Source currently translates validated form state into `MetricsSourceConfigurationInput` before calling its service layer.
