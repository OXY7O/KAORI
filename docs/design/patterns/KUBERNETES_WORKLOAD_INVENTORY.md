# Kubernetes Workload Inventory Standard

Workload Inventory is the canonical KAORI Inventory Resource Page for Kubernetes controller and batch workload evidence.

## Composition

```text
Canonical Hero
Compact Snapshot Context
Workload Delivery Posture
Compact Workload Inventory Table
Detail Style 2 — Full Workspace Modal
```

Filter changes that alter resource scope must replace the complete `workloads-page-workspace` so Hero metrics, Snapshot Context, posture, filter options, and table rows remain consistent. Pagination may replace table content only.

## Committed evidence boundary

The page reads the latest committed inventory generation. It does not query the Kubernetes API live. Workload and related Pod rows are resolved from committed database snapshots.

A missing Kubernetes `status` object is not equivalent to zero replicas or a healthy controller. KAORI classifies that condition as `Unknown` and displays `Runtime State Not Reported`.

## Canonical operational posture

Workload types are heterogeneous. KAORI normalizes controller evidence into:

- Stable
- Progressing
- Failed
- Suspended
- Unknown

The supporting state remains type-specific, such as `3/3 Available`, `1/1 Complete`, `Scheduled`, `2 Active`, or `Progress Deadline Exceeded`.

### Deployment

- `Failed` when the Progressing condition is `False` with reason `ProgressDeadlineExceeded` or `ReplicaFailure=True` is reported.
- `Stable` only when the observed generation is current and available, updated, and unavailable replica evidence matches the desired state.
- `Progressing` when the controller has not observed the latest generation, even if replica counters appear converged.
- `Unknown` when status evidence is absent.

### StatefulSet

- `Stable` when desired replicas are ready and updated and reported revisions are current.
- `Progressing` while readiness, update, or revision evidence is incomplete.
- `Unknown` when status evidence is absent.

### DaemonSet

- `Stable` when desired Pods are ready and updated, with no unavailable or misscheduled Pods.
- `Progressing` when any of those conditions is not satisfied.
- `Unknown` when status evidence is absent.

### Job

Job posture uses authoritative Job conditions. A failed Pod attempt alone does not mean the Job has failed because retry budget may remain.

- `Failed` when the Job `Failed=True` condition is reported.
- `Stable` when `Complete=True` is reported or committed completion evidence is satisfied with no active Pod.
- `Suspended` when `spec.suspend=true`.
- `Progressing` while active or pending.
- `Unknown` when runtime status is absent.

### CronJob

- `Suspended` when `spec.suspend=true`.
- `Stable` when the schedule is enabled. Active child Jobs remain factual supporting evidence.

## Compact table contract

The table contains six columns:

1. Workload
2. Scope
3. Operational State
4. Managed Pods
5. Update Strategy
6. Details

Age remains in detail. Container counts remain Pod-template detail evidence and must not replace Update Strategy in the compact row. Jobs and CronJobs display `Not Applicable` for update strategy with their execution model as supporting context.

## Pod-template and placement evidence

Pod-template evidence includes containers, init containers, ServiceAccount, restart policy, priority class, scheduler, host-network state, DNS policy, volumes, and runtime class.

Node selectors, affinity, tolerations, topology-spread constraints, and runtime class remain factual scheduling evidence until evaluated against an explicit governance policy.

Missing Pod-template evidence must be shown as `Not Reported`. It must not be rendered as zero containers, zero placement constraints, or a confirmed absence of selectors and tolerations.

## Controller condition evidence

Controller conditions are committed with:

- type;
- status;
- reason;
- message;
- last transition time.

The detail workspace exposes this evidence separately from the normalized operational posture.

## Relationships

Associated Pods use `related_resource_collection.html`, not timeline geometry. Detail queries count related Pods and load only the first eight preview rows.

No associated Pods are an exception only for controller workloads that expect replicas. A stable completed Job or an idle CronJob does not require retained Pods.

## Export contract

Workload collection commits canonical top-level fields for XLSX and CSV:

- desired replicas;
- current replicas;
- updated replicas;
- ready replicas;
- available replicas;
- unavailable replicas;
- update strategy.

The export payload also supports legacy nested `state_rows` and `delivery_rows` so previously committed snapshots remain exportable.
