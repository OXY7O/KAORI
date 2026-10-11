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


## Bucket Environment Filter

Buckets & Containers exposes the committed system Environment as an explicit filter
alongside System, Provider, Type and Search. The selected environment remains visible
and is preserved across HTMX pagination and page-size changes; Clear Filters resets
it with the other active filters. This is a database snapshot filter, not a live
provider query.


## Fleet Evidence Completeness

The grouped Fleet Inventory Posture reports positive protection attention and
public exposure separately from assessed coverage. Missing/unknown encryption,
immutability, versioning or exposure evidence is not a clean bill of health.
A green zero-attention / zero-public-exposure state requires complete committed
evidence for the corresponding inventory assets; a partial or absent assessment
uses warning or unknown semantic tones. No live provider reads or compliance
verdicts are involved.


## SQL Resource List Contract

Systems and Buckets & Containers apply the active filters to SQL queries before
canonical `paginate_query` (5/10/25/50 records). The owning integration identity
joins through committed metadata and provider records, and only one requested page
is normalized into full presentation dictionaries. SQL aggregation and DISTINCT
scalar filter-option projections avoid full fleet row/evidence materialization on
operational list reads. Tied asset names sort by stable ID. The Snapshot Context
Bar uses the same committed fleet semantics through a SQL aggregate read model.
No live provider calls are permitted on GET routes.
For Systems and Buckets list rendering, the canonical first-owner plus current MinIO-compatible provider-record join is now projected in one scoped SQL read per **visible page**, reused for all rows sharing that managed system. Other provider-record types retain the existing integration-kernel owner resolver as a compatibility fallback. System and bucket details remain independently scoped, and the lookup must not change the authoritative committed provider identity.


## Bounded Inventory Overview fleet read model (#1370)

Inventory Overview aggregates committed registered-system status, inventory observation coverage and provider distribution through grouped SQL and the existing canonical owner joins. Bucket/Container quota, protection, exposure, and usage evidence is aggregated by `inventory/aggregates.py::bucket_fleet_posture`, using the exact existing assessed/unknown, negative-control, and public-exposure definitions. No full bucket ORM collections or per-system provider-owner resolution are required by the Overview. Systems/Buckets paginated list pages remain separately governed by #1262; dashboard Fast Shell and its per-section evidence remain #1367. These operations read committed KAORI state only and do not contact MinIO or another provider.

## Empty Inventory Snapshot Interpretation (#1383)

Buckets & Containers uses committed fleet observation coverage, not only the number of stored bucket rows, to distinguish `Collection Pending` (no successful observation), `Partial Inventory` (some systems observed zero, others unobserved), `Observed Empty` (all registered systems observed successfully with zero buckets), and `No Matches` (buckets exist but active filters return zero rows). A successful first empty sync is valid committed inventory evidence. The Snapshot Context Bar separately communicates stale/provider conditions. None of these read-only states triggers a provider query.

## Guarded Zero-Bucket Reconciliation (#1382)

Automatic/ordinary Object Storage Inventory Sync refuses an unexpected zero-bucket ListBuckets result when the previous committed snapshot contains assets. That guard remains authoritative: failure, credentials/scope drift, or incomplete bucket discovery must not erase last-good evidence. Malformed and truncated ListBuckets responses now fail closed even on first collection.

For an intentionally emptied provider, an operator with the existing `jobs.execute` **and** `storage.sync` permissions can use **Job Execution → Object Storage Inventory Sync → Confirm an Empty Bucket Inventory**. Choose the **specific** previously observed nonempty system, independently verify the provider really has no buckets, and enter `CONFIRM EMPTY`. This submits a CSRF-protected manual job using the existing global inventory execution serialization, with actor and target committed to JobExecution parameters/payload. Scheduler and generic Run Now jobs never opt into this recovery behavior.

The worker rechecks provider eligibility and the locked committed system observation timestamp and prior bucket count; then it requires two separate, complete, empty ListBuckets observations. If either returns assets, malformed data, warnings, a provider error, or the committed snapshot has changed, the transaction rolls back without deleting records. Only after both pass does the worker atomically remove prior bucket rows and commit a new `inventory_observed_at`. JobExecution result evidence and operator notification include the selected system, actor, previous/removed count, two confirmations, and outcome. This mutates **KAORI committed state only**, never provider data. A zero-bucket first collection remains valid without reconciliation.

**Local validation before human acceptance:** initial empty, unexpected zero, confirmed nonempty→zero, failed/partial/malformed ListBuckets, conflicting confirmations, snapshot drift, concurrent attempts, rollback, zero→nonempty recovery, JobExecution/RBAC/CSRF, and Inventory Overview/Systems/Buckets UI. Do not run automatic confirmation or bypass explicit operator approval. CI/CD, Developer Check, Full Admission, official staging/main/release HOLD until explicitly authorized.
