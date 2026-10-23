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

## Access-denied guidance ownership

For **Access Denied / Access Role Unavailable**, the approved design is **one** neutral guidance surface with two interpretation areas, not two independent callout cards. It reuses the already-approved Analytics presentation primitives from `analytics/components/_analysis_surfaces.html` (see `ANALYTICS_OVERVIEW_GUIDANCE_STANDARD.md`) for the single shell, header, internal divider and brand/insight guidance roles.

Continue to use `operational_callout.render` for standalone informational or semantic notices in operational views. Do not introduce page-local style bundles or a second wrapper just to simulate the unified Analytics presentation. Server-side permission checks remain authoritative.
