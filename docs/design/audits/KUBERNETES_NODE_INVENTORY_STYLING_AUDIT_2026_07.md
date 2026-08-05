> Historical Snapshot — retained for traceability. The active contract is `docs/design/patterns/KUBERNETES_NODE_INVENTORY.md`; see the August 2026 alignment audit.

# Kubernetes Node Inventory Styling Audit — July 2026

## Approved package

- A1 — Inventory Resource Page Pattern
- B1 — Compact Node Inventory Table
- C1 — Detail Style 1: Inline Expanded Detail
- D1 — Technical Value standard

## Implemented corrections

- separated hero readiness posture from capacity and scheduling evidence;
- corrected all-NotReady posture from Unknown to Critical;
- mapped unrecognized readiness to Unknown;
- changed Node role from status label to metadata label;
- standardized filters, table geometry, pagination, and visible Rows label;
- grouped CPU, memory, and ephemeral storage into one Capacity column;
- added complete capacity, kernel, runtime, and Kubernetes version detail;
- added visible committed-snapshot boundary and state-aware operational guidance;
- removed page-local detail macros in favor of shared detail primitives.

## Reusable standards created

- Inventory Resource Page Pattern;
- Resource Posture Grid;
- Detail Style 1 — Inline Expanded Detail;
- Technical Value.
