# KAORI Detail Styles

## Detail Style 1 — Inline Expanded Detail

Semantic key: `inline-expanded`

Shared owners:

- `components/details/_expandable_row.html`
- `components/details/_detail_content.html`

Use this style when a table row owns a dense detail view that benefits from the full table width. The Node Inventory page is the canonical reference.

### Required behavior

- one expanded row per detail group;
- compact `View Details` row action;
- on-demand detail request;
- summary first, then domain cards, metadata, and operational context;
- two columns on ordinary laptop widths and up to three columns on larger screens;
- visible data boundary and state-aware next action;
- `data-kaori-detail-variant="inline-expanded"` on the detail root.

Do not use Inline Expanded Detail for a short identity summary that fits better in the shared right-side drawer. A new detail style requires a materially different information architecture and shared owner.
