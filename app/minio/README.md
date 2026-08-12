# MinIO Provider Workspace

`app/minio/` owns the HTTP/forms/presentation workflow for the first
`Storage → Object Storage` provider. It does not construct Prometheus clients or
persist provider-pair relationships.

## Phase 1 contract

- Register one MinIO S3 API connection after a successful connection test.
- Persist the provider through canonical `IntegrationInstance` identity plus one
  provider-neutral `ObjectStorageSystem` asset.
- Store the secret key using KAORI `EncryptedText` credential handling.
- Resolve the product-specific compatibility profile and its qualified release range. The current MinIO profile qualifies `RELEASE.2024-08-03T04-33-23Z`; AStor remains a separate qualification boundary.
- Bind an existing Prometheus provider to the same object-storage asset using
  canonical `IntegrationBinding` plus an explicit selector.
- Validate the selector through the MinIO `object_storage_system` Prometheus
  binding profile.

Object Storage Inventory consumes this normalized provider contract through canonical Job Execution. `Object Storage Inventory Sync` runs on the shared `inventory` queue, is scheduled automatically through `JobPolicy`, and is also available for manual execution from Jobs & Executions. Full Validation and Runtime Refresh do not commit bucket inventory. Failed inventory collection preserves the last committed system/bucket snapshot.

Object Storage Analytics remains deferred and will consume committed inventory snapshots rather than owning MinIO or Prometheus credentials.
