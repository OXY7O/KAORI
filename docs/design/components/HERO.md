# KAORI Hero Component Standard v1.6

This document is the authoritative implementation and semantic contract for authenticated KAORI page heroes.

Canonical implementation:

```text
app/templates/components/page_hero.html
```

Canonical enforcement:

```text
scripts/verify_hero_component_standard.py
tests/contracts/design/test_hero_component_standard_contract.py
```

The v1.6 change does **not** redesign the Hero. It preserves the accepted v1.5 Violet surface, geometry, typography, dark-mode ownership, accessibility, HTMX stability, context metric limit, and right-header accessory registry. v1.6 adds reusable **Hero Profile** ownership and explicit **Hero State** semantics so pages with the same operational role cannot drift while still passing visual token checks.

## Purpose

A Hero answers, in order:

1. Where am I?
2. What page or object is this?
3. What is the page used for?
4. What scope, evidence boundary, readiness, or posture applies?
5. What is the primary next action?

Required hierarchy:

```text
Identity → Purpose → Context → Action
```

Tables, charts, evidence lists, workflow instructions, diagnostics, pagination, and filters remain below the Hero.

## Hero Profile and Hero State

A **Hero Profile** describes the page role. A **Hero State** describes the current operational condition. They are independent concepts.

Approved profile vocabulary begins with:

- `landing` — entry/access orientation;
- `operational-dashboard` — snapshot-backed operational dashboards;
- `operational-workspace` — normal operational workspaces;
- `analytics` — analytical evidence and posture workspaces;
- `inventory-operations` — inventory, governance, and operational resource workspaces;
- `transactional-admin` — create/edit/configuration and administration workflows.

Approved state vocabulary:

- `normal` — the workspace is operational and expected evidence is available for its current scope;
- `blocked` — a required setup or readiness dependency prevents the primary operational workflow;
- `degraded` — the workspace remains usable while one dependency or capability is degraded;
- Landing is an explicit profile exception and does not need an operational state presentation.

The governing rule is:

> **same Profile + same State = same structural Hero grammar.**

A domain may change nouns, values, icons, and destination URLs. It must not change the profile's shell hierarchy, metadata roles, context metric roles, state presentation, or action role.

## Canonical reusable renderer ownership

High-value families must use a high-level profile renderer from `components/page_hero.html` instead of rebuilding the shell from low-level primitives. The first locked profile renderer is:

```jinja
page_hero.operational_dashboard(...)
```

It owns the complete Dashboard Hero composition: shell, layout, identity, title, description, metadata row, context panel, state presentation, two context metrics, and action/footer slot.

Shared blocked Hero-right context composition is owned by:

```jinja
page_hero.blocked_context_body(...)
```

This renderer owns the context panel shell, approved header accessory, exactly two compact readiness metrics, and one concise information strip. Domain wrappers provide semantic values only.

Low-level macros such as `shell_classes()`, `layout_classes()`, `intro(...)`, and `context_metric(...)` remain compatibility primitives for existing families while their profile migrations are performed. New same-context family implementations must not fork a fresh page-local full Hero shell when an approved profile renderer exists.

## Canonical composition

A normal operational Hero contains:

- one eyebrow;
- one leading icon;
- one authoritative `h1`;
- one concise description;
- **exactly three metadata** items for Normal operational profiles;
- one optional right-side context panel;
- zero to two compact context metrics;
- one primary action when the profile is interactive.

Explicit exceptions:

- Landing may use two orientation/access metadata items;
- Blocked may use reduced readiness metadata when that better communicates the setup boundary;
- Degraded keeps the usable operational structure and expresses degradation in status/context instead of pretending the page is blocked.

Metadata communicates identity, scope, evidence boundary, or stable operating context. Health/severity belongs in semantic status components.

## Operational Dashboard Hero Profile

Kubernetes Operations Dashboard and Object Storage Operations Dashboard are the paired reference implementation.

The profile uses exactly three metadata roles:

1. Inventory evidence;
2. analytics/metrics evidence;
3. alert evidence.

The right-side panel uses two semantic metric roles in this order:

1. `Active Scope`;
2. `Data Authority`.

`Data Authority` describes the request-time evidence boundary, not whether a particular observation exists. For the current paired dashboards the authority is `Committed Snapshots`.

The Dashboard Hero action role is **operational source/readiness management**. Domain labels and URLs may differ, but the action must remain in that semantic role. Generic navigation that does not manage readiness/source configuration must not replace it.

The dashboard renderer exposes `data-kaori-hero-profile="operational-dashboard"` and `data-kaori-hero-state="..."` for contract and rendering verification.

