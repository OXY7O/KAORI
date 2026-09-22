# KAORI Hero Component Standard v1.8

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

The v1.8 change preserves the accepted Violet identity, dark-mode ownership, accessibility, HTMX stability, context semantics, and tablet/desktop Hero grammar while adding a **phone-native compact composition** below `sm` (640 px). The phone contract removes desktop minimum-height floors, reduces padding/gaps and typography, omits the decorative leading icon, and prioritizes primary metadata/context evidence. From `sm` upward, the established v1.7 geometry and typography remain authoritative. UAT clarification under #470 makes the description intent executable: 7–15 words, preferably 8–12 words, one action-oriented sentence, maximum 68 characters, and **one visual line at canonical desktop/laptop widths (1280 px and above)** without ellipsis, clipping, or hidden overflow. Tablet/mobile may wrap naturally for readability.

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

It owns the complete Dashboard Hero composition: shell, layout, identity, title, description, persistent metadata row, context panel, state presentation, two context metrics, and action/footer slot.

Operational metadata is rendered through the shared persistent renderer. Where a profile defines metadata, the same metadata roles remain present in **normal, blocked, and degraded** states. A blocked/degraded readiness panel is additive context and must never remove the left-side metadata row.

Shared blocked Hero-right context composition is owned by:

```jinja
page_hero.blocked_context_body(...)
```

This renderer owns the context panel shell, approved header accessory, exactly two compact readiness metrics, and one concise information strip. Domain wrappers provide semantic values only.

Low-level macros such as `shell_classes()`, `layout_classes()`, `intro(...)`, and `context_metric(...)` remain compatibility primitives for existing families while their profile migrations are performed. New same-context family implementations must not fork a fresh page-local full Hero shell when an approved profile renderer exists.

## Canonical composition

An operational Hero contains:

- one eyebrow;
- one leading icon from `sm` upward; on phone the leading icon is decorative and omitted;
- one authoritative `h1`;
- one concise description;
- **exactly three metadata** items for profiles that define the three-slot operational metadata contract; on phone only the primary item is visible while the remaining items stay present in the DOM and return at `sm`;
- one optional right-side context panel;
- zero to two compact context metrics; on phone the primary metric is visible and secondary detail returns at `sm`;
- one primary action when the profile is interactive.

Explicit exceptions:

- Landing may use two orientation/access metadata items;
- Blocked preserves the profile metadata row and adds readiness/remediation context;
- Degraded preserves the usable operational structure and metadata row while expressing degradation in status/context.

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

The Dashboard Hero action role is **operational source/readiness management**. Kubernetes Dashboard uses the canonical label `Open Cluster Integrations` and destination `integrations.kubernetes`; generic `Add Cluster` wording is prohibited. Other domains may use an equivalent source-management label and route without changing the semantic role. Generic navigation that does not manage readiness/source configuration must not replace it.

The dashboard renderer exposes `data-kaori-hero-profile="operational-dashboard"` and `data-kaori-hero-state="..."` for contract and rendering verification. Its metadata surface exposes `data-kaori-hero-metadata` and `data-kaori-hero-metadata-policy="persistent"` for state-level regression verification.

## Blocked readiness grammar

Blocked state remains profile-specific while repeated geometry stays shared. The Hero remains visible, the left-side operational metadata remains visible, the right context tells the operator why the workspace cannot proceed, and detailed remediation stays immediately below the Hero.

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

Blocked Analytics still renders the profile's three metadata labels through `page_hero.analytics_metadata(...)`. The Kubernetes Storage Analysis regression case is authoritative: readiness may change, but metadata remains visible beside it.

The Hero does not prioritize generic `Current Step` / `Progress` values. Detailed dependency progress is owned by the shared `Analytics Setup Path` surface below the Hero, which shows Complete / Current Blocker / Pending states and the authoritative next action.

## Theme and surface contract

The Hero surface is owned by `.kaori-hero-shell` and `--kaori-hero-background`. Templates must not use `bg-kaori-primary` for the outer Hero shell.

Light mode uses the canonical Bright Violet identity surface. Dark mode uses the controlled tonal gradient defined in `components/DARK_MODE.md`; it is the only approved authenticated-page gradient.

Internal surfaces remain component-owned:

- `.kaori-hero-panel` — right context panel;
- `.kaori-hero-tile` — metric cards, leading/context icons, supporting information;
- `.kaori-hero-chip` — eyebrow and metadata labels.

## Technical geometry

v1.8 defines one shared responsive Hero authority with a phone-native compact composition and the established geometry from `sm` upward.

| Element | Phone `<640 px` | `sm+` / desktop |
|---|---|---|
| Outer shell | `.kaori-hero-shell p-4` with no minimum-height floor | `sm:min-h-[15.5rem] sm:p-5 lg:min-h-[17.5rem] lg:p-6` — 248 px / 280 px minimum from `sm` |
| Outer radius | `rounded-2xl` | unchanged, 16 px |
| Internal grid | `gap-4` with no minimum-height floor | `sm:min-h-[13rem] sm:gap-5 lg:min-h-[14.5rem]` |
| Intro composition | one content column; decorative leading icon omitted | two-column icon/content grammar restored at `sm` |
| Desktop layout | single stacked flow | `xl:grid-cols-12`, content 7 / context 5 |
| Context panel | compact `p-3 gap-2.5`, no minimum-height floor | `sm:min-h-[13rem] sm:p-4 sm:gap-3` |
| Metric grid | one visible primary metric; secondary metric remains in DOM but hidden | `sm:grid-cols-2 sm:auto-rows-fr`, both metrics visible |
| Metadata row | one visible primary item; remaining items remain in DOM but hidden | all profile metadata items visible from `sm` |
| Footer slot | `mt-auto min-h-10` when present | unchanged |
| Context action | `h-10` | unchanged |

