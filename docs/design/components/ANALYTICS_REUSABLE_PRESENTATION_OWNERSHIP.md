# Analytics Reusable Presentation Ownership

## Purpose

All Kubernetes Analytics hero context panels use `components/page_hero.html` as the single presentation owner. Domain templates provide only semantic data: labels, values, tones, and helper text.

## Canonical contracts

- `context_posture_header(...)` owns posture eyebrow, posture title scale, and status badge.
- `context_metric(...)` owns metric card geometry, label, compact value scale, and helper text.
- `context_panel_metrics_classes()` owns the two-column metric row.
- `context_single_action_classes()` owns the full-width primary action.
- Analytics heroes show no more than three metadata labels.
- Analytics hero metric values use the Inventory-aligned `text-lg` scale.
- Analytics hero templates must not override `value_classes` or render manual `text-xl`/`text-2xl` metric values.

## Reason

Prior drift occurred because each hero used the reusable shell but still supplied local value-size overrides or recreated the metric card markup. The shell was reusable, but typography ownership remained page-local. The canonical contract now removes those page-level overrides.
