# Object Storage Inventory Domain

`app/storage/object_storage/inventory/` owns collection, synchronization, committed
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
`app.storage.object_storage.analytics` and its metrics-source contract.

Do not recreate the retired `app.storage_inventory` package or forward imports
from it.


## Inventory Table Contextual Help

The **Systems** and **Buckets & Containers** table titles each expose one shared `components/info_tip.html` guide describing technical columns (including provider release, inventory coverage, quota, protection and snapshot freshness). Column headers and row values remain plain, with no per-column hover icons. Help is hover/focus/touch accessible, does not modify provider facts, and never treats an unreported quota, protection control, or snapshot value as a healthy/compliant state. The existing detail workspace remains the source of full technical evidence; inventory reads stay committed-state only.
