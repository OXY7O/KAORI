# Kubernetes inventory domain

Inventory stores normalized Kubernetes resource snapshots and presents resource
identity and relationships consistently across clusters.

## Boundaries

- `collector.py` reads and normalizes source data.
- `service.py` owns snapshot persistence, query use cases, and inventory rules.
- `routes.py` handles HTTP/HTMX only.
- `topology/` owns relationship-map construction and presentation.

All-cluster views use database snapshots. Do not introduce hidden live Kubernetes
API calls into list or detail pages.

## Consistency rules

Inventory pages use the same filter, pagination, label, empty-state, and detail
patterns. Default page size is 5 with 5/10/25/50 options. Keep raw payloads and
technical exceptions out of rows; expose only relevant normalized information.
Topology relationships must come from the latest inventory snapshot and preserve
Cluster and Namespace boundaries.

## Template data access

When a template receives a dictionary key whose name overlaps a Python mapping method,
such as `items`, `keys`, or `values`, use bracket access (`payload['items']`). Dot
access can resolve to the mapping method and produce a runtime iterable error.
