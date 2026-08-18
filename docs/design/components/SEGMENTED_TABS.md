# Compact Segmented Tabs

## Registered Name

- Review name: **Tab Style 3 — Compact Segmented Tabs**
- Semantic key: `compact-segmented`
- Shared owner: `components/segmented_tabs.html`

## Purpose

Use this style for two or three mutually exclusive local views inside one component, inspector, drawer, or visualization toolbar.

Examples:

- Graph / Resource List;
- Details / Relationships;
- compact local presentation modes that do not change the page domain.

## Contract

- renders one compact segmented surface;
- active segment uses a filled surface and Violet text;
- inactive segments remain neutral;
- each control has `role="tab"`, `aria-controls`, `aria-selected`, and roving `tabindex`;
- the shared component owns stable `data-kaori-segmented-group` and `data-kaori-segmented-tab` hooks; consumers scope their controller by group and read the tab key from the shared hook instead of inventing page-local `data-*` attributes;
- Left/Right/Home/End keyboard navigation is supported by the owning JavaScript controller;
- each matching panel uses `role="tabpanel"` and `aria-labelledby`;
- state may be local or URL-backed when the selected view should survive refresh/share;
- a maximum of three segments is recommended.

## Usage Boundary

Do not use Tab Style 3 for top-level workspace domains or four-plus peer operational sections. Those use Tab Style 1 — Integrated Workspace Tabs or Tab Style 2 — Framed Workspace Tabs according to the parent surface contract.

Do not create another tab style for color, radius, icon, or spacing variation alone.

### Controller Hook Ownership

`components/segmented_tabs.html` is the only owner of segmented-tab DOM hooks. The component renders `data-kaori-segmented-group="<prefix>"` and `data-kaori-segmented-tab="<key>"` on every segment. Consumer JavaScript may bind behavior to those stable hooks, but must not require dynamically generated attribute names such as `data-topology-node-tab` or `data-topology-view-tab`. This keeps the contract formatter-safe and prevents a valid visual tab from becoming inert when template formatting changes.
