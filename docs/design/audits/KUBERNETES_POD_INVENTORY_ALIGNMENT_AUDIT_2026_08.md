# Kubernetes Pod Inventory Alignment Audit — August 2026

## Outcome

Pod Inventory is aligned with the current KAORI Inventory Resource Page standard and committed-evidence semantics.

## Functional corrections

- Missing `containerStatuses` is stored and displayed as `Not Reported`, not `0/0` or authoritative Not Ready.
- Ready totals use the regular Pod specification container count rather than the number of status records returned.
- Pods with a deletion timestamp use lifecycle `Terminating` while preserving the raw Kubernetes phase in detail.
- Pod identity requires namespace and name before persistence.
- Regular, init, and ephemeral container restart, image, volume-mount, and configuration-reference evidence is collected.
- Waiting reasons such as `CrashLoopBackOff`, `ImagePullBackOff`, and container configuration failures receive critical runtime presentation.
- A terminated container with no exit-code evidence remains Unknown rather than being inferred as failed.

## Owner-resolution evidence

ReplicaSet-to-Deployment and Job-to-CronJob enrichment is optional supporting evidence. Permission or API unavailability is committed to `ClusterInventory.collection_evidence`; it does not abort Pod collection. Detail exposes incomplete higher-level owner resolution without labelling the Pod standalone when a direct owner exists.

## Workspace and filter corrections

- Cluster, Namespace, Owner Type, Lifecycle Phase, Node, and Search filters replace `pods-page-workspace`.
- Hero, Snapshot Context, posture, dependent options, and table remain in one active scope.
- Null or blank phases are selectable as `Unknown`.
- Unscheduled Pods are selectable through `Not Scheduled`.
- Pagination and Rows remain table-scoped.

## Missing-evidence semantics

- Specification absence is not represented as zero containers, zero volumes, no selectors, or no tolerations.
- Runtime absence is not represented as zero restarts or `0/0` readiness.
- Condition, volume, configuration-reference, and storage-reference empty states distinguish authoritative absence from unreported evidence.
- Security-context absence is `Not Configured` only when Pod specification evidence exists.
- Unknown runtime posture never receives a healthy snapshot-ready recommendation.

## Export corrections

Pod XLSX/CSV export leaves runtime-derived and specification-derived numeric fields blank when their authoritative evidence is unavailable. Container count supports canonical `details.configuration.container_count`; image count describes regular, init, and ephemeral image references.

## Accessibility and maintainability

- Filter controls use explicit IDs and labels.
- The Pod table and volume table have accessible captions and scoped column headers.
- Pod semantics and detail assembly were split into focused modules.
- Resolved code-health debt entries for `get_pods` and `get_pod_detail` were removed.
- A dedicated Pod Inventory verifier is registered in the KAORI quality gate.

## Validation boundary

- Pod-focused Kubernetes contracts: `19 passed`.
- Pod collector and export behavioral tests: `9 passed`.
- Full Kubernetes contract suite: `194 passed`; two pre-existing failures remain in Secret choice-card styling and TLS rotation schema guard contracts.
- Python syntax verification: `841` source files passed.
- Pod, Workload, Namespace, and Node Inventory static verifiers passed.
- Tabular export verifier passed.
- Eight Pod templates parsed successfully with Jinja.
- Code-health verification reports no Pod-specific line, branch, argument, or module-size debt.

Runtime tests that bootstrap the full Flask application could not be collected in the audit container because Flask is not installed. Live browser validation therefore remains required for 14-inch layout, dark mode, HTMX focus continuity, and detail-modal rendering against a running Flask/PostgreSQL/Kubernetes environment.
