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
| References | Kubernetes Operations Dashboard; Protected Secret Reveal |
| Content relationship | Peer sections within one workspace and one active scope |
| Surface | Integrated divider; no separate card shell |
| State | Stored in the URL and preserved through HTMX scope changes |
| Layout | Horizontal tabs with narrow-screen overflow |

Use Tab Style 1 for operational dashboards, analytics workspaces, and peer task/status/approval views such as Protected Secret Reveal, where each tab is a full workspace perspective on the same governed context.

For server-rendered workspaces that use the client-controlled `render_controlled()` variant, the server-selected panel is the initial source of truth. Client code must validate that the requested key has both a tab and a panel before changing `hidden` state. Explicit URL query state takes precedence; a legacy hash-only deep link may select a different view only after the controller validates the matching tab/panel pair. Otherwise the server-rendered active panel remains authoritative, so refresh cannot blank the workspace.

## Tab Style 2 — Framed Workspace Tabs

| Property | Contract |
|---|---|
| Semantic key | `framed-workspace-v2` |
| Component | `components/framed_workspace_tabs.html` |
| References | Kubernetes Integration detail and Integration Overview |
| Content relationship | Peer operational domains inside one explicit parent workspace |
| Surface | Framed parent card with raised connected tabs and optional compact badges |
| State | URL-backed with browser-history synchronization |
| Layout | Horizontal tabs with narrow-screen overflow and roving keyboard focus |

Use Tab Style 2 when the parent workspace shell is part of the information architecture and its domains benefit from compact posture or scope badges. The detailed contract lives in `FRAMED_WORKSPACE_TABS.md`.

## Tab Style 3 — Compact Segmented Tabs

| Property | Contract |
|---|---|
| Semantic key | `compact-segmented` |
| Component | `components/segmented_tabs.html` |
| References | Kubernetes Topology Graph/List and Details/Relationships |
| Content relationship | Two or three mutually exclusive local views |
| Surface | Compact segmented control inside one component or toolbar |
| State | Local by default; URL-backed when the view must survive refresh/share |
| Layout | Horizontal segments with roving keyboard focus |

Use Tab Style 3 for local view switching in a visualization, inspector, drawer, or compact component. Do not use it for top-level workspace domains or four-plus peer sections. The detailed contract lives in `SEGMENTED_TABS.md`.

## Future Styles

Future styles must be added to this registry before implementation. Use a semantic name in addition to the next numeric review label. A vertical navigation model for a dense configuration workspace may justify another style when a real page requires it.

Never name implementation files `tab_style_3.html` or similar. File and component names remain semantic; the numeric label is a review shorthand.
