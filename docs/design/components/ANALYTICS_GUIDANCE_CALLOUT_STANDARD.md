# Analytics Guidance Callout Standard

Status: Canonical KAORI Analytics presentation contract

Implementation owner: `app/templates/analytics/components/_analysis_surfaces.html`

## Purpose

All Kubernetes Analytics pages use one visual and semantic grammar for operator guidance. This applies to:

- How To Read;
- What To Do;
- What To Watch;
- Operational Reading;
- Recommended Action;
- Recommended Review Path;
- Forecast Decision;
- Operational Guidance;
- materialization remediation.

## Canonical Composition

Every guidance callout contains:

1. one semantic icon tile on the left;
2. one uppercase eyebrow label;
3. one concise operational headline;
4. one neutral supporting description;
5. a semantic tone only when the callout represents Normal, Warning, Critical, Unknown, or Info state.

Use:

```jinja
{{ analysis_surface.interpretation_callout(
    'What To Do',
    'Validate Trend And Node Concentration Before Resizing',
    'Open Trend Analysis for sustained pressure and Node Detail for concentration.',
    icon='scan-search',
    tone=action_tone
) }}
```

For an existing record or side-panel wrapper, use the shared inner composition:

```jinja
{{ analysis_surface.interpretation_content(...) }}
```

## Surface Ownership

- Primary evidence remains bright.
- Guidance regions use `bg-surface-hover` through `interpretation_grid_classes()`, `guidance_card_classes()`, or `record_guidance_classes()`.
- Page templates provide semantic text, icon, and tone only.
- Page templates must not recreate icon tiles, label typography, headline sizing, or tone classes.

## Tone Rules

- How To Read and factual measurement guidance normally use Info.
- What To Do, Recommended Action, and Operational Reading use the owning evidence tone when a status exists.
- Unknown or unavailable evidence uses Unknown rather than Normal.
- Supporting body text remains neutral even when the headline and icon are semantic.

## Density

- Section-level callouts use the default density.
- Expanded records and compact side panels use `compact=true`.
- Repeated per-resource lanes may use `interpretation_content(..., compact=true)` to avoid nested card geometry while retaining the same icon, label, headline, and body hierarchy.

## Prohibited Patterns

- raw `How To Read`, `What To Do`, or `Recommended Action` markup in domain templates;
- page-local semantic icon class bundles;
- label-only guidance without a headline;
- long paragraphs promoted to the headline;
- expandable containers for primary operational guidance.
