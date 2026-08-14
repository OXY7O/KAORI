# Integrations Workspace Standard

> Status: Locked canonical baseline under **KAORI Integrations Lock v1** (`docs/design/KAORI_INTEGRATIONS_LOCK_V1.md`).

Latest locked refinement: **KAORI Integrations Lock v1.1**.

## Purpose

This standard aligns the Integrations Overview, provider registries, source bindings, runtime evidence, and Kubernetes connection workspace without flattening provider-specific operational detail.

## Global Hierarchy

```text
Hero
Controls / Filters
Bright Operational Evidence
Provider-Specific Technical Evidence
Darker Interpretation or Recommended Action
Pagination / Lifecycle Actions
```

Primary source, runtime, validation, capability, binding, and coverage evidence uses `bg-surface-card`. `bg-surface-hover` is reserved for interpretation, warning context, remediation, attention strips, and destructive-boundary guidance.

## Shared Components

Canonical Integrations presentation lives under:

```text
app/templates/integrations/components/_workspace.html
app/templates/integrations/components/_provider_registry.html
app/templates/integrations/components/_semantic_status.html
```

Responsibilities:

- `_workspace.html` owns section shells, headers, bright metric strips, controls, and interpretation panels.
- `_provider_registry.html` owns provider-registry headers, filters, loading, and full-page/HTMX pagination ownership.
- `_semantic_status.html` is the Integrations adapter to global `components/table_label.html`; it must not define an independent palette.

Provider templates supply factual labels, icons, endpoint data, compatibility evidence, and actions. They do not copy shared geometry or semantic colors.

## Domain Landing Workspace Contract

`Orchestration`, `Observability`, and `Storage` use one shared domain landing pattern. Domain pages do not invent provider-specific cards or a Storage-only composition.

```text
Hero / Domain Posture
Capability Registry
Domain Workspace
├── Provider Registry
└── Bindings
Domain Operating Boundary
```

The **Provider Registry** lists canonical `IntegrationInstance` targets owned by the domain. It uses the global five-row default and `5 / 10 / 25 / 50` page sizes, provider readiness, capability ownership, consumer-binding count, and one route back to the product-specific workspace. Provider workspace actions remain visible in the workspace header in both empty and populated states; registration/navigation actions MUST NOT exist only inside an empty-state row.

The **Bindings** tab is a consumer registry, not a duplicate of provider ownership. Native asset-owner attachments such as Kubernetes→`kubernetes_cluster` and MinIO→`object_storage_system` remain internal ownership evidence and are not displayed or counted as consumer bindings. The tab includes:

- Prometheus, Alertmanager, or future reusable-source bindings whose `asset_type` is owned by the current domain; and
- bindings whose source provider belongs to a source-oriented domain such as Observability.

This means Orchestration shows Prometheus/Alertmanager consumer bindings targeting Kubernetes clusters while Kubernetes API ownership remains in Provider Registry. Storage behaves the same way: MinIO owns the `object_storage_system`, while Prometheus and Alertmanager appear only after explicit consumer binding. Observability shows Prometheus/Alertmanager bindings across their consumer assets because those providers own the source side.

The **Provider Registry / Bindings** switch is server-owned but MUST use HTMX replacement of `#domain-workspace` with URL push-state. Tab switching must not perform a full document navigation; the shared content-tab contract owns `hx-get`, `hx-target`, `hx-select`, `hx-swap`, and an operation-scoped loading indicator.

Managed asset ownership is declared by Integration taxonomy capability metadata (`asset_types`). Domain landing services must remain provider-neutral and must not query `KubernetesConnection`, `PrometheusInstance`, `AlertmanagerInstance`, `MinioInstance`, or future provider-specific models directly.

Provider Core Validation and Binding Validation remain separate evidence boundaries on the domain page. Provider Registry readiness reflects provider Core Validation; the Bindings tab shows the selected consumer profile, selector, and binding validation status.

## Provider Front Page Contract

Kubernetes, Prometheus, Alertmanager, and MinIO provider landing pages use one canonical front-page hierarchy. Provider-specific technical evidence may differ inside the workspace, but the navigation and visual grammar must not.

```text
Operational Integration Hero
├── Registered Connections
├── Ready Connections
├── Consumer Bindings
└── Register Connection

<Provider> Integration Overview
├── Registered Connections
├── Validated Connections
├── Needs Attention
├── Coverage Gaps
├── Integration Contract
├── Consumer Resolution
└── Authority Boundary

Provider Workspace
├── Integration Coverage
└── Connection Registry
```

Shared ownership is deliberate rather than visual copy/paste:

```text
app/templates/integrations/components/_provider_frontpage.html
  ├── provider Hero
  └── Integration Overview

app/templates/components/integration_workspace_tabs.html
  └── Integration Coverage / Connection Registry tabs

app/templates/integrations/components/_provider_registry.html
  ├── canonical Connection Registry geometry
  ├── direct-provider Asset Coverage geometry
  └── observability Scope Coverage geometry
```

Provider pages supply provider-specific copy, routes, evidence, and row data. They must not duplicate the shared Hero, overview metrics, registry headers, `colgroup`, or table-width contract.

Canonical Connection Registry columns for Kubernetes, Prometheus, Alertmanager, and MinIO are:

```text
Connection | Endpoint / Scope | Core Readiness | Compatibility | Bindings | Actions
```

Canonical direct-provider coverage columns for Kubernetes and MinIO are:

```text
Asset / Scope | Provider API | Metrics Source | Alert Source | Coverage | Actions
```

Canonical observability-provider coverage columns for Prometheus and Alertmanager are:

```text
Consumer Asset | Environment | Primary Source | Consumer Binding | Coverage | Actions
```

Rules:

