# Kubernetes Storage Inventory Standard

## Purpose

Storage Inventory presents committed Kubernetes storage configuration and binding evidence for three resource families:

- StorageClass
- PersistentVolume
- PersistentVolumeClaim

It does not infer filesystem utilization, I/O health, durability, performance, or application availability. Those belong to Storage Analytics and workload-specific evidence.

## Canonical collection contract

Each family records an independent collection state in `ClusterInventory.collection_evidence`:

- `inventory.storageclasses`
- `inventory.persistentvolumes`
- `inventory.persistentvolumeclaims`

Allowed states are `Collected`, `Permission Unavailable`, `API Unavailable`, and `Adapter Not Selected`. HTTP 403 and 404 become explicit evidence limitations. Unexpected provider errors remain fatal to the transactional inventory generation.

Missing values remain `None` in persistence. Presentation strings such as `Not Reported`, `Not Configured`, `Not Assigned`, and `Not Applicable` are produced only at the service or export boundary. Missing provider methods are `API Unavailable`; unexpected generated-client failures are not hidden.

## Lifecycle semantics

The canonical lifecycle states are:

- StorageClass: `Configured`
- PV/PVC: `Bound`, `Available`, `Pending`, `Released`, `Terminating`, `Failed`, `Lost`, `Unknown`, or `Not Reported`

A deletion timestamp takes precedence and produces `Terminating`, while the raw Kubernetes phase remains in JSON evidence.

## Evidence distinctions

- `allowVolumeExpansion=false` means `Not Allowed`.
- A missing `allowVolumeExpansion` field means `Not Reported`.
- Volume expansion on PV/PVC is `Not Applicable`.
- PVC requested capacity and status-reported bound capacity are separate fields.
- Requested and status-reported access modes remain separate.
- Explicitly classless PV/PVC objects are `Not Configured`, while missing specification evidence is `Not Reported`.
- A PVC with reported status but no bound capacity is `Not Assigned`, not `Not Reported`.
- `dataSource` and `dataSourceRef` are normalized into one factual data-source record.
- A missing claim or Pod relationship is only considered empty when the related inventory family was collected. Otherwise it is `Not Reported`.
- Mounted-Pod relationship lookup is exact for all committed claims; it must not silently cap the claim set.

## Page boundary

Storage uses one canonical workspace:

```text
#storage-page-workspace
├── Hero
├── Inventory Data Snapshot
├── Storage Lifecycle Posture
└── Storage Inventory table
```

Scope-changing filters refresh the workspace. Pagination and page size refresh only `#storage-table-content`. The default page size is five rows.

## Table contract

The compact table contains:

- Storage Object
- Scope
- Provisioning
- Capacity & Access
- Binding & Lifecycle
- Details

Age is detail-only.

## Detail contract

The detail workspace contains:

- Storage Identity
- Capacity & Access
- Binding & Lifecycle
- Provisioning Configuration
- Related Claims
- Mounted Pods
- type-specific configuration evidence
- labels and annotations
- operational guidance

## Export and topology

XLSX/CSV exports consume the same canonical lifecycle, capacity, access, binding, expansion, and evidence fields as the page. Topology consumes canonical lifecycle and binding references for PV and PVC nodes. Neither path reads presentation fallbacks from retired wrappers.
