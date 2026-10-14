# Tab Style 6 — Vertical Technical Category Tabs

- Semantic key: `technical-category-vertical`
- Shared owner: `app/templates/components/technical_category_tabs.html`
- Approved reference: Tenant Allocation Change → Technical Details

## Why a distinct style exists

The reviewed Tenant Allocation Change UX has **three technical data categories in a vertical navigation column**, with a wide read-only comparison area. Converting it to horizontal integrated workspace navigation or a compact segmented control would alter the approved information architecture, and neither existing shared component owns vertical geometry. This style exists for technical-detail category switching, not as a general replacement for other KAORI tabs.

## Contract

- Shared `tablist()` renders `role="tablist"`, accessible name, `aria-orientation="vertical"`, canonical border/spacing and `data-kaori-tab-variant="technical-category-vertical"`.
- The calling workspace supplies category buttons and panels as semantic children. Preserve their existing IDs, `aria-controls`, `aria-selected`, roving `tabindex`, named `tabpanel` and per-form `data-tenant-allocation-detail-*` hooks.
- Tenant Allocation's controller retains Arrow Up/Down (and existing Left/Right support), Home/End, focus, active Violet/inactive neutral visual treatment, and form/HTMX lifecycle. Dynamic `data_namespace` exists solely for an explicit consumer controller hook.
- The current/proposed quota and LimitRange comparison and Advanced Controls remain **read only**; no provider reconcile is performed merely by switching tabs. A selection never implies admission or approval.
- Preserve approved layout: 14rem technical side rail on large screens, comparison/content panel filling the remainder, and stacking on narrow screens.

## Acceptance evidence

Before release, execute canonical UI style verifier, Jinja/djlint, affected Tenant functional/contract tests, and exact-head Developer Check and Full Admission. Browser QA must cover active panel, keyboard roving focus, screen-reader labels, responsive light/dark presentation, HTMX fragment insertion, and disabled/not-authorized allocation actions. Neither the doc nor this refactor constitutes UAT PASS.