- the Hero eyebrow is `Operational Integration`;
- the primary action is `Register Connection`;
- Hero metadata uses `Registered Connections`, `Ready Connections`, and `Consumer Bindings`;
- the four overview metrics retain the same order on every provider and the fourth metric is always `Coverage Gaps`;
- the Integrations landing-page Provider Catalog shows registered count, ready count, real readiness percentage, and provider posture from persisted evidence;
- `Integration Contract`, `Consumer Resolution`, and `Authority Boundary` retain the same three-column geometry;
- every provider front page exposes `Integration Coverage` and `Connection Registry` through the shared framed workspace tabs;
- provider-specific evidence belongs inside those two tabs rather than replacing the front-page hierarchy;
- Kubernetes and MinIO use the same direct-provider asset coverage table contract; their API labels and consumer evidence may differ, but their geometry may not;
- Prometheus and Alertmanager use the same observability scope coverage component and only supply provider-specific semantics;
- empty state, populated state, filters, table header, and pagination retain one geometry; an empty provider page must not replace the registry with a provider-specific onboarding card;
- identity, endpoint, profile, selector, and source text uses controlled wrapping and a bounded horizontal table minimum rather than `table-fixed` truncation.

## Provider Registration Action Footer Contract

New Kubernetes, Prometheus, Alertmanager, and MinIO connection forms use one embedded registration-gate footer owned by:

```text
app/templates/integrations/components/_provider_registration_actions.html
```

The footer is part of the main connection form surface; it must not render as a detached rounded card below the form. Its desktop hierarchy is:

```text
Connection Test Required / Connection Verified        Cancel | Register Connection
short gate explanation
```

Rules:

- before a successful Test Connection, the state is `Connection Test Required` with `Complete Test Connection before registration.`;
- after successful Test Connection, the state changes in place to `Connection Verified` with `Verified connection payload is ready to register.`;
- the status block is a compact bordered surface with an operation-state icon, not a long plain helper sentence;
- `Register Connection` remains disabled through the canonical disabled button tokens until the signed connection proof is valid;
- `Cancel` and `Register Connection` use the shared action-button component and stack responsively on narrow viewports;
- provider registration pages must call `provider_registration_actions.render(...)` instead of copying their own footer markup;
- edit/save forms may retain their task-appropriate save action bar because the Test Connection registration gate applies only to new provider registration.

The retired sentence `Run Test Connection successfully before KAORI enables Register Connection.` must not be reintroduced as registration-footer UI copy.

## Provider Registry Contract

Prometheus and Alertmanager registries share:

- one registry shell;
- Search plus provider-specific filters;
- five-row default and `5 / 10 / 25 / 50` page sizes;
- `Showing a–b of n` footer;
- explicit full-page `href` and owning-panel HTMX URL;
- one consistent identity and action geometry;
- readiness, compatibility, binding count, and factual provider fields;
- one empty state.

Provider-specific evidence remains explicit. Prometheus retains profile/query evidence. Alertmanager retains deployment type and notification-specific evidence.

## Coverage Contract

Provider coverage uses the shared coverage component and the same pagination ownership as provider registries. Normal links always resolve the complete provider page; HTMX requests replace only the coverage panel.

Coverage status is not provider runtime health. `Covered`, `Uncovered`, missing binding, validation-required binding, and incompatible source remain distinct states.

## Runtime Overview Contract


- Integration Runtime Overview reserves a dedicated action column wide enough for the canonical shared `View More` control; do not compress the action column until the button clips or overlaps the table boundary.
- Runtime Observation `Diagnostic Review` presents status first, technical evidence in a bounded neutral evidence surface, and `Recommended Action` as one shared KAORI guidance surface. Failed/blocked provider observations must not use a bare left-border recommendation treatment or provider-specific remediation styling.
Runtime Overview separates:

```text
Bright Summary Metrics
Provider / Health / Readiness Filters
Bright Runtime Records
Shared Pagination
```

Health, Provider Core Validation readiness, and consumer Binding Validation are separate signals. A healthy runtime observation does not imply provider Core Validation or consumer eligibility.

## Semantic Status Contract

Global semantic rendering is owned by:

```text
app/templates/components/table_label.html
```

Integrations uses `integration_status(...)` only as an adapter for provider-specific labels and icons. Canonical states include:

```text
Ready
Validation Required
Compatible
Compatible With Warnings
Unsupported Version
Capability Mismatch
Not Observed
Legacy Fallback
Uncovered
```

Backend services emit semantic state keys and factual labels. They must not emit Tailwind classes as a presentation API.

## Compact Label Role Contract

Integrations follows the global label decision from `components/table_label.html`. The least visually heavy representation that preserves meaning is required.

```text
Operational state in a sparse card/header? → status_label (text only)
Operational state repeated in a table/list? → status_indicator_label (semantic dot)
Context, scope, provider type, category, or count? → metadata_label
Exceptional security/eligibility/high-attention state? → special_label
Ordinary value, timestamp, version, name, or count in a sentence? → plain text
```

Icon rules:

- Lucide icons are permitted in metadata labels only when the icon adds independent context, such as scope, provider, source, time window, or externally linked identity.
- Counts, lifecycle words, readiness states, provider names beside an existing provider icon, and repeated table statuses do not receive Lucide icons.
- A semantic dot from `status_indicator_label(...)` is a scan aid, not a decorative icon.
- `integration_status(...)` must choose `display='text'` or `display='indicator'` on newly touched overview/table surfaces. `display='icon'` is retained only for an audited provider-specific exception.
- Icon + border compact labels are reserved for `display='special'` and must represent an exceptional posture, security boundary, or eligibility gate.

Integration Overview is the reference implementation: scope metadata may carry a filter icon, count metadata remains iconless, provider lifecycle/readiness uses text or dot labels, and runtime table states use dot labels.


Kubernetes Integration applies the same roles:

- connection, registry, capability, runtime, inventory, binding, and history statuses use `display='indicator'` when repeated or scanned alongside peer records;
- TLS verification uses `display='special'` because it is a transport-security boundary;
- compatibility profile, environment, provider/source identity, and other context may use `metadata_label(...)` with an icon only when no adjacent identity icon already provides that context;
- requirement levels, counts, capability totals, retained-report counts, and lifecycle values use iconless metadata labels or plain text;
- a status shown in a section header is not repeated again as a decorative metadata chip in the same visual block.

## Technical Evidence Contract

Capability and validation evidence follows a stable order:

1. capability identity and requirement level;
2. semantic result;
3. observed evidence;
4. success criteria;
5. operational impact;
6. source owner;
7. remediation;
8. optional runnable technical check.

Runnable commands or expressions use technical-value presentation. Explanatory prose remains normal KAORI typography. Technical matrices may use horizontal scrolling only where preserving side-by-side column comparison is operationally necessary.

