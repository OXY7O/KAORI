# Color and Semantic Standard

The global palette is token-owned in `frontend/styles.css`. Templates use semantic utilities and shared component classes; they do not use raw hex values.

## Brand role

Brand Violet is reserved for identity, primary interaction, focus, selection, links, and restrained analytical emphasis. It is not an operational status color and must not become the default color for ordinary text or repeated card surfaces.

## Operational semantic mapping

- Normal/healthy: green.
- Information and pending: blue.
- Warning and degraded: amber.
- Critical and destructive: red.
- Unknown and disabled: slate.
- Maintenance follows the documented maintenance token family.

Color is never the only status signal. Pair state color with text and, when useful, an icon. Missing or unavailable data must not render as healthy.

## Theme ownership

Light and dark mode use the same functional token names. Dark mode does not introduce page-local token sets. The exact dark surface stack, content contrast, Violet allocation, Hero exception, and sidebar treatment are defined in:

```text
docs/design/components/DARK_MODE.md
```

## Functional color usage

Use:

- `surface-*` for page, shell, card, elevated, selected, hover, and overlay layers;
- `content-*` for ordinary text hierarchy;
- `outline-*` for boundaries and focus;
- `kaori-*` for brand interaction and identity;
- `status-*` for operational state.

Do not substitute a literal color family for a semantic role.

## Shared ownership for compact operational feedback

The following visual bundles are component-owned and must not be copied into page templates:

- Background sync and process surfaces use `components/activity_status_card.html`.
- Semantic warning, critical, normal, unknown, and informational callouts use `components/operational_callout.html`.
- Notification counters use compact rectangular `rounded-md` geometry; numeric counters must not introduce page-local pill labels.

Page templates own content, URLs, identifiers, and polling attributes. Shared components own surface geometry, semantic border/surface pairing, focus treatment, and compact-label shape.
