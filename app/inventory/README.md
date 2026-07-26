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

## Inventory Presentation Consistency

All resource inventory pages use the shared KAORI table block, loading bar, filter controls, and row-action components. Filter changes replace the complete inventory scope so summary metrics, dependent filter options, and table rows remain synchronized. Pagination replaces table content only. Resource detail actions remain compact neutral actions, while semantic labels use the global status-label mapping.

### Cross-Resource Visual Contract

- Overview and resource summaries use one bordered data block with internal metric cells; do not reintroduce independent decorative cards.
- Resource-name columns use `text-sm` with optional muted supporting text. Use semibold primary text only where the row identity needs emphasis; Workload and Pod rows use regular-weight text, remain icon-free, and overview rows keep the icon only in the Cluster identity column.
- Table row actions use `components/table.html`; semantic labels are compact `rounded-md` labels, never pills. Inventory row labels default to text-only, with tone carrying status meaning instead of decorative icons.
- Resource type, update strategy, quota, and Pod Security values use plain table text when the value is descriptive metadata rather than an operational state.
- Inventory loading indicators use `components/loading_bar.html` and sit directly beneath the block header.
- List services must not compute related-object counts that are not rendered in the current table. Related composition belongs in the detail endpoint.

### Reusable Interaction Contract

- Page-size selectors use the shared `data-kaori-auto-submit` behavior implemented in `app/static/js/pagination.js`; do not add inline `onchange` handlers.
- Long key/value metadata that cannot safely share one row uses `components/detail_object.html::stacked_row`, with the key above the value and explicit wrapping.
- Detail rows use `components/details/_expandable_row.html` and `app/static/js/detail_rows.js`; page-specific inline toggle scripts are not permitted.
- Title Case applies to user-facing inventory metadata labels while Kubernetes identifiers and canonical resource names retain their original casing.
- Remove page-specific partials after their callers migrate to shared components; do not retain unreferenced compatibility templates.


## Presentation Contracts

- Inventory row identity icons are reserved for cluster identity and section-level context. Routine namespace, workload, Pod, owner, role, status, condition, label, and annotation values should remain text-only unless an icon materially improves identification.
- Phase, readiness, restart, and lifecycle states may use compact semantic labels without icons. Pod restart tone is Normal at `0`, Warning at `1–4`, and Critical at `5+`, matching the canonical high-restart rule.
- Kubernetes labels and annotations use compact wrap-safe text labels without decorative icons. Long annotation values must wrap inside the card boundary.
- Type, image policy, volume type, mounted-container names, namespace, workload name, Pod name, and owner values use regular-weight text unless they are the primary cluster identity.
- Topology detail status values are normalized to Title Case before presentation.
