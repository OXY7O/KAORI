# KAORI Operational Section Card Standard

## Purpose

`operational_section_card.html` is the canonical shell for a dashboard or operational workspace block. It prevents each partial from redefining the same card geometry and typography.

## Shared ownership

The component owns:

- `rounded-xl` surface, standard border, and restrained shadow;
- header padding and divider;
- 40 px Violet Soft icon surface;
- `text-base font-semibold` Title Case title;
- sentence-case supporting description;
- one optional compact metadata/status label;
- one optional 36 px section-header action;
- body padding.

The domain partial owns data, metrics, tables, charts, state logic, and HTMX parameters through `caller()`.

## Usage

```jinja
{% import "components/operational_section_card.html" as operational_section_card %}

{% call operational_section_card.render(
    'Cluster Health Summary',
    'Compare inventory, utilization, and active signal posture by cluster.',
    'activity',
    id='dashboard-cluster-health-section',
    action_href=url_for('kubernetes_inventory.overview'),
    action_label='Open Inventory'
) %}
    ...
{% endcall %}
```

## Rules

- Use one section card for one operational purpose.
- Do not add another outer card around a set of already-carded tab panels.
- Do not copy its shell classes into page templates.
- Header title is a card/block title, not a page title.
- A header has at most one compact action.
- Place large charts or tables directly in the body; avoid unnecessary nested card surfaces.
