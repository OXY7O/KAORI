# KAORI Table Component Re-Audit — July 2026

## Scope

The re-audit inspected the cumulative KAORI source after the global button, pagination, table-standard, inventory summary fix, and table-guidance refinement patches.

Observed scope:

- 53 template files containing tables.
- 57 table elements.
- Kubernetes inventory, analytics, integrations, operations, governance, reports, intelligence, notifications, users, roles, and provider administration.

## Re-audit findings

The first table-standard migration established the shared contract but left several visual inconsistencies in existing templates. The re-audit found:

- 28 direct arbitrary table typography declarations using 10 px or 11 px values.
- 19 table headers that still inherited legacy uppercase or expanded-tracking declarations in their opening `<thead>` markup.
- Multiple inventory and integration table headers using Primary Violet text instead of the standard muted column-label color.
- Routine table actions using provider-blue or page-local styling instead of the shared neutral utility appearance.
- Visible action labels longer than two words, including `View Catalog Rule`, `Open Scope Workspace`, `Run Full Validation`, `Open Full Record`, and role-management labels.
- Existing title cells and labels remain context-dependent; a blind global insertion of icons or labels would reduce scanability and was intentionally avoided.
- Center alignment remains only for full-width empty-state cells, matrix controls, and other documented non-data exceptions. Ordinary data cells remain left aligned and final action cells remain right aligned.

## Adjustments completed

- Normalized every directly declared `<thead>` size to the approved `text-xs` table-header level.
- Removed force-uppercase and expanded tracking from all audited `<thead>` opening tags.
- Normalized direct table-header weight to semibold.
- Replaced Primary Violet table-header text with the standard muted content color.
- Normalized the remaining 10 px ordinary detail cell to the approved supporting-text size.
- Shortened visible table action labels while preserving meaning:
  - `View Catalog Rule` → `View Rule`.
  - `Open Scope Workspace` → `Open Scope`.
  - `Run Full Validation` → `Run Validation`.
  - `View Full Audit` → `View Audit`.
  - `View all reports` → `View Reports`.
  - `Archive & cleanup` → `Archive Data`.
  - `Open Full Record` → `View Record`.
  - `Edit custom role` → `Edit Role`.
  - `Delete custom role` → `Delete Role`.
- Replaced the legacy provider-blue Integrations row action with the shared neutral utility interaction pattern.
- Normalized Users row utility actions and the TLS record action to the same compact neutral geometry, hover, focus, pointer, and disabled behavior.
- Preserved Critical styling for destructive actions and preserved domain behavior, URLs, HTMX targets, permissions, and filters.

## Contextual exceptions retained

The following are valid exceptions and are not treated as alignment violations:

- A `colspan` empty-state cell may be centered because it represents the complete table body rather than one data column.
- Permission matrices may center binary controls when comparison across rows and columns requires it.
- Expanded detail content may contain semantic cards and labels that do not represent ordinary row cells.
- Technical identifiers may use monospace only when the format itself benefits from fixed-width presentation.
- More than two visible actions remain permitted when the documented width, frequency, and scanability conditions are satisfied.

## Compliance status after re-audit

- Shared table visual contract: available and documented.
- Table-header size, casing, tracking, weight, and semantic color: normalized across the audited templates.
- Ordinary table action appearance: normalized in identified legacy implementations.
- Known visible table action labels longer than two words: corrected.
- Contextual icon and label usage: retained; no decorative mass insertion performed.
- Default page size and numeric pagination: standardized through the shared pagination component.
- Full migration of every table markup fragment to `table_ui.*`: still incremental because domain-specific HTMX, expandable rows, sorting, permissions, and responsive priorities differ.
- Loading-bar placement: remains a targeted module-level review item where legacy asynchronous regions do not yet use the shared block structure.
- Accessibility completion: remains incremental for legacy tables missing `scope="col"`, `aria-sort`, or region-level `aria-busy`.

## Forward guidance

New tables must use the shared table component and the authoritative guidance in `docs/design/components/TABLE_AND_LABEL.md`. Existing tables should be migrated when their module is changed, but every migration must preserve routes, query state, authorization, HTMX behavior, and domain-specific responsive priorities.
