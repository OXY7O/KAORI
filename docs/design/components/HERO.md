# KAORI Hero Component Standard

This document is the authoritative contract for authenticated KAORI heroes. All pages that require a hero use `app/templates/components/page_hero.html`. Page-local hero geometry, typography, action styling, and alignment are prohibited.

## Purpose

A hero provides stable page identity, concise purpose, current context, and the primary action. It is not an empty state, dashboard, diagnostic panel, or workflow body.

## Geometry

The active shared implementation is the baseline and supersedes the earlier experimental 164–188 px proposal.

- Compact outer minimum height: **248 px** (`min-h-[15.5rem]`).
- Desktop outer target/minimum height from `lg`: **280 px** (`lg:min-h-[17.5rem]`).
- Compact internal grid minimum height: **208 px** (`min-h-[13rem]`).
- Desktop internal grid minimum height: **232 px** (`lg:min-h-[14.5rem]`).
- Outer padding: **20 px compact**, **24 px desktop**.
- Desktop grid: **7/5 columns**.
- Column gap: **20 px**.
- Outer radius: **16 px**.

The component uses minimum height to preserve visual stability while allowing responsive wrapping. Repeated growth beyond the baseline indicates excessive content and must be corrected by moving content below the hero.

## Typography

KAORI uses Inter through `font-sans`.

| Element | Size | Weight | Line height | Rule |
|---|---:|---:|---:|---|
| Eyebrow | 10 px | 700 | 16 px | Uppercase, tracking `0.14em`, one line |
| Title | 30 px compact / 36 px from small screens | 700 | 40 px | Tracking `-0.02em`, one line preferred, two maximum |
| Supporting description | 13 px | 400 | 20 px | One meaningful line minimum, two lines maximum |
| Metadata label | 11 px | 700 | Natural in 32 px minimum height | Two minimum, three maximum |
| Supporting-strip label | 10 px | 700 | 16 px | Uppercase, tracking `0.12em` |
| Supporting-strip text | 12 px | 400 | 20 px | Short context only |
| Hero action | 14 px | 600 | 20 px in 40 px height | Visible full-text label |
| Posture metric label | 11 px | 600 | 16 px | Maximum four metrics |
| Posture metric value | 20–24 px | 700 | 28–32 px | Semantic when operational |

The page title is the page's single `h1`.

The shared `page_hero.title_classes()` macro is the only source of hero title typography. It renders at 30 px on narrow layouts and 36 px from the small-screen breakpoint. Page-local title size, weight, line-height, tracking, or color overrides are prohibited.

## Supporting description

- States the operational purpose of the page.
- Normally 60–120 characters.
- Renders as one or two lines on the target desktop viewport.
- Maximum text width: 44rem, approximately 704 px.
- The shared `page_hero.description_classes()` macro is the only source of description typography.
- It renders at 13 px with a 20 px line height consistently across compact and desktop viewports.
- Page-local `text-sm`, `text-[13px]`, `text-[15px]`, font-weight, line-height, color, or width overrides are prohibited.
- Uses active, direct language.
- Does not contain diagnostics, remediation, endpoint detail, full workflow, or multi-sentence guidance.

## Metadata labels

Every normal hero contains **two or three** contextual metadata labels. Human-readable metadata wording uses Title Case.

Preferred order:

1. Environment or scope.
2. Provider, mode, object type, or page context.
3. Count, source role, compatibility profile, or other operational metadata.

Metadata uses Violet because it communicates identity or context. Health, severity, readiness, failure, and process state use semantic status components. Metadata labels are borderless, rectangular, and never pills. The context-panel posture badge is a documented special-label exception because it combines an explicit status icon and semantic border; ordinary hero metadata must not copy that treatment.

## Right-side context panel

The Node Inventory hero is the visual baseline for a hero right-side context panel. Use the shared context-panel macros rather than page-local geometry.

Required structure:

1. Compact uppercase eyebrow identifying the posture domain.
2. Title Case panel title describing the operational posture.
3. One semantic status label aligned at the top right.
4. Exactly two compact metric cards in a two-column grid.
5. One full-width bottom slot containing either an action or one short non-interactive operational notice.

Shared macros:

- `page_hero.context_panel_classes()`
- `page_hero.context_panel_eyebrow_classes()`
- `page_hero.context_panel_title_classes()`
- `page_hero.context_panel_metrics_classes()`
- `page_hero.context_metric(...)`

Geometry and density:

