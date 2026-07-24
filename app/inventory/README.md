# Kubernetes inventory domain

Inventory stores normalized Kubernetes resource snapshots and presents resource
identity and relationships consistently across clusters.

## Boundaries

- `collectors/` reads Kubernetes APIs and normalizes resource payloads.
- `persistence.py` writes one inventory generation atomically.
- `synchronization.py` owns collection orchestration and commits the generation marker.
- `resources/` owns read use cases for lists, filter options, summaries, details, and SQL pagination.
- `routes.py` handles HTTP/HTMX concerns and validates request filters.
- `topology/` owns relationship-map construction and presentation.

All-cluster views use database snapshots. Do not introduce hidden live Kubernetes
API calls into list, summary, detail, or topology pages.

## Committed-generation invariant

`ClusterInventory.collected_at` is the committed generation marker for a cluster.
Every read of a generation-scoped inventory model must pass through
`filter_current_generation`, including:

- table rows and summary aggregates;
- dependent filter options;
- detail drawers and related-object counts;
- overview totals and per-cluster counts;
- topology nodes and relationships.

This prevents an incomplete, stale, or superseded generation from being mixed with
the active snapshot. `Cluster` and `ClusterInventory` themselves are not filtered by
this helper because they define cluster identity and the generation marker.

## HTMX filter scope

Resource filters replace the complete `*-inventory-scope` block. The scope contains
both summary cards and the table card so totals always describe the active filters.
Pagination replaces only `*-table-content`; it must not rebuild filter options or
summary cards. Resource services must use `app.common.pagination.paginate_query`
so only the requested ORM rows are materialized. Summary cards may use lightweight
filtered projections, but routes must never call `.all()` and slice the full result.
A cluster change must rebuild dependent namespace, status, type, role, owner, node,
or class options from the same committed generation.

## Consistency rules

Inventory pages use the same filter, pagination, label, empty-state, and detail
patterns. Default page size is 5 with 5/10/25/50 options. Keep raw payloads and
technical exceptions out of rows; expose only relevant normalized information.
Topology relationships must come from the latest committed snapshot and preserve
Cluster and Namespace boundaries.

Workload Pod configuration is authoritative only when supplied by the workload
collector's schema-v2 `pod_template`. Do not infer configuration from runtime Pods;
a missing template is an explicit unavailable state and requires a fresh sync.

## Template data access

When a template receives a dictionary key whose name overlaps a Python mapping method,
such as `items`, `keys`, or `values`, use bracket access (`payload['items']`). Dot
access can resolve to the mapping method and produce a runtime iterable error.
