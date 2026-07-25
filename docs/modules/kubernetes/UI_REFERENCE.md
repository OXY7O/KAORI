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
- Workload Inventory is a resource-specific exception: the `State` column uses ordinary table text rather than a semantic label, while detailed runtime state may retain richer semantic presentation.
- Primary resource cells use a compact `28 × 28 px` icon container when the row title has one text line. A `32 × 32 px` container is reserved for cells that can render a second supporting line, such as a node hostname.
- Workload, Namespace, Pod, Service, Ingress, Storage, and Configuration resource-name cells use the compact single-line icon treatment. Node rows retain the two-line icon treatment because hostname may appear below the node name.
- UUIDs, IP addresses, and runtime identifiers use sans-serif with safe wrapping in ordinary detail cards.
- Missing data never renders as healthy.

## Operations and governance

- Live Kubernetes selectors use HTMX where appropriate and must not force a full-page reload.
- ConfigMap, Secret, and TLS Secret workflows use live Kubernetes authority according to their module contract.
- Live lookup failures present concise UI feedback and record technical evidence in Activity Audit Log.
- Destructive and security-sensitive actions use their established confirmation, permission, CSRF, audit, and notification flows.

Detailed page fields, table columns, and action names belong in the relevant Kubernetes module README rather than this summary.
