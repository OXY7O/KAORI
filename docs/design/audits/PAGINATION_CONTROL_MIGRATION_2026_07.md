# Pagination Control Migration Audit — July 2026

## Scope

The audit inspected every Jinja template containing visible `Previous` or `Next` pagination navigation after application of the global button and pagination-summary standards.

## Result

- 36 pagination-bearing templates were migrated.
- Previous and Next now consume the shared `components/pagination.html` visual contract.
- Active controls use neutral secondary styling with Violet-soft hover behavior.
- Disabled controls preserve geometry and use a muted, non-interactive state.
- Missing Chevron Left and Chevron Right icons were added.
- Page-size selectors in migrated templates consume the shared selector style when their field name exposes `per_page` or `page_size`.

## Preserved behavior

The migration intentionally preserves each page's existing:

- endpoint and query parameters;
- HTMX target, swap, and indicator;
- filter, sort, cluster, namespace, provider, and time-range state;
- page numbering implementation.

## Remaining structural migration

Some pages still render a compact current-page indicator such as `Page 1 of 4` instead of a complete numeric sequence. This is not a style exception for Previous and Next. Numeric-page generation should be consolidated separately once a common pagination data model is available across modules.

## Guardrail

All new pagination navigation must use the shared component. Local visual variants are prohibited.
