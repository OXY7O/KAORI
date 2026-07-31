# Analytics Overview Surface Hierarchy

Status: Canonical KAORI Analytics Overview presentation contract

Implementation: `app/templates/analytics/components/_overview_surfaces.html`

## Purpose

Analytics Overview contains dense operational evidence. Surface contrast communicates the role of each region and must not be chosen independently by each tab.

## Surface Roles

### Primary Data Surface

Use `bg-surface-card` for controls, Prometheus status, committed snapshot metadata, metric grids, charts, ranked data, and analytical context panels. Primary evidence remains bright and easy to scan.

### Context Panel

Use `overview_surface.context_panel_classes(...)`. Context panels such as Pressure Posture, Storage Risk Context, Anomaly Context, and Resource Outlook remain bright. They are separated by borders and grid position, not by a gray fill.

### Interpretation or Action Strip

Use `overview_surface.interpretation_grid_classes(...)` or `overview_surface.interpretation_panel_classes(...)`. `bg-surface-hover` is reserved for concise interpretation, recommended action, review path, or execution guidance. It must not wrap the primary metric or chart body.

### Attention Strip

Use `overview_surface.attention_strip_classes()`. Dataset freshness exceptions remain on the darker soft surface and include semantic warning or critical treatment. The source/readiness content above the strip remains bright.

## Semantic Status

All Analytics Overview status labels normalize their tone through `table_label.semantic_tone(...)`. Presentation code should emit semantic values (`normal`, `warning`, `critical`, `info`, `unknown`, `maintenance`), while the shared label component temporarily accepts legacy color aliases for compatibility. A critical status must never render with the Unknown/slate treatment.

## Hero Posture Notice

When an Analytics hero has no bottom action, one short operational notice may occupy the same full-width bottom slot using `page_hero.context_bottom_notice(...)`. The notice appears after the compact metrics. It does not replace the posture title or add another metric card.

## Prohibited Patterns

- Do not apply `bg-surface-hover` to an entire data/readiness body.
- Do not use a dark fill for analytical side context such as Pressure Posture.
- Do not duplicate tone maps in individual Overview partials.
- Do not render semantic values such as `critical` through an Unknown/slate fallback.
- Do not add a hero bottom notice and a bottom action simultaneously.
