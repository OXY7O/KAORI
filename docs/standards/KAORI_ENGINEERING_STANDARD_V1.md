# KAORI Engineering Standard v1

This document is the mandatory review index for KAORI implementation, final recheck, and release work. It does not duplicate component geometry. The detailed implementation contract remains owned by the referenced canonical component or architecture document.

## Review rule

Every page/domain recheck must evaluate all applicable standards below before it can be marked `PASS — LOCKED`. A previously locked page is not redesigned during recheck, but a real bug, security defect, accessibility defect, DRY violation, or mismatch with an approved shared standard is fixed as a targeted change.

For each item use one of:

- `PASS` — applicable and conforming.
- `TARGETED FIX` — applicable and corrected without reopening the design.
- `N/A` — not semantically applicable to the page.
- `BLOCK RELEASE` — unresolved correctness, security, reliability, or release evidence gap.

## 1. Brand, color, theme, and typography

Canonical owners:

- `docs/design/components/COLOR_AND_SEMANTIC.md`
- `docs/design/components/DARK_MODE.md`
- `docs/design/components/TYPOGRAPHY.md`
- `docs/design/components/TECHNICAL_VALUE.md`
- `docs/design/components/SPACING.md`

Requirements:

- KAORI Bright Violet remains the primary brand/action color.
- Semantic green/amber/red/info/unknown colors communicate state only.
- Light and dark mode are both mandatory.
- Technical identifiers, commands, hashes, paths, queries, and API values use the technical-value/monospace contract where appropriate.
- Human-readable labels use the canonical Title Case rules; technical casing is preserved.

## 2. Hero

Canonical owner: `docs/design/components/HERO.md`.

Every authenticated page hero must use the shared `page_hero` implementation. The right-side context-panel header accessory must be classified as exactly one of:

1. **Action Icon Box** — interactive immediate hero-context action.
2. **Context Icon Box** — non-interactive identity/domain/scope marker.
3. **Status Badge Box** — semantic readiness/health/lifecycle/decision state.

If no right-side context header accessory is required, record `N/A`. Do not invent a fourth visual variant.

## 3. Tables, status labels, and pagination

Canonical owners:

- `docs/design/components/TABLE_AND_LABEL.md`
- `docs/design/components/PAGINATION.md`

Requirements include:

- canonical shared table primitives;
- left-aligned data with the rightmost action aligned consistently;
- default Rows = 5;
- Rows options = 5 / 10 / 25 / 50;
- stable filter and pagination state;
- canonical compact rectangular status/metadata labels;
- status never communicated by color alone;
- table loading, empty, and error states remain inside the table surface.

## 4. Right-side content rail

Canonical owner: `docs/design/components/RIGHT_CONTEXT_RAIL.md`.

If a content workspace has a desktop right rail, use shared rail geometry and one of the registered semantic side-box components. Do not create page-local right cards when Info Flow, Related Page Card, Information Guide Card, Context Guidance Card, Page Context Card, Workspace Summary Card, or an existing readiness component already matches the purpose.

## 5. Tabs

Canonical registry: `docs/design/components/TAB_STYLES.md`.

Approved tab families are:

1. **Tab Style 1 — Integrated Workspace Tabs** for peer sections within one active workspace/scope.
2. **Tab Style 2 — Framed Workspace Tabs** for peer domains inside an explicit parent workspace shell.
3. **Tab Style 3 — Compact Segmented Tabs** for two or three local views inside one component/inspector/visualization.

A new visual variation is not a new tab type. A fourth type requires a real information-architecture need and must be registered before implementation.

## 6. Progressive disclosure and detail content

Canonical owners:

- `docs/design/components/VIEW_MORE_CONTENT.md`
- `docs/design/components/MODAL_DRAWER.md`
- `docs/design/components/SIDE_DRAWER.md`
- `docs/design/components/RESOURCE_DETAIL_MODAL.md`
- `docs/design/components/EXPANDABLE.md`

Choose disclosure by content purpose:

- **View Details / inline expand** for concise optional secondary content below the trigger.
- **Modal** for focused bounded detail or decision content that should temporarily overlay the current page.
- **Drawer** for contextual inspection, relationship/evidence detail, or a longer side-oriented inspector while retaining page context.
- **Inline expanded box** for secondary guidance/evidence where the surrounding layout must stay visible.

Do not use `View More` as an ambiguous default label when `View Details`, `View Evidence`, or another precise label is available.

## 7. Buttons and action bars

Canonical owners:

- `docs/design/components/BUTTON.md`
- `docs/design/components/FORM_ACTION_BAR.md`
- `docs/design/components/SECTION_HEADER_ACTION.md`

