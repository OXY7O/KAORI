# Analytics Overview Snapshot Standard

Status: Canonical KAORI Analytics Overview presentation contract

Implementation: `app/templates/analytics/components/_overview_surfaces.html`

## Purpose

Analytics Overview contains multiple operational domains that differ in content but must read as one product. The Capacity tab is the reference composition for the shared visual grammar; other tabs follow the same hierarchy without being forced into an identical layout.

## Baseline Composition

Every Overview tab uses these layers in this order when the domain has the corresponding content:

1. **Snapshot shell** — one `rounded-xl` bordered card with restrained shadow.
2. **Snapshot header** — icon, Title Case title, semantic posture, short description, and at most one drill-down action.
3. **Metric strip** — four metrics by default; five are allowed when the domain genuinely needs five peer signals, as in Alerts.
4. **Evidence body** — charts, ranked records, findings, or operational context on a bright surface.
5. **Interpretation/action region** — concise reading guidance, review path, decision, or recommended action on the darker soft surface.

Use the shared macros:

- `snapshot_shell_classes()`
- `snapshot_header_classes()`
- `snapshot_header_icon_classes()`
- `metric_grid_classes(columns)`
- `metric_cell_classes()`
- `context_panel_classes(...)`
- `interpretation_grid_classes(...)`
- `interpretation_panel_classes(...)`

A domain may omit the metric strip or use a ranked evidence body when that better represents the data. It must still retain the same header, surface hierarchy, semantic status, spacing rhythm, and interpretation boundary.

## Surface Roles

### Primary Data Surface

Use `bg-surface-card` for controls, Prometheus status, committed snapshot metadata, metric grids, charts, ranked data, findings, and analytical context panels. Primary evidence remains bright and easy to scan.

Ranked rows use `ranked_item_classes(...)`. Empty analytical evidence uses `empty_evidence_classes(...)`.

### Context Panel

Use `context_panel_classes(...)`. Context panels such as Pressure Posture, Storage Risk Context, Anomaly Context, and Resource Outlook remain bright. They are separated by borders and grid position, not by a gray fill.

### Interpretation or Action Strip

Use `interpretation_grid_classes(...)`, `interpretation_panel_classes(...)`, or `guidance_card_classes(...)`. `bg-surface-hover` is reserved for concise interpretation, recommended action, review path, decision guidance, or execution guidance. It must not wrap the primary metric, chart, or ranked-data body.

A bright nested evidence card inside a darker interpretation panel uses `nested_evidence_card_classes(...)`.

### Attention Strip

Use `attention_strip_classes()`. Dataset freshness exceptions remain on the darker soft surface and include semantic Warning or Critical treatment. The source/readiness content above the strip remains bright.

## Loading Contract

Each lazy Overview section keeps its local skeleton. The Overview page may additionally show one compact **composite progress strip** because all tracked requests belong to the same Analytics Overview workspace and the strip reports determinate section progress.

Required behavior:

- every tracked section declares `data-overview-lazy-section="true"` and its load state;
- the tracker counts completed or failed sections rather than simulating progress;
- filter refreshes reuse the same tracker and the local form loading bar;
- the tracker hides after completion and does not replace the hero;
- `components/loading_bar.html` uses the shared indeterminate moving segment for local HTMX indicators.

This exception does not authorize a global loading bar across unrelated dashboard domains.

## Semantic Status

All Analytics Overview status labels normalize their tone through `table_label.semantic_tone(...)`. Presentation code should emit semantic values (`normal`, `warning`, `critical`, `info`, `unknown`, `maintenance`), while the shared label component temporarily accepts legacy color aliases for compatibility. A critical status must never render with the Unknown/slate treatment.

## Hero Posture Notice

When an Analytics hero has no bottom action, one short operational notice may occupy the same full-width bottom slot using `page_hero.context_bottom_notice(...)`. The notice appears after the compact metrics. It does not replace the posture title or add another metric card.

## Prohibited Patterns

- Do not apply `bg-surface-hover` to an entire data/readiness body.
- Do not use a dark fill for analytical side context such as Pressure Posture.
- Do not use the interpretation surface as the background for charts or ranked records.
- Do not duplicate shell/header/metric geometry in individual Overview partials.
- Do not duplicate tone maps in individual Overview partials.
- Do not render semantic values such as `critical` through an Unknown/slate fallback.
- Do not add a hero bottom notice and a bottom action simultaneously.
- Do not use a page-level progress strip for unrelated asynchronous dashboard sections.
