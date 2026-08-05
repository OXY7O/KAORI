# Kubernetes Pod Inventory Standard

Pod Inventory is the fourth reference implementation of the KAORI Inventory Resource Page Pattern.

```text
Canonical Hero
Compact Snapshot Context
Pod Runtime Posture
Compact Pod Inventory Table
Detail Style 2 — Full Workspace Modal
```

## Committed evidence boundary

Pod Inventory reads only the latest committed inventory generation. Filters, summary posture, table rows, detail, and tabular export must interpret the same committed Pod evidence and must not perform live Kubernetes API reads from the web request.

Optional owner enrichment through ReplicaSet and Job APIs is supporting evidence. A `403` or `404` from those APIs must not discard Pod inventory; KAORI retains the direct owner and records owner-resolution collection state.

## Runtime and lifecycle semantics

Semantic operational state is separate from raw Kubernetes phase evidence:

- `Ready`: phase is `Running` and all regular containers report Ready.
- `Starting`: phase is `Pending`.
- `Not Ready`: phase is `Running` with authoritative incomplete regular-container readiness.
- `Terminating`: `metadata.deletionTimestamp` exists, regardless of the raw phase.
- `Failed`: phase is `Failed`.
- `Completed`: phase is `Succeeded`.
- `Unknown`: phase or container readiness evidence is incomplete or unsupported.

A missing `containerStatuses` field is `Not Reported`; it must not be represented as `0/0` or as an authoritative Not Ready state. Restart totals are cumulative snapshot values and include regular, init, and ephemeral container status evidence when available.

## Collection coverage

The Pod collector commits:

- Pod identity, namespace, raw Kubernetes phase, lifecycle state, node, Pod IP, and owner chain.
- Regular, init, and ephemeral container specification and runtime evidence.
- Conditions, waiting or termination reasons, timestamps, exit codes, and restart activity.
- Node selectors, affinity presence, tolerations, topology spread, scheduler, priority class, and host-network evidence.
- Volumes and mounts, including mounts from ephemeral containers.
- ConfigMap, Secret, image-pull-secret, and PersistentVolumeClaim references.
- Explicit collection evidence for ReplicaSet and Job owner resolution.

Objects without both namespace and Pod name are not persisted.

## Workspace ownership

Cluster, Namespace, Owner Type, Lifecycle Phase, Node, and Search filters replace the complete `pods-page-workspace`.

```text
Filter change
→ Hero
→ Snapshot Context
→ Runtime Posture
→ Dependent filter options
→ Pod table
```

Pagination and Rows only replace the table scope because they do not change summary semantics.

## Compact table

```text
Pod | Scope | Runtime State | Placement | Ownership & Activity | Details
```

Age remains supporting identity text and detailed metadata. Missing specification or runtime evidence is displayed as `Not Reported`, not as a factual zero.

## Detail composition

```text
Pod Summary
├── Pod Identity
├── Runtime & Conditions
├── Placement & Network
├── Pod Specification
├── Container Runtime
├── Volumes & Resource References
├── Pod Labels / Annotations
└── Operational Context
```

Use `container_runtime_collection.html` for container evidence, `related_resource_collection.html` for ConfigMap, Secret, and PVC references, and `technical_metadata_collection.html` for labels and annotations.

Empty states distinguish:

- No configuration was reported by an authoritative Pod specification.
- The relevant specification or runtime evidence was not collected.

## Export contract

Pod XLSX and CSV export use the same committed evidence contract:

- Runtime-derived restart count is blank when runtime evidence was not reported.
- Container, image, configuration-reference, and PVC counts are blank when specification evidence was not reported.
- Image count represents regular, init, and ephemeral image references, not a distinct-image calculation.
- Pod presentation and export require explicit canonical evidence flags. Snapshots produced before the canonical evidence contract must be recollected instead of inferred through presentation-field fallbacks.

## Policy boundary

QoS, restart policy, DNS policy, host network, security-context presence, pull policy, selectors, tolerations, and owner resolution are factual evidence. They do not receive compliance severity until an explicit governance policy evaluates them.
