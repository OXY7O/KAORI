# Side Drawer

## Purpose

The Side Drawer displays detailed context for a selected row without expanding the table or navigating away from the current comparison view.

Shared implementation:

```text
app/templates/components/side_drawer.html
```

## Canonical Behavior

- opens from a compact row action such as `View Details`;
- appears from the right over a semantic overlay;
- closes through the close button, overlay click, or Escape;
- keeps domain content scrollable while the header and optional footer remain visible;
- may include one primary destination action in the footer.

## Shared Content Primitives

The component also owns reusable drawer content geometry:

```jinja
side_drawer.section(...)
side_drawer.metric(...)
```

`section(...)` owns section radius, border, icon, title hierarchy, optional description, optional badge, and highlight variant. `metric(...)` owns compact summary geometry for a label, value, icon, and optional helper.

Domain templates provide the values and operational meaning. They must not rebuild section or summary-card geometry inline.

## Visual Contract

- right-aligned full-height panel;
- default maximum width `max-w-xl`, with `max-w-2xl` for richer read-only details;
- standard card background and left border;
- header title uses `text-lg font-semibold`;
- domain sections use `text-base font-semibold`;
- optional summary section may use the Violet-soft highlight variant;
- footer uses shared action-button classes;
- no page-local fixed-position drawer shell.

## Mobile Contract

- Below `sm`, the canonical drawer uses the available phone width and dynamic viewport height so browser chrome changes do not strand actions outside the visible surface.
- Header and body padding compact on phone while `sm+` retains the established desktop/tablet spacing.
- When the optional footer action is present, Close and the destination action stack as full-width controls below `sm`; `sm+` restores the horizontal right-aligned action bar.
- Domain consumers must not patch footer direction, action width, or viewport geometry locally. Responsive behavior remains owned by `components/side_drawer.html`.

## Detail Composition

A rich operational drawer should follow this order when applicable:

```text
Summary
Identity and Snapshot Context
Domain Breakdown
Signals or Conditions
Operational Context
Footer Destination Action
```

The final Operational Context section explains the data boundary and gives one state-aware next action. This information remains visible and is not expandable.

## Accessibility

- `role="dialog"`;
- `aria-modal="true"`;
- labelled title and description;
- explicit close labels;
- Escape support;
- background overlay is independently closable.

## Usage Boundary

Use a drawer when the row detail is too large for an expanded table row but the user benefits from retaining the comparison table context. Use a dedicated page when the detail becomes a full workflow or requires multiple primary actions.

## Header and Summary Density

- Drawer descriptions are one concise sentence and should normally fit on one or two lines.
- Self-explanatory section titles such as `Cluster Identity` and `Snapshot Context` may omit descriptions.
- Use `density='compact'` for short identity/context sections.
- Use `metric(..., variant='plain')` inside a divided summary row when nested metric cards would create card-inside-card density.
- The summary surface prioritizes values; helper text is short and optional.

## Long Values in Narrow Columns

Drawer identity and snapshot sections may use a two-column layout, but long values must remain inside their owning column. Use `components/details/_detail_content.html::stacked_detail_row(...)` only for genuinely long values such as provider name, subject, issuer, or other descriptive text that can exceed a compact label/value row. Canonical short values such as Inventory `Snapshot Source: Committed Snapshot` use `detail_row(..., nowrap=True)` to preserve horizontal alignment. The stacked value uses normal wrapping and `overflow-wrap:anywhere`; do not add horizontal scrolling to the drawer for descriptive text.