## Runtime History Contract

One shared runtime-history component owns:

- summary metrics;
- immutable observation records;
- health, readiness, compatibility, diagnostics, and drift evidence;
- five-row default;
- `5 / 10 / 25 / 50` page size;
- full-page and HTMX pagination ownership;
- a lifecycle-management action when permitted.

Provider routes pass the required context directly to:

```text
app/templates/integrations/partials/_runtime_history.html
```

Provider-local presentation wrappers are prohibited.

Full-page pagination must preserve route path arguments and open the owning workspace tab. HTMX pagination must call the partial endpoint and replace only the runtime-history region.

## Binding Contract

Source Readiness, Binding Validation, and Effective Resolution are separate evidence boundaries. A binding must not appear operational merely because the reusable source is Ready.

Long selectors, source identities, and scope keys use controlled wrapping. Unexpected persistence failures must record sanitized user-facing Activity Audit evidence and preserve the original stack trace with application exception logging.

## Kubernetes Front-Page Coverage Contract

Kubernetes front-page `Integration Coverage` follows the same direct-provider asset coverage table used by MinIO. It reports the Kubernetes API plane and downstream metrics/alert consumer coverage without introducing a provider-only card hierarchy.

Detailed readiness-path evidence remains valid Kubernetes-specific evidence, but belongs to Kubernetes connection detail, capability, validation, or runtime workspaces where it does not alter the front-page information architecture. The front page must not introduce a provider-only giant card layout.

## Kubernetes Registry Navigation Contract

Kubernetes connection detail pages return to the canonical Kubernetes Integration registry via `integrations.kubernetes`. The legacy `cluster.list_clusters` endpoint is not part of the current cluster blueprint and must not be referenced by active Integration templates. The visible action label is `Back to Registry`, matching the parent workspace and avoiding an invalid Flask URL build at render time.

## Action Contract

- Test Connection is synchronous and verifies submitted draft settings.
- Provider Core Validation is asynchronous and authoritative only for
  provider-owned compatibility/capability evidence; it must remain
  consumer-neutral.
- Binding Validation is asynchronous and asset-specific. It resolves the
  consumer profile, selector, and functional evidence required by that binding.
- Consumer eligibility combines provider-owned execution capability evidence with asset-specific Binding Validation evidence. Provider readiness alone is insufficient, and Binding Validation must not duplicate provider-core transport capability ownership.
- Runtime Refresh is asynchronous and lightweight.
- Save, remove, and delete operations repeat guardrails in the service boundary.
- Every outcome records durable Activity Audit evidence and persistent feedback.

## Responsive Contract

- Avoid horizontal scrolling for registries when responsive records preserve all evidence.
- Technical matrices may scroll only when column comparison is essential.
- Long endpoints, selectors, capability names, and profiles use controlled wrapping and title/detail disclosure.
- Arbitrary micro typography, raw palette utilities, and page-local semantic badges are prohibited.
- Primary metrics remain bright even when their semantic state is Warning or Critical; severity is carried by labels and operational copy.

## Deliberate Technical-Evidence Scrolling Exceptions

Canonical provider and capability registries must not force desktop horizontal scrolling. Internal scrolling is reserved for evidence whose exact side-by-side or literal syntax must be preserved, such as long PromQL/API requests, YAML/code blocks, or an explicitly documented dense technical matrix.

The Kubernetes Capability Registry is not an exception, and the Minimum Validation RBAC example is tabbed rather than side-by-side. Any technical evidence scroll container must remain bounded inside its owning surface and must never force the entire page to scroll.

## Final Lock Ownership

The final frozen contract is documented in `docs/design/KAORI_INTEGRATIONS_LOCK_V1.md` and enforced by `scripts/verify_integrations_final_lock.py`. Structural changes to locked Integration workspaces require a coordinated documentation, verifier, and regression-test update; page-local exceptions are not accepted.

## Review Checklist

- [ ] Primary evidence is bright.
- [ ] Interpretation/remediation is darker.
- [ ] Health, readiness, compatibility, capability, and coverage remain separate.
- [ ] Semantic labels resolve through the global table-label component.
- [ ] Pagination preserves route arguments, active tabs, filters, and HTMX ownership.
- [ ] Normal navigation never opens a partial-only template.
- [ ] Every mutation has route, permission, service guardrail, Activity Audit, feedback, and exception-logging coverage.
- [ ] Provider-specific evidence remains factual after reuse.
- [ ] Empty, disconnected, not-observed, and validation-required states render without live provider access.

## Dark Mode Brand Allocation

Integration workspaces use semantic design tokens only. Brand Violet is an identity cue, not a status color.

```text
Light mode identity icon  → bg-kaori-soft + text-kaori-primary
Dark mode identity icon   → bg-kaori-soft + text-kaori-accent
Status / health / warning → semantic status tokens
```

Rules:

- provider, section, and resource identity icons use Violet in light mode and Lavender Accent in dark mode;
- `text-kaori-primary-dark` must not be used as a dark-mode identity treatment;
- normal white/light surfaces use `bg-surface-card`, `bg-surface-subtle`, and outline tokens so the same template remains valid in dark mode;
- raw `violet-*`, `purple-*`, `slate-*`, or fixed hex colors are prohibited for normal Integration content;
- semantic Green, Amber, Red, and Slate remain reserved for operational state, never provider/category identity;
- primary buttons may remain brand Violet in both modes because the brand token itself changes for dark mode.

The repository dark-mode verifier is part of the Integration regression gate.

## Single-Line Compact Label Contract

Compact KAORI labels are one-line by default. The shared `components/table_label.html` macros own this behavior through `whitespace-nowrap`.

Use wrapping only when the caller explicitly opts into `metadata_label(..., wrap=true)` for a genuinely long technical identifier. Do not allow compact state labels such as `Committed Snapshot`, `Guardrails Passed`, `Validation Required`, or `Not Observed` to stack word-over-word because a surrounding column is too narrow; widen/rebalance the owning layout instead.

## Recent Runtime Observation Detail Contract

Kubernetes, Prometheus, and Alertmanager use one shared runtime-history surface and one shared detail dialog:

```text
app/templates/integrations/partials/_runtime_history.html
app/templates/integrations/components/_runtime_observation_modal.html
app/static/js/native_dialogs.js
```