## Blocked readiness grammar

Blocked state remains profile-specific while repeated geometry stays shared. The Hero remains visible, the right context tells the operator why the workspace cannot proceed, and detailed remediation stays immediately below the Hero.

### Operational Dashboard blocked context

The paired Kubernetes/Object Storage dashboards use:

1. `Dashboard Readiness`;
2. domain-specific setup title;
3. semantic `Blocked` status;
4. `Active Scope`;
5. `Data Authority`;
6. one concise setup information strip.

`Data Authority` remains truthful while blocked; it describes the evidence boundary, not successful evidence availability.

### Operational workspace blocked context

Inventory, Kubernetes Operations, Kubernetes Governance, and equivalent Object Storage operational workspaces follow the Kubernetes Operations/Governance reference pattern. The context uses the domain readiness label/title, one resource-availability metric such as `Connected Clusters` or `Registered Systems`, a `Workspace State` value of `Blocked`, and one concise information strip. The shared renderer owns the geometry; domain wrappers own nouns and setup wording.

The section blocker below the Hero uses `components/states/_blocked_state.html` with setup status, concise description, ordered steps when useful, and one permission-aware primary action. Pages with the same semantics must not rebuild a local blocker card.

### Analytics blocked context

Analytics uses:

1. `Analytics Readiness`;
2. concise blocker title;
3. semantic `Blocked` status;
4. `Active Scope`;
5. `Missing Evidence`;
6. one concise next-requirement information strip.

The Hero does not prioritize generic `Current Step` / `Progress` values. Detailed dependency progress is owned by the shared `Analytics Setup Path` surface below the Hero, which shows Complete / Current Blocker / Pending states and the authoritative next action.

## Theme and surface contract

The Hero surface is owned by `.kaori-hero-shell` and `--kaori-hero-background`. Templates must not use `bg-kaori-primary` for the outer Hero shell.

Light mode uses the canonical Bright Violet identity surface. Dark mode uses the controlled tonal gradient defined in `components/DARK_MODE.md`; it is the only approved authenticated-page gradient.

Internal surfaces remain component-owned:

- `.kaori-hero-panel` — right context panel;
- `.kaori-hero-tile` — metric cards, leading/context icons, supporting information;
- `.kaori-hero-chip` — eyebrow and metadata labels.

## Technical geometry

The accepted v1.5 geometry remains unchanged.

| Element | Canonical implementation | Effective geometry |
|---|---|---:|
| Outer shell | `.kaori-hero-shell min-h-[15.5rem] lg:min-h-[17.5rem]` | theme-owned background, 248 px / 280 px minimum |
| Outer padding | `p-5 lg:p-6` | 20 px / 24 px |
| Outer radius | `rounded-2xl` | 16 px |
| Internal grid | `min-h-[13rem] lg:min-h-[14.5rem]` | 208 px / 232 px minimum |
| Grid gap | `gap-5` | 20 px |
| Desktop layout | `xl:grid-cols-12` | content 7 / context 5 |
| Context panel | `.kaori-hero-panel min-h-[13rem] rounded-xl p-4` | 208 px minimum |
| Metric grid | `grid-cols-2 auto-rows-fr gap-2` | two equal-height columns |
| Footer slot | `mt-auto min-h-10` | bottom-aligned 40 px minimum |
| Context action | `h-10` | 40 px |

The right panel retains the same 12 px row rhythm. Do not add page-local height, padding, margin, radius, or breakpoint compensation.

## Technical typography

| Element | Tailwind owner | Effective typography |
|---|---|---|
| Eyebrow | `intro()` / `eyebrow()` | 12 px, semibold, uppercase |
| Title | `title_classes()` | 30 px compact / 36 px from `sm`, bold |
| Description | `description_classes()` | 16 px, regular, 28 px line height, max width 44 rem |
| Metadata label | `meta_label()` | 12 px semibold, 32 px minimum height |
| Context eyebrow | `context_panel_eyebrow_classes()` | 12 px semibold, uppercase |
| Context title | `context_panel_title_classes()` | 16 px semibold, 24 px line height |
| Status badge | `context_status_badge()` | 12 px semibold, 28 px minimum height |
| Metric value | `context_metric_value_classes()` | 18 px semibold, 24 px line height |
| Context action | `context_action_classes()` | 14 px semibold, 40 px height |

Page templates must not add arbitrary Hero typography overrides.

## Context panel accessory registry

Exactly three top-right header accessory variants are approved:

