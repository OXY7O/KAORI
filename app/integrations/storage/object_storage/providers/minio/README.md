# MinIO Integration

MinIO is the first `Storage → Object Storage` provider registered with the KAORI Integration kernel.

The provider owns the S3 API plane and one provider-neutral `object_storage_system` asset through the MinIO connection record. That owner relationship is not a consumer binding. Metrics Source and Alertmanager remain independent Observability sources and may bind to the asset for metrics and alerts. No direct MinIO → Metrics Source/Alertmanager foreign key, MinIO self-binding, or product-specific binding table is allowed.

Compatibility is definition-driven and product-specific. The current 2026 policy qualification is `minio-community-policy-v1`, mapped to the stable `s3-object-storage-v1` Core API contract. The declared MinIO Community release window is `RELEASE.2021-12-29T06-49-06Z` through `RELEASE.2025-10-15T17-29-55Z` (`extended_supported`; upstream `archived_community`). A newer release is **Future Unverified** with degraded readiness when mandatory S3 probes succeed; releases older than the policy floor are blocked as End of Life. The annual compatibility policy is governed by #473 and the source-controlled `app/definitions/catalogs/integrations/storage/object_storage/contract.yaml`; AStor is a separate product family and does not inherit MinIO qualification.

## Provider workspace standard

MinIO uses the same KAORI provider interaction model as Kubernetes, Metrics Source,
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
  → minio-community-policy-v1 / s3-object-storage-v1
  → provider-owned S3/API capabilities
  → Provider Core Validation
  → Ready

ObjectStorageSystem
  ├── Metrics Source binding
  │     → object-storage-metrics-v1
  │     → provider-qualified MinIO Metrics v2 validator
  │     → Binding Validation
  └── Alertmanager binding
        → object-storage-alerts-v1
        → Binding Validation
```

MinIO API readiness must not depend on Metrics Source evidence, Alertmanager alert presence, or inventory freshness. Conversely, metrics and alert readiness belong to their Metrics Source/Alertmanager-to-`object_storage_system` consumer bindings and must not mutate provider readiness.

Inventory collection is a separate canonical Job Execution. `Full Validation` proves MinIO identity, release qualification, S3 access and `ListBuckets` as the required provider-core capabilities; optional per-bucket versioning, lifecycle, policy, encryption and object-lock reads remain **Not Checked** in Core Validation unless independently observed, and their evidence belongs to Inventory Sync. `Runtime Refresh` performs lightweight endpoint health observation only; non-successful fallback HTTP probes must never be labeled healthy. `Object Storage Inventory Sync` collects and atomically commits system/bucket snapshots on the `inventory` queue. The job is enabled by default on the same 60-minute policy cadence as Kubernetes Inventory Sync and can be run manually from Jobs & Executions → Job Configuration.

A future S3-compatible provider reuses the same asset/binding model with its own
compatibility profile and provider-qualified observability adapters.

## Asset-owner lifecycle parity

MinIO follows the same managed-asset ownership pattern as Kubernetes. The MinIO
connection owns one canonical `object_storage_system` asset; Metrics Source and
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
  → bound Metrics Source/Alertmanager inventory (read-only)
  → governed Delete Connection
```

Deleting the MinIO asset owner removes the MinIO provider identity, the managed
object-storage asset, and every binding targeting that asset. Shared Metrics Source and
Alertmanager connections remain registered. Active KAORI jobs referencing either the
MinIO provider or the object-storage asset block deletion until they complete. Runtime
observation history and Activity Audit records remain retained evidence.

Connection-sensitive configuration changes preserve the canonical object-storage asset
and its consumer bindings but reset MinIO provider readiness until Core Validation is
run again. Provider source identity changes advance a committed source generation;
previous bucket observations remain last-known historical evidence and the MinIO
Inventory & Lifecycle surface must identify them as **Source Changed / Sync Required**
until a matching inventory job commits the new source generation. Configuration writes
and inventory commits share the system-row lock to avoid cross-generation commits.
Consumer binding creation, validation, update, and removal are performed from
the Metrics Source or Alertmanager workspace; MinIO only inventories those bound sources.
