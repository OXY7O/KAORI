# Analytics Reusable Presentation Ownership

This document is a focused ownership note. The active domain contract is `ANALYTICS_HERO.md`; the global geometry and typography contract is `HERO.md`.

## Purpose

All Kubernetes Analytics hero context panels use `components/page_hero.html` as the single presentation owner. Domain templates provide semantic data only: labels, values, tones, helper text, and the cluster-management target.

## Canonical contracts

- `context_card(...)` owns the complete `<aside>` and context-card composition.
- `context_card_body(...)` owns the same composition when a lazy partial already has an `<aside>`.
- `context_status_badge(...)` owns posture state presentation.
- `context_metric(...)` owns metric-card geometry and typography.
- `context_panel_metrics_classes()` owns the two-column metric row.
- `context_single_action_classes()` owns the full-width primary action.
- Analytics heroes show no more than three metadata labels in a rendered branch.
- Analytics metric values use the shared `text-lg` scale.
- Analytics templates do not override `value_classes` or render local metric typography.

## Removed legacy APIs

The following APIs are not part of the active component and must not return:

- `context_posture_header(...)`;
- `context_posture_note(...)`;
- `context_bottom_notice(...)`.

Interpretation, attention, and remediation content belongs below the hero.
