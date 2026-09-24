# KAORI Design System v2 Reference Implementation and Enforcement Map

**Parent authority:** #572  
**Workstream:** #609  
**Scope:** Production-reference, validation-ownership, and design-system extension policy

## Purpose

This document is the final Design System v2 reference and enforcement coverage map. It connects current design authority to shared implementation, active production references, executable validation, and governed Visual QA.

It does not create demo pages, a second component library, or a new validation framework.

The governing chain is:

```text
Design authority
→ shared implementation owner
→ active production reference
→ executable verifier / contract
→ canonical viewport + theme evidence
→ human UAT where visual judgment remains necessary
```

A production reference proves that a component or pattern is used in the real KAORI product. It is not a frozen visual specimen and does not override the canonical component/pattern authority.

## Coverage Principles

1. Use the current authority order in `DESIGN_SYSTEM.md`.
2. Reuse the semantic owner registered in `components/REUSABLE_COMPONENT_OWNERSHIP.md`.
3. Classify page intent through `patterns/PAGE_ARCHETYPE_AND_NAVIGATION_REGISTRY.md`.
4. Extend existing verifiers/contracts when machine enforcement is possible.
5. Use `KAORI_VISUAL_QA.md` for viewport/theme/rendered evidence.
6. Treat historical locks and audits as evidence only.
7. Never increase a debt/style baseline merely to make a failing gate green.
8. Page-local overrides are not accepted substitutes for shared ownership.

## Global Authority Coverage

| Concern | Shared implementation owner | Active production reference | Executable enforcement | Visual / UAT evidence |
| --- | --- | --- | --- | --- |
| Global tokens / semantic color | `frontend/styles.css` | authenticated shell and all shared components | `verify_ui_style.py`; dark-mode contracts | canonical light/dark Visual QA |
| Dark mode | global token layer + shared components | authenticated application shell | `verify_dark_mode_standard.py`; design contracts | canonical light/dark viewport evidence |
| Typography / density | shared component typography + `FOUNDATION_AND_CONTENT_DENSITY.md` | Hero, tables, forms, cards across current production pages | `verify_ui_style.py`; design contracts | Visual QA typography/density rubric |
| Responsive / interaction | shared shell/components + `RESPONSIVE_ACCESSIBILITY_INTERACTION.md` | authenticated shell, overlays, inventory/detail and operational workspaces | browser UI suites + design contracts | canonical viewport matrix |
| Reuse ownership | `components/REUSABLE_COMPONENT_OWNERSHIP.md` | active consumers across all product domains | `verify_ui_reuse.py` + ownership contracts | shared-component Visual QA review |

## Shared Component Family References

| Family | Canonical owner | Production reference | Primary enforcement owner |
| --- | --- | --- | --- |
| Hero and context | `components/page_hero.html`; `components/HERO.md` | Kubernetes/Object Storage operational dashboards; Inventory pages; Welcome | `verify_hero_component_standard.py`; Hero contracts; browser Hero assertions |
| Readiness / empty / blocked | shared operational callout + state components | Kubernetes zero-cluster onboarding; Inventory blocked/zero states | empty-state contracts; Hero/readiness contracts |
| Section shells / operational metrics | `operational_section_card.html`; `operational_metric_card.html` | Kubernetes/Object Storage dashboards and Integration workspaces | `verify_ui_reuse.py`; `verify_ui_style.py`; design contracts |
| Tables / filters / loading / pagination | `table.html`; `table_primitives.html`; `table_registry.html`; `loading_bar.html`; `pagination.html` | Kubernetes Node Inventory; Notification Center; Object Storage Inventory | `verify_filter_layout_standard.py`; table/filter contracts; `verify_ui_style.py` |
| Status labels | `table_label.html` + semantic component helpers | Inventory and registry tables | `verify_ui_style.py`; table/label contracts |
| Forms / action bars / context rail | `form_field.html`; `form_action_bar.html`; `form_with_context_rail.html` | reviewed ConfigMap/Secret operations; Protected Reveal; Integration registration | form/context contracts; `verify_ui_reuse.py`; `verify_ui_style.py` |
| Destructive confirmation | `destructive_confirmation_modal.html` + shared JS | ConfigMap/Secret delete flows and persisted-object detach/delete flows | interaction contracts + browser evidence |
| Resource detail modal / drawer | `resource_detail_modal.html`; `side_drawer.html`; shared detail runtime | Node/Namespace/Workload/Pod/Service/Ingress/Storage/Configuration Inventory; Topology inspector | browser interaction tests; UI reuse/style checks; #614 for generic side-drawer focus parity |
| Navigation / application shell | shared sidebar/navbar/navigation owners | every authenticated KAORI workspace | `verify_application_shell_standard.py`; shell contracts; responsive browser tests |
| Operational toast / feedback | `operational_toast.html`; `operational_progress_toast.html`; `operation_feedback_oob.html` | Metrics Source, Alertmanager, and provider operational flows | application-shell/feedback contracts + browser tests; #613 for reduced-motion completion |
| Workspace tabs | `workspace_tabs.html`; `framed_workspace_tabs.html`; `segmented_tabs.html`; `content_tabs.html` | Kubernetes Operations, Integrations, Analytics, Topology | `verify_ui_style.py`; reuse ownership contracts; styling-guide contract |
| Context / guidance / summary cards | `context_guidance_card.html`; `information_guide_card.html`; `workspace_summary_card.html`; `page_context_card.html` | Register Alertmanager Instance; Alertmanager Instance Manage | reusable ownership contracts; `verify_ui_reuse.py`; `verify_ui_style.py` |