Every action must use the correct Primary, Secondary, Destructive, navigation, compact-table, or disclosure role. Geometry and interaction state are shared, not page-local.

## 8. Loading, toast, and operational feedback

Canonical owners:

- `docs/design/components/LOADING.md`
- `docs/design/components/OPERATIONAL_ACTION_FEEDBACK.md`

Requirements:

- long/HTMX work uses the canonical loading bar in the affected region;
- same-page mutations use canonical operational feedback;
- self-dismissing toasts use the shared progress/countdown bar and disappear according to the registered lifecycle;
- errors that require user attention do not auto-dismiss prematurely;
- toast delivery and Activity Audit evidence follow the same normalized operational event contract where required.

## 9. Notification style

Canonical release contract: `docs/design/KAORI_NOTIFICATION_CENTER_LOCK_V1_2.md` plus `components/OPERATIONAL_ACTION_FEEDBACK.md`.

Notification Center remains personal and read-only; Activity Audit remains administrative/system-wide evidence. Notification tables, filters, pagination, category presentation, loading, and Title Case follow the shared KAORI table and feedback standards.

## 10. Application shell, navbar, and sidebar

Canonical owners:

- `docs/design/components/NAVBAR.md`
- `docs/design/components/SIDEBAR_NAVIGATION.md`

Quick Actions, Notification Deck, Account menu, breadcrumb, sidebar control, and navigation state are global shell behavior. Page templates must not replace or reimplement them.

First-party interactive shell JavaScript must live in static JavaScript modules, pass JavaScript syntax verification, and avoid complex inline `x-data` programs that can be corrupted by HTML formatting.

## 11. Accessibility

Canonical owner: `docs/design/components/ACCESSIBILITY.md`.

At minimum verify:

- one authoritative `h1`;
- visible keyboard focus;
- labels and accessible names;
- dialog/drawer semantics;
- Escape/close behavior where applicable;
- roving keyboard behavior for tabs where applicable;
- table headers and pagination semantics;
- status not color-only;
- decorative icons marked appropriately;
- light/dark contrast.

## 12. Responsive and HTMX behavior

Canonical owner: `docs/design/components/RESPONSIVE_AND_HTMX.md`.

Verify the supported compact laptop/desktop layouts, narrow viewport reflow, no accidental page-level horizontal overflow, stable HTMX targets, shared loading indicators, and preservation of state across partial swaps.

## 13. Empty, error, blocked, and permission states

Canonical owner: `docs/design/components/EMPTY_ERROR_STATE.md`.

Unknown, unavailable, empty, permission denied, disconnected, pending, and not configured are distinct states. Do not expose raw provider/backend exceptions to end users.

## 14. Architecture and ownership

The expected dependency direction is:

```text
route → application/service → domain → repository/provider
```

Presentation must not become persistence logic, routes must not become provider clients, and page-local wrappers must not duplicate canonical shared components. Legacy/compatibility wrappers, dead code, hidden duplicate implementations, and obsolete docs are reviewed on every final recheck.

## 15. Security and reliability

For each external or privileged boundary review authentication, authorization, input validation, CSRF, XSS-sensitive output, SSRF/path handling where relevant, credential redaction, timeout, retry, transaction rollback, idempotency, stale-resource conflict handling, failure isolation, and audit evidence.

Authorization must execute before readiness probes or data/provider reads that could reveal protected state.

## 16. Testing and release evidence

Each final recheck asks whether the current tests actually prove behavior rather than merely matching source strings. Use the appropriate layers:

- static quality;
- contract tests;
- unit tests;
- functional/behavioral tests;
- integration tests;
- security regression tests;
- rendering/UI contracts;
- critical end-to-end smoke journeys.

A verifier should protect a durable invariant, not whitespace. Formatter/linter/type-checker ownership must not be duplicated by brittle source-string checks.

## 17. Per-page final recheck checklist

For every page/domain record:

1. Product/data contract.
2. Route and RBAC.
3. Architecture and ownership.
4. Legacy/dead code.
5. Security and reliability.
6. Hero including the three right-header variants.
7. Violet/theme/light-dark.
8. Tables/status/pagination where applicable.
9. Right content rail where applicable.
10. Tab type where applicable.
11. View Details/modal/drawer/expand behavior where applicable.
12. Buttons/action bars.
13. Loading/toast/notification behavior.
14. Navbar/sidebar global shell interaction.
15. Responsive/14-inch layout.
16. Accessibility.
17. Empty/error/blocked states.
18. DRY/reusable component ownership.
19. Title Case/technical typography.
20. Tests and missing negative cases.
21. Verifiers/scripts.
22. Documentation.
23. Performance/query/provider boundaries.
24. Regression and release-gate evidence.

Only after all applicable items pass may the page be marked `PASS — LOCKED`.
