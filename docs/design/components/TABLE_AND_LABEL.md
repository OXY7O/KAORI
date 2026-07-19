# KAORI Table and Compact Label Standard

## Table alignment

- Headers and body cells are left aligned by default.
- The final column is right aligned.
- Action controls in the final column are grouped against the right edge.
- Ordinary operational values, labels, and status descriptions are not centered.
- A domain-specific visualization may deviate only when the exception is documented by the owning module.

## Density and pagination

- Default page size: 5.
- Available sizes: 5, 10, 25, and 50.
- Headers render once.
- Filters and table belong to one coherent content block unless the page pattern explicitly requires separation.
- Row expansion uses shared detail patterns rather than custom per-table mechanics.

## Compact labels

`app/templates/components/table_label.html` is authoritative.

### Status labels

- Use the semantic family matching the operational state.
- Minimum height: 24 px.
- Horizontal padding: 8 px.
- Vertical padding: 2 px.
- Text: 10 px, semibold.
- Line height: 16 px.
- Internal gap: 4 px.
- Icon: 12 px.
- Radius: 6 px (`rounded-md`).
- Borderless.

### Metadata labels

- Use Primary Violet for identity and context.
- Use the same geometry as status labels.
- Environment, provider, scope, resource type, and neutral count are metadata rather than status.
- Labels are rectangular and never pills.

Timestamps are plain text, not compact labels. Do not create page-specific badge sizes.