## Page Archetype Production References

The page-archetype taxonomy remains owned by `patterns/PAGE_ARCHETYPE_AND_NAVIGATION_REGISTRY.md`. This table records the active reference used when reviewing composition and enforcement.

| Archetype | Production reference |
| --- | --- |
| Landing | `app/templates/welcome/index.html` |
| Overview | `app/templates/kubernetes/inventory/overview/index.html`; `app/templates/integrations/overview.html`; `app/templates/reports/overview/index.html` |
| Dashboard | `app/templates/kubernetes/dashboard/index.html` + `patterns/OPERATIONAL_DASHBOARD.md` |
| Inventory / List | `app/templates/kubernetes/inventory/nodes/index.html`; `app/templates/kubernetes/inventory/pods/index.html` |
| Analytics | `app/templates/kubernetes/analytics/overview/index.html`; Capacity; Alerts & Anomalies workspaces |
| Operational Workspace | `app/templates/kubernetes/operations/configmaps/index.html`; Kubernetes Secret Operations |
| Configuration / Manage | Metrics Source instance detail; MinIO instance detail; `components/INTEGRATION_MANAGE_WORKSPACE.md` |
| Detail / Inspector | `app/templates/components/resource_detail_modal.html`; Kubernetes Topology inspector |
| Workflow / Wizard | `app/templates/reports/generate/index.html` |
| Administration | Users, Roles, Identity Providers, and General Settings workspaces |

A new route does not become a new archetype merely because its domain is new. Classify operator intent first, then compose the existing pattern.

## Navigation / Tab Production References

| Semantic relationship | Shared owner | Production reference |
| --- | --- | --- |
| Local mutually exclusive views | Compact Segmented Tabs | Kubernetes Topology Graph/List and Details/Relationships |
| Related subordinate content views | Content Tabs | Kubernetes/Object Storage Analytics; Alert Intelligence |
| Peer domains within an explicit framed parent workspace | Framed Workspace Tabs | Integration Overview / Integration detail |
| Peer sections defining the workspace itself | Integrated Workspace Tabs | Kubernetes Operations Dashboard |
| No tab relationship | normal sections/routes/cards | use when hierarchy is clearer without tabs |

Page-local `role="tablist"` geometry is not an extension mechanism.

## Enforcement Coverage Map

