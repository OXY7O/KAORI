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

For server-rendered peer workspaces that need URL persistence, use the canonical Alpine `render()` contract with an optional fifth `href` tuple value. Alpine owns instant tab switching and URL synchronization; the real `href` is only a progressive server-navigation fallback if Alpine is unavailable. Panels bind visibility to `activeTab`, while the server-selected view remains the initial state on refresh. Do not add a second custom JavaScript tab controller beside Integrated Workspace Tabs.

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

## Tab Style 4 — Content Tabs

| Property | Contract |
|---|---|
| Semantic key | `content-tabs` |
| Component | `components/content_tabs.html` |
| References | Kubernetes Analytics Overview and domain analysis workspaces |
| Content relationship | Several closely related content views inside one established workspace |
| Surface | Compact rounded controls within or directly under the workspace header |
| State | Consumer-owned; Analytics uses the native `analytics_controls.js` controller |
| Layout | Wrap by default; approved one-row overflow mode for dense compact navigation |

Use Tab Style 4 for compact intra-workspace analysis navigation. The component owns visual active/inactive class tokens; the controller owns state. Internal dataset, snapshot, DOM-target, or loader identifiers must never be passed through as visible badges. Dense Overview navigation may use the documented no-wrap mode only with concise user-facing labels. The detailed contract lives in `CONTENT_TABS.md`.

## Future Styles

Future styles must be added to this registry before implementation. Use a semantic name in addition to the next numeric review label. A vertical navigation model for a dense configuration workspace may justify another style when a real page requires it.

Never name implementation files `tab_style_3.html` or similar. File and component names remain semantic; the numeric label is a review shorthand.


### Progressive Enhancement Contract

Controlled Integrated Workspace Tabs used for security-sensitive peer workspaces such as Protected Reveal must retain a server-navigation fallback. The rendered tab owns a real `href` to the same workspace with its server-owned view parameter, while JavaScript may intercept only after a valid tab/panel pair is confirmed. A controller failure must never leave a visible but inert tab.
