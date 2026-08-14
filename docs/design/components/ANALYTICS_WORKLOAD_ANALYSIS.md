# Analytics Workload Analysis

Status: Canonical KAORI Workload Analysis presentation, evidence, and runtime contract

Implementation:

- `app/analytics/kubernetes/workload/service.py`
- `app/analytics/kubernetes/workload/quota.py`
- `app/analytics/kubernetes/workload/mapping.py`
- `app/analytics/kubernetes/workload/domain.py`
- `app/analytics/kubernetes/workload/presentation.py`
- `app/analytics/kubernetes/workload/routes.py`
- `app/templates/analytics/kubernetes/workload/`
- `app/integrations/prometheus/query_profiles/kubernetes_v1.py`

## Purpose

Workload Analysis combines Namespace ResourceQuota governance with active workload request, limit, QoS, current runtime, and selected-window peak evidence. It must separate configuration facts from runtime observations and must never manufacture a healthy or right-sizing conclusion from missing evidence.

## Workspace Composition

```text
Hero
Controls & Data Readiness
Quick Workload Overview
Integrated Tabbed Detailed Workspace
├── Tenant Quota Analysis
├── Workload Resource Mapping
└── Workload Recommendations
```

The active deep-linked tab renders in the initial full-page response. Inactive Tenant Quota and Workload Mapping panels load only on first tab activation through HTMX. Hidden panels do not request, poll, or materialize a second snapshot.

## Materialization and Presentation Ownership

Committed dataset identity:

```text
analytics.workload
+ cluster_id
+ time_range
```

The following values are presentation state and must not create snapshot variants:

- Namespace;
- active tab;
- tenant/workload search;
- quota status, configuration, QoS, type, and risk filters;
- page number;
- rows per page.

`service.py` owns provider orchestration and committed payload construction. `presentation.py` owns namespace scoping, local filters, active-tab state, pagination, option lists, and presentation-scoped recommendations.

## Active-Pod Evidence Boundary

All Workload runtime, request, limit, owner, and QoS evidence is restricted to Pods whose phase is `Pending` or `Running`.

Terminal Pods must not affect:

- active Pod counts;
- namespace runtime demand;
- request or limit coverage;
- workload mapping;
- QoS distribution;
- current usage;
- selected-window peak evidence.

PromQL must intersect each workload series with the canonical active-Pod identity:

```promql
max by (namespace, pod) (
  kube_pod_status_phase{phase=~"Pending|Running"} == 1
)
```

## Duplicate-Series Handling

Kube-state-metrics, kubelet, and cAdvisor series may be scraped through multiple targets. Gauge and rate inputs must be normalized with `max by` at their canonical identity before aggregation.

Canonical identities:

```text
Resource requests/limits : namespace + pod + container
Container usage          : namespace + pod + container
Pod phase                : namespace + pod
Pod owner                : namespace + pod + owner kind + owner name
Pod QoS                  : namespace + pod + QoS class
ResourceQuota            : namespace + ResourceQuota object + resource + type
```

Do not sum duplicate scrape copies.

## ResourceQuota Object Semantics

ResourceQuota evidence is retained per object:

```text
namespace
└── resourcequota
    └── resource
        ├── hard
        └── used
```

Multiple ResourceQuota objects are evaluated independently. Their hard values must not be flattened into one arbitrary namespace-level map.

- **Quota Pressure** is the highest valid `used / hard` ratio from a specific quota object and resource.
- **Runtime Demand** is active-Pod demand against the most restrictive positive applicable hard boundary and names the owning quota object.
- A configured quota key with numeric value `0` remains configured. Missing-key detection checks key presence, not truthiness.
- A zero or missing denominator does not produce `0%`; it produces unavailable evidence.
- The UI shows the quota object count and object names so the operator can identify the controlling boundary.

## Request and Limit Coverage

Request Coverage:

- `Complete`
- `Partial`
- `Missing`
- `Unknown`

Limit Coverage:

- `Complete`
- `Memory Limit Missing`
- `CPU Limit Unset`
- `Limits Unset`
- `Partial`
- `Unknown`

Missing CPU or memory requests are high-risk because scheduling and right-sizing depend on them. Missing memory limits are warning-level governance evidence. `CPU Limit Unset` is factual information by default unless a separate policy explicitly requires CPU limits.

## Workload Identity

A workload aggregate key includes:

```text
namespace + owner kind + owner name
```

