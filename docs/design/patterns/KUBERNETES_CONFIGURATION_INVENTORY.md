# Kubernetes Configuration Inventory Standard

Configuration Inventory is the committed-snapshot catalog for Kubernetes `ConfigMap` and `Secret` objects. It stores object identity, object type, Secret type, immutable configuration, creation timestamp, and sorted key names. It never stores, decodes, logs, displays, or exports ConfigMap or Secret values.

## Canonical evidence

- `inventory.configmaps` records ConfigMap collection capability.
- `inventory.secrets` records Secret collection capability.
- `inventory.pods` governs whether current Pod-reference counts are factual.
- `0 references` is valid only when Pod collection is `Collected`; otherwise the result is `Not Reported`.
- Key count is derived from `key_names` and is not stored as a duplicate database column.

## Page contract

The page owns one `#configuration-page-workspace` containing Hero, Snapshot Context, posture, filters, and table. Scope-changing filters replace the workspace. Pagination and page-size changes replace only `#configuration-table-content`. Default page size is five.

The compact table contains Configuration Object, Scope, Object Type, Key Index & Mutation, Current Pod References, and Details. Age remains in the detail workspace.

## Detail contract

The detail workspace shows identity, protected data boundary, a bounded key preview, evidence-aware Pod references, committed-snapshot guidance, and permission-gated links to ConfigMap or Secret Operations. The key preview shows at most 100 entries while preserving the factual total.

## Export contract

XLSX and CSV export key names only. The workbook declares `Metadata Boundary = Key Names Only` and `Value Persistence = None`. Synthetic payload size is prohibited.