`View More` opens a centered native `<dialog>` in the browser top layer. Provider-local expandable runtime-history detail rows are prohibited. This prevents HTMX filter swaps from carrying stale expanded-row state and guarantees the same detail composition across all providers.

The runtime-history workspace uses a compact `Observation Posture` strip before the table so Ready, Attention, Blocked, and Not Observed records can be scanned without reading every row. The strip remains a summary of persisted records, not a live provider-health inference.

`View More` is a shared Integration record action from `integrations/components/_record_actions.html`; Capability Registry and Recent Runtime Observations must not maintain separate button styling. The action reuses the canonical KAORI table-action primitive (`table_ui.action_classes()`): compact rectangular geometry, neutral default surface, controlled Violet hover/focus emphasis, and a quiet trailing `chevron-right`. Avoid oversized `h-9` registry buttons, `panel-top-open` iconography, or page-local action classes.

The runtime observation dialog uses the shared `integrations/components/_record_detail_modal.html` with `size='standard'`. It is content-sized and decision-first rather than a full-height evidence dump. Information order is:

1. `Observation Decision` — persisted Runtime Posture + Validation Readiness, without repeating the diagnostic error body;
2. `Observation Context` — observed time, trigger, health score, latency, compatibility profile, and state change;
3. standalone observation detail only when no diagnostic rows exist;
4. Kubernetes lifecycle boundary when applicable;
5. capability evidence / persisted drift when applicable;
6. `Diagnostic Review` — the single authoritative location for detailed provider error evidence and Recommended Action.

The dialog shows immutable persisted evidence only. A provider error must not be rendered once as an operational reading and then repeated again inside Diagnostic Review. Do not infer live health, do not add nested disclosures, and do not restore a provider-specific standalone modal shell. Native dialog controls use `data-kaori-dialog-open`, `data-dialog-target`, and `data-kaori-dialog-close`. Inline `onclick`, `onchange`, and `onsubmit` handlers are prohibited in Integration templates.

## Provider Binding Workspace Layout

Prometheus and Alertmanager place binding decisions and consumer resolution on full-width surfaces. Persistent decision side rails are prohibited when the same facts can be summarized horizontally.

```text
Binding Summary
Bound Kubernetes / Operational Scopes       ← full width
Binding Decision                            ← horizontal full width
Effective Consumer Resolution               ← full width
Connection Lifecycle                        ← full width
```

This avoids squeezing selectors, preference, validation, effective-resolution, consumer evidence, and lifecycle actions beside a narrow decision rail. Source Readiness, Binding Validation, and Effective Resolution remain independent states. Candidate-level consumer evidence may remain expandable because it is genuinely deeper detail; the primary resolution row must stay readable without expansion.

## Toast Countdown Contract

Self-dismissing operational toasts use one compact countdown bar rather than a full-width semantic accent.

Ownership:

```text
app/templates/components/operational_toast.html
app/static/js/operational_toasts.js
```

The countdown bar:

- is brand Violet and uses the dark-mode brand token in dark mode;
- animates from full to empty with Web Animations API when available;
- uses a forced-layout CSS transition fallback for HTMX/OOB inserted toasts;
- pauses on hover and keyboard focus and resumes from the remaining duration;
- is cancelled when the toast is manually dismissed;
- does not replace semantic status labels or Activity Audit persistence.

## DRY Ownership Rules

Integration UI changes must prefer shared ownership in this order:

1. global primitives (`components/table.html`, `components/table_label.html`);
2. Integration adapters/components (`integrations/components/*`);
3. provider-specific template content only when the evidence contract differs.

Do not copy runtime observation modals, dialog JavaScript, semantic label geometry, provider-registry table geometry, or toast lifecycle logic into Kubernetes, Prometheus, or Alertmanager templates.

## Final Refinement Guardrails — 2026-08-07

The final Integration refinement preserves the last approved KAORI workspace behavior and treats regressions to older inline/expanded layouts as defects.

- **Minimum Validation RBAC Example** opens its complete baseline and optional Secret-reader YAML in a modal. The summary card remains compact; large RBAC manifests must not expand the manage workspace inline. Inside the modal, `Baseline Validation Reader` and `Optional Secret Reader` are separate KAORI-style tabs so only one large YAML manifest is visible at a time. Each tab owns its own copy action, scope metadata, bounded code viewport, and access-boundary guidance. Do not render both manifests side-by-side or as two long stacked code blocks.
- **Kubernetes Runtime Health & Diagnostics** uses two full-width surfaces only: horizontal `Runtime Decision`, followed by `Runtime Evidence`. Runtime Decision merges Runtime Posture, Current Runtime Gate, Validation Readiness, Observation Context, Primary Finding, and Next Operational Action. Runtime Evidence merges the lifecycle contract and concise diagnostic rows into one evidence workspace. Do not restore Runtime Snapshot, separate Lifecycle/Diagnostic cards, or a sticky Runtime Decision rail. Current-page error copy is concise; detailed provider errors and remediation belong to the Recent Runtime Observations modal. Runtime health must never be inferred from connection or validation state.
- Pagination nouns shown to operators use Title Case, including `Scopes` and `Connections`.
- **Prometheus Validation & PromQL** keeps the registry compact. The `Contract` cell shows only the contract category; source owner, criteria, technical evidence, complete PromQL, impact, and recommended action belong in the shared record-detail modal opened by `View More`.
- **Alertmanager Validation & Capability Matrix** follows the same modal-detail contract. API request evidence and remediation must not expand as an inline table row.
- **Alertmanager Validation & Capability Matrix** uses one horizontal `Validation Decision` surface above a full-width canonical KAORI capability table. The registry uses shared table/filter/loading/pagination primitives, defaults to 5 rows with 5/10/25/50 choices, numeric pages, Previous/Next, and `Showing x–y of z Capabilities`. `View More` is decision-first and keeps full API request evidence in Technical Verification without repeating the same evidence across multiple cards. Persistent Validation Decision side rails and forced desktop horizontal scroll are prohibited.
- `View More` for persisted runtime observations and validation/capability registries uses the shared/native dialog pattern. Inline disclosure remains allowed only for intentionally local supporting evidence that is not a registry record-detail workflow.
- **Kubernetes Capability Registry `View More`** uses a compact `standard` native dialog with one deliberate reading flow rather than a wall of nested cards: `Capability Decision` → `Contract Snapshot` → `Validation Evidence` → `Operational Decision` → `Verification Command`. The contract snapshot is a four-fact strip; validation evidence is a symmetric three-step row; operational impact and recommended action are peer decisions with a single governance boundary beneath them. The verification command is always visible and carries compact scope/stability/identity metadata instead of a second side panel. Do not nest another disclosure/accordion inside this modal; the modal is already the detail boundary.
- **Kubernetes capability workspace** renders `Kubernetes Capability Readiness` through the same shared `integrations/components/_capability_readiness.html` surface used by Prometheus and Alertmanager. Coverage, the three evidence metrics, Operational Gate, Evidence Boundary, and Next Operational Action therefore share the same light/dark tokens, spacing, icon treatment, and divider geometry across all three providers. Kubernetes supplies provider-specific API/RBAC data only; do not reintroduce a page-local readiness/decision surface. The `Capability Registry` remains full-width with separate `Capability`, `Resource`, `API Contract`, `Requirement`, `Status`, and `Details` columns.
- **Kubernetes Capability Registry table** uses the canonical KAORI table, filter, loading, and pagination primitives. Default page size is 5 with 5/10/25/50 choices; the footer uses `Showing x–y of z Capabilities`, numeric pages, Previous/Next controls, and local filtering resets to page 1. The full-width table uses fixed proportional columns without a forced minimum width or desktop horizontal scroll.

