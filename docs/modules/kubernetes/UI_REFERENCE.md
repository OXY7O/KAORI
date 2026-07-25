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

### ConfigMap View & Update Sidebar

The View & Update ConfigMap page uses a dedicated sticky right rail on desktop. The right rail contains the KAORI Flow panel followed by the standard Update Guardrails panel. Both panels remain visible while the operator reviews or edits long ConfigMap content. The KAORI Flow communicates the controlled update sequence; Update Guardrails uses the standard neutral KAORI section header and compact guardrail rows. The main selection, editor, and action surfaces remain in the left content column.


### ConfigMap Create and Update Sidebar Layout

- **Create Kubernetes ConfigMap** and **View & Update ConfigMap** use the same two-column operational layout.
- The left column is an independent `space-y-6` content stack so adjacent workflow cards keep a fixed 24 px vertical gap and are not stretched by the right sidebar.
- The right column contains **KAORI Flow** followed by the operation-specific **Create Guardrails** or **Update Guardrails** panel.
- The complete right sidebar uses `xl:sticky xl:top-6`; sticky positioning is applied to the sidebar wrapper, not to individual grid rows.
- Do not use a multi-row spanning sidebar for these pages because spanning content can influence grid track sizing and create excessive vertical distance between left-column sections.
