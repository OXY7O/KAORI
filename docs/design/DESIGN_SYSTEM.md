# KAORI Design System Authority Index

This file is the compact compatibility entry point for KAORI interface standards. It does **not** define a separate design-system version and does not supersede the canonical global authority.

## Authority Order

Use the current approved authorities in this order:

1. `KAORI_DESIGN_SYSTEM.md` — global visual and interaction contract.
2. `KAORI_STYLING_GUIDE.md` — practical component-selection and page-review workflow.
3. `components/*.md` — reusable component contracts.
4. `patterns/*.md` — reusable page-composition contracts.
5. owning module documentation — domain-specific content and behavior.
6. `KAORI_VISUAL_QA.md` — governed multi-viewport visual evidence and human-UAT boundary.

Historical lock and audit documents remain evidence. They do not override a newer current authority.

The Design System v2 revalidation inventory is recorded in
`audits/KAORI_DESIGN_SYSTEM_V2_AUTHORITY_AUDIT_20260924.md`.

## Foundation Authorities

- `components/TYPOGRAPHY.md` — type scale, hierarchy, casing, wrapping, and technical text.
- `components/COLOR_AND_SEMANTIC.md` — brand and semantic color roles.
- `components/DARK_MODE.md` — locked neutral-first dark surface and restrained Violet emphasis contract.
- `components/SPACING.md` — layout rhythm and density.
- `components/ICONS.md` — icon hierarchy and contextual use.
- `components/ACCESSIBILITY.md` — focus, semantics, keyboard behavior, and accessible state.
- `components/RESPONSIVE_AND_HTMX.md` — responsive composition and partial-update behavior.

## Shared Component Authorities

Use the documented shared owner before introducing local markup or utility bundles.

- `components/HERO.md`
- `components/CARD.md`
- `components/TABLE_AND_LABEL.md`
- `components/BUTTON.md`
- `components/FORM.md`
- `components/FORM_ACTION_BAR.md`
- `components/PAGINATION.md`
- `components/LOADING.md`
- `components/EMPTY_ERROR_STATE.md`
- `components/MODAL_DRAWER.md`
- `components/TAB_STYLES.md`
- `components/CONTENT_TABS.md`
- `components/WORKSPACE_TABS.md`
- `components/FRAMED_WORKSPACE_TABS.md`
- `components/SEGMENTED_TABS.md`
- `components/RIGHT_CONTEXT_RAIL.md`
- `components/FORM_WITH_CONTEXT_RAIL.md`
- `components/REUSABLE_COMPONENT_OWNERSHIP.md`
- `components/SIDEBAR_NAVIGATION.md` — locked v1.4 sidebar hierarchy, geometry, naming, and information architecture.
- `components/NAVBAR.md`
- `components/OPERATIONAL_ACTION_FEEDBACK.md`
- `components/WORKSPACE_SUMMARY_CARD.md`
- `components/RELATED_PAGE_CARD.md`
- `components/VISUALIZATION_WORKSPACE.md`

`docs/design/README.md` contains the complete registered component catalog.

## Reusable Page Pattern Authorities

- `patterns/INVENTORY_AND_OPERATIONAL_PAGES.md`
- `patterns/INVENTORY_RESOURCE_PAGE.md`
- `patterns/OPERATIONAL_DASHBOARD.md`
- `patterns/WELCOME_WORKSPACE_CATALOG.md`
- Kubernetes inventory/operations patterns under `patterns/`
- Object Storage inventory pattern under `patterns/`

The v2 page-archetype registry is intentionally handled by #606 so this index does not create a competing pattern taxonomy.

## Global Guardrails

- New features compose approved primitives and patterns before creating a variant.
- A local variant requires a semantic gap, not aesthetic preference.
- Page-local copies of Hero, table, label, tabs, loading, pagination, state, modal/drawer, or context-rail geometry are prohibited when a shared owner exists.
- Violet remains brand/interaction identity; operational status uses semantic colors.
- Light/dark and responsive behavior belong to shared components, not page-local patches.
- Jinja/HTMX remains the frontend architecture; this revalidation does not authorize a parallel framework.
- Existing `verify_ui_reuse.py`, `verify_ui_style.py`, contract tests, and Visual QA are extended when enforcement needs to grow. Do not add one-off validation scripts.

## Design System v2 Workstream Boundary

#572 is the umbrella architecture authority. Its bounded revalidation work is split into:

- #605 — authority inventory and consolidation map.
- #606 — page archetype and navigation/tab decision registry.
- #607 — foundation and content-density matrices.
- #608 — responsive, accessibility, state, and interaction contracts.
- #609 — reference implementation and enforcement coverage.

Until those workstreams are accepted, existing approved component and pattern behavior remains authoritative.
