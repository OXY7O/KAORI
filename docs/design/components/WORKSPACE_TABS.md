# KAORI Workspace Tabs Standard

## Purpose

`workspace_tabs.html` provides standalone navigation between peer sections inside one workspace. It does not wrap the tab panels in a second card.

## Required behavior

- Use `role="tablist"`, `role="tab"`, and matching `role="tabpanel"` semantics.
- Each tab owns `aria-controls`, selected state, and focus state.
- The active tab is represented in the URL, for example `?tab=capacity`.
- Scope, filter, and HTMX refreshes preserve the active tab.
- Invalid tab values resolve to the module default.
- Panels remain in semantic DOM order and only the active panel is displayed.

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

The owning page supplies `activeTab` and `setTab()` state and renders panels with matching IDs.

## Visual contract

- standalone `rounded-xl` shared surface;
- horizontal overflow on narrow viewports;
- `text-sm font-semibold` tab labels;
- Violet bottom border and text for the active tab;
- no heavy selected background;
- no page-local tab geometry.

## Do not use

Do not use tabs to hide blockers, required fields, errors, primary flows, or content that is not a peer workspace section.
