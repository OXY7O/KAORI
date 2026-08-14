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

`app.inventory.kubernetes` owns Kubernetes collection, committed-generation
persistence, topology, and read models. `app.inventory.object_storage` owns
Object Storage collection, synchronization, committed snapshot presentation,
and inventory job integration.

Inventory represents committed current state. It does not own operational
metric history or forecasting.

Normalized Object Storage presentation uses **provider** terminology. Retired
`product_key`, `product_label`, `product` filter parameters, and duplicate
product/provider counters are not part of the canonical contract.

## Analytics boundary

`app.analytics.kubernetes` owns Kubernetes-specific analytics and its committed
`AnalyticsSnapshot` materialization model. `app.analytics.object_storage` owns
Object Storage analytics semantics. Only genuinely cross-domain contracts and
helpers may live in `app.analytics.shared`.

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
Qualified asset-provider + metrics-provider adapter
        ↓
Provider runtime
```

Canonical metric meaning belongs to KAORI. Query language, provider response
shape, retry semantics, and provider exceptions belong to the adapter.

The first qualified adapter is:

```text
MinIO + Prometheus → sources/minio_prometheus.py
```

The resolver is intentionally pair-qualified. A Prometheus binding alone does
not authorize MinIO PromQL for every Object Storage provider. A future provider
must register its own qualified adapter, for example:

```text
Ceph RGW + Prometheus   → ceph_prometheus.py
S3 provider + CloudWatch → s3_cloudwatch.py
Object Storage + OTel  → provider_otlp.py
```

Adding one of those adapters must not require changes to the Object Storage
Analytics service or presentation contract.

## Interactive failure policy

Interactive Analytics must fail fast when an operational metrics source is down.
The current MinIO + Prometheus adapter disables provider retries for interactive
queries. If the first query fails with a transport or authentication error, the
request-local evidence reader opens a source circuit and skips all remaining
metric reads for that page request.

Query-specific failures do not open the source circuit because unrelated metric
keys may remain valid. Background/materialization workloads may define a
separate retry policy.

This policy prevents one unreachable metrics endpoint from multiplying a single
page request into dozens of repeated network attempts.

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
- direct Prometheus dependencies in Object Storage Analytics service code;
- unqualified Object Storage metrics-source registration;
- retired Object Storage product/provider compatibility fields and filters;
- Prometheus-specific dependency wording in provider-neutral Analytics UI;
- loss of the Operations Center navigation distinction.

The verifier runs from both `scripts/quality_gate.sh` and
`scripts/verify_final_release.py`.
