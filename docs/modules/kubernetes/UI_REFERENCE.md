# Kubernetes UI Reference

This document contains Kubernetes-specific presentation decisions that must not be treated as global Design System rules.

## Dashboard and analytics

- `All Clusters` represents database snapshot aggregation.
- Live Prometheus and Alertmanager signals require a selected cluster and must be explained explicitly.
- CPU may use Violet and memory Blue inside approved analytics visualizations.
- Cluster health is the primary non-collapsed operational table and may expose resource values, active alerts, source availability, and freshness context.

## Topology

- Relationship and resource-node colors may differ inside the graph and legend where color distinguishes data categories.
- Those graph colors do not leak into generic buttons, filters, labels, or navigation.
- Loading uses Info/Pending, truncation uses Warning, startup failure uses Critical, and unknown resource state uses Neutral.

## Inventory pages

- Kubernetes resource inventory pages consume the shared Inventory List and Expandable Detail patterns.
- Resource-specific columns, metrics, nested objects, and actions are maintained by the owning inventory specification or route README.
- Cluster, namespace, role, workload type, update strategy, object counts, labels, and annotations are descriptive metadata.
- Readiness, lifecycle, pressure, scheduling, collection availability, quota state, and other dynamic conditions use semantic labels.
- UUIDs, IP addresses, and runtime identifiers use sans-serif with safe wrapping in ordinary detail cards.
- Missing data never renders as healthy.

## Operations and governance

- Live Kubernetes selectors use HTMX where appropriate and must not force a full-page reload.
- ConfigMap, Secret, and TLS Secret workflows use live Kubernetes authority according to their module contract.
- Live lookup failures present concise UI feedback and record technical evidence in Activity Audit Log.
- Destructive and security-sensitive actions use their established confirmation, permission, CSRF, audit, and notification flows.

Detailed page fields, table columns, and action names belong in the relevant Kubernetes module README rather than this summary.

### Inventory table row presentation

- Inventory table bodies follow the Resources By Cluster reference: ordinary row values use `text-sm` with `leading-5`, primary resource names use `text-sm font-semibold`, supporting context uses `text-xs`, and compact metadata or semantic labels retain the shared 10 px label contract.
- Every inventory Cluster cell uses the shared two-line cluster identity from Resources By Cluster: 32 × 32 px server icon, cluster name as the primary line, and the normalized environment as supporting text. Cluster identity is not rendered as a metadata label.
- Single-line resource-name cells use a 28 × 28 px icon container with a 16 × 16 px Lucide icon. Supporting text must not be added merely to fill icon height.
- Workload type remains violet descriptive metadata, while update strategy uses the blue Info semantic treatment so the two adjacent labels are visually distinguishable. Workload state is rendered as ordinary text.
- Ingress host data is available in expandable details and is not duplicated in the main inventory table.
- Storage capacity is ordinary text without a label or icon.
- Configuration type remains violet descriptive metadata. Immutable is Warning/amber and Mutable is Normal/green so mutability is distinct from object type.
- Node resource cells follow the same single-line name-cell geometry as other inventory pages. Hostname context remains in details instead of creating inconsistent two-line rows.
