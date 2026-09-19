# Domain Namespace and Metrics Source Boundary

## Decision

KAORI organizes Inventory and Analytics by **capability → asset domain**. Domain
ownership must be explicit in source code, templates, static modules, tests, and
release contracts.

Canonical ownership is:

```text
app/inventory/
├── kubernetes/
└── object_storage/

app/analytics/
├── shared/
├── kubernetes/
└── object_storage/
```

The capability roots are composition boundaries, not compatibility namespaces.
A domain extraction is a direct cutover: update every importer, task name,
template path, test path, documentation reference, and verifier in the same
change. Retired packages must be deleted rather than kept as forwarding modules,
re-exports, aliases, wrappers, or shims.

Public URLs and Flask blueprint names are independent API contracts. They may
remain stable when their semantics have not changed; stable public routing does
not justify retaining a retired Python namespace.

## Inventory boundary

`app.kubernetes.inventory` owns Kubernetes collection, committed-generation
persistence, topology, and read models. `app.storage.object_storage.inventory` owns
Object Storage collection, synchronization, committed snapshot presentation,
and inventory job integration.

Inventory represents committed current state. It does not own operational
metric history or forecasting.

Normalized Object Storage presentation uses **provider** terminology. Retired
`product_key`, `product_label`, `product` filter parameters, and duplicate
product/provider counters are not part of the canonical contract.

## Analytics boundary

`app.kubernetes.analytics` owns Kubernetes-specific analytics and its committed
`AnalyticsSnapshot` materialization model. `app.storage.object_storage.analytics` owns
Object Storage analytics semantics. Only genuinely cross-domain contracts and
helpers may live in `app.common.analytics`.

A module is not shared merely because several domains could theoretically use
it. Shared code must be provider-neutral and asset-domain-neutral in both
semantics and dependencies.

## Object Storage operational metrics

Object Storage Analytics consumes the provider-neutral `MetricsSource` contract:

```text
Object Storage Analytics service
        ↓
Canonical metric keys
        ↓
MetricsSource
        ↓
Object Storage source resolver
        ↓
Qualified asset-provider metrics adapter
        ↓
Provider runtime
```

Canonical metric meaning belongs to KAORI. Query language, provider response
shape, retry semantics, and provider exceptions belong to the adapter.

The first qualified asset adapter is:

```text
MinIO → sources/minio_metrics.py
```

The Object Storage resolver is asset-provider qualified, while `MetricsConsumer`
resolves the bound Metrics Source independently through the global
`metrics_source` contract. A Metrics Source binding alone does not authorize a
MinIO metric profile for every Object Storage provider. A future Object Storage
provider registers its own asset adapter/profile, while a future metrics backend
is registered behind the Metrics Source adapter registry. Those two extension
axes are independent.

Adding either extension must not require changes to the Object Storage Analytics
service or presentation contract.

## Metrics readiness and validation ownership

Metrics contract discovery belongs to the **source-owned binding validation**
workflow. Object Storage Analytics must not issue discovery probes while
rendering a page.

```text
Metrics Source Full Validation
        ↓
object-storage-metrics-v1 consumer profile
        ↓
provider-qualified validation adapter
        ↓
MinIO v2 metric family + label + query audit
        ↓
IntegrationBinding.validation_evidence
        ↓
MetricsSource.readiness
        ↓
Object Storage Analytics readiness presentation
```

The generic Object Storage consumer profile does not mean every Object Storage
provider shares MinIO metrics. Validation adapters are pair-qualified in the
same way as runtime metrics-source adapters. A future Object Storage asset profile must register its own validator rather than extending a MinIO conditional.

Readiness evidence and runtime health are separate facts. Persisted readiness
records the last proven metric contract. Runtime query failures describe current
reachability. A network outage must not erase the last validated contract, and
a successful historic validation must not hide a current transport failure.

The canonical Object Storage consumer profile is `object-storage-metrics-v1`.
A binding that still carries a retired provider-specific consumer profile is
reported as **Consumer Validation Stale** and is not treated as eligible. Upgrade
migrations reset that binding to the canonical profile and force revalidation;
no runtime compatibility alias is retained. Provider Full Validation remains
provider-core only; consumer bindings are revalidated explicitly from the source
workspace. The `integration-validation` worker must run the same deployed code
version as the web application so terminal job state, binding evidence, and UI
polling converge on the same lifecycle contract.

Readiness tiers are explicit:

- **required** — minimum canonical metrics for usable Object Storage Analytics;
- **recommended** — enriches health, performance, and consumer analysis;
- **optional** — absence is supported and does not block the required contract.

## Interactive failure policy

Interactive Analytics must fail fast when an operational metrics source is down.
The current MinIO asset adapter requests the resolved Metrics Source with interactive retries disabled. If the first query fails with a transport or authentication error, the
request-local evidence reader opens a source circuit and skips all remaining
metric reads for that page request.

Query-specific failures do not open the source circuit because unrelated metric
keys may remain valid. Background/materialization workloads may define a
separate retry policy.

This policy prevents one unreachable metrics endpoint from multiplying a single
page request into dozens of repeated network attempts.

## Object Storage forecast materialization

Long-range Object Storage forecast history is worker-owned rather than
interactive-request owned:

```text
JobPolicy: object_storage.forecast.materialize
        ↓
forecasting queue
        ↓
provider-neutral MetricsSource (background mode)
        ↓
7d / 30d / 90d history
        ↓
ObjectStorageForecastSnapshot
        ↓
Forecast UI + Overview 30d posture
```

The worker and Kubernetes Forecast share the forecasting workload class and
queue, but not a persistence model or asset-domain service. Object Storage uses
its own artifact because Kubernetes `AnalyticsSnapshot` is cluster-scoped. This
is direct ownership, not a wrapper around the Kubernetes model. Snapshot status
distinguishes current, stale, expired, pending, and failed refresh attempts, and
the last usable payload remains readable within its configured stale-grace
window.

## Integration binding boundary

`IntegrationBinding` remains the only provider-to-asset persistence contract.
The generic `create_source_binding()` application service accepts an explicit
`SourceBindingSpec`. Domain-specific compatibility wrappers and result aliases
are not retained. Kubernetes routes construct the canonical asset specification
directly, just as future asset domains must.

## Navigation naming

`PLATFORM OPERATIONS` remains the sidebar category. Its primary workspace is
named **Operations Center** so category and workspace labels are not duplicated.
Internal package ownership remains `app/platform_operations/`; UI wording does
not require a package rename.

## Enforcement

`scripts/verify_domain_namespace_architecture.py` blocks:

- retired Inventory and Analytics namespaces;
- imports from retired namespaces;
- domain implementation files leaking back into capability roots;
- direct metrics-backend dependencies in Object Storage Analytics service code;
- unqualified Object Storage metrics-source registration;
- retired Object Storage product/provider compatibility fields and filters;
- product-specific Metrics Source wording in provider-neutral Analytics UI;
- loss of the Operations Center navigation distinction.

The verifier runs from both `scripts/quality_gate.sh` and
`scripts/verify_final_release.py`.
