# KAORI Hero Component Standard v1.3

This document is the authoritative implementation contract for authenticated KAORI page heroes.

Canonical implementation:

```text
app/templates/components/page_hero.html
```

Canonical enforcement:

```text
scripts/verify_hero_component_standard.py
tests/contracts/design/test_hero_component_standard_contract.py
```

Page templates provide content and semantic values. They do not own hero geometry, typography, theme surface, context-panel structure, or action styling.

## Purpose

A hero gives the page stable identity and immediate operational context. It answers:

1. Where am I?
2. What page or object is this?
3. What is the page used for?
4. What scope or posture applies?
5. What is the primary next action?

Required hierarchy:

```text
Identity → Purpose → Context → Action
```

Tables, charts, evidence lists, workflow instructions, long diagnostics, pagination, and filters belong below the hero.

## Canonical composition

A normal hero contains:

- one eyebrow;
- one leading icon;
- one authoritative `h1`;
- one concise description;
- two or three metadata labels;
- one optional right-side context panel;
- one primary action in the context panel when the panel is interactive.

The right-side context panel normally contains:

- one posture eyebrow;
- one panel title;
- one semantic status badge;
- exactly two compact metrics;
- one full-width bottom action.

`context_card(...)` and `context_card_body(...)` enforce the two-metric limit by rendering `metrics[:2]`.

## Theme and surface contract

The Hero surface is owned by `.kaori-hero-shell` and `--kaori-hero-background`. Templates must not use `bg-kaori-primary` for the outer Hero shell.

Light mode uses the canonical Bright Violet identity surface. Dark mode uses the controlled tonal gradient defined in `components/DARK_MODE.md`; it is the only approved authenticated-page gradient.

Internal surfaces are also component-owned:

- `.kaori-hero-panel` — right context panel;
- `.kaori-hero-tile` — metric cards, leading/context icons, and supporting information;
- `.kaori-hero-chip` — eyebrow and metadata labels.

These classes prevent generic brand-surface tokens from making the dark Hero too luminous. Page templates must not recreate their background, border, opacity, blur, or glow values.

## Technical geometry

The following values mirror the active Tailwind implementation and are locked by the hero verifier.

| Element | Canonical implementation | Effective geometry |
|---|---|---:|
| Outer shell | `.kaori-hero-shell min-h-[15.5rem] lg:min-h-[17.5rem]` | theme-owned background, 248 px / 280 px minimum |
| Outer padding | `p-5 lg:p-6` | 20 px / 24 px |
| Outer radius | `rounded-2xl` | 16 px |
| Internal grid | `min-h-[13rem] lg:min-h-[14.5rem]` | 208 px / 232 px minimum |
| Grid gap | `gap-5` | 20 px |
| Desktop layout | `xl:grid-cols-12` | content 7 / context 5 |
| Context panel | `.kaori-hero-panel min-h-[13rem] rounded-xl p-4` | 208 px minimum, 12 px radius, 16 px padding |
| Metric grid | `grid-cols-2 gap-2` | two columns, 8 px gap |
| Context action | `h-10` | 40 px |

Minimum height protects alignment while allowing natural wrapping. If a hero grows repeatedly beyond the baseline, reduce the copy or move content below the hero. Do not create a page-local height variant.

## Technical typography

| Element | Tailwind owner | Effective typography |
|---|---|---|
| Eyebrow | `intro()` / `eyebrow()` | 12 px, semibold, uppercase |
| Title | `title_classes()` | 30 px compact / 36 px from `sm`, bold, 40 px line height |
| Description | `description_classes()` | 16 px, regular, 28 px line height, max width 44 rem |
| Metadata label | `meta_label()` | 12 px semibold, 32 px minimum height |
| Context eyebrow | `context_panel_eyebrow_classes()` | 12 px semibold, uppercase |
| Context title | `context_panel_title_classes()` | 16 px semibold, 24 px line height |
| Status badge | `context_status_badge()` | 12 px semibold, 28 px minimum height |
| Metric label | `context_metric_label_classes()` | 12 px semibold, 20 px line height |
| Metric value | `context_metric_value_classes()` | 18 px semibold, 24 px line height |
| Metric helper | `context_metric_helper_classes()` | 12 px medium, 20 px line height |
| Context action | `context_action_classes()` | 14 px semibold, 40 px height |

The implementation uses standard Tailwind sizes. Page templates must not add arbitrary hero typography such as `text-[13px]`, `text-[15px]`, or local title/description overrides.

## Intro and metadata

Use:

```jinja
{% call page_hero.intro('icon', 'Domain Eyebrow', 'leading-icon') %}
    <h1 class="{{ page_hero.title_classes() }}">Page Title</h1>
    <p class="mt-2 {{ page_hero.description_classes() }}">Concise purpose.</p>
    <div class="{{ page_hero.metadata_row_classes() }}">
        {{ page_hero.meta_label('server', selected_cluster_name) }}
        {{ page_hero.meta_label('boxes', '12 Resources') }}
    </div>
{% endcall %}
```

Metadata rules:

- use two or three labels in a normal branch;
- use Title Case for human-readable labels;
- preserve exact casing for Kubernetes names, profile keys, URLs, versions, hashes, and provider identifiers;
- metadata communicates identity or scope, not health or severity;
- operational state uses `context_status_badge(...)` or another semantic component.

## Context panel

Preferred implementation:

