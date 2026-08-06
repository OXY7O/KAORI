# KAORI Tab Style 2 — Framed Workspace Tabs

## Registered Name

- Review name: **Tab Style 2 — Framed Workspace Tabs**
- Semantic key: `framed-workspace-v2`
- Shared owner: `components/framed_workspace_tabs.html`
- Reference implementations: Kubernetes Integration detail and Integration Overview

## Purpose

Use this style when several peer operational domains belong to one parent workspace and the parent surface must remain visually explicit. The tab strip is framed by the parent card and each active tab connects directly to the content surface below it.

Typical uses:

- configuration, validation, runtime, and lifecycle domains for one integration;
- provider catalog, runtime overview, and domain coverage inside one integration portfolio;
- workspaces where compact semantic badges help identify environment, readiness, runtime posture, or scope.

## Contract

- the parent page owns one rounded workspace shell;
- the shared component owns the raised tab geometry and top surface;
- the active tab uses a white connected surface with Violet text;
- inactive tabs remain neutral and do not use full-box accent colors;
- each tab has `role="tab"`, `aria-controls`, `aria-selected`, and roving `tabindex`;
- Left/Right/Home/End keyboard navigation is provided by the owning Alpine controller;
- each panel uses the matching `role="tabpanel"` and `aria-labelledby`;
- state is URL-backed so refresh, browser history, and shared links preserve the active domain;
- optional compact badges may show environment, readiness, runtime posture, target count, or scope count;
- badge IDs follow `<prefix>-<key>-tab-badge` so HTMX OOB updates remain provider-neutral.

## Usage Boundary

Use Tab Style 2 when a visible parent workspace shell is part of the information architecture. Use Tab Style 1 when peer navigation should attach through only a divider without a framed parent card.

Do not use Tab Style 2 for two or three local visualization modes. Those use Tab Style 3 — Compact Segmented Tabs.
