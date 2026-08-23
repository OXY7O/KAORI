# Operational Callout

## Purpose

`components/operational_callout.html` owns reusable informational and semantic callout geometry inside operational sections. It prevents page templates from copying semantic border, surface, icon, and text bundles.

## Variants

### Neutral

Use for explicit evidence boundaries, warnings, or the introduction to an action flow. Operational dashboards should avoid a generic “What This Summary Means” callout when the section title and evidence already establish meaning.

- neutral elevated outer surface;
- semantic icon tile;
- `text-sm font-semibold` title;
- `text-xs` description.

### Semantic

Use for compact interpretation cards such as Critical, Warning, Info, Normal, or Unknown.

- complete semantic soft surface;
- matching semantic border and text;
- icon included for recognition;
- not a compact status label.

## Usage

```jinja
{% import "components/operational_callout.html" as operational_callout %}

{{ operational_callout.render(
    'Warning',
    'Degradation or risk is developing. Investigate before escalation.',
    icon='triangle-alert',
    tone='warning',
    variant='semantic'
) }}
```

Page templates must not copy the semantic class bundle inline. Standard compact labels remain borderless and continue to use `table_label.html`.
