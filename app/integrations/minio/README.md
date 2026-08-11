# MinIO Integration

MinIO is the first `Storage → Object Storage` provider registered with the KAORI Integration kernel.

The provider owns the S3 API plane and binds to a provider-neutral `object_storage_system` asset. Prometheus remains an independent Observability provider and is bound to the same asset for MinIO v2 metrics. No direct MinIO → Prometheus foreign key or product-specific binding table is allowed.

Initial compatibility target: `RELEASE.2024-08-03T04-33-23Z` (`minio-release-2024-08-03`).
