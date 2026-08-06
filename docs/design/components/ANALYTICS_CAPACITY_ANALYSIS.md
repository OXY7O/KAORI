# Analytics Capacity Analysis

Status: KAORI domain presentation and evidence standard

## Scope

Capacity Analysis is a cluster-level **Ready-worker fleet** workspace. It does not expose a node selector; node-level pressure belongs to Resource Utilization. The scheduling denominator contains only nodes that:

1. are not labelled with role `control-plane` or legacy `master`; and
2. currently expose `kube_node_status_condition{condition="Ready",status="true"} == 1`.

CPU, memory, and pod calculations use the same Ready-worker boundary for allocatable capacity, configured requests, configured limits, current usage, and peak usage. Control-plane and NotReady nodes are context only and cannot silently enlarge the scheduling envelope.

## Runtime and Ownership

The web request reads one committed `analytics.capacity` snapshot. Prometheus access belongs to the materialization worker:

```text
Prometheus / kube-state-metrics
        ↓
CapacityEvidenceCollector
        ↓
Capacity domain interpretation
        ↓
Committed analytics.capacity snapshot
        ↓
Capacity presenter
        ↓
Server-rendered KAORI workspace
```

Canonical ownership:

- `app/analytics/capacity/evidence.py` — query registry consumption, exact evidence availability, and query-once collection;
- `app/analytics/capacity/domain.py` — capacity, allocation, overcommit, headroom, risk, and governance semantics;
- `app/analytics/capacity/service.py` — orchestration and recommendation assembly only;
- `app/analytics/capacity/presentation.py` — display normalization and bottleneck selection;
- `app/analytics/capacity/routes.py` — committed snapshot resolution and selected-tab restoration.

A materialization run collects every required Capacity signal once. The service must not rebuild the same CPU, memory, pod, request, limit, or peak query through Utilization helpers.

## Page Structure

1. Hero with selected cluster, semantic capacity posture, lowest scheduling headroom, and observation window.
2. Controls & Data Readiness with Cluster and Time Range.
3. Capacity Analysis Overview.
4. One tabbed workspace containing:
   - Worker Capacity Summary;
   - Allocation & Headroom;
   - Capacity Risk Summary; and
   - Capacity Recommendations.

The selected tab is presentation state. It is preserved when Cluster or Time Range changes but is removed from the materialization fingerprint.

## Scheduling Resources Versus Filesystem Reference

Only these resources participate in Kubernetes scheduling posture:

```text
CPU, Memory, Pods
```

Node Filesystem is an **operational reference**, not Kubernetes allocatable storage capacity. It may be displayed to help correlate node pressure, but it must not:

- determine the lowest scheduling headroom;
- mark Capacity posture Critical, Watch, or Healthy;
- generate Kubernetes capacity-expansion recommendations; or
- appear as a Capacity governance finding.

Filesystem remediation continues in Storage Analysis. Filesystem queries are optional reference evidence and do not block Capacity readiness when the Ready-worker scheduling contract is otherwise complete.

## Evidence and Unavailable State

Missing capacity evidence is not zero utilization. Each scalar retains an explicit availability flag. KAORI displays `Unknown` and `N/A`, suppresses the progress bar, and describes the missing evidence when any required numerator or denominator is absent.

Examples:

- missing allocatable CPU does not become `0 cores`;
- missing request or limit metrics do not become a Healthy commitment profile;
- a valid zero current usage remains available evidence and is distinct from an empty Prometheus result;
- a missing peak series is not replaced with current usage;
- an unavailable filesystem series remains an optional Unknown reference.

Capacity posture is **Healthy** only when CPU, memory, and pod scheduling evidence is complete and no scheduling resource is under pressure. A known request overcommit, peak breach, usage-critical signal, or limit overcommit keeps its Critical/Watch priority even when another signal is missing; it is never downgraded to Healthy. Partial evidence without a known pressure condition produces `Limited Evidence`, while a fully unavailable boundary produces `Unknown`.

## Allocation Semantics

CPU and memory allocation sections distinguish:

- **Allocatable** — Ready-worker schedulable denominator;
- **Configured Requests** — scheduler reservation commitment;
- **Configured Limits** — maximum configured workload envelope;
- **Actual Avg Usage** — current observed consumption; and
- **Peak Usage** — maximum observed consumption in the selected time range.

Status priority is deterministic:

1. Request Overcommit — requests are at least 100% of allocatable;
2. Peak Over Capacity — observed peak is at least 100%;
3. Usage Critical — actual usage is at least 95%;
4. Limit Overcommit — limits are at least 100%;
5. Near Capacity / Watch — a known signal crosses the warning threshold;
6. Limited Evidence — one or more commitment or usage signals are missing;
7. Healthy — all required signals are known and within the envelope.

Pod allocation contains one row each for Pod Capacity, Current Pods, and Remaining Pod Slots. It must not duplicate Current Pods as a separate “Pod Usage” row.

## Capability Contract

Capacity requires:

```text
instant_query
range_query
kubernetes_identity
capacity_metrics
resource_requests_limits
```

`capacity_metrics` validates node info, node roles, Ready conditions, allocatable CPU/memory/pods, pod placement, and container CPU/memory usage. `resource_requests_limits` validates `namespace`, `node`, `pod`, `resource`, and `unit` labels so Ready-worker scoping can be applied consistently.

A missing metric or label is an integration capability failure. Capacity must not introduce provider-specific fallbacks, IP identity matching, or unscoped cluster-total queries.

## Semantic Color

Capacity status bars use the shared semantic renderer: Healthy/Normal is green, Watch is amber, Critical is red, and Unknown is slate. KAORI Violet remains reserved for composition-only indicators, navigation, and primary actions. Resource lanes and card surfaces stay neutral so the semantic bar and compact status badge remain readable without tinting the entire box.

Primary evidence uses bright KAORI surfaces. Interpretation, review paths, and action guidance use the darker shared Analytics guidance surface.

## Risk and Review Path

Resource Risk Queue includes CPU, memory, pods, and the explicitly labelled Node Filesystem reference. Governance Findings include scheduling-resource findings only. Recommended Review Path remains a separate navigation surface and must not be mixed into findings.

All review URLs use the canonical scoped-link helper so existing query parameters receive `&`, not a second `?`.

## Loading and Client Runtime

Capacity is server-rendered from one committed snapshot and does not use a composite load tracker. The filter owns the page-level HTMX indicator. Capacity does not load Chart.js and has no page-specific chart runtime.