Owner kind is mandatory. A Deployment and StatefulSet with the same name in one namespace must remain separate records. ReplicaSet owners are normalized to their Deployment name where the owner relationship supports it. Pod-name inference is a fallback only when owner evidence is absent.

## QoS Semantics

Kubernetes QoS is factual metadata:

- `Guaranteed`
- `Burstable`
- `BestEffort`
- `Mixed`
- `Unknown`

QoS uses metadata-label treatment. Risk remains owned by Request Coverage, Limit Coverage, runtime evidence, and the dedicated Risk field.

## Analytics Evidence Coverage

Every workload record exposes runtime Evidence Coverage:

- `Complete`: every active Pod has current CPU, current memory, selected-window CPU peak, and selected-window memory peak observations.
- `Partial`: at least one signal exists, but the complete four-signal set is not available for every active Pod.
- `Unavailable`: no usable complete runtime and selected-window evidence is available.

Right-sizing is active only when Evidence Coverage is `Complete`. Partial or unavailable evidence must defer increase/reduction recommendations.

## Runtime Terminology

Instant observations are labeled `Current Usage`.

The selected-window aggregate is labeled `Selected-Window Pod Peak Sum`. It is an upper-bound signal because individual Pod peaks may occur at different timestamps. It must not be described as a simultaneous workload peak or an average.

CPU and Memory request utilization remain separate. Do not calculate one averaged `Efficiency` value.

## Aggregate Posture

Allowed states:

- `Critical`
- `Watch`
- `Limited Evidence`
- `Healthy`
- `Unknown`

`Healthy` is allowed only when tenant quota and workload evidence are complete and no actionable governance finding exists. No records means `Unknown`, not `Healthy`. Incomplete quota pressure, runtime demand, requests, or selected-window metrics means `Limited Evidence` unless a stronger warning or critical finding already exists.

Governance findings contain only factual findings. Do not create a synthetic “no findings” row to force a positive posture.

## Filters, Pagination, and URL Ownership

Normal links target the full page:

```text
/analytics/workload?tab=quotas
/analytics/workload?tab=mapping
```

HTMX partial endpoints:

- require `HX-Request: true`;
- redirect direct navigation to the full page;
- return `Cache-Control: no-store, max-age=0`;
- vary on `HX-Request`;
- push the canonical full-page URL.

Cluster, Namespace, Time Range, active tab, local filters, and 5/10/25/50 page-size choices remain in the browser URL. Local filters do not change top-level scope summary cards.

## Surface Hierarchy

- Summary metrics, scope context, quota evidence, workload records, and expanded CPU/Memory evidence use bright surfaces.
- Operational Reading, Recommended Action, and interpretation guidance use the darker Analytics guidance surface.
- Semantic status is carried by shared labels, not by tinting entire rows.
- Workload uses the same integrated workspace composition as Storage Analysis: the workspace header, tabs, and active panel share one `analysis_workspace.tabbed(...)` surface. Active panel content is rendered inside the workspace body rather than as a detached sibling card.
- Tenant Quota Analysis and Workload Resource Mapping use a plain panel heading followed by shared evidence/record surfaces, matching the Storage Analysis panel hierarchy. Workload Recommendations uses the shared evidence shell for recommendation rows and pager, so no second top-level snapshot card competes with the workspace shell.
- Missing values render `N/A`, use Unknown semantics, and suppress progress bars.

## Recommendation Destinations

Recommendations deep-link to the owning tab and filter context:

- missing ResourceQuota → Quotas / Missing;
- incomplete requests → Mapping / Requests Missing or Requests Partial;
- BestEffort → Mapping / BestEffort;
- right-sizing review → Mapping / relevant Risk;
- general practices → Recommendations.

## Prohibited Patterns

- No terminal Pod evidence in active workload metrics.
- No duplicate-scrape summation before identity normalization.
- No namespace-level ResourceQuota flattening that loses object identity.
- No snapshot variants for namespace, filters, tab, or pagination.
- No right-sizing recommendation when Evidence Coverage is not Complete.
- No synthetic zero for missing denominator or missing observation.
- No synthetic healthy finding.
- No composite CPU/Memory Efficiency value.
- No CSS class in domain status payloads.
- No semantic tone inference in Jinja.
- No QoS health coloring.
- No partial endpoint as a normal full-page destination.
- No compatibility aliases for retired workload fields.