- Minimum panel height: **208 px** (`min-h-[13rem]`).
- Padding: **16 px**.
- Metric grid gap: **8 px**.
- Metric card padding: **12 px horizontal / 10 px vertical**.
- Metric title: **11 px semibold**.
- Metric value: normally **20 px bold**.
- Metric description: **10 px**, sentence case, maximum two short lines.
- Bottom slot: full width, 40 px target height. Use `context_single_action_classes()` for an action or `context_bottom_notice(...)` for a non-interactive notice.

The panel is operational context, not a second dashboard. Do not add charts, lists, more than two metric cards, long descriptions, or multiple bottom rows. A bottom action and bottom notice are mutually exclusive.

## Hero metadata casing

Human-readable metadata labels use **Title Case**. Numbers and dynamic values may precede the label, but the descriptive words remain Title Case.

Correct:

- `4 Nodes Tracked`
- `64 CPU Cores`
- `3 Registered Instances`
- `2 Scope Bindings`
- `Ready`

Incorrect:

- `4 nodes tracked`
- `3 registered instances`
- `2 scope bindings`

Technical identifiers preserve canonical casing and must not be transformed mechanically. Examples include `kube-system`, `prometheus-v3`, `v1beta1`, `OAuth`, and provider-defined profile names. Metadata Title Case applies to the human-readable label, not to technical values.

## Actions

### Right-Side Context Actions

Every interactive button or link inside the hero right-side context panel uses `page_hero.context_action_classes()` or `page_hero.context_single_action_classes()`. This is the sole action treatment permitted inside that panel.

- White background.
- KAORI Violet text.
- White-compatible border and subtle shadow.
- Soft Violet hover.
- Visible keyboard focus ring.
- Height 40 px.
- Full width within its action column.
- One or two actions maximum.

When two actions are present, both remain white. Hierarchy is communicated through ordering, wording, and icon choice rather than a translucent secondary color. Disabled actions preserve the same white geometry with reduced opacity and no interactive hover state.

### Actions Outside the Context Panel

`page_hero.primary_action_classes()` and `page_hero.secondary_action_classes()` remain general hero primitives, but they must not be used inside the right-side context panel.

### Destructive

Use the Critical semantic family. Destructive actions are never converted to white merely to match the context panel; move destructive workflows below the hero unless they are the page's only essential action.

## Official hero types

Only five hero types are permitted. They share the same geometry, typography, responsive behavior, and semantic contract.

### Standard Hero

Default for list, settings, reports, governance, operations, and general module pages. It contains identity, purpose, two or three metadata labels, and actions or one compact context panel.

### Dashboard Hero

For operational and analytics overview pages. It may include one compact posture panel with no more than four metrics. Charts, trends, and expensive analytics remain below the hero.

### Workspace Hero

For ongoing operational workspaces. It may show object identity, lifecycle context, and compact posture. Workflow instructions, diagnostics, remediation, and historical evidence remain below the hero.

### Wizard Hero

For create, register, import, and guided setup workflows. It may show the current step and short phase context. Hero height remains stable between steps.

### Detail Hero

For one managed object. It prioritizes object identity, environment or scope, provider or type, lifecycle context, and primary object actions.

## Empty Hero

The hero remains visible when the page has no records.

Required:

- eyebrow
- title
- supporting description
- two or three factual metadata labels
- creation or recovery action when authorized

Use factual context such as `0 Connections` or `No Active Binding`. The content region below the hero owns the full empty-state explanation. Do not repeat identical no-data copy in both places.

## Busy Hero

HTMX requests, filtering, pagination, polling, runtime refresh, validation, synchronization, and background jobs must not replace or re-render the hero.

Do not:

- hide the hero
- replace it with a spinner or skeleton
- collapse it
- dim the entire hero
- target it with routine HTMX swaps

Loading appears in the affected content card or initiating control. A disabled action must retain its dimensions and position.

## Hero stability

The following remain stable during dynamic operations:

- outer height
- padding
- leading icon
- eyebrow position
- title position
- description position
- metadata row
- action group
- right context-panel geometry

Filters, search, pagination, polling, validation, inventory synchronization, and runtime updates must not cause layout jumps. Long dynamic values use canonical display names, concise presentation, or a detail view rather than local hero overrides.

## Hero content rule

Every hero answers five questions:

1. **Where am I?** — Eyebrow.
2. **What page or object is this?** — Title.
3. **What is its purpose?** — Supporting description.
4. **What is the current context?** — Metadata and optional compact posture.
5. **What is the primary action?** — Right-side action group.

Required hierarchy:

