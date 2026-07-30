# Kubernetes Workload Inventory Styling Audit — July 2026

## Outcome

Workload Inventory now follows the canonical Inventory Resource Page Pattern.

## Standardized

- canonical hero with delivery and runtime posture;
- Workload Delivery Posture through the shared Resource Posture Grid;
- compact six-column table;
- dependent Cluster → Namespace → Type → Status filters;
- resource-aware HTMX pagination;
- Inline Expanded Detail with natural height and maximum three columns;
- full-width delivery, placement, and container evidence;
- Related Resource Collection for associated Pods;
- Technical Metadata Collection for labels, annotations, selectors, and tolerations;
- visible committed-snapshot boundary and state-aware guidance.

## Engineering corrections

- summary aggregation uses grouped database counts;
- detail counts related Pods separately and loads only eight preview rows;
- dead associated-Pod template fallback was removed;
- presentation semantics moved from Jinja to the resource service.
