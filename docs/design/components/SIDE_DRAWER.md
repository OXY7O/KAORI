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

## Visual Contract

- right-aligned full-height panel;
- default maximum width `max-w-xl`;
- standard card background and left border;
- header title uses `text-lg font-semibold`;
- domain sections use `text-base font-semibold`;
- footer uses shared action-button classes;
- no page-local fixed-position drawer shell.

## Accessibility

- `role="dialog"`;
- `aria-modal="true"`;
- labelled title and description;
- explicit close labels;
- Escape support;
- background overlay is independently closable.

## Usage Boundary

Use a drawer when the row detail is too large for an expanded table row but the user benefits from retaining the comparison table context. Use a dedicated page when the detail becomes a full workflow or requires multiple primary actions.
