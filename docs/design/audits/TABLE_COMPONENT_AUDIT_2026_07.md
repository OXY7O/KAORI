# KAORI Table Component Audit — July 2026

## Scope

The audit inspected all HTML templates under `app/templates/` in the cumulative KAORI source after the global button and pagination migrations.

Observed scope:

- 53 template files containing tables.
- 57 table elements.
- Kubernetes inventory, analytics, integrations, operations, governance, reports, intelligence, notifications, users, roles, and provider administration.

## Findings before this migration

- 31 table templates applied uppercase transformation and expanded letter spacing to column headers.
- Header typography varied between 10 px, 11 px, and 12 px and between primary Violet and muted content colors.
- Several table-local actions used long labels, including a three-word cluster settings action.
- Loading indicators were implemented using both block-level bars and absolute overlays attached to headers.
- Status and metadata labels are mostly routed through shared semantic helpers, but legacy `rounded-full` usage still exists in mixed-purpose table templates and requires context-sensitive review because some occurrences represent progress dots or non-label decoration.
- Final-column right alignment is broadly present in primary inventory tables but is not yet generated from one universal table renderer.

## Changes in this patch

- Expanded the authoritative table documentation into a complete Table, Data Block, and Compact Label Standard.
- Added `app/templates/components/table.html` as the shared presentation contract for table blocks, loading bars, filters, headers, cells, resource titles, and compact actions.
- Removed force-uppercase and expanded tracking from table headers across all audited table templates.
- Normalized legacy 10 px table-header typography to 11 px where the class was declared directly on `<thead>`.
- Shortened the Prometheus cluster action from `Open cluster settings` to `Open Settings`.
- Added automated guardrails for header casing, shared component availability, alignment rules, filter geometry, action geometry, and documentation coverage.

## Intentionally not mass-rewritten

The audit did not replace every table with a single rendering macro. Domain tables have different row structures, responsive priorities, HTMX targets, expandable content, and authorization controls. A blind renderer migration would risk functional regressions.

The following remain controlled migration work:

- importing shared table classes into every existing table;
- context-sensitive replacement of legacy `rounded-full` occurrences;
- moving all table-region loading indicators below their block headers;
- shortening every row-action label after verifying its domain meaning;
- adding `scope="col"` and `aria-busy` where missing;
- consolidating repeated filter markup into a shared filter-field component.

New tables must use the shared component immediately. Existing tables should be migrated by module while preserving endpoint, filter, sort, permission, and HTMX behavior.

## Compliance status

- Table-header casing and tracking: migrated globally.
- Shared visual contract: available and documented.
- Default page size and numeric pagination: already standardized.
- Compact semantic labels: shared helper already available.
- Full shared-component adoption: in progress by module.
- Loading-bar placement: requires targeted module migration.
- Accessibility completion: requires targeted module migration.


## Guidance addendum: contextual density and action flexibility

The standard was refined after design review to avoid over-standardizing decoration. Two-line resource title cells now use a larger icon container, while single-line cells retain the compact icon geometry. Table typography is constrained to one application font family and an approved size hierarchy. Icons and compact labels are explicitly optional and must be chosen for semantic value rather than applied to every cell.

The preferred action count remains two, but a row may expose more than two actions when the controls fit without wrapping, remain high-frequency and concise, and do not overpower the row data. All ordinary non-CRUD actions use the same neutral utility color and interaction behavior; CRUD actions may use semantic variants while preserving identical geometry.
