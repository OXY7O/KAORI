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
- Left/Right/Home/End keyboard navigation is supported by the owning JavaScript controller;
- each matching panel uses `role="tabpanel"` and `aria-labelledby`;
- state may be local or URL-backed when the selected view should survive refresh/share;
- a maximum of three segments is recommended.

## Usage Boundary

Do not use Tab Style 3 for top-level workspace domains or four-plus peer operational sections. Those use Tab Style 1 — Integrated Workspace Tabs or Tab Style 2 — Framed Workspace Tabs according to the parent surface contract.

Do not create another tab style for color, radius, icon, or spacing variation alone.
