# Object Storage Inventory Pattern v1.1

Object Storage Inventory is a committed-snapshot workspace. Provider registration and validation remain owned by Integrations → Storage; inventory pages never query the provider API live.

## Setup prerequisite

`ObjectStorageSystem` is the canonical managed asset created by a registered Storage integration. When no managed system exists, Object Storage Inventory is setup-blocked rather than rendered as a normal empty inventory.

Blocked composition:

1. Canonical Hero remains visible.
2. Hero metadata uses `Committed Inventory` + `Object Storage Setup Required`; zero asset counters are not presented as evidence.
3. Hero right panel uses `Inventory Readiness / Object Storage Setup Required` with `Registered Systems = 0` and `Workspace State = Blocked`.
4. The setup banner directs authorized operators to Integrations → Storage.
5. Inventory Data Snapshot, posture/summary cards, filters, tables, and drawers remain hidden.
6. Direct HTMX inventory reads return the setup banner while blocked.

A registered system with no committed inventory is **not** setup-blocked. It is a collection-pending inventory state and must continue to expose the Inventory Data Snapshot with missing/partial collection evidence.

## Inventory Data Snapshot

Overview, Systems, and Buckets & Containers all place the canonical `Inventory Data Snapshot` immediately below the Hero in ready state. It reports committed source, freshness, active scope, system coverage, and snapshot exceptions using `components/snapshot_context_bar.html`.

## Ownership

- Integrations → Storage: registration, configuration, validation, runtime health.
- Jobs & Executions: Object Storage Inventory Sync scheduling and execution.
- Object Storage Inventory: committed systems/buckets/containers evidence only.
- Object Storage Analytics: live/metric-derived analysis after inventory and metrics dependencies are eligible.
