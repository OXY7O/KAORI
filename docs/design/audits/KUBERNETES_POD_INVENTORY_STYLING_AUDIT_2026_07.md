# Kubernetes Pod Inventory Styling Audit — 2026-07

## Decision

Approved package: Inventory Resource Page Pattern, compact Pod table, adaptive inline detail, Pod runtime semantics, Container Runtime Collection, reference-only Related Resource Collection rows, and no implicit Pod configuration scoring.

## Corrected debt

- removed page-local hero posture geometry and arbitrary typography;
- replaced Running coverage with Pod Runtime Posture;
- separated operational state from Kubernetes phase and readiness evidence;
- replaced the wide eight-column table with six grouped columns;
- corrected the Rows selector to refresh the owning Pod inventory scope;
- removed fixed detail heights and four-column density;
- corrected condition semantics so every `False` value is not Critical;
- corrected init/terminated container semantics using exit code and readiness evidence;
- displayed ConfigMap, Secret, and PVC references already collected by the worker;
- migrated labels and annotations to Technical Metadata Collection;
- removed implicit scoring for QoS, restart, DNS, host-network, pull-policy, and placement configuration.

## Reusable additions

- `components/container_runtime_collection.html`;
- reference-only rows in `components/related_resource_collection.html`;
- `patterns/KUBERNETES_POD_INVENTORY.md`.
