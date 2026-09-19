# KAORI Analytics and Inventory UI Convergence

This document is the canonical UI contract that keeps Kubernetes Analytics and
Kubernetes Inventory inside one KAORI product language.

Analytics may introduce charts, evidence interpretation, and domain-specific
workflows. It must not introduce a second palette, table system, filter system,
pagination grammar, or action hierarchy.

## Canonical ownership

The shared UI owners are:

```text
app/templates/components/table_primitives.html
app/templates/components/table.html
app/templates/components/pagination.html
app/templates/components/table_label.html
app/templates/analytics/components/_analysis_surfaces.html
app/templates/kubernetes/analytics/components/_analysis_workspace.html
app/templates/kubernetes/analytics/components/_evidence_record_list.html
app/templates/kubernetes/analytics/components/_record_filter_bar.html
app/templates/analytics/components/_record_pagination.html
```

Inventory and Analytics must consume the same global tokens from
`frontend/styles.css`. The `.kaori-analytics-page` marker may identify an
Analytics workspace for JavaScript and contract tests, but it must not redefine
surface, outline, or typography tokens.

## Palette contract

The global KAORI palette applies to both domains:

- page, card, muted, hover, and selected surfaces use the same Violet-tinted
  neutral system;
- section identity uses KAORI Violet;
- semantic colors remain reserved for operational status;
- dark mode uses the same global KAORI dark surfaces and outlines.

Analytics must not replace these tokens with a slate or gray workspace palette.
Domain differentiation belongs in charts, semantic badges, compact role icons,
and analytical copy.

## Table and evidence-record contract

Inventory tables are the visual reference. Analytics record collections may use
responsive grid rows when expanded evidence is required, but their shell must
remain visually equivalent to the Inventory table system:

- `rounded-xl` outer shell;
- `border-outline-default` and `shadow-sm`;
- header row on `bg-surface-hover`;
- left-aligned headers and right-aligned action column;
- `hover:bg-kaori-mist` row interaction;
- canonical identity cell from `components/table_primitives.html`, exposed through `components/table.html` for Inventory;
- canonical empty state;
- default page size `5`, options `5/10/25/50`.

A page must not create a local table header, row-hover color, action-button
style, or pagination footer.

## Pagination wording

All Inventory and Analytics record collections use this grammar:

```text
Showing 1–4 of 4 Nodes    Rows [5]    Previous  1  Next
```

The resource label is mandatory and singularizes when the count is one.
`Rows` is the only page-size label. Text such as `Scope Contains`, `Filtered
Records`, `Page Size`, or domain-specific alternatives is not allowed.

The shared footer styling is owned by `components/pagination.html`.

## Filter contract

Analytics record filters use the same label, input, select, focus, and hover
classes as Inventory:

- visible label above every field;
- explicit `for` and `id` association;
- `h-10`, `rounded-md`, and global KAORI outline tokens;
- Violet focus border and soft focus ring;
- `bg-surface-hover` filter region;
- filters align on one row at desktop when the available width permits it.

## Guidance and review paths

Analytical guidance remains domain-specific but uses Inventory-compatible
container geometry:

- one bordered card, not multiple competing nested accent boxes;
- Violet for review-path identity and navigation;
- semantic color only for the actual finding or status;
- review links render as rows separated by subtle dividers;
- hover uses `bg-kaori-mist`;
- title, description, and action hierarchy match KAORI table/detail patterns.

## Exceptions

Charts, forecast canvases, topology-like analytical diagrams, and dense
methodology panels may differ structurally. Their surrounding shell, header,
typography, controls, status badges, and actions must still use the canonical
KAORI components.
