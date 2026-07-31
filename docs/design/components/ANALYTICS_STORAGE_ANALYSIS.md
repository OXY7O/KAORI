# Analytics Storage Analysis

Status: KAORI domain presentation standard

## Scope Model

Storage Analysis combines evidence with different Kubernetes scopes. The page must never imply that one selector applies to every dataset.

- Top controls: Cluster and Namespace.
- Node is local to the Filesystem tab; Node Filesystem evidence may use Cluster or one selected node.
- PVC evidence follows Namespace scope.
- PV evidence remains cluster-scoped.
- Recommendations: Derived from the owning filesystem, PVC, PV, or baseline evidence.

Every primary panel displays its effective scope. The local Node selector belongs only to Node Filesystem Usage.

## Page Structure

1. Hero with selected cluster, semantic storage posture, highest node pressure, and PVC demand.
2. Controls and Data Readiness with Cluster and Namespace.
3. Bright Storage Analysis Overview with explicit filesystem, PVC, and PV scope.
4. One tabbed workspace containing Capacity & Utilization, Node Filesystem Usage, Persistent Volume Claims, Persistent Volumes, and Storage Recommendations.

## Loading Ownership

Storage does not use a composite page tracker. The page filter owns its HTMX indicator. Filesystem, PVC, and PV are heavy record-oriented panels and load on first tab activation. Hidden tabs do not request or poll. Each loaded panel owns its local filter and pagination indicator.

## Storage Capacity Semantics

Do not describe observed PVC usage as PV used capacity. PersistentVolume evidence is presented as factual provisioning context:

- Provisioned PV Capacity;
- Requested Claim Capacity;
- Observed Claim Usage; and
- Unallocated Provisioned Difference.

A claim-to-provisioning ratio may be displayed only when the label and scope are explicit. It must not be called PV utilization, PV consumed, or PV free capacity.

## Unavailable Evidence

Missing filesystem, PVC, or PV evidence renders semantic `Unknown` and `N/A`. A missing denominator suppresses the progress bar. Zero is displayed only when it is a valid observed value.

## Pressure Threshold

Filesystem and PVC pressure use one threshold contract:

- below 75%: Healthy / Normal;
- 75% through 89.9%: Watch / Warning;
- 90% and above: Critical.

Progress fills remain KAORI Violet. Severity belongs to status labels and operational reading.

## Evidence Record List

Record-oriented Analytics panels use `analytics/components/_evidence_record_list.html` for desktop column headers, responsive rows, mobile labels, semantic status placement, and empty evidence. Local record filters use `analytics/components/_record_filter_bar.html`. Filesystem, PVC, and PV pagination use the global 5/10/25/50 contract and update only the owning panel through HTMX.

## Lifecycle Semantics

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

Reclaim policy is factual configuration. Do not classify `Retain` or `Delete` as healthy or unhealthy without an explicit governance policy.

## URL State

The canonical workspace parameter is `tab` with values `capacity`, `filesystem`, `pvc`, `pv`, or `recommendations`. Do not introduce a second public tab parameter. Local filters and numeric pagination use partial HTMX endpoints while preserving a full-page Storage URL for refresh and sharing.
