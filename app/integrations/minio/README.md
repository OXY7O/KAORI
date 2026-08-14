# MinIO Integration

MinIO is the first `Storage → Object Storage` provider registered with the KAORI Integration kernel.

The provider owns the S3 API plane and one provider-neutral `object_storage_system` asset through the MinIO connection record. That owner relationship is not a consumer binding. Prometheus and Alertmanager remain independent Observability providers and may bind to the asset for metrics and alerts. No direct MinIO → Prometheus/Alertmanager foreign key, MinIO self-binding, or product-specific binding table is allowed.

Compatibility is product-specific and range-aware. The current qualified MinIO profile is `minio-release-2024-08-03`, with `RELEASE.2024-08-03T04-33-23Z` as both the minimum and maximum qualified release. AStor is a separate product family and does not inherit the MinIO range until its own profile is qualified.

## Provider workspace standard

MinIO uses the same KAORI provider interaction model as Kubernetes, Prometheus,
and Alertmanager:

```text
MinIO Integrations
  → Integration Overview
  → Integration Coverage / Connection Registry
  → Register Connection
  → Connection Configuration
  → Test Connection
  → Validation & Capabilities
  → Runtime & History
  → Inventory & Lifecycle
```

The visual shell, registration terminology, Hero hierarchy, tab structure,
readiness semantics, and empty/populated registry states are shared. Only
MinIO-specific technical fields and consumer contracts differ.

Registration `Test Connection` is intentionally narrower than Core Validation. It verifies the submitted S3 API endpoint, SigV4 credentials, and bucket-discovery permission (`s3:ListAllMyBuckets`). Product identity and the declared MinIO release remain Core Validation evidence. KAORI accepts MinIO identity evidence from `x-minio-deployment-id`, the server header, or `/minio/health/live`; this avoids false negatives when a reverse proxy strips MinIO-specific response headers.

## Validation boundary

MinIO follows the canonical provider lifecycle:

```text
MinIO Connection
  → minio-release-2024-08-03
  → provider-owned S3/API capabilities
  → Provider Core Validation
  → Ready

ObjectStorageSystem
  ├── Prometheus binding
  │     → object-storage-metrics-v1
  │     → provider-qualified MinIO Metrics v2 validator
  │     → Binding Validation
  └── Alertmanager binding
        → object-storage-alerts-v1
        → Binding Validation
```

MinIO API readiness must not depend on Prometheus metric presence, Alertmanager alert presence, or inventory freshness. Conversely, metrics and alert readiness belong to their Prometheus/Alertmanager-to-`object_storage_system` consumer bindings and must not mutate provider readiness.

Inventory collection is a separate canonical Job Execution. `Full Validation` proves MinIO identity, compatibility, S3 access, and provider capability contracts; `Runtime Refresh` performs only lightweight endpoint health observation; `Object Storage Inventory Sync` collects and atomically commits system/bucket snapshots on the `inventory` queue. The job is enabled by default on the same 60-minute policy cadence as Kubernetes Inventory Sync and can be run manually from Jobs & Executions → Job Configuration.

A future S3-compatible provider reuses the same asset/binding model with its own
compatibility profile and provider-qualified observability adapters.

## Asset-owner lifecycle parity

MinIO follows the same managed-asset ownership pattern as Kubernetes. The MinIO
connection owns one canonical `object_storage_system` asset; Prometheus and
Alertmanager are reusable sources that may bind to that asset but are never deleted
with it. The provider detail therefore exposes the same operator lifecycle boundaries:

```text
Configuration
  → Configure Connection
Validation & Capabilities
Runtime & History
  → Refresh Runtime
Inventory & Lifecycle
  → committed Object Storage Inventory Sync snapshot (read-only)
  → bound Prometheus/Alertmanager source inventory (read-only)
  → governed Delete Connection
```

Deleting the MinIO asset owner removes the MinIO provider identity, the managed
object-storage asset, and every binding targeting that asset. Shared Prometheus and
Alertmanager connections remain registered. Active KAORI jobs referencing either the
MinIO provider or the object-storage asset block deletion until they complete. Runtime
observation history and Activity Audit records remain retained evidence.

Connection-sensitive configuration changes preserve the canonical object-storage asset
and its consumer bindings but reset MinIO provider readiness until Core Validation is
run again. Consumer binding creation, validation, update, and removal are performed from
the Prometheus or Alertmanager source workspace; MinIO only inventories those bound sources.
