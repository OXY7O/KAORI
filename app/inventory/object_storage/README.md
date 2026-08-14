# Object Storage Inventory Domain

`app/inventory/object_storage/` owns collection, synchronization, committed
snapshot presentation, and job integration for provider-neutral Object Storage
systems.

MinIO is the first provider implementation, but persisted inventory models and
web presentation remain based on `ObjectStorageSystem` and
`ObjectStorageBucket`, not MinIO-specific asset models.

## Package responsibilities

- `sync.py` collects and normalizes provider observations.
- `sync_jobs.py` owns synchronization job orchestration.
- `tasks.py` and `job_adapter.py` connect inventory synchronization to KAORI Job
  Execution.
- `routes.py` owns HTTP/HTMX inventory surfaces.
- `presentation.py` and `system_presentation.py` prepare UI evidence.

Inventory is canonical current-state evidence. Operational history, rate,
latency, traffic, growth, and forecast behavior belong to
`app.analytics.object_storage` and its metrics-source contract.

Do not recreate the retired `app.storage_inventory` package or forward imports
from it.
