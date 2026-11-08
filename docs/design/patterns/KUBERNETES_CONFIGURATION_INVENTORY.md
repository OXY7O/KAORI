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

### Table layout and concise evidence copy

The six-column fixed-width inventory allocates **Configuration Object 27%, Scope 23%, Object Type 11%, Key Index & Mutation 15%, Current Pod References 14%, Details 10%**. Long object names and cluster/namespace scope receive half of the available width. Preserve `min-w-[72rem]`, responsive horizontal scrolling, shared table primitives, accessible headings, and View Details.

Object Type shows the ConfigMap/Secret badge. The ConfigMap supporting line reads **Values not stored** (KAORI's protected persistence boundary); Secret supporting text remains its factual Kubernetes Secret type, with truncation and a full hover title. Key count and **Mutable / Immutable** are compact siblings; mutation describes whether updates are permitted, **not** observed modification history.

**Current Pod References** uses a factual compact number and noun, such as **0 Pods**, **1 Pod**, or **2 Pods**, only when committed Pod collection is `Collected`; its supporting line reads **In committed snapshot**. If collection is unavailable, retain **Not Reported** and the source collection-state explanation. Preserve full canonical labels and supporting evidence in hover titles and the detail workspace. A zero does not prove the object has no consumers outside the committed Pod snapshot.

## Detail contract

The detail workspace shows identity, protected data boundary, a bounded key preview, evidence-aware Pod references, committed-snapshot guidance, and permission-gated links to ConfigMap or Secret Operations. The key preview shows at most 100 entries while preserving the factual total.

## Export contract

XLSX and CSV export key names only. The workbook declares `Metadata Boundary = Key Names Only` and `Value Persistence = None`. Synthetic payload size is prohibited.
