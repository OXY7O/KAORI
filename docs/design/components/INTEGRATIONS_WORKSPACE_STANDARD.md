# Integrations Workspace Standard

> Status: canonical and implemented.

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

Runtime Overview separates:

```text
Bright Summary Metrics
Provider / Health / Readiness Filters
Bright Runtime Records
Shared Pagination
```

Health, Validation Readiness, and Capability Attention are separate signals. A healthy runtime observation does not imply Full Validation readiness.

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

## Kubernetes Operational Readiness Layout Contract

`Operational Readiness Paths` uses a professional three-column desktop comparison: Kubernetes Inventory, Kubernetes Analytics, and Alert Intelligence are equal peer cards in one row at `xl` width. Each card uses the same four-stage readiness model (`Direct Cluster Authority`, provider resolution, `Cluster Binding`, `Effective Consumer`) so the three paths stay visually aligned and can be compared without interaction. For the direct Inventory path, provider resolution and Cluster Binding are explicitly presented as `Direct Path` rather than omitted.

Simple readiness evidence is always visible. Do not add `View Evidence`, accordions, disclosure buttons, or hidden evidence panels to this workspace unless the evidence becomes materially more complex than the four-stage comparison. Each card ends with an `Operational Outcome` footer; the Provider Resolution Boundary remains a quiet full-width explanatory band below the three cards.

## Kubernetes Registry Navigation Contract

Kubernetes connection detail pages return to the canonical Kubernetes Integration registry via `integrations.kubernetes`. The legacy `cluster.list_clusters` endpoint is not part of the current cluster blueprint and must not be referenced by active Integration templates. The visible action label is `Back to Registry`, matching the parent workspace and avoiding an invalid Flask URL build at render time.

## Action Contract

- Test Connection is synchronous and verifies submitted draft settings.
- Full Validation is asynchronous and authoritative for capability/readiness evidence.
- Runtime Refresh is asynchronous and lightweight.
- Binding Validation is asynchronous and scope-specific.
- Save, remove, and delete operations repeat guardrails in the service boundary.
- Every outcome records durable Activity Audit evidence and persistent feedback.

## Responsive Contract

- Avoid horizontal scrolling for registries when responsive records preserve all evidence.
- Technical matrices may scroll only when column comparison is essential.
- Long endpoints, selectors, capability names, and profiles use controlled wrapping and title/detail disclosure.
- Arbitrary micro typography, raw palette utilities, and page-local semantic badges are prohibited.
- Primary metrics remain bright even when their semantic state is Warning or Critical; severity is carried by labels and operational copy.

## Deliberate Technical-Matrix Exceptions

The following layouts may retain minimum widths because simultaneous comparison is the core task:

- Prometheus registry compatibility/runtime/binding matrix;
- Kubernetes capability and minimum-RBAC evidence matrices;
- dense validation evidence tables.

These exceptions must remain inside an owning `overflow-x-auto` region and must not force the entire page to scroll.

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
- **Kubernetes capability workspace** uses one horizontal `Kubernetes Capability Readiness` decision surface above the registry. It owns capability coverage, required-usable contracts, API stability, required blocks, the operational gate, and the next controlled action. Do not duplicate the same evidence in a second `Validation Decision` side rail. The `Capability Registry` is full-width and exposes separate `Capability`, `Resource`, `API Contract`, `Requirement`, `Status`, and `Details` columns so dense capability sets remain scan-friendly without sacrificing table width to a persistent side panel.
- **Kubernetes Capability Registry table** uses the canonical KAORI table, filter, loading, and pagination primitives. Default page size is 5 with 5/10/25/50 choices; the footer uses `Showing x–y of z Capabilities`, numeric pages, Previous/Next controls, and local filtering resets to page 1. The full-width table uses fixed proportional columns without a forced minimum width or desktop horizontal scroll.

- **PromQL Capability Registry** follows the canonical KAORI data-table contract: shared table/filter/pagination primitives, default 5 rows, 5/10/25/50 options, numeric pages, Previous/Next controls, and `Showing x–y of z Capabilities`. Filtering resets to page 1. `View More` opens a decision-first modal with Validation Result, Latest Evidence, Contract Evaluation, Technical Verification, and Next Operational Action; evidence must not be repeated across multiple modal cards.
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

Prometheus and Alertmanager validation workspaces follow the Kubernetes `Compatibility & Capability Matrix` composition:

- one validation header with the canonical shared loading bar;
- one horizontal provider capability-readiness surface before the registry;
- coverage progress and three compact provider-specific evidence metrics;
- an integrated operational-gate / evidence-boundary / next-action strip;
- one full-width server-backed capability registry below the summary;
- no persistent `Validation Decision` side rail or duplicate decision card;
- capability detail remains behind the canonical `View More` modal boundary.

The provider summary is owned by `integrations/components/_capability_readiness.html` so Prometheus and Alertmanager cannot drift independently.

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

- **Configuration** — Prometheus and Alertmanager render one shared horizontal `Configuration Decision` surface above a full-width configuration form. Persistent Configuration Decision side rails are prohibited. The shared decision surface owns current contract facts, change impact, `Configure → Validate → Observe → Resolve`, and the provider consumer boundary.
- **Provider workspace tabs** — Prometheus and Alertmanager use `integration_workspace_tabs.js` as the shared tab-state controller. Page-local copies of URL/hash synchronization, keyboard navigation, and `moveTab()` logic are prohibited.
- **Runtime Observation modal** — the content macro must call `_record_detail_modal.html` with `size='standard'`; it must not own a second standalone `<dialog>` shell. Diagnostic detail is shown once under `Diagnostic Review`; only a non-duplicative `standalone_message` may appear above it. Lifecycle and capability evidence remain optional dedicated boundaries.
- **Integration Runtime Overview** — runtime records use a full-width fixed-layout KAORI table and the shared native `View More` modal. Inline `View More / Hide Details` expansion is prohibited for runtime record detail.
- **Top-level connection registries** — Kubernetes, Prometheus, and Alertmanager use responsive filter grids and full-width fixed-layout tables without forced desktop minimum widths (`min-w-[...]`) or registry-level horizontal scroll. Dense technical matrices remain the only horizontal-scroll exception.
- **Hero metrics** — provider Hero context metrics use `page_hero.context_metric()` instead of copied metric-card markup.
- **Style debt** — no new Integration verifier debt may be added. When an Integration file drops below its recorded debt ceiling, update the baseline in the same patch.
