# Kubernetes Operations Dark-Mode and Catalog Refinement Audit — July 2026

**Status:** Historical module audit. Current global dark-mode authority is `docs/design/components/DARK_MODE.md`.

## Scope

- ConfigMap Management
- Secret Management
- Create Secret
- ConfigMap and Secret destructive workflows
- shared Hero, action, disclosure, workflow catalog, and choice-card components

## Findings corrected

1. Management destinations appeared as multiple floating boxes with nested validation and authority boxes.
2. Secondary and validation hover states could become low contrast in dark appearance.
3. Hero context status labels inherited dark-page semantic soft colors that were weak on Violet.
4. Secret Type badges could all appear selected because Alpine expressions embedded JSON quotes in HTML attributes.
5. Creation Summary was secondary-collapsed even though it is the primary create context.
6. Delete action OOB fragments rendered as ordinary page content during a full-page GET when a validation receipt existed.

## Final decisions

- Management destinations use flat catalog rows inside one surface.
- Shared secondary hover becomes solid Violet with white text.
- Hero context labels use opaque white high-contrast surfaces.
- Secret Type selection is owned by native radio `:checked` state.
- Creation Summary opens by default; secondary policy guidance remains collapsed.
- Delete action OOB fragments are emitted only for HTMX responses.
