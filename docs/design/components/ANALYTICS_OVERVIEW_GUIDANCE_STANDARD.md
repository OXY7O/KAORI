# KAORI Analytics Guidance and Semantic Visual Standard

This standard applies to Analytics Overview and to shared interpretation regions across every Kubernetes Analytics page.

Covered guidance labels include:

- How To Read
- What To Do
- What To Watch
- Operational Reading
- Recommended Action
- Recommended Review Path
- Operational Triage
- Forecast Decision

## Visual hierarchy

Analytics uses three distinct visual layers:

1. **Neutral structure**
   - page, panel, metric, evidence, and interpretation surfaces use the standard surface and outline tokens;
   - guidance areas use `bg-surface-muted` only to separate interpretation from primary evidence;
   - text remains `text-content-primary`, `text-content-secondary`, or `text-content-muted` according to hierarchy.

2. **KAORI identity**
   - Bright Violet is reserved for section identity, navigation, metadata, links, and actions;
   - violet must not communicate Normal, Warning, Critical, or Unknown health.

3. **Semantic state**
   - semantic colors are limited to compact status labels, the glyph inside a neutral icon tile, and quantitative status bars;
   - semantic colors must not tint an entire guidance box, metric card, headline, or evidence surface.

## Shared guidance composition

Every Analytics guidance region uses `interpretation_callout()` from:

```text
app/templates/analytics/components/_analysis_surfaces.html
```

Canonical composition:

```jinja
<div class="{{ analysis_surface.interpretation_grid_classes() }}">
    {{ analysis_surface.interpretation_callout(
        'How To Read',
        headline,
        description,
        icon='chart-column',
        tone='info'
    ) }}
    {{ analysis_surface.interpretation_callout(
        'Recommended Action',
        action_headline,
        action_description,
        icon='triangle-alert',
        tone=action_tone
    ) }}
</div>
```

Rules:

- use one continuous neutral interpretation region rather than separate colored cards;
- use horizontal separation on desktop and vertical separation on smaller screens;
- keep label uppercase and muted;
- keep headline neutral and semibold;
- keep supporting copy neutral and compact;
- tone affects only the icon glyph inside the neutral icon tile;
- do not add top accent bars, semantic borders, semantic backgrounds, or semantic headline colors;
- do not recreate guidance labels in raw template markup.

## Operational metric cards

Overview metric and health cards use neutral icon tiles:

```jinja
{{ analysis_surface.metric_icon_classes() }}
```

Health signal cards may use:

```jinja
{{ analysis_surface.semantic_icon_classes(signal_tone) }}
```

The tile remains neutral. Only the glyph receives the semantic color. The compact status badge remains the primary semantic indicator.

Operational Health Summary uses a maximum of three columns so the label, value, status, and description remain readable. Six narrow single-row cards are not allowed.

## Status bars

Status-bearing progress bars use `progress_bar.semantic_bar()`:

- Normal → green
- Warning → amber
- Critical → red
- Unknown → slate
- Info → cyan/blue

The bar is the quantitative semantic indicator. Surrounding cards and labels remain neutral.

Composition-only progress, loading, and navigation indicators may continue to use KAORI Violet.

## Attention and unavailable states

Attention strips use a neutral surface and outline. They contain:

- a neutral icon tile with a semantic glyph;
- a concise title and supporting description;
- a compact semantic status label when action is required.

Unavailable states use neutral dashed surfaces. They must not use a large violet or semantic-tinted background.

## Cross-page consistency

Because Utilization, Capacity, Storage, Workload, Forecast, Top Consumers, Alerts, and Overview import the same surface macros, changes to the shared guidance composition must be regression-tested across all Analytics domains.
