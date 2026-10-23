# KAORI Analytics Guidance Standard

This standard applies to Analytics Overview and to every reusable
interpretation region across Kubernetes Analytics.

Covered labels include:

- How To Read
- What To Do
- What To Watch
- Operational Reading
- Recommended Action
- Recommended Review Path
- Operational Triage
- Forecast Decision
- Measurement Standard
- Methodology

The complete color-role contract is defined in:

```text
docs/design/components/ANALYTICS_VISUAL_ROLE_SYSTEM.md
```

## Shared ownership

Every guidance region uses `interpretation_callout()` or
`interpretation_content()` from:

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
        role='insight'
    ) }}
    {{ analysis_surface.interpretation_callout(
        'What To Do',
        action_headline,
        action_description,
        icon='scan-search',
        role='brand'
    ) }}
</div>
```

## Cross-domain unified access guidance

The Access Denied (403) view is a second consumer of the **presentation-only** Analytics guidance primitives. It requires one calm `guidance_card_classes()` shell and one `snapshot_header_classes()` header; within the same outer border, `interpretation_grid_classes()` places two `interpretation_callout(..., role=...)` areas separated by subtle neutral dividers. These utility macros render no analytics data and carry no authentication policy. The Access domain continues to own RBAC, 403 response and Activity Audit.

```jinja
{% import "analytics/components/_analysis_surfaces.html" as analysis_surface %}

<section class="{{ analysis_surface.guidance_card_classes() }}"
         aria-labelledby="access-guidance-title">
    <header class="{{ analysis_surface.snapshot_header_classes() }}">
        <h2 id="access-guidance-title">Access Resolution Guidance</h2>
    </header>
    <div class="{{ analysis_surface.interpretation_grid_classes() }}">
        {{ analysis_surface.interpretation_callout(
            'Required Action',
            'Request Access Review',
            'Ask an administrator to review your role and permissions.',
            icon='user-cog', role='brand'
        ) }}
        {{ analysis_surface.interpretation_callout(
            'Security Boundary',
            'Server-Side Authorization',
            'Navigation is guidance; server-side permissions enforce access.',
            icon='shield-check', role='insight'
        ) }}
    </div>
</section>
```

- This is **one surface**, not two separate cards or a new one-off component.
- Role-color is limited to icon/eyebrow; security permission denial is not represented as a fake operational severity.
- Single-column narrow layout and two-column desktop layout are owned by the shared grid. Heading remains accessible; no clipping of copy or long content.
- Do not place authentication logic or provider calls into the visual macros.

## Role selection

### Insight

Use `role='insight'` for explanation and methodology:

- How To Read;
- Measurement Standard;
- Methodology;
- Decision Thresholds.

This role uses the KAORI information/cyan family as a compact visual cue.

### Brand

Use `role='brand'` for navigation and recommended action:

- What To Do;
- Recommended Action;
- Recommended Review Path;
- Forecast Decision;
- Operational Triage.

This role uses KAORI Bright Violet as the product/action cue.

### Evidence

Use `role='evidence'` for passive scope or contextual guidance that is neither
an action nor a health state.

### Status

Use `role='status'` only when the guidance itself communicates the current
operational state. Supply the resolved semantic `tone`.

Example:

```jinja
{{ analysis_surface.interpretation_callout(
    'Operational Reading',
    reading.headline,
    reading.description,
    icon='triangle-alert',
    role='status',
    tone=reading.tone
) }}
```

## Surface and typography

Guidance uses a neutral surface to protect readability. Color is concentrated
in the compact icon tile and eyebrow label.

Canonical hierarchy:

```text
Icon tile    visual role color
Label        role-aware eyebrow color
Headline     text-content-primary
Body         text-content-secondary
Container    bg-surface-card
Divider      outline-subtle
```

Do not apply a full Violet, cyan, green, amber, red, or slate fill to an
ordinary guidance row. Do not color the headline semantically. Do not add a
local accent bar.

Recommended spacing:

```text
Icon to content       12px
Label to headline      6px
Headline to body       6px
Horizontal padding    16–20px
Vertical padding      16px
```

## Responsive layout

On desktop, paired guidance uses two columns separated by a subtle neutral gap.
On mobile, it becomes a vertical stack with the same separator treatment.

The shared grid must own this behavior; domain templates must not recreate the
divider geometry.

## Status bars

Guidance containers remain neutral. Quantitative status bars still follow
semantic meaning:

- Normal → green;
- Warning → amber;
- Critical → red;
- Unknown → slate;
- Info → blue.

Composition-only bars remain KAORI Violet.

## Attention and unavailable states

Dataset Attention uses a neutral surface with:

- a semantic warning glyph;
- a compact Warning/Refresh Required badge;
- primary title text;
- secondary explanatory text.

Unavailable states use neutral dashed surfaces and explicit Unknown/N/A text.
They must not imply Normal health.

## DRY enforcement

Every Analytics interpretation invocation must declare `role=` explicitly.
Do not add `semantic=true`, domain-local icon color maps, or duplicated raw
brand icon geometry. Shared-role regression tests enforce this contract.