Phone compaction is presentation-only. It must not remove the page title, primary scope/readiness evidence, semantic status, or primary action.

The right panel retains the same 12 px row rhythm. Do not add page-local height, padding, margin, radius, or breakpoint compensation.

## Technical typography

| Element | Tailwind owner | Effective typography |
|---|---|---|
| Eyebrow | `intro()` / `eyebrow()` | 12 px, semibold, uppercase |
| Title | `title_classes()` | 24 px / 32 px line height on phone; 36 px / 40 px from `sm`, bold |
| Description | `description_classes()` | 14 px / 24 px on phone; 16 px / 28 px from `sm`; natural wrapping below `xl`; one untruncated visual line from `xl` (1280 px) |
| Metadata label | `meta_label()` | 12 px semibold, 32 px minimum height |
| Context eyebrow | `context_panel_eyebrow_classes()` | 12 px semibold, uppercase |
| Context title | `context_panel_title_classes()` | 16 px semibold, 24 px line height |
| Status badge | `context_status_badge()` | 12 px semibold, 28 px minimum height |
| Metric value | `context_metric_value_classes()` | 18 px semibold, 24 px line height |
| Context action | `context_action_classes()` | 14 px semibold, 40 px height |

Page templates must not add arbitrary Hero typography overrides. Phone compaction is owned only by the shared Hero macros; page-local mobile title, description, metadata, or context forks are prohibited.

## Context panel accessory registry

Exactly three top-right header accessory variants are approved:

1. **Action Icon Box** — interactive icon-only immediate context action;
2. **Context Icon Box** — non-interactive domain/identity/scope marker;
3. **Status Badge Box** — non-interactive semantic readiness/health/lifecycle state.

Do not invent a fourth header-accessory geometry.

`context_card(...)`, `context_card_body(...)`, and `blocked_context_body(...)` enforce **exactly two compact metrics** through `metrics[:2]`.

## Content density

Copy budget is canonical and executable:

- description boundary: 7–15 words, preferably 8–12 words, maximum 68 characters;
- description form: one action-oriented complete sentence with no manual line break;
- desktop/laptop rendering: exactly one visual line from the canonical 1280 px laptop viewport upward, with no ellipsis, clipping, hidden overflow, or page-local typography shrink;
- right-panel title: 2–4 words;
- status label: 1–3 words;
- metric label: 1–3 words;
- metric helper: optional and concise.

Reference examples are `Review health, capacity, alerts, inventory, and prioritized actions.` and `Review report execution, artifact readiness, storage, and lifecycle state.`

Word count and the maximum 68 characters are executable copy-density boundaries. The rendered desktop/laptop single-line invariant is the visual authority: fitting the character budget alone is not sufficient if the text still overflows or wraps at the canonical 1280 px laptop viewport. The 8–12 word range is preferred for scanability. Descriptions remain action-oriented and start with an imperative-style action verb; semantic clarity remains mandatory. Long evidence explanations belong below the Hero.

## Dynamic and HTMX behavior

The Hero is a stable page anchor. Filtering, pagination, polling, runtime refresh, inventory synchronization, validation, and background jobs must not replace or collapse it.

A lazy right-side context partial may update only its owned context region while preserving shell dimensions. State changes must not remove a profile-defined persistent metadata row.

## Empty, Blocked, and Degraded behavior

The Hero remains visible when no records exist or a dependency is blocked/degraded.

Blocked state communicates setup/readiness and does not pretend normal operational evidence is available. Degraded state preserves the usable workspace and expresses dependency degradation through status/context. For operational profiles, persistent metadata remains present in normal, blocked, and degraded states. Full remediation workflows remain below the Hero.

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

### Persistent metadata renderers

- `persistent_metadata(...)`
- `analytics_metadata(...)`

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
- verify Analytics metadata uses the persistent shared renderer and remains outside blocker branches;
- enforce the description target and hard boundary for every Hero description that can be resolved deterministically from source;
- require the shared `kaori-hero-description` marker and desktop `xl:whitespace-nowrap` ownership so browser tests can verify one-line rendering and overflow without page-local selectors;
- audit shared profile-renderer descriptions at their call sites instead of bypassing copy checks because composition is centralized;
- reject unmanaged Hero-like local surfaces that bypass the component;
- report compatibility-shell, profile-consumer, and description-audit counts separately.

The canonical verifier enforces the 7–15 word boundary, maximum 68 characters, one complete sentence, action-oriented wording, no manual line break, shared description-marker ownership, and desktop single-line presentation ownership. Browser evidence remains responsible for proving that the rendered line fits without overflow at canonical desktop/laptop widths. The preferably 8–12 words range is an editorial target for scanability within that executable boundary.

Integration domain descriptions are audited from `app/definitions/catalogs/integrations/taxonomy.yaml` because `app/templates/integrations/domain.html` renders those descriptions dynamically. Other source-controlled dynamic Hero copy must gain an equally explicit audit path when introduced.

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
- one `h1` and one concise 7–15 word description, preferably 8–12 words, action-oriented, no more than 68 characters, and one visual line at canonical desktop/laptop widths;
- operational profile metadata is persistent in normal, blocked, and degraded states;
- phone presentation keeps primary metadata/context evidence visible while secondary detail is restored from `sm`;
- context panel has no more than two metrics;
- one primary action preferred and its semantic role matches the profile;
- no page-local Hero geometry or typography fork;
- dynamic Hero description sources have a deterministic verifier path;
- Hero remains stable during HTMX/background activity;
- technical identifiers preserve source casing;
- documentation, verifier, and family contracts are synchronized.
