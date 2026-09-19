# Provider Persistence Authority

Canonical `IntegrationInstance` rows own cross-provider identity, lifecycle, bindings, runtime observations, and shared orchestration metadata. Provider-native tables own only configuration/evidence that cannot be represented generically.

## Metrics Source

`MetricsSource` stores provider-neutral connection state plus extensibility axes:

- `provider_key` — concrete product/provider implementation;
- `adapter_key` — registered backend protocol adapter;
- `query_language` — declared query language;
- endpoint/authentication settings;
- compatibility/readiness evidence.

It does not create separate tables per metrics product. Prometheus, Thanos Query, and future metrics providers share `metrics_sources`.

## Alertmanager and asset providers

Alertmanager and managed asset providers keep their provider-specific configuration in their owning models. Cross-domain relationships are canonical bindings and must not be duplicated as product-specific foreign-key mapping tables.

## Rule

A new metrics product must not require a new global model/table merely because its product name differs. A new schema boundary is justified only when the data semantics are genuinely different from the Metrics Source contract.
