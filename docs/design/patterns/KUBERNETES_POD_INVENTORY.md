# Kubernetes Pod Inventory Pattern

Pod Inventory is the fourth reference implementation of the Inventory Resource Page Pattern.

```text
Canonical Hero
Compact Snapshot Context
Pod Runtime Posture
Compact Pod Inventory Table
Detail Style 2 — Full Workspace Modal
```

## Runtime semantics

Semantic operational state is separate from Kubernetes phase evidence:

- Ready: Running and every regular container is Ready.
- Starting: Pending.
- Not Ready: Running with incomplete regular-container readiness.
- Failed: Failed phase.
- Completed: Succeeded phase.
- Unknown: unsupported or incomplete evidence.

The table displays operational state plus phase/readiness evidence. Restart counts are cumulative snapshot values and do not imply an active incident.

## Compact table

```text
Pod | Scope | Runtime State | Placement | Ownership & Activity | Details
```

The Rows selector refreshes the owning `pods-inventory-scope` so page-size state remains synchronized with the filter form.

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

## Policy boundary

QoS, restart policy, DNS policy, host network, security-context presence, pull policy, selectors, and tolerations are factual evidence. They do not receive semantic compliance severity until an explicit governance policy evaluates them.
