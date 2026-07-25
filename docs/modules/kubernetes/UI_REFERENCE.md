# Kubernetes UI Reference

This document contains Kubernetes-specific presentation decisions that must not be treated as global Design System rules.

## Dashboard and analytics

- `All Clusters` represents database snapshot aggregation.
- Live Prometheus and Alertmanager signals require a selected cluster and must be explained explicitly.
- CPU may use Violet and memory Blue inside approved analytics visualizations.
- Cluster health is the primary non-collapsed operational table and may expose resource values, active alerts, source availability, and freshness context.
- Kubernetes Operations Dashboard groups detailed sections into four no-reload tabs: Operations Overview, Capacity & Demand, Signals & Actions, and Reporting.
- Dashboard sections use lazy HTMX loading when their tab becomes visible so hidden categories do not generate unnecessary requests.

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

## Kubernetes Operations Dashboard Expandable Defaults

All expandable dashboard sections are open on initial render. Users may collapse a section after reviewing it, but navigating to the dashboard or loading a tab must not hide operational data behind a closed default state.
- The Signals & Actions tab places Alert Interpretation & Response beside Alerts Summary. The guidance box is open by default and explains severity meaning, source/freshness validation, triage order, evidence review, approved remediation, rollback, and recovery verification.
