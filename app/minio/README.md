# MinIO Provider Workspace

`app/minio/` owns the HTTP/forms/presentation workflow for the current
`Storage → Object Storage` provider. It does not construct Metrics Source
clients or persist provider-pair relationships.

## Provider contract

- Register one MinIO S3 API connection after a successful connection test.
- Persist the provider through canonical `IntegrationInstance` identity plus one
  provider-neutral `ObjectStorageSystem` asset.
- Store the secret key using KAORI `EncryptedText` credential handling.
- Resolve the product-specific compatibility profile and its qualified release
  range. A different S3-compatible product remains a separate qualification
  boundary until a provider definition is registered for it.
- Bind an existing Metrics Source to the same object-storage asset through
  canonical `IntegrationBinding` plus an explicit selector.
- Validate metrics evidence through the adapter-qualified
  `object_storage_system` binding profile. MinIO never owns the metrics backend
  or its credentials.

Object Storage Inventory consumes this normalized provider contract through
canonical Job Execution. `Object Storage Inventory Sync` runs on the shared
`inventory` queue, is scheduled automatically through `JobPolicy`, and is also
available for manual execution from Jobs & Executions. Full Validation and
Runtime Refresh do not commit bucket inventory. Failed inventory collection
preserves the last committed system/bucket snapshot.

Object Storage Analytics consumes the committed inventory snapshot for
canonical current-state evidence and resolves time-series evidence through the
provider-neutral `MetricsSource` contract. The analytics domain does not depend
on a concrete Metrics Source product, query payload implementation, or
credentials. Alertmanager lifecycle correlation remains separate and requires
its own alert-source binding.
