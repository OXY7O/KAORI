# MinIO Integration

MinIO is the first `Storage → Object Storage` provider registered with the KAORI Integration kernel.

The provider owns the S3 API plane and binds to a provider-neutral `object_storage_system` asset. Prometheus and Alertmanager remain independent Observability providers and may bind to the same asset for metrics and alerts. No direct MinIO → Prometheus/Alertmanager foreign key or product-specific binding table is allowed.

Initial compatibility target: `RELEASE.2024-08-03T04-33-23Z` (`minio-release-2024-08-03`).

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
  → Core Validation
  → Runtime & History
  → Bindings & Consumers
```

The visual shell, registration terminology, Hero hierarchy, tab structure,
readiness semantics, and empty/populated registry states are shared. Only
MinIO-specific technical fields and consumer contracts differ.

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
  │     → minio-metrics-2024-v1
  │     → Binding Validation
  └── Alertmanager binding
        → minio-alerts-v1
        → Binding Validation
```

MinIO API readiness must not depend on Prometheus metric presence or Alertmanager
alert presence. Conversely, metrics and alert readiness belong to their
provider-to-`object_storage_system` bindings and must not mutate MinIO,
Prometheus, or Alertmanager provider readiness.

A future S3-compatible provider reuses the same asset/binding model with its own
compatibility and consumer profiles.