- **PromQL Capability Registry** follows the canonical KAORI data-table contract: shared table/filter/pagination primitives, default 5 rows, 5/10/25/50 options, numeric pages, Previous/Next controls, and `Showing x–y of z Capabilities`. Filtering resets to page 1. `View More` uses the shared provider capability-detail architecture: Capability Contract → Validation Evidence / Operational Impact → Recommended Action → Technical Verification → Evidence Boundary. Evidence must not be repeated across multiple modal cards.
- **Capability Registry loading ownership** uses one visible loading bar inside the registry header and the validation form targets that exact shared indicator id. Do not maintain a second hidden header indicator with a different id.
- **Prometheus Binding Decision** is a full-width horizontal decision surface. Resolution posture, resolver contract, metrics identity boundary, and next action must not live in a sticky right rail. `Effective Consumer Resolution` and `Connection Lifecycle` follow below at full width. Destructive deletion remains secondary to the lifecycle explanation and must be disabled with KAORI disabled-state styling while guardrails block removal.
- **Alertmanager Runtime Health & Diagnostics** uses two full-width surfaces: horizontal `Runtime Decision`, then `Runtime Evidence`. Runtime posture, gate, validation readiness, observation context, primary finding, and next action are consolidated in the decision surface. Endpoint context and concise diagnostics live in Runtime Evidence. Do not restore a sticky Runtime Decision rail; detailed provider errors belong in Recent Runtime Observations rather than being duplicated in the current workspace.
- **Alertmanager Binding Decision** is horizontal and full width. Source readiness, binding counts, resolver contract, alert-identity boundary, and next action are summarized once. `Effective Consumer Resolution` remains full width; candidate evidence may use local disclosure because it is genuinely deeper detail. `Connection Lifecycle` is a horizontal guardrail surface with a secondary destructive action, not a solid-red full-width CTA.
- **Inventory & Lifecycle workspace** uses one horizontal `Inventory & Lifecycle Decision` surface instead of a persistent right rail. Snapshot freshness, evidence coverage, retention, lifecycle gate, removal/retention boundaries, and the next lifecycle action belong in that full-width decision box. `KAORI Operational Consumers` and `Bound Observability Sources` then use the full content width below it. Do not restore the old 28–30rem sticky `Inventory Decision` side panel.
- Self-dismissing operational toasts initialize their countdown at `scaleX(1)` so HTMX/OOB insertion cannot render an apparently empty timer before JavaScript scheduling starts.

Regression ownership is enforced in `tests/contracts/integrations/`, including `test_integrations_final_refinement_20260807_contract.py`.


## Connection Registration Dark Mode

Connection add/edit workspaces for Kubernetes, Prometheus, and Alertmanager follow the global neutral-first dark-mode contract. The canonical Hero remains the only gradient surface. Ordinary cards below the Hero use `surface-card`, `surface-muted`, or `surface-elevated`; Bright Violet is limited to primary actions, focus, links, compact icon accents, and selected metadata.

The shared `related_page_card.html` is the controlled contextual exception: it remains Violet in both themes through `.kaori-brand-domain-panel`. In dark mode that class resolves to the deeper `#2F1A4F`, keeping the relationship card visibly branded without competing with the Hero or surrounding neutral operational surfaces. This rule applies globally to every Related Page Card usage, not only Integration forms. Registration flows, guide cards, validation headers, and expandable references remain neutral and use Accent Violet only for compact icons or step markers. Secondary validation/cancel controls use `components/action_button.html` so dark hover becomes solid Violet with white text instead of low-contrast Violet-on-translucent-Violet.

### Provider Capability Registry Loading and Interaction

Prometheus `PromQL Capability Registry` and Alertmanager `Alert Management Capability Registry` follow the same interaction contract as `Recent Runtime Observations`:

- Search, filter, Rows, Previous/Next, and numeric pagination are server-backed HTMX interactions.
- Every registry owns exactly one shared `components/loading_bar.html` indicator directly below its registry header.
- Every registry request targets that same indicator with `hx-indicator`; synthetic Alpine timers or page-local loading state are prohibited.
- Server-side filtering and pagination use `app.integrations.capability_registry.build_capability_registry_view` and the canonical `(5, 10, 25, 50)` pagination contract.
- Registry content swaps with `outerHTML`, keeping filters, table, pagination, loading state, and current-page detail modals in one reusable partial boundary.

## Provider Capability Matrix Alignment

Prometheus and Alertmanager validation workspaces follow the Kubernetes `Compatibility & Capability Matrix` composition. For Prometheus, the provider-level matrix is intentionally consumer-neutral (`prometheus-core-v1`); Kubernetes, MinIO, and future exporter/domain evidence belongs to the corresponding asset binding rather than the shared provider state:

- **Alertmanager provider validation is consumer-neutral.** Provider Core Validation owns Alertmanager product/version compatibility plus Status, Alerts, and Silences API v2 evidence. Kubernetes, MinIO, infrastructure, and future alert payload semantics belong to `IntegrationBinding` consumer profiles such as `kubernetes-alerts-v1` and `object-storage-alerts-v1`. A non-global binding requires an alert identity selector; missing or malformed consumer evidence may affect that binding but must not mutate Alertmanager provider readiness.
- **Alertmanager binding tables expose Consumer Profile explicitly.** The registry shows Consumer Asset, Alert Identity, Consumer Profile, role/priority, Binding Validation, Effective Resolution, and Actions. Provider-wide active-alert payload fields are not presented as Core Validation capabilities.
- **MinIO mirrors Kubernetes as an asset-owner provider while preserving the shared provider shell.** Its list Hero says `MinIO Integrations`, primary action says `Register Connection`, and provider details use `Configuration`, `Validation & Capabilities`, `Runtime & History`, and `Inventory & Lifecycle`. The lifecycle workspace inventories the canonical `object_storage_system` asset plus its bound Prometheus/Alertmanager sources read-only; binding creation/removal belongs to the Observability source workspace. Deleting MinIO removes the managed asset and bindings that target it without deleting reusable Prometheus or Alertmanager source connections.

- one validation header with the canonical shared loading bar;
- one horizontal provider capability-readiness surface before the registry;
- coverage progress and three compact provider-specific evidence metrics;
- an integrated operational-gate / evidence-boundary / next-action strip;
- one full-width server-backed capability registry below the summary;
- no persistent `Validation Decision` side rail or duplicate decision card;
- capability detail remains behind the canonical `View More` modal boundary.

The capability summary is owned by `integrations/components/_capability_readiness.html` for Kubernetes, Prometheus, and Alertmanager so color, spacing, dark-mode behavior, evidence-boundary layout, and operational-action treatment cannot drift independently.

## Provider Runtime Alignment

Prometheus and Alertmanager `Runtime Health & Diagnostics` use the Kubernetes runtime information architecture:

- one full-width `Runtime Decision` surface;
- Runtime Posture, Current Runtime Gate, Validation Readiness, and Observation Context as peer facts;
- one compact `Operational Response` containing Primary Finding, Next Operational Action, and Evidence Handoff;
- one full-width `Runtime Evidence` surface for provider contract context and concise diagnostic summaries;
- no sticky/right-side Runtime Decision rail;
- long diagnostic detail and remediation belong to `Recent Runtime Observations -> View More`;
- the runtime observation modal must suppress a top-level observation message when it repeats a diagnostic detail already shown in `Diagnostic Review`.

The provider decision shell is owned by `integrations/components/_runtime_decision.html`. Provider-specific runtime templates supply only context values and evidence rows.

### Capability Registry detail interaction

Kubernetes, Prometheus, Alertmanager, Runtime Observations, and Integration Runtime Overview use the same shared `View More` action from `_record_actions.html`. The action reuses `table_ui.action_classes()` with a quiet trailing `chevron-right`; `panel-top-open`, oversized `h-9` page-local buttons, and provider-specific action geometry are prohibited. Provider capability modals mirror the Kubernetes capability-evidence information architecture rather than inventing provider-specific card stacks: **Capability Contract → Validation Evidence / Operational Impact → Recommended Action → Technical Verification → Evidence Boundary**. Provider-specific query/request syntax belongs only in Technical Verification.
- Shared Integration `View More` actions must preserve the optional `role` keyword so Runtime Observations, Capability Registry, Prometheus, and Alertmanager can share one presentation macro without breaking semantic data markers.


- `Bindings & Consumers` tab badges count registered binding records, not only operational bindings. Source disconnects, failed runtime health, or failed binding validation must change binding status inside the workspace, not erase the registered-binding count.
- Kubernetes Runtime Decision `Primary Finding` must always resolve to one concise persisted-observation summary when attention factors exist; it must never render an empty finding because a presentation key is missing.


## Final Integration Audit Refinements — 2026-08-08

Before final lock, Integrations use the following canonical composition rules:

- **Configuration** — provider detail pages are read-only connection-contract workspaces. Kubernetes, Prometheus, Alertmanager, and MinIO expose registered identity, endpoint/transport evidence, authority boundary, operational flow, and a canonical `Configure Connection` action. Editing occurs on the dedicated `Edit <Provider> Connection` page; provider detail tabs MUST NOT embed editable forms.
- **Provider workspace tabs** — Prometheus and Alertmanager use `integration_workspace_tabs.js` as the shared tab-state controller. Page-local copies of URL/hash synchronization, keyboard navigation, and `moveTab()` logic are prohibited.
- **Runtime Observation modal** — the content macro must call `_record_detail_modal.html` with `size='standard'`; it must not own a second standalone `<dialog>` shell. Diagnostic detail is shown once under `Diagnostic Review`; only a non-duplicative `standalone_message` may appear above it. Lifecycle and capability evidence remain optional dedicated boundaries.
- **Integration Runtime Overview** — runtime records use a full-width fixed-layout KAORI table and the shared native `View More` modal. Inline `View More / Hide Details` expansion is prohibited for runtime record detail.
- **Top-level connection registries** — Kubernetes, Prometheus, and Alertmanager use responsive filter grids and full-width fixed-layout tables without forced desktop minimum widths (`min-w-[...]`) or registry-level horizontal scroll. Dense technical matrices remain the only horizontal-scroll exception.
- **Hero metrics** — provider Hero context metrics use `page_hero.context_metric()` instead of copied metric-card markup.
- **Style debt** — no new Integration verifier debt may be added. When an Integration file drops below its recorded debt ceiling, update the baseline in the same patch.

- Provider detail Hero posture is owned by `integrations/components/_provider_detail_posture.html` so the right-side posture card has identical geometry across Kubernetes, Prometheus, Alertmanager, and MinIO. Provider-specific text and evidence values may differ; card structure, metric density, and actions do not.

## Domain workspace visual and runtime feedback contract

