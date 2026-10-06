# KAORI Analytics Workload Runtime Audit — 2026-08

## Scope

Reviewed:

- Kubernetes Analytics → Workload Analysis full page and HTMX fragments;
- active-Pod PromQL and ResourceQuota evidence;
- workload identity, requests, limits, QoS, current usage, and selected-window peaks;
- materialization fingerprint and presentation filters;
- Analytics Overview and report consumers;
- code ownership, duplicate logic, legacy surfaces, documentation, and regression contracts.

## Findings and Disposition

### Terminal Pods contaminated active workload evidence

**Before:** request, limit, owner, QoS, usage, and Pod-count queries could retain completed or failed Pods.

**After:** all Workload signals are intersected with `Pending|Running` Pod phase evidence. Active Pod counts no longer use unscoped `kube_pod_info`.

### Duplicate scrape series could inflate values

**Before:** container-level gauges/rates could be summed before duplicate scrape copies were normalized.

**After:** `max by(namespace,pod,container)` removes duplicate copies before namespace or Pod aggregation.

### ResourceQuota objects were flattened

**Before:** namespace/resource keys could overwrite values from another ResourceQuota object.

**After:** hard and used evidence retain `namespace/resourcequota/resource`; every object is evaluated independently. Pressure and runtime-demand outputs identify the controlling object.

### Materialization accepted presentation state

**Before:** routes passed the complete query string into materialization resolution, obscuring the actual snapshot ownership contract.

**After:** `_snapshot_parameters()` permits only `cluster_id` and `time_range`. Namespace, tab, search, filters, and pagination are applied by `presentation.py`.

### Hidden tabs performed unnecessary work

**Before:** hidden content could be requested on initial load and mapping deep links still required a second request.

**After:** the active deep-linked tab renders immediately. Inactive quota/mapping panels request once on first activation.

### Partial endpoints lacked a transport guard

**Before:** a fragment route could be opened as a standalone page and did not publish explicit cache ownership.

**After:** direct navigation redirects to the full workspace. HTMX responses are `no-store`, vary on `HX-Request`, and push the canonical full-page URL.

### Missing evidence could appear healthy

**Before:** an empty finding list could allow aggregate posture to appear healthy, and a synthetic healthy finding obscured missing evidence.

**After:** no evidence is `Unknown`; incomplete evidence is `Limited Evidence`; `Healthy` requires complete tenant and workload evidence. Governance findings contain only factual findings.

### Workload owner collisions

**Before:** aggregation identity omitted owner kind, allowing a Deployment and StatefulSet with the same name to merge.

**After:** canonical identity is `namespace + owner kind + owner name`.

### Monolithic service and duplicate helpers

**Before:** `service.py` exceeded 2,000 lines and mixed provider collection, ResourceQuota domain rules, workload aggregation, presentation filters, pagination, and posture logic.

**After:** ownership is split:

```text
service.py       provider orchestration and committed context
quota.py         ResourceQuota object parsing and tenant evaluation
mapping.py       workload identity and resource evidence evaluation
domain.py        governance findings and aggregate posture
presentation.py  namespace/filter/tab/pagination projection
formatting.py    workload-specific display formatting
routes.py        full-page and HTMX transport boundary
```

`service.py` is below 500 lines and no Workload code-health exception remains.

## Report Boundary

The Workload report still consumes the canonical `WorkloadAnalysisService`, but namespace options are derived from already collected tenant and workload rows. It no longer runs a second namespace-discovery query set.

## Deployment

The PromQL boundary and committed payload schema changed. After deployment, refresh:

```text
analytics.workload + cluster_id + time_range
```

for configured time ranges, or wait for the scheduled Analytics materializer. Old snapshots may still include terminal Pods or flattened ResourceQuota evidence until replaced.

## Validation

The patch adds focused runtime/domain tests and static contracts for:

- independent ResourceQuota objects;
- configured zero quota keys;
- owner-kind identity;
- Unknown/Limited Evidence posture;
- active-Pod/deduplicated PromQL;
- exact materialization parameters;
- lazy deep-link rendering;
- HTMX/cache transport guard;
- report query reuse;
- split module ownership.
