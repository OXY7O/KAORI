# KAORI Tab Style 1 — Integrated Workspace Tabs

## Identity

- Review name: **Tab Style 1**
- Semantic key: `integrated-workspace`
- Component: `app/templates/components/workspace_tabs.html`
- Reference implementation: Kubernetes Operations Dashboard

The numeric name is convenient during UI reviews. The semantic key is the stable implementation identifier used in code and documentation.

## Purpose

Tab Style 1 provides integrated navigation between peer sections inside one operational workspace. The tabs attach visually to the content area and do not render as a separate card or floating block.

Use this style when each tab represents a peer view of the same resource scope, operational context, or workspace. This includes server-rendered **level-3 route peers inside one sidebar capability** such as Kubernetes Inventory `Overview · Topology · Nodes · ...`.

## Required behavior

- Use `role="tablist"`, `role="tab"`, and matching `role="tabpanel"` semantics.
- Each tab owns `aria-controls`, selected state, and focus state.
- The active tab is represented in the URL, for example `?tab=capacity`.
- Scope, filter, and HTMX refreshes preserve the active tab.
- Invalid tab values resolve to the module default.
- Panels remain in semantic DOM order and only the active panel is displayed.
- Arrow Left/Right move and wrap focus across peer tabs; Home selects the first tab and End selects the last tab.
- The shared component exposes `data-kaori-tab-variant="integrated-workspace"` for audit and regression checks.

## Usage

```jinja
{% import "components/workspace_tabs.html" as workspace_tabs %}

{% set tabs = [
    ('overview', 'Operations Overview', 'layout-dashboard'),
    ('capacity', 'Capacity & Demand', 'gauge'),
    ('signals', 'Signals & Actions', 'siren'),
    ('reporting', 'Reporting', 'file-text')
] %}

{{ workspace_tabs.render(tabs, prefix='kubernetes-dashboard') }}
```

The owning page supplies `activeTab`, `setTab()`, and `moveTab()` state and renders panels with matching IDs.

## Server-owned route mode

`render_navigation()` is the canonical mode for server-rendered peer routes.

Use it when:

- sidebar level 1/2 already establishes workspace and capability identity;
- each level-3 item is a real route;
- the route row should feel attached to the workspace rather than floating above it;
- active state is server-owned with `aria-current="page"`.

Tuple shape:

```text
(key, label, icon, badge, href)
```

This is the canonical KAORI treatment for route-level level-3 navigation under Sidebar v2.1.

## Visual contract

- no outer `rounded`, border, background, or shadow shell;
- one bottom divider shared with the content workspace;
- horizontal overflow on narrow viewports;
- `text-sm font-semibold` tab labels;
- Violet bottom border and text for the active tab;
- transparent inactive state with restrained hover treatment;
- no page-local tab geometry.

## Do not use

Do not use Tab Style 1 to hide blockers, required fields, errors, primary flows, or content that is not a peer workspace section.

Do not create a new tab style only to change color, radius, or icon placement. A new style must represent a meaningfully different information architecture and must be registered in `TAB_STYLES.md`.