| Rule family | Existing executable owner |
| --- | --- |
| Page-local style drift / raw colors / arbitrary typography / radius / local Hero / pagination / tab copies | `scripts/verify_ui_style.py` |
| Inline style/script/event-handler debt and reusable ownership boundaries | `scripts/verify_ui_reuse.py` |
| Hero profile/copy/shared-shell ownership | `scripts/verify_hero_component_standard.py` |
| Dark-mode token/surface ownership | `scripts/verify_dark_mode_standard.py` |
| Filter geometry / Clear Filters ownership | `scripts/verify_filter_layout_standard.py` |
| Application shell / navbar interaction ownership | `scripts/verify_application_shell_standard.py` |
| Jinja/component documentation contracts | `tests/contracts/design/` |
| Responsive/focus/keyboard/HTMX representative behavior | `tests/ui/` |
| Rendered geometry / visual signatures / evidence inventory | `tests/ui/visual_audit.py`; `tests/ui/test_visual_regression.py` |
| Human visual acceptance | `docs/design/KAORI_VISUAL_QA.md` |

`scripts/quality_gate.sh` already invokes the canonical UI style, UI reuse, Hero, dark-mode, filter-layout, and application-shell verifiers. #609 does not add another validation script.

## Baseline and Debt Policy

Two existing debt ceilings are relevant:

- `docs/architecture/ui-style-debt-baseline.json` for style-drift candidates;
- `docs/architecture/ui-inline-debt-baseline.json` for inline style/script/event-handler debt.

The current verifiers enforce both directions:

- a count **above** the baseline fails because debt increased;
- a count **below** the baseline also requires updating the baseline in the same change so retired debt cannot silently return later.

### Baseline increase rule

A baseline increase is exceptional. It requires:

1. an implementation issue that identifies the semantic/technical need;
2. evidence that an existing shared owner cannot represent the requirement;
3. explicit review of why extending the shared owner is not appropriate;
4. the baseline update in the same PR as the authorized implementation;
5. existing Developer Check and Full Admission evidence.

A failing check is never, by itself, justification to raise a baseline.

### Baseline decrease rule

When debt is removed, lower the baseline in the same PR. Do not leave unused allowance behind.

## Design-System Change / Extension Policy

For every UI change:

1. classify the page using the page-archetype registry;
2. identify the semantic component family using the reusable ownership registry;
3. inspect current production references before changing geometry or interaction;
4. extend the shared owner when the need is reusable;
5. keep domain data, permissions, workflow semantics, and provider authority in the owning domain;
6. extend an existing verifier/contract when the new boundary is machine-checkable;
7. run canonical viewport/light-dark evidence when rendered behavior changes;
8. record a bounded issue before creating a genuinely new semantic component or pattern.

A new component is justified by a new semantic role, not aesthetic preference.

## Exception Policy

A design-system exception must be explicit, bounded, and traceable.

Accepted exception characteristics:

- the semantic role cannot be represented without distorting an existing component;
- the exception has one documented owner;
- responsive, dark-mode, accessibility, loading/state, and focus behavior are defined;
- it has production use, not a demo-only consumer;
- it has a removal/review path if temporary;
- verifier/contract ownership is identified.

Prohibited exception patterns:

- page-local copied shared geometry;
- device-specific CSS patches for a shared component;
- arbitrary font-size/radius/color compensation;
- duplicate HTMX/focus/loading state owners;
- hidden baseline increases;
- demo-only reference implementations;
- aesthetic-only component variants.

## Visual QA and Human Acceptance

Machine enforcement proves deterministic invariants; it does not decide visual preference.

For user-visible changes, the candidate must use the existing Visual QA authority for:

- canonical viewport evidence;
- light/dark parity;
- hierarchy, spacing, alignment, density, and responsive recomposition review;
- shared-component ownership review;
- intentional baseline capture when the reviewed visual signature changes.

Human UAT remains final authority for hierarchy preference, visual balance, and acceptance of intentional visual changes. A rejected measurable behavior should become an executable shared contract when practical.

## Current Bounded Follow-Up Gaps

#608 identified two implementation gaps that remain outside #609's documentation scope:

- #613 — reduced-motion coverage across shared interaction feedback;
- #614 — generic side-drawer focus containment and focus return.

These do not create new Design System v2 authorities. Their implementations must extend the shared owners and existing test/verifier families.

## #609 Completion Boundary

#609 is complete when:

- important locked shared families have an active production reference;
- all registered page archetypes have production references;
- documentation → shared implementation → executable enforcement → Visual QA ownership is explicit;
- baseline/debt and extension/exception policy is explicit;
- no new one-off verifier or demo-only reference implementation is introduced.

Final broad visual acceptance remains owned by parent #572.