Orchestration, Observability, and Storage MUST use the same domain workspace shell and interaction hierarchy. The **Provider Registry** / **Bindings** tab rail is visually separated from the registry table surface; a table header must never appear as a continuation of the active tab strip. Provider and binding rows must preserve readable identity text when the application sidebar is open: prefer wrapping with bounded minimum table width and horizontal overflow over truncating operational identity or contract text.

Provider labels shown to operators use the canonical provider family name. Prometheus-compatible query backends remain compatibility/runtime implementation details; registry and workspace labels are **Prometheus**, not `Prometheus / Thanos` or `Thanos Query`.

Loading feedback is operation-scoped. Full/Core Validation may animate only its validation loader; Runtime Refresh may animate only its runtime loader; capability registry filters/pagination may animate only the capability-registry loader; binding validation may animate only the binding loader. A parent validation job MUST NOT automatically activate nested registry loading bars.

Validation and Runtime HTMX responses MUST refresh their framed-tab status badge out-of-band so newly persisted readiness/health labels are visible without a full page refresh. Provider-level labels remain derived from provider evidence; consumer-binding labels remain derived from binding evidence.

### Provider empty-state and registration consistency

- Provider front pages are already protected by `settings.manage_integrations`; registry and coverage empty states MUST NOT repeat the same authorization decision inside the template. If the page is renderable, the canonical `Register Connection` action is renderable when no filters suppress it.
- Cross-provider consumer coverage uses the asset-centric term **Consumer Asset** and pagination uses **Assets**, not provider-specific `Scopes`.
- Registration workspaces share the same interaction hierarchy: Hero → `Connection Configuration` → `Connection Identity` → `Endpoint & Access` with operation-scoped `Test Connection` → compatibility/request controls → action bar.
- Registration Hero ownership is shared by `integrations/components/_provider_registration_hero.html`. Kubernetes, Prometheus, Alertmanager, and MinIO MUST NOT copy their own registration-posture panel. The shared right-side contract is `Registration Posture` / `Pre-save Requirements` / `Draft`, with `Before Save · Test Connection` and `After Save · Core Validation`, followed by `Back to Registry`.
- Registration naming uses **Register `<Provider>` Connection**. `Add Kubernetes Connection` and `Register Alertmanager Instance` are retired operator-facing labels.
- Registration/configuration right-context ownership is shared by `integrations/components/_provider_registration_context.html`. Provider connection forms render exactly two context surfaces: the provider flow and one `Related Operational Workspace` card. Do not restore separate expandable `Connection Identity & Contract`, `Compatibility Guide`, `After Registration`, or lifecycle cards beside the connection form; those details belong to Configuration, Validation & Capabilities, Runtime & History, or the provider's final lifecycle/source workspace after registration.
- The related workspace points to the provider domain (`Orchestration`, `Observability`, or `Storage`) and keeps the authority boundary concise. Any initial consumer binding created by a registration shortcut is described inside that related-workspace context instead of adding a third side card.
- `Test Connection` MUST be an HTMX operation with its own loading indicator and signed registration proof; it MUST NOT submit or refresh the entire registration workspace.
- Registration action bars use the shared gated-footer contract: `Connection Test Required` / `Complete Test Connection before registration.` before verification, then `Connection Verified` / `Verified connection payload is ready to register.` after verification, with `Cancel` + `Register Connection`. Prometheus and Alertmanager MUST NOT omit Cancel or use `Instance` terminology in operator-facing actions.
- Registration identity fields use one wording contract: `Connection Name`, `Environment` when the provider persists environment context, and `Description`. Canonical placeholders are `<Provider> Production` and `Operational purpose and ownership context`. Endpoint placeholders use `https://<provider>.example.internal`; basic-auth usernames use `service-account`; secret fields use action wording such as `Enter password`, `Enter bearer token`, or `Enter secret key`.
- Keep field-level helper text sparse. Section headers own the explanation for Connection Identity, Endpoint & Access, compatibility, and operational controls. Per-field helper text is reserved for controls whose behavior cannot be expressed by label/placeholder alone (for example kubeconfig replacement behavior). Do not add explanatory mini-cards under ordinary registration fields.
- MinIO `Test Connection` proves S3 endpoint reachability, request signing, and the read-only discovery permission required by the provider. MinIO product identity and release compatibility are Core Validation evidence. Product identity may use MinIO deployment/server headers or the unauthenticated `/minio/health/live` probe so a reverse proxy that strips response headers does not create a false registration failure.
- Provider-specific fields may differ, but MinIO, Prometheus, Alertmanager, and Kubernetes must keep the same visual and interaction hierarchy.


### Asset-owner provider lifecycle

Kubernetes and MinIO are asset-owning providers. Their detail workspaces use the same
operator lifecycle model even though the technical evidence differs:

```text
Configuration
  → managed provider connection contract
  → Configure Connection
Validation / Capabilities
Runtime & History
  → operation-scoped Runtime Refresh
Inventory / Lifecycle
  → bound observability-source inventory
  → deletion guard
  → Delete Connection
```

Deleting an asset-owning provider removes only that provider identity, its managed
asset, and bindings that target the asset. Reusable cross-domain providers such as
Prometheus and Alertmanager remain registered. Runtime observation and Activity Audit
history remain retained evidence. Active jobs referencing the provider or managed asset
block deletion.

Shared ownership:

- tab state and asset-owner destructive state are owned by `integration_workspace_tabs.js`;
- Kubernetes and MinIO destructive dialogs use `integrations/components/_asset_owner_delete_modal.html`;
- provider-specific templates supply only the asset label and deletion consequence;
- Kubernetes and MinIO use `Inventory & Lifecycle` as the fourth asset-owner workspace. It presents bound Prometheus/Alertmanager sources as read-only operational inventory plus the asset deletion lifecycle; source-binding mutation stays in Observability.


### Asset-owner detail workspace parity

Kubernetes and MinIO are asset-owner providers. Their detail workspaces MUST share the same operational composition contract even when the provider-specific evidence differs:

- `Configuration` owns the persisted connection contract.
- `Validation & Capabilities` owns compatibility, provider capability readiness, an HTMX-filtered capability registry, and `5/10/25/50` pagination.
- `Runtime & History` owns operation-scoped runtime refresh plus the canonical shared runtime-history table with HTMX filters and pagination.
- the fourth asset-owner workspace is `Inventory & Lifecycle`. Kubernetes and MinIO render their bound Prometheus/Alertmanager sources through the shared asset-owner source table with HTMX pagination; this workspace is read-only for binding mutation and owns only asset lifecycle actions such as governed deletion.

