# Expanded Inventory Detail

## Purpose

Provide one polished, reusable row-owned detail experience for every Kubernetes Inventory table.

## Shared owners

- `components/details/_expandable_row.html`
- `components/details/_detail_content.html`
- `app/static/js/detail_rows.js`

## Action contract

- closed label: `View Details`;
- open label: `Close Details`;
- eye icon in the closed state;
- close icon and rotated chevron in the open state;
- one open row per resource group;
- `aria-expanded` and `aria-controls` are mandatory.

## Workspace contract

Every fetched detail uses the shared expanded workspace outer, shell, header, and icon classes. Content order is:

```text
Resource Header
Summary Strip
Adaptive Evidence
Relationships and Metadata
Committed Snapshot Boundary
State-Aware Guidance
```

The detail is visually separated from the table with a subtle Violet boundary without becoming a second page hero.
