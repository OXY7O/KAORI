# Analytics Workload Analysis

Status: Canonical KAORI Workload Analysis presentation, evidence, and runtime contract

Implementation:

- `app/kubernetes/analytics/workload/service.py`
- `app/kubernetes/analytics/workload/quota.py`
- `app/kubernetes/analytics/workload/mapping.py`
- `app/kubernetes/analytics/workload/domain.py`
- `app/kubernetes/analytics/workload/presentation.py`
- `app/kubernetes/analytics/workload/routes.py`
- `app/templates/kubernetes/analytics/workload/`
- `app/integrations/observability/metrics_source/query_profiles/kubernetes_v1.py`

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

## Tenant Quota Record Detail Modal (Visual UAT #4763)

The Tenant Quota View Details modal reuses `kubernetes/analytics/components/_record_detail_modal.html` with its opt-in `evidence_context=true`, leaving existing record modal callers unchanged. The header follows the standard KAORI hierarchy: domain label, **Committed Snapshot** chip, Namespace title, short description, and factual **Active Pods / Quota Objects** metadata. The footer uses the established evidence icon/source pattern, explicitly indicates **Read Only**, retains committed Workload Analysis provenance, and keeps the Close action accessible on mobile and desktop. Modal interaction, focus, Escape, backdrop dismissal, and content-sized scrolling remain owned by the shared macro.

The ResourceQuota Object Evidence grid uses full available width when a single object is committed, and two columns only for multiple quota objects at desktop sizes. Hard and used keys, missing-key warnings, runtime interpretation, and recommendations remain unchanged. This is presentation only; it cannot manufacture quota usage or runtime demand from unavailable evidence.

## ResourceQuota Evidence Readability and Guide (#4769)

The Tenant Quota Records heading uses the established Violet `info_tip.render(..., variant='guide', placement='right')` beside its title; this is distinct from the Tenant Quota Analysis Guide. The read-only `ResourceQuota Object Evidence` card retains the object name and Hard Key count while organizing **Hard Boundary** and **Observed Used** in bordered evidence panels with aligned semantic `dl/dt/dd` rows, visible row dividers, and readable numeric units. A single quota object spans the full detail region and shows the two evidence panels side by side on desktop. Multiple object cards retain the compact two-column outer layout with vertically stacked inner evidence panels. No quota observations are hidden.

The Workload formatter `format_resource_quota_value` continues to use the existing CPU-core and memory-GiB utilities. It now treats Kubernetes quota `requests.storage`, `requests.ephemeral-storage`, and `limits.ephemeral-storage` as **raw bytes** for display using the existing `bytes_to_gib` function; for example, `107374182400` bytes renders as **`100.00 GiB`**. Recognized count-based quota keys use integer formatting, and original provider resource keys remain visible for correlation. The same representation applies independently to `hard_items` and `used_items`; underlying committed hard/used objects, quota percentages and risk are unchanged. Unknown or absent used keys remain unavailable rather than inferred zero.

## Workload Detail Modal Evidence Hierarchy (#4777)

The **Workload Resource Mapping → View Details** modal now opts into `record_detail_modal.render(..., evidence_context=true)`, reusing the same approved committed-snapshot header/footer as Tenant Quota. Factual Type, Namespace, and Pod count chips are provided from the committed workload row, rather than repeating a long subtitle. This retains the shared dialog, focus, Escape/backdrop/Close, responsive sizing, and read-only provenance semantics. No other modal consumer changes.

The **Evidence Boundary and Request Fit Interpretation** now uses a full-width, three-part guidance surface separated with standard Analytics dividers: Interpretation, How To Read The Bars, and Current vs Selected-Window Peak. The normal/warning/critical threshold badges are preserved and the selected-window Pod Peak Sum remains an upper-bound signal. **Pod Membership** uses its own compact full-width record list with readable Pod identity, bounded overflow for many Pods, and an explicit no-evidence state, rather than occupying a tall side column beside interpretation text. All original CPU/Memory profiles and Recommended Action remain in their prior order.

In the Tenant Quota modal, **Hard Boundary** and **Observed Used** use aligned tabular-value rows with a minimum value column width, full resource label, semantic `dt/dd`, and natural wrapping. Byte-based storage and integer-count resource keys remain normalized exclusively in the authoritative Workload formatter, not with a second conversion in Jinja. Source and risk semantics, including missing versus observed zero, are unchanged. UAT screenshots showing raw `2147483648.00` or integer counts as `2.00` must be checked against the actual running application SHA/data materialization; source at this issue already supports `2.00 GiB` and integer counts.

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
