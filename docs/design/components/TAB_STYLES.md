# KAORI Tab Style Registry

## Purpose

This registry names and governs reusable tab patterns across KAORI. It prevents each page from creating local tab geometry while still allowing multiple approved tab styles for different content structures.

Each approved style has:

- a review name such as **Tab Style 1**;
- a stable semantic key;
- one shared component owner;
- a clearly defined information architecture;
- at least one reference implementation.

A new style is justified only when the content relationship or interaction model is materially different. Color, radius, spacing, or icon changes alone do not justify another style.

## Tab Style 1 — Integrated Workspace Tabs

| Property | Contract |
|---|---|
| Semantic key | `integrated-workspace` |
| Component | `components/workspace_tabs.html` |
| Reference | Kubernetes Operations Dashboard |
| Content relationship | Peer sections within one workspace and one active scope |
| Surface | Integrated divider; no separate card shell |
| State | Stored in the URL and preserved through HTMX scope changes |
| Layout | Horizontal tabs with narrow-screen overflow |

Use Tab Style 1 for operational dashboards, analytics workspaces, and similar pages where each tab is a peer perspective on the same governed context.

## Future Styles

Future styles must be added to this registry before implementation. Use a semantic name in addition to the next numeric review label. Examples of potentially distinct patterns include a compact segmented switch for two mutually exclusive views or a vertical navigation model for a dense configuration workspace, but neither is approved until reviewed.

Never name implementation files `tab_style_2.html` or similar. File and component names remain semantic; the numeric label is a review shorthand.
