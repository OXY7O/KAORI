# Metrics Source Domain Boundary

`app/metrics_sources` owns KAORI's provider-neutral Metrics Source web/domain workflow:
provider selection, registration, instance workspace, source-to-asset binding
presentation, lifecycle actions, Activity Audit integration, and HTTP routes.

Backend implementation belongs exclusively to `app/integrations/observability/metrics_source/`.
Transport, provider adapters, query sessions, query profiles, capability
declarations, validation evidence, compatibility profiles, and runtime adapter
logic must not be duplicated in this package.

Persistence uses `MetricsSource`, `IntegrationInstance`, and
`IntegrationBinding`. `IntegrationInstance.provider_type` remains
`metrics_source`; product identity is stored as `MetricsSource.provider_key`.
No alternate import path or retired bookmark redirect is part of the active
contract.

## Registration and manage workspace

The provider selector is registry-driven. A provider definition supplies its
label, endpoint guidance, backend adapter, query language, default horizon,
version-detection mode, compatibility options, and support presentation.
Registration then uses the same canonical route/workspace for every Metrics
Source provider.

Each instance has Configuration, Validation & Capabilities, Runtime & History,
and Scope & Resolution. Consumer asset bindings are source-owned; Kubernetes,
Object Storage, and future asset-owner pages display them read-only.

## Provider invocation

Domain services call the Integration Registry for every provider operation.
They must not import or branch on concrete backend clients. The stable query
boundary is the generic Metrics Source operation set and `MetricsQuerySession`.

## Provider readiness and consumer validation

Provider readiness is consumer-neutral. It proves endpoint identity,
compatibility, and adapter-owned execution capabilities. Asset-specific metrics,
selectors, and evidence belong to `IntegrationBinding` and are validated using
the binding profile selected by `adapter_key + asset_type`.

This allows one provider to serve multiple asset families and allows one asset
to bind multiple providers without changing provider readiness or introducing
pair-specific schemas.

## Analytics query runtime contract

Kubernetes and Object Storage Analytics consume metrics through
`MetricsConsumer`. The consumer resolves a source by eligibility and routing
policy, builds a generic reusable query session, and records only bounded query
fingerprints and aggregate telemetry. Product client classes and raw endpoint
credentials never cross into the analytics domains.

Runtime observations are advisory for a later worker attempt when the binding
and required execution capabilities remain eligible. The actual dataset query
is the authoritative runtime probe. Transient connection and retryable HTTP
failures receive bounded retries according to the global Metrics Source
analytics configuration.

## Instance deletion

Instance deletion is a governed database lifecycle action. Every source binding
must be removed first, including disabled bindings. Active provider jobs also
block deletion. KAORI repeats these checks in the service boundary before
deleting the provider record and its canonical integration identity atomically.
Historical runtime observations and Activity Audit records remain available.