Provider-owned API identity MUST NOT be duplicated as a consumer binding. MinIO API ownership is represented by the MinIO/ObjectStorageSystem relationship; Kubernetes API ownership is represented by the Kubernetes connection/cluster relationship.

### Shared provider detail and observability coverage

- Prometheus and Alertmanager Configuration tabs use `integrations/components/_provider_configuration_contract.html` and expose `Configure Connection`; edit forms live on dedicated edit routes.
- Edit connection pages for Kubernetes, Prometheus, Alertmanager, and MinIO keep exactly two right-context surfaces through `_provider_registration_context.html`: the provider flow and `Related Operational Workspace`. Validation matrices, RBAC explainers, runtime history, and binding diagnostics belong to their detail workspaces, not the edit form rail.
- **Observability binding mutation is source-owned.** Prometheus owns Prometheus binding create/update/validate/remove actions; Alertmanager owns the equivalent alert-binding actions. Asset-owner workspaces never duplicate those mutation controls.
- Observability coverage is asset-centric, not Kubernetes-only. Prometheus and Alertmanager coverage enumerates every managed asset registered in `consumer_assets.py`, currently `kubernetes_cluster` and `object_storage_system`. Binding mutation is source-owned: operators create, validate, update, and remove Prometheus bindings from Prometheus and Alertmanager bindings from Alertmanager. Kubernetes/MinIO asset-owner pages expose bound-source evidence read-only and link back to Observability.
- The `Bindings & Consumers` workspace on Prometheus/Alertmanager uses one shared `Add Binding` modal. Asset type and asset identity are selected first; the Consumer Profile is resolved from the canonical asset registry plus the source provider's binding-profile registry. Provider-specific `Add Kubernetes Binding` or `Add MinIO Binding` forms are prohibited.
- **Bindings & Consumers final-lock contract (2026-08-13).** Prometheus and Alertmanager use the same seven-column registry contract: Consumer Asset, provider identity selector, Consumer Profile, Resolver Preference, Binding Validation, Effective Resolution, and Actions. `Primary → Secondary → Fallback` is preference only; lower priority wins within the same role. Source Readiness, Binding Validation, and Effective Resolution are never collapsed into one state. New bindings and selector edits enter `Validation Required`; only successful Binding Validation grants binding eligibility.
- The shared Add Binding dialog explains the three-step workflow (`Consumer → Preference & Identity → Validation`) and the source-owned mutation boundary. Kubernetes and Object Storage asset-owner workspaces remain read-only for binding mutation. Loading bars stay header-owned and binding registries use canonical `5/10/25/50` pagination.

- Future managed assets such as Vault extend the same flow by registering a canonical asset definition (for example `vault_system`) and compatible source profiles such as `vault-metrics-v1` and/or `vault-alerts-v1`. Once registered, the asset becomes eligible in Observability coverage and the shared Add Binding modal without a new product-specific Prometheus/Alertmanager form or binding table.
- Prometheus/Alertmanager Capability Registry tables use the same KAORI table hierarchy as domain Capability Registry: shared filter geometry, standard headers/cells, status inside the Status column, `View More` for detailed evidence, 5/10/25/50 pagination, and operation-scoped HTMX loading. Readiness labels must not float outside their canonical table/decision surface.
- Provider Configuration combines authority and lifecycle guidance into one `Operational Context` surface through `_provider_operational_context.html`; separate `Operational Boundary` and `Operational Flow` cards are retired.
- Provider readiness explanation uses `_readiness_explanation.html` and adapts content/style to Ready, Attention/Degraded, or Blocked/Failed while keeping the same geometry across Orchestration and Observability.

## Provider Detail Workspace Final Contract

Kubernetes, Prometheus, Alertmanager, and MinIO connection details share the same first three lifecycle domains:

1. **Configuration** — read-only `Connection Contract`; mutations happen in the dedicated edit workspace.
2. **Validation & Capabilities** — operator-facing lifecycle name. The action is **Run Full Validation**. Provider Core Validation may remain an internal architecture term, but provider detail UI must not expose `Core Validation` as the tab or workspace title.
3. **Runtime & History** — `Runtime Refresh` owns current reachability, latency, health, and diagnostics. It never substitutes for Full Validation.

The fourth domain is authority-specific: Kubernetes and MinIO use **Inventory & Lifecycle**; Prometheus and Alertmanager use **Bindings & Consumers**.

Provider detail Hero posture evidence is sourced as **Produced by Full Validation**. Capability counts use **Validated Capabilities** consistently. Prometheus, Alertmanager, and MinIO runtime pages use the shared `integrations/components/_runtime_decision.html` decision surface; provider-specific technical evidence follows underneath. Kubernetes may retain additional lifecycle evidence, but its Runtime Decision semantics must remain equivalent.

Bindings remain source-owned mutations. Asset-owner workspaces expose observability binding evidence read-only. Object Storage Inventory remains committed-snapshot owned and must not be recomputed by opening the MinIO integration detail page.


## Notification Channels

Notification Channels is the platform-wide outbound delivery integration at `/integrations/notification-channels`. It owns encrypted provider credentials, destination validation, provider adapters, retry/deduplication policy, and delivery journaling. Current providers are Telegram, SMTP email, and Microsoft Teams Workflows.

Consumer capabilities own event meaning and content. Current event contracts are `alert_intelligence.active_alert`, `report.generated`, and the Automation Control lifecycle events `automation.approval_required`, `automation.execution_started`, `automation.execution_completed`, `automation.execution_failed`, and `automation.verification_failed`. Alert Intelligence remains responsible for enriched alert context; Reports remains responsible for report completion semantics; Automation Control owns governed decision/execution lifecycle semantics. Report schedules persist configured **channel identities**, not provider names or credentials. Automation Control does not own provider credentials or transport adapters.

A channel must be enabled, successfully tested, allowed for the requested event type, and scoped to the event domain before it is eligible for delivery. Provider choice changes transport only; it must not change the semantic meaning of the emitted event.
