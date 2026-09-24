# Responsive and HTMX Standard

Desktop layouts use horizontal composition where space permits. Tablet and mobile layouts stack actions and filters without compressing primary content. Low-priority table columns may hide; primary identity, state, and actions remain available.

HTMX requests preserve filter, sort, page, per-page, cluster, namespace, provider, and time-range state. Partial swaps must not duplicate headers, reset unrelated controls, or move the hero.

## Mobile Overlay Composition

Shared overlays own their narrow-screen behavior. The Notification Deck stays full-width on phone, preserves Active Work / Inbox / Notifications access, compacts non-critical header/footer detail, and uses dynamic viewport height. Canonical side-drawer footers stack their secondary and primary actions as full-width controls below `sm` and return to the horizontal action bar at `sm+`.

Consumers must extend the shared overlay owner instead of adding page-local mobile drawer, footer, or notification geometry.

## Scroll and History Alignment

The authenticated shell owns scroll-target alignment through `main[data-kaori-main-scroll]`.

- fragment targets and `scrollIntoView({ block: 'start' })` must respect the shell-owned top inset;
- HTMX partial swaps must not introduce page-local scroll offsets;
- `show:none` remains appropriate when a partial refresh should preserve the current viewport;
- deliberate navigation to a lower workspace may scroll that workspace into view, but it must not collide with the top scrollport boundary;
- domain templates must not add arbitrary top margins to compensate for shell/history behavior.