1. **Action Icon Box** — interactive icon-only immediate context action;
2. **Context Icon Box** — non-interactive domain/identity/scope marker;
3. **Status Badge Box** — non-interactive semantic readiness/health/lifecycle state.

Do not invent a fourth header-accessory geometry.

`context_card(...)`, `context_card_body(...)`, and `blocked_context_body(...)` enforce **exactly two compact metrics** through `metrics[:2]`.

## Content density

Copy budget remains:

- description target: 7–12 words; hard maximum 16 words;
- right-panel title: 2–4 words;
- status label: 1–3 words;
- metric label: 1–3 words;
- metric helper: optional and concise.

Character count may be audited as an additional safety rail, but word budget and semantic clarity are authoritative. Long evidence explanations belong below the Hero.

## Dynamic and HTMX behavior

The Hero is a stable page anchor. Filtering, pagination, polling, runtime refresh, inventory synchronization, validation, and background jobs must not replace or collapse it.

A lazy right-side context partial may update only its owned context region while preserving shell dimensions.

## Empty, Blocked, and Degraded behavior

The Hero remains visible when no records exist or a dependency is blocked/degraded.

Blocked state communicates setup/readiness and does not pretend normal operational evidence is available. Degraded state preserves the usable workspace and expresses dependency degradation through status/context. Full remediation workflows remain below the Hero.

## Accessibility

- exactly one `h1` per page;
- visible keyboard focus;
- status communicated by text/icon, never color alone;
- context `<aside>` has a meaningful accessible label;
- decorative icons use `aria-hidden="true"`;
- dynamic values remain readable and are not silently truncated.

## Public macro contract

### Profile renderers

- `operational_dashboard(...)`

### Shared blocked context renderer

- `blocked_context_body(...)`

### Compatibility shell and identity primitives

- `shell_classes()`
- `layout_classes()`
- `content_classes()`
- `aside_classes()`
- `intro(...)`
- `title_classes()`
- `description_classes()`
- `metadata_row_classes()`
- `meta_label(...)`

### Context panel primitives

- `context_panel_classes()`
- `context_card(...)`
- `context_card_body(...)`
- `context_status_badge(...)`
- `context_header(...)`
- `context_header_action(...)`
- `context_header_status(...)`
- `context_panel_metrics_classes()`
- `context_metric(...)`
- `context_info(...)`
- `context_actions_classes(...)`
- `context_action_classes()`
- `context_single_action_classes()`

Compatibility primitives are not permission to create a new same-context family fork. Profile renderers and shared blocked context ownership take precedence wherever defined.

## Domain extensions

Domain documents may constrain content but cannot override shared geometry or typography.

- Kubernetes Analytics: `components/ANALYTICS_HERO.md`
- Operational Dashboard: `patterns/OPERATIONAL_DASHBOARD.md`

## Enforcement and migration guardrail

The verifier must:

- verify canonical implementation and documentation tokens;
- verify required/removed macro ownership;
- verify every compatibility shell still composes canonical primitives;
- verify paired Operational Dashboard pages call the single shared profile renderer and do not locally assemble the shell;
- verify shared blocked-context wrappers do not rebuild context-panel geometry locally;
- verify Object Storage Analytics Normal metadata does not conditionally fall from three to two items;
- reject unmanaged Hero-like local surfaces that bypass the component;
- report compatibility-shell and profile-consumer counts separately.

A family migration to a profile renderer must add family-level parity contracts before removing its compatibility composition.

## Change procedure

A Hero-standard change must update, in the same work item:

1. `app/templates/components/page_hero.html`;
2. this document;
3. affected domain/pattern documents;
4. `scripts/verify_hero_component_standard.py`;
5. `docs/design/components/DARK_MODE.md` only when theme behavior changes;
6. Hero/dark-mode/family contract tests;
7. the current Hero alignment audit when the decision materially changes ownership.

Run:

```bash
python scripts/verify_hero_component_standard.py
python -m pytest -q \
  tests/contracts/design/test_hero_component_standard_contract.py \
  tests/contracts/design/test_dark_mode_standard_contract.py
```

## Review checklist

- profile and state are explicit for a profile-managed family;
- same Profile + same State has one composition;
- one `h1` and one concise description;
- Normal operational profile has exactly three metadata items;
- Landing/Blocked/Degraded exceptions are explicit;
- context panel has no more than two metrics;
- one primary action preferred and its semantic role matches the profile;
- no page-local Hero geometry or typography fork;
- Hero remains stable during HTMX/background activity;
- technical identifiers preserve source casing;
- documentation, verifier, and family contracts are synchronized.