```jinja
{{ page_hero.context_card(
    'Capacity Posture',
    'Capacity Posture',
    'Ready-Worker Headroom',
    posture_label,
    posture_tone,
    [
        ('cpu', 'CPU Headroom', cpu_value, 'Ready-worker capacity'),
        ('memory-stick', 'Memory Headroom', memory_value, 'Ready-worker capacity')
    ],
    'Manage Clusters',
    url_for('integrations.kubernetes'),
    'server-cog'
) }}
```

Use `context_card_body(...)` only when a lazy-loaded partial already owns the `<aside>` wrapper.

Manual context panels are allowed only when the page needs a different semantic arrangement. They must still compose:

- `aside_classes()`;
- `context_panel_classes()`;
- shared context typography;
- shared metric-card classes;
- shared context actions.

Do not copy the utility strings into page templates.

## Context status

`context_status_badge(label, tone)` supports:

- `normal`;
- `warning`;
- `critical`;
- `unknown`;
- `info` as the fallback.

The badge uses an opaque light surface because it sits on a Violet hero. Status wording accompanies color and must remain readable without truncation.

## Actions

The canonical context action is:

```jinja
class="{{ page_hero.context_single_action_classes() }}"
```

For two coordinated actions in a manual panel, use:

```jinja
<div class="{{ page_hero.context_actions_classes() }}">
```

and apply `context_action_classes()` to both controls.

Rules:

- one action is preferred;
- two actions are the maximum for a manual panel;
- destructive workflows normally move below the hero;
- disabled actions retain their dimensions;
- icon-only actions require an accessible name.

## Content density

Recommended copy budget:

- description target: 7–12 words; hard maximum 16 words;
- right-panel title: 2–4 words;
- status label: 1–3 words;
- metric label: 1–3 words;
- metric helper: optional, normally no more than 4 words.

The component does not compensate for verbose copy. Long explanations and evidence boundaries belong below the hero.

## Dynamic and HTMX behavior

The hero is a stable page anchor. Filtering, pagination, polling, runtime refresh, inventory synchronization, validation, and background jobs must not replace or collapse it.

Do not:

- target the hero with routine HTMX swaps;
- replace it with a spinner or skeleton;
- dim the entire hero during a local request;
- move actions while a request is running;
- place volatile progress streams inside the hero.

Loading belongs to the affected card or initiating control.

A lazy right-side context partial may update only its owned context region while preserving the hero shell and its dimensions.

## Empty and blocked states

The hero remains visible when no records exist or a dependency is blocked.

Use factual metadata such as:

- `0 Connections`;
- `No Cluster Selected`;
- `Step 2 · Configuration Required`.

The full explanation and remediation workflow belong below the hero. Blocked context panels must still use the shared panel geometry.

## Responsive behavior

On narrow screens:

1. eyebrow;
2. leading icon and title block;
3. description;
4. metadata;
5. context panel.

At `xl`, the layout becomes the canonical 7/5 split. Mobile wrapping may increase height naturally. Page-local breakpoint geometry is prohibited.

## Accessibility

- exactly one `h1` per page;
- visible keyboard focus;
- status is communicated by text and icon, not color alone;
- context `<aside>` has a meaningful `aria-label`;
- decorative icons use `aria-hidden="true"`;
- dynamic values remain readable and are not silently truncated.

## Public macro contract

### Shell and identity

- `shell_classes()`
- `layout_classes()`
- `content_classes()`
- `aside_classes()`
- `intro(...)`
- `title_classes()`
- `description_classes()`
- `metadata_row_classes()`
- `meta_label(...)`

### Context panel

- `context_panel_classes()`
- `context_card(...)`
- `context_card_body(...)`
- `context_status_badge(...)`
- `context_header(...)`
- `context_panel_eyebrow_classes()`
- `context_panel_title_classes()`
- `context_panel_metrics_classes()`
- `context_metric(...)`
- `context_metric_card_classes()`
- `context_metric_label_classes()`
- `context_metric_value_classes()`
- `context_metric_helper_classes()`
- `context_icon_classes()`
- `context_info(...)`
- `context_actions_classes(...)`
- `context_action_classes()`
- `context_single_action_classes()`

Macros removed from the active contract must not be referenced by templates, tests, or documentation. The quality gate rejects reintroduction of the removed legacy posture-note and free-floating action APIs.

## Domain extensions

Domain documents may constrain content but cannot override shared geometry or typography.

- Kubernetes Analytics: `components/ANALYTICS_HERO.md`
- Inventory copy-density audit: `audits/KUBERNETES_INVENTORY_HERO_COPY_AUDIT_2026_07.md`

## Change procedure

A hero-standard change must update all of the following in the same commit:

1. `app/templates/components/page_hero.html`;
2. this document;
3. affected domain extension documents;
4. `scripts/verify_hero_component_standard.py`;
5. `docs/design/components/DARK_MODE.md` when theme behavior changes;
6. hero and dark-mode contract tests.

Run:

```bash
python scripts/verify_hero_component_standard.py
python -m pytest -q \
  tests/contracts/design/test_hero_component_standard_contract.py \
  tests/contracts/design/test_dark_mode_standard_contract.py
```

## Review checklist

- shared component imported;
- canonical shell/layout/content primitives used;
- one `h1` and one concise description;
- two or three metadata labels;
- no page-local title or description typography;
- context panel uses shared geometry;
- no more than two context metrics;
- one primary action preferred;
- hero remains stable during HTMX and background activity;
- technical identifiers preserve source casing;
- documentation and verifier updated with implementation changes.
