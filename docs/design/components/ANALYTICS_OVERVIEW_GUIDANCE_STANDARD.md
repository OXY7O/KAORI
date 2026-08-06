# KAORI Analytics Neutral Guidance Standard

This standard applies to Analytics Overview and the shared interpretation regions used by every Kubernetes Analytics page.

Covered labels include:

- How To Read
- What To Do
- What To Watch
- Operational Reading
- Recommended Action
- Recommended Review Path
- Operational Triage
- Forecast Decision

## Visual hierarchy

Analytics uses three deliberately separated visual layers.

### 1. Neutral evidence and guidance

Analytics pages apply the `kaori-analytics-page` token scope.

Light mode uses:

- white primary cards;
- slate-50 supporting and icon surfaces;
- slate supporting typography;
- neutral slate outlines.

Dark mode uses:

- neutral charcoal cards rather than purple-tinted panels;
- neutral charcoal supporting surfaces;
- slate supporting typography;
- neutral slate outlines.

The analytics scope must not restore the former lavender values such as `#f8f5fc`, `#ded6e8`, or `#26212f`.

### 2. KAORI identity

Bright Violet is reserved for:

- section identity icons;
- tabs and active navigation;
- links and buttons;
- non-semantic guidance icons;
- loading and composition indicators.

Violet must not represent Normal, Warning, Critical, or Unknown health.

### 3. Semantic state

Semantic colors are reserved for:

- compact status labels;
- an explicitly semantic status glyph;
- quantitative pressure or utilization bars;
- compact threshold legends.

Semantic colors must not tint an entire guidance region, metric card, headline, divider, or evidence surface.

## Shared guidance composition

Every Analytics interpretation region uses `interpretation_callout()` from:

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
        icon='chart-column'
    ) }}
    {{ analysis_surface.interpretation_callout(
        'What To Do',
        action_headline,
        action_description,
        icon='scan-search'
    ) }}
</div>
```

Rules:

- use one white or neutral-charcoal interpretation region;
- do not use a full lavender, green, amber, red, or blue background;
- use a subtle horizontal separator on mobile and vertical separator on desktop;
- use a muted uppercase label;
- use a neutral primary headline;
- use stronger neutral secondary text for the explanatory body;
- use a Violet icon for How To Read, What To Do, Recommended Action, and Review Path;
- use `semantic=true` only when the callout itself communicates an actual health state, such as Operational Reading;
- do not add accent bars, semantic borders, semantic headline colors, or separate colored cards;
- do not recreate shared guidance labels using raw template markup.

## Operational cards

Metric cards and health cards use neutral icon tiles:

```jinja
{{ analysis_surface.metric_icon_classes() }}
```

The compact status badge is the primary health indicator. Do not repeat the same status using a colored metric icon unless the icon is the only status indicator available.

Operational Health Summary uses no more than three columns at desktop width so each label, value, status, and description remains readable.

## Status bars

Status-bearing progress bars use `progress_bar.semantic_bar()`:

- Normal → green
- Warning → amber
- Critical → red
- Unknown → slate
- Info → blue

The bar is the quantitative semantic indicator. Its card, heading, and supporting text remain neutral.

Composition-only loading bars may continue to use KAORI Violet.

## Attention and unavailable states

An attention strip uses:

- a white or neutral-charcoal surface;
- a neutral border;
- one semantic warning glyph;
- one compact warning badge;
- primary title text;
- neutral secondary explanatory text.

For singular grammar use `1 Dataset Needs Attention`; for plural grammar use `N Datasets Need Attention`.

Unavailable states use a neutral dashed surface and explicit Unknown/N/A wording. They must not use a large Violet or semantic-tinted background.

## Typography

Canonical guidance hierarchy:

```text
Label       12px semibold uppercase, muted slate
Headline    14px semibold, primary text
Body        12px regular with 20px line-height, secondary slate
```

Recommended spacing:

```text
Icon to content       12px
Label to headline      6px
Headline to body       6px
Horizontal padding    16–20px
Vertical padding      16px
```

## Cross-page consistency

Utilization, Capacity, Storage, Workload, Forecast, Top Consumers, Alerts, and Overview import the same surface macros. Forecast must also carry the `kaori-analytics-page` scope so shared neutral tokens are identical across every Analytics page.

Any change to shared guidance composition or Analytics color tokens requires regression coverage for:

- neutral light-mode surface values;
- neutral dark-mode surface values;
- brand-only non-semantic guidance icons;
- semantic bars and status labels;
- absence of semantic card fills and accent bars;
- Forecast analytics token scope.
