# Resource Posture Grid

## Purpose

`components/resource_posture_grid.html` presents capacity and operational evidence for one inventory resource type without duplicating hero posture.

## Contract

- The owning section uses `operational_section_card.html`.
- Metrics use consistent title, value, helper, icon, and grid geometry.
- Capacity values remain neutral; operational exception metrics may use semantic icon surfaces.
- The grid does not repeat exact snapshot time, coverage, or hero readiness totals.
- Use three columns for six balanced metrics and four columns only for naturally four-part evidence.

## Metric tuple

```text
(icon, label, value, description, tone)
```

Supported tones are `brand`, `normal`, `warning`, `critical`, and `unknown`.
