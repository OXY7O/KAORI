# KAORI Analytics Visual Role System

This document is the canonical, reusable visual contract for every Kubernetes
Analytics workspace:

- Overview
- Resource Utilization
- Capacity Analysis
- Storage Analysis
- Workload Analysis
- Forecast Analysis
- Top Consumers
- Alerts & Anomalies

The objective is not to remove the KAORI palette. The objective is to assign
color a stable meaning so the interface remains expressive, readable, and
predictable in both light and dark mode.

## Design principle

Analytics uses color by **visual role**, not by individual template preference.
All templates must consume the shared primitives in:

```text
app/templates/analytics/components/_analysis_surfaces.html
```

A domain template must not recreate icon geometry, role colors, guidance
surfaces, or status-bar colors using local class strings.

## Four canonical visual roles

### Brand

KAORI Bright Violet identifies product ownership and interaction.

Use Brand for:

- page and section identity;
- primary Analytics icons;
- tabs and selected navigation;
- links and primary actions;
- recommended review paths and next-step guidance;
- loading or composition indicators that do not express health.

Shared usage:

```jinja
{{ analysis_surface.role_icon_classes('brand') }}
{{ analysis_surface.role_label_classes('brand') }}
```

Brand Violet must not be used to represent Normal, Warning, Critical, or
Unknown status.

### Insight

Cyan/Info identifies explanation, methodology, and interpretation.

Use Insight for:

- How To Read;
- Measurement Standard;
- Methodology;
- Decision Thresholds;
- memory and storage category cues where a secondary category color improves
  scanning without implying health.

Shared usage:

```jinja
{{ analysis_surface.role_icon_classes('insight') }}
{{ analysis_surface.role_label_classes('insight') }}
```

Insight is informational. It must not be interpreted as Normal health.

### Evidence

Slate-neutral identifies passive facts, scope, context, and ownership.

Use Evidence for:

- Namespace, Workload, Pod, ownership, and scope cues;
- contextual facts that are not actions or health states;
- secondary evidence labels and neutral record metadata.

Shared usage:

```jinja
{{ analysis_surface.role_icon_classes('evidence') }}
{{ analysis_surface.role_label_classes('evidence') }}
```

### Status

Semantic color communicates an actual operational condition.

Use Status only for:

- Normal or Healthy;
- Warning or Watch;
- Critical;
- Unknown or Limited Evidence;
- actual alert and anomaly severity;
- quantitative utilization, pressure, or headroom bars.

Shared usage:

```jinja
{{ analysis_surface.semantic_icon_classes(tone) }}
{{ table_label.status_label(label, tone) }}
{{ progress_bar.semantic_bar(percent, tone) }}
```

Status color must not tint an entire metric card or guidance region. The
semantic badge, glyph, or quantitative bar is sufficient.

## Surface hierarchy

Color is concentrated in compact visual anchors. Larger surfaces remain
readable and calm.

Canonical hierarchy:

```text
Primary section/card       bg-surface-card
Supporting evidence        bg-surface-muted
Subtle divider/border       border-outline-subtle
Primary text                text-content-primary
Supporting text             text-content-secondary
Muted metadata              text-content-muted
```

Do not create full-card Violet, cyan, green, amber, red, or slate fills for
normal Analytics content. A full semantic surface is reserved for an explicit
system notice component whose complete purpose is to communicate that state.

## Resource category mapping

Use the shared resource mapper instead of choosing a color locally:

```jinja
{{ analysis_surface.resource_icon_classes(resource_name) }}
```

Current mapping:

- CPU and primary compute identity → Brand;
- Memory, Storage, Filesystem, PVC, and PV → Insight;
- Namespace, Workload, Pods, ownership, and scope → Evidence.

This creates category contrast without misusing semantic health colors.

## Guidance composition

Every explanatory or action region uses:

```jinja
{{ analysis_surface.interpretation_callout(
    label,
    headline,
    body,
    icon='scan-search',
    role='brand'
) }}
```

Role rules:

- How To Read, Methodology, Measurement Standard → `role='insight'`;
- What To Do, Recommended Action, Review Path → `role='brand'`;
- evidence context → `role='evidence'`;
- Operational Reading that communicates current health → `role='status'` with
  the resolved tone.

Guidance rows use a neutral card surface and a subtle neutral separator. Their
identity comes from the compact icon and eyebrow label, not a large tinted box.

## Progress-bar contract

A progress bar must first be classified by meaning.

### Status-bearing bars

Use semantic colors when the percentage itself represents health, pressure,
utilization, headroom, or risk:

- Normal/Healthy → green;
- Warning/Watch → amber;
- Critical → red;
- Unknown → slate;
- Info → blue.

Use:

```jinja
{{ progress_bar.semantic_bar(percent, tone) }}
```

### Composition bars

Use KAORI Violet when a bar represents composition, contribution, rank,
loading, or completion and does not express health.

Examples:

- Top Consumer contribution;
- ranked evidence contribution;
- materialization progress;
- loading progress.

## DRY requirements

Analytics templates must:

- use `kaori-analytics-page` at every page root;
- import `_analysis_surfaces.html` for role presentation;
- declare `role=` for every interpretation call;
- use `resource_icon_classes()` for category cues;
- use `semantic_icon_classes()` and semantic badges for actual status;
- use `progress_bar.semantic_bar()` for status-bearing percentages;
- keep composition-only progress Violet;
- avoid duplicated `bg-kaori-soft text-kaori-primary` icon geometry outside the
  shared component and canonical content tabs.

No compatibility wrapper or domain-local color map may be added to bypass this
contract.

## Accessibility and dark mode

- Text remains on neutral surfaces with stable contrast.
- Color is never the only status indicator; status text or a badge accompanies
  semantic color.
- Category color never implies health.
- Dark mode uses the same roles and meaning, not a separate palette logic.
- Supporting descriptions use `text-content-secondary`, not low-contrast
  brand-tinted text.

## Regression ownership

The visual-role contract is locked by:

```text
tests/contracts/analytics/test_analytics_visual_role_system_contract.py
tests/contracts/analytics/test_analytics_guidance_callout_standard_contract.py
tests/contracts/analytics/test_semantic_status_bar_contract.py
tests/contracts/analytics/test_overview_semantic_visual_hierarchy_contract.py
```
