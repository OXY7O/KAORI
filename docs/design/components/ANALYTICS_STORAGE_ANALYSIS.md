# Analytics Storage Analysis

Status: KAORI domain presentation and evidence standard

## Scope Model

Storage Analysis combines evidence with different Kubernetes scopes. The page must never imply that one selector or denominator applies to every dataset.

- Top controls own Cluster and Namespace.
- Node is local to the Filesystem tab.
- PVC evidence follows Namespace scope.
- PV evidence remains cluster-scoped.
- Recommendations link back to the owning Filesystem, PVC, PV, or Capacity tab.

Every primary panel displays its effective scope. Namespace and Node are presentation filters over one committed cluster snapshot; they do not create additional materialization variants.

## Runtime Ownership

The browser reads only committed `analytics.storage` snapshots. Provider queries run in the Analytics worker through these boundaries:

1. `app/analytics/storage/evidence.py` collects every registered signal once.
2. `app/analytics/storage/parsing.py` normalizes Prometheus labels and duplicate series.
3. `app/analytics/storage/domain.py` derives rows, evidence availability, lifecycle risk, pressure, and aggregate posture.
4. `app/analytics/storage/presentation.py` applies Namespace, Node, local filters, independent pagination, and view models.
5. Jinja templates render the presentation model and do not implement thresholds or business decisions.

The materialized fingerprint is cluster-only:

```text
analytics.storage + cluster_id
```

Namespace, Node, tab, search, status, StorageClass, page, and page size are URL/presentation state only.

## Query and Evidence Contract

The Storage collector issues each canonical query one time per materialization run. It does not run aggregate totals and then repeat the same provider query per row.

Core transport capabilities:

- `instant_query`
- `kubernetes_identity`

Filesystem and PVC observation capabilities are advisory. A missing advisory capability degrades the affected evidence domain without blocking unrelated Storage evidence.

The page may therefore render:

- complete filesystem evidence with unavailable PVC evidence;
- complete PVC/PV inventory with unavailable filesystem evidence; or
- any other partial combination.

Missing evidence remains `Unknown` or `N/A`; it must never be converted to zero or Healthy.

## Filesystem Semantics

The preferred mountpoint is `/var`, with `/` as the fallback. A mountpoint is usable only when both size and available-byte signals exist for the same node.

- A size sample without available bytes is incomplete evidence.
- An available-byte sample without size is incomplete evidence.
- Incomplete rows do not enter aggregate used, free, utilization, or highest-pressure calculations.
- Duplicate scrape series use the maximum value for the same node and signal rather than being summed.
- The selected mountpoint is displayed in Hero, Overview, record rows, recommendations, and reports.

## PVC Capacity Semantics

Requested capacity, observed volume capacity, used bytes, and available bytes are distinct signals:

- **Requested Capacity** is Kubernetes demand from `kube_persistentvolumeclaim_resource_requests_storage_bytes`.
- **Observed Capacity** is the volume filesystem capacity reported by `kubelet_volume_stats_capacity_bytes`.
- **Observed Usage** is `kubelet_volume_stats_used_bytes`.
- **Observed Available** is `kubelet_volume_stats_available_bytes`.

PVC pressure uses:

```text
observed used bytes / observed volume capacity bytes
```

Requested capacity is never used as the pressure denominator. It remains factual demand evidence and may differ from the mounted volume capacity during expansion, driver reporting, or lifecycle transitions.

If observed available bytes are missing but observed capacity and used bytes are complete, free bytes may be derived as `capacity - used` and must be labeled as derived. Missing capacity or used bytes suppresses the pressure bar.

## PersistentVolume Provisioning Semantics

Do not describe observed PVC usage as PV used capacity. PersistentVolume evidence is factual cluster provisioning context:

- Provisioned PV Capacity;
- Requested Claim Capacity;
- Observed Claim Usage; and
- Unallocated Provisioned Difference.

Each comparison value has its own availability flag. Missing claim evidence does not hide valid PV inventory or capacity evidence.

A claim-to-provisioning ratio may be displayed only when its boundary is explicit. It must not be called PV utilization, PV consumed, or PV free capacity.

## Lifecycle and Posture Semantics

PVC lifecycle:

- Bound → Normal;
- Pending → Warning;
- Lost → Critical;
- other or missing → Unknown.

PV lifecycle:

- Bound → Normal;
- Available → Info;
- Released → Warning;
- Failed → Critical;
- other or missing → Unknown.

The row risk uses the highest observed severity across lifecycle and pressure. Lifecycle risk cannot be cleared by a healthy pressure value: a Lost claim or Failed volume remains Critical even when usage evidence is missing. Critical pressure also remains Critical when a claim is Pending or its lifecycle is unknown.

Aggregate posture is:

- **Critical** when any critical filesystem, PVC, or PV signal exists;
- **Watch** when warning signals exist and no critical signal exists;
- **Healthy** only when Filesystem, PVC, and PV evidence domains are complete and no active risk exists;
- **Limited Evidence** when at least one domain is observed but the three-domain contract is incomplete;
- **Unknown** when no committed Storage evidence is available.

An observed empty inventory is a valid zero-resource state. It displays `0`, `No Claims`, or `No Volumes`, not `N/A`.

## Pressure Threshold

Filesystem and PVC pressure use one threshold contract:

- below 75%: Healthy / Normal;
- 75% through 89.9%: Watch / Warning;
- 90% and above: Critical.

The Python domain model owns these thresholds. Jinja does not recalculate them. Progress fills remain KAORI Violet; semantic severity belongs to status labels and operational interpretation.

## Loading and URL Ownership

Storage does not use a composite page tracker. The page filter owns its HTMX indicator.

- Capacity and Recommendations are rendered with the page.
- Filesystem, PVC, and PV load on first activation when hidden.
- A directly requested deep-link tab is rendered immediately and does not first render a lazy placeholder.
- Lazy requests preserve active local search, status, StorageClass, page, and page size.
- Cluster or Namespace changes preserve the canonical `tab` parameter.
- Direct navigation to a partial endpoint redirects to the complete Storage page.
- Partial responses use `Cache-Control: no-store, max-age=0` and `Vary: HX-Request`.

The canonical workspace parameter is `tab` with values `capacity`, `filesystem`, `pvc`, `pv`, or `recommendations`. Do not introduce a second public tab parameter.

## Evidence Record and Pagination Standard

Record-oriented panels use:

- `analytics/components/_evidence_record_list.html`
- `analytics/components/_record_filter_bar.html`
- `analytics/components/_record_pagination.html`

Filesystem, PVC, and PV pagination is independent and follows the global 5/10/25/50 contract. Full-page links and partial HTMX endpoints must preserve the owning panel state.

## Report Compatibility

Storage report payloads consume the same collector and presentation model as the page. PDF evidence labels must use **Observed Volume Capacity** as the PVC pressure boundary. Reports may show Requested Capacity separately, but must not describe used percentage as “of requested”.

After a PromQL or evidence-contract deployment, rematerialize `analytics.storage` for each cluster or wait for the scheduled Analytics worker to replace older committed snapshots.
