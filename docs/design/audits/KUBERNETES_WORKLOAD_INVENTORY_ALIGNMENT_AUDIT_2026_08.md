# Kubernetes Workload Inventory Alignment Audit — August 2026

## Outcome

Workload Inventory is aligned with the current KAORI Inventory Resource Page standard and committed-evidence semantics.

## Functional corrections

- Missing Deployment, StatefulSet, DaemonSet, or Job status is classified as `Unknown`, not as a healthy zero-replica state.
- Deployment `ProgressDeadlineExceeded` and explicit `ReplicaFailure=True` are classified as failed.
- A Deployment cannot be classified as stable while `status.observedGeneration` is behind `metadata.generation`.
- StatefulSet stability includes update and revision evidence.
- DaemonSet stability includes updated, unavailable, and misscheduled evidence.
- Job failure uses the authoritative `Failed=True` condition; failed Pod attempts do not automatically fail the Job.
- Completed and suspended Jobs use canonical `Stable` and `Suspended` posture.
- Workload identity requires both namespace and name before persistence.

## Controller condition evidence

Controller condition evidence is committed with type, status, reason, message, and last transition time. Detail renders the conditions in a dedicated factual section.

## Export corrections

The collector now stores desired, current, updated, ready, available, and unavailable replica fields plus update strategy at the top level of the workload evidence payload. Inventory export uses these canonical fields and falls back to legacy nested rows when reading older snapshots.

## Workspace and filter corrections

- Cluster, Namespace, Type, Operational State, and Search filters replace `workloads-page-workspace`.
- Hero, Snapshot Context, posture, dependent options, and table remain in the same active scope.
- Operational State filtering is canonical across heterogeneous workload types.
- Unknown and unrecognized state evidence remains filterable.

## Table alignment

The compact row now shows Workload, Scope, Operational State, Managed Pods, Update Strategy, and Details. Age remains in detail and container counts remain Pod-template evidence.

## Missing-evidence semantics

- Missing Pod-template evidence is displayed as `Not Reported`.
- Placement evidence is not represented as zero selectors, zero tolerations, or no affinity when the template was not collected.
- Empty posture metrics use Unknown tone rather than implying a healthy state.
- Stable completed Jobs and idle CronJobs do not receive a false missing-Pod ownership warning.

## Accessibility and maintainability

- Filter controls have explicit labels and IDs.
- The table has an accessible caption and scoped headers.
- A dedicated Workload Inventory verifier is registered in the KAORI quality gate.
- Behavioral tests cover missing status, stale observed generation, replica failure, progress deadline failure, Job retry semantics, completion, suspension, and canonical export fields. Legacy nested export fallback has been removed; older snapshots require recollection.

## Validation boundary

- Focused Workload Inventory contracts and behavioral tests: `37 passed`.
- Kubernetes contract suite: `188 passed`; two pre-existing failures remain in Secret choice-card styling and TLS rotation schema guard contracts.
- Python syntax verification: `835` source files passed.
- Workload, Namespace, and Node Inventory static verifiers passed.
- Code-health verification reports no remaining line or branch debt for the modified Workload collector and service functions.

Live browser validation remains required for 14-inch layout, dark mode, HTMX focus continuity, and detail-modal rendering against a running Flask/PostgreSQL/Kubernetes environment.