`Identity → Purpose → Context → Action`

Content that does not answer one of these questions belongs below the hero.

## Copy density budget

Hero geometry does not compensate for verbose copy. Authenticated workspace heroes use the following content budget:

- description target: 7–12 words; hard maximum 16 words;
- right-panel title: normally 2–4 words;
- status label: normally 1–3 words;
- metric label: normally 1–3 words;
- metric helper: optional and normally no more than 4 words.

Inventory and operations context metrics normally include a one-to-four-word helper when it clarifies the value. A fully self-explanatory metric may use label + value only. Explanations, evidence boundaries, and longer interpretation belong below the hero. Repeated phrases such as “from committed Kubernetes inventory snapshots” must not appear on every resource page when the shared Snapshot Context already owns that boundary.

## Density

Maximum content:

- one eyebrow
- one title
- one description
- two or three metadata labels
- two normal actions; three visible actions absolute maximum
- one optional context panel
- four metrics maximum in that panel

A hero does not contain tables, charts, diagnostic lists, long progress areas, multiple nested cards, or a mini-dashboard.

## Responsive behavior

Desktop uses the 7/5 grid. Tablet and mobile preserve this order:

1. Eyebrow.
2. Title.
3. Description.
4. Metadata.
5. Supporting context.
6. Actions.
7. Page content.

Actions never move above the title. Mobile wrapping may increase height naturally; page-local breakpoint geometry is not allowed.

## Accessibility and performance

- One `h1` per page.
- WCAG AA contrast.
- Visible keyboard focus.
- Icon-only actions have accessible names.
- State wording accompanies color.
- Hero data is lightweight page context.
- Historical metrics, large inventory counts, capability validation, runtime history, and expensive analytics load below the hero.

## Shared macros

Use:

- `page_hero.shell_classes()`
- `page_hero.layout_classes()`
- `page_hero.content_classes()`
- `page_hero.aside_classes()`
- `page_hero.intro(...)`
- `page_hero.title_classes()`
- `page_hero.description_classes()`
- `page_hero.metadata_row_classes()`
- `page_hero.action_group_classes()`
- `page_hero.primary_action_classes()`
- `page_hero.secondary_action_classes()`
- `page_hero.destructive_action_classes()`
- `page_hero.meta_label(...)`

Do not copy their utility strings into page templates.

## Compliance checklist

- Correct official hero type.
- Shared component used.
- 248/280 px baseline retained.
- 7/5 desktop split retained.
- Typography matches the contract.
- Description remains within two lines.
- Two or three metadata labels in canonical order.
- Primary action is white with Violet text.
- Operational state uses semantic color.
- Hero does not re-render during routine dynamic operations.
- Responsive order remains stable.
- Accessibility and lightweight-data rules pass.


Primary hero actions use a white surface with KAORI Violet text and a natural soft-violet hover state.

## Full-Application Audit Guardrail

The July 2026 full audit requires every Hero right-side panel rendered through
`page_hero.aside_classes()` to use `page_hero.context_panel_classes()` for its
outer panel geometry. Page-specific content may vary, but local copies of the
panel surface, border, minimum height, and padding are not allowed.

Human-readable metadata fragments use Title Case. Technical identifiers retain
their canonical casing and must not be passed through a mechanical whole-string
Title Case transformation.

## Reusability Enforcement — July 2026

Infrastructure Integrations and Kubernetes Integrations are the canonical visual references, but they do not own page-local styling. Their layout is produced from the same `page_hero` primitives used throughout KAORI.

The full-application audit covers 74 authenticated Hero templates. A compliant Hero must compose shared shell, layout, content, intro, title, description, metadata, aside, context-panel, metric, and action primitives. Domain-specific components may encapsulate semantic content, but must call the same shared primitives internally.

The following local copies are prohibited:

- Violet Hero shell geometry;
- 7/5 grid classes;
- title or description typography;
- metadata row spacing;
- right-side context-panel surface and minimum height;
- context metric-card geometry;
- Hero CTA geometry.

The contract is enforced by `tests/contracts/ui/test_global_hero_reusability_contract.py`.

## Violet-surface contrast guardrail

The Hero right-side panel sits on a Violet surface and does not inherit ordinary dark-page semantic label treatments.

- Context status labels use an opaque white surface with a dark semantic or Violet foreground.
- Context status text must not be truncated.
- Context actions keep a white surface and Strong Violet text in both light and dark appearance.
- Hover may strengthen border and shadow, but must not replace the white action surface with a translucent dark-mode Violet surface.
