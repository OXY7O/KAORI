# MinIO Integration

MinIO is the first `Storage → Object Storage` provider registered with the KAORI Integration kernel.

The provider owns the S3 API plane and binds to a provider-neutral `object_storage_system` asset. Prometheus remains an independent Observability provider and is bound to the same asset for MinIO v2 metrics. No direct MinIO → Prometheus foreign key or product-specific binding table is allowed.

Initial compatibility target: `RELEASE.2024-08-03T04-33-23Z` (`minio-release-2024-08-03`).


## Validation boundary

MinIO follows the canonical provider lifecycle:

```text
MinIO Provider
  → minio-release-2024-08-03
  → provider-owned S3/API capabilities
  → Provider Core Validation
  → Ready

ObjectStorageSystem Binding
  → Prometheus provider
  → minio-metrics-2024-v1
  → Binding Validation
  → Object Storage consumer eligibility
```

MinIO API readiness must not depend on Prometheus metric presence. Conversely,
MinIO metric readiness belongs to the Prometheus-to-`object_storage_system`
binding and must not mutate Prometheus provider readiness. A future S3-compatible
provider reuses the same asset/binding model with its own compatibility and
consumer profiles.
