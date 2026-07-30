# Kubernetes Workload Inventory

Workload Inventory is the third canonical Inventory Resource Page implementation.

## Composition

```text
Canonical Hero
Compact Snapshot Context
Workload Delivery Posture
Compact Workload Inventory Table
Detail Style 2 — Full Workspace Modal
```

## Operational semantics

Workload types are heterogeneous. KAORI separates semantic posture from factual controller evidence:

- Stable
- Progressing
- Failed
- Suspended
- Unknown

The supporting state remains type-specific, such as `3/3 Available`, `1/1 Complete`, `Scheduled`, or `2 Active`.

## Configuration evidence

Update strategy, restart policy, DNS policy, pull policy, selectors, tolerations, and placement settings remain factual evidence until evaluated against an explicit governance policy.

## Relationships

Associated Pods use `related_resource_collection.html`, not timeline geometry. Detail queries count related Pods and load only the first eight preview rows.
