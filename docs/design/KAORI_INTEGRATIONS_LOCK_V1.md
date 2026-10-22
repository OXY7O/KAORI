# KAORI Integrations Lock v1

Status: Locked baseline
Date: 2026-08-08

## Locked Scope

This lock applies to the Integration workspaces that have completed final visual and interaction refinement:

- Integrations Overview and Runtime Overview;
- Kubernetes Integration registry and detail workspaces;
- Metrics Source registry, configuration, validation/capability, runtime, bindings/consumers, and lifecycle surfaces;
- Alertmanager registry, configuration, validation/capability, runtime, bindings/consumers, and lifecycle surfaces;
- shared provider capability/readiness components;
- shared Recent Runtime Observations table and detail modal;
- shared Integration `View More`, loading, pagination, provider-tab, configuration-decision, and runtime-detail interaction contracts;
- Kubernetes minimum-validation RBAC example and optional governed Secret-reader boundary.

This lock freezes presentation and interaction architecture. Provider-specific factual evidence, compatibility profiles, capability definitions, runtime values, and operational status may continue to evolve without reopening the design contract.

## Frozen Workspace Architecture

### Capability and Validation

Kubernetes, Metrics Source, and Alertmanager use the same shared capability-readiness presentation contract:

```text
Capability Readiness
  -> coverage / provider facts
  -> Operational Gate
  -> Evidence Boundary
  -> Next Operational Action

Capability Registry
  -> Search / Requirement / Validation Status
  -> canonical KAORI table
  -> canonical pagination
  -> shared View More modal
```

Rules:

- `app/templates/integrations/components/_capability_readiness.html` owns capability-readiness geometry and color treatment.
- Provider registries use one real HTMX request path for search, filters, rows, and pagination.
- Each registry owns exactly one shared KAORI loading bar. Synthetic Alpine timers or page-local fake loading states are prohibited.
- Default rows remain 5 with `5 / 10 / 25 / 50` choices.
- `View More` uses the shared Integration record action and shared record-detail modal shell.
- Provider technical queries/requests appear only in the Technical Verification boundary; they are not duplicated across modal cards.

### Runtime Health and Diagnostics

Runtime design follows the same mental model across providers:

```text
Runtime Decision
  -> Runtime Posture
  -> Current Runtime Gate
  -> Validation Readiness
  -> Observation Context
  -> Primary Finding
  -> Next Operational Action
  -> Evidence Handoff

Runtime Evidence
  -> lifecycle/provider context
  -> concise diagnostics

Recent Runtime Observations -> View More
  -> full immutable technical evidence and remediation
```

Rules:

- Current workspace error text is concise; full diagnostic detail belongs in the runtime-observation modal.
- Runtime Health, Connection State, Validation Readiness, and Binding Resolution remain separate evidence dimensions.
- Runtime Observation detail uses `integrations/components/_record_detail_modal.html` with standard sizing. A second standalone dialog shell is prohibited.
- Failed/blocked Diagnostic Review presents technical evidence once and one shared `Recommended Action` guidance surface.

### Configuration

Configuration is the deliberate exception to the full-width decision pattern:

```text
Connection Configuration | Configuration Decision
```

The main form remains the working surface while the shared side decision panel provides compact contract facts, change impact, controlled flow, and consumer boundary.

Rules:

- Metrics Source and Alertmanager use `integrations/components/_configuration_decision.html`.
- The canonical desktop rail is 25rem and 27rem at 2xl.
- Left and right surfaces stretch to the same visual height.
- Save actions use the embedded form-action footer; a floating nested action card is prohibited.

### Bindings and Consumers

- Registered binding count is independent of source runtime health. Provider badges count registered `binding_rows`; a disconnected or failed source can still have registered bindings.
- Source Readiness, Binding Validation, and Effective Resolution remain separate.
- Metrics Source and Alertmanager Binding Decision is horizontal and full width.
- Effective Consumer Resolution is full width; only genuinely deeper candidate evidence may use local disclosure.
- Destructive lifecycle actions remain secondary to guardrail explanation and must honor disabled state when removal is blocked.

### Tables, Loading, and Pagination

- Canonical tables use shared KAORI table primitives.
- Registries avoid forced desktop horizontal scrolling when proportional columns can preserve evidence.
- Technical code/query evidence may scroll inside its own bounded evidence surface.
- Loading bar position is `header -> loading -> filters -> table -> pagination`.
- Pagination uses resource-aware `Showing a–b of n`, default 5 rows, and 5/10/25/50 choices.

### Shared Detail Actions

`app/templates/integrations/components/_record_actions.html` owns Integration record-detail actions:

- shared `table_ui.action_classes()`;
- compact rectangular geometry;
- trailing `chevron-right`;
- optional `role` keyword retained for semantic data markers;
- provider-local oversized `View More` styling is prohibited.

### Kubernetes RBAC Boundary

Minimum Full Validation reader explicitly excludes cluster-wide Secret reads.

Optional Secret access is a separate namespace-scoped `Role + RoleBinding`, visible in its own modal tab and intended only for approved governance workflows. It must never be merged into the baseline validation `ClusterRole`.

## Frozen Visual Contract

- KAORI Violet owns brand identity and interaction emphasis; semantic colors represent operational state only.
- Dark mode uses the global token contract. Provider pages do not define private dark palettes.
- Contextual related-workspace surfaces may remain deep Violet in dark mode through shared KAORI contextual-brand ownership.
- Visible headings, table headers, form labels, modal titles, tabs, and buttons use Title Case.
- Raw Tailwind palette utilities, raw hex colors, inline `style=`, and inline DOM handlers are prohibited in locked Integration templates.
- Shared components own geometry whenever the same concept appears across Kubernetes, Metrics Source, and Alertmanager.

## Dead / Legacy Paths Removed

The final lock removes obsolete presentation paths that were no longer referenced after modal/runtime/capability consolidation:

- `app/templates/integrations/partials/_runtime_detail_content.html`
- `app/templates/integrations/observability/metrics_source/partials/_analytics_readiness.html`

Previously retired Integration compatibility paths remain registered in `scripts/cleanup_obsolete_files.sh` and are protected by the final verifier.

## Change Policy

After this lock, structural redesign is not a normal maintenance change. A future design-contract change requires, in the same commit:

1. design-system documentation update;
2. explicit rationale in a lock/audit document;
3. verifier and contract-test update;
4. regression coverage for the changed behavior;
5. no silent style-debt baseline increase.

Normal post-lock work should prefer defect fixes, content corrections, provider capability additions, backend/data improvements, and security fixes without changing the frozen workspace architecture.

## Enforcement

Run:

```bash
python scripts/verify_integrations_final_lock.py
pytest -q tests/contracts/integrations
python scripts/verify_dark_mode_standard.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_core_workspace_legacy_cleanup.py
python scripts/verify_python_syntax.py
python scripts/verify_ui_style.py
```

Repository-wide `verify_ui_style.py` may still report explicitly tracked debt in unrelated domains such as Notifications or Reports. The Integration lock does not permit new Integration debt.

## Notification Channels Workspace Navigation — scoped approval (#2662, 2026-10-22)

The Notification Channels delivery capability retains its three server-owned
workspaces (**Overview**, **Channels**, **Delivery Activity**) and all existing
provider governance, RBAC, credential secrecy, journal, retry/deduplication,
HTMX registry filtering and default-five pagination. The operator-approved
page-hierarchy alignment deliberately replaces its formerly **framed tabs below
Hero** with shared **Integrated Workspace Tabs above Hero**, matching the
level-3 navigation pattern elsewhere in KAORI. The tab selector, Hero and active
view share one server-rendered HTMX replacement boundary, retaining ordinary
anchor fallback and `?tab=` deep links.

For page-level Notification Channels workspaces, **no generic view title or
paragraph is inserted immediately after Hero**. The first post-Hero content
is the substantive workspace block. Contextual **section-level** headings and
concise descriptions remain valid **above their specific cards**, using the
canonical `components/section_intro.html` contract when appropriate. This
distinguishes a meaningful card section title from redundant page introduction
text; the rule supersedes the earlier per-view generic title arrangement.

Following approved follow-up #2672, the Integrated Workspace Tabs show labels
only, with **no per-tab numeric badges** (counts remain in their owning table
headers/results). Delivery Contract and Delivery Ownership share one governed
card and one contextual section introduction. Configured Channels has its own
section introduction above the channel table card; Delivery Journal uses a
specific section heading above a canonical **table header → loading → filters →
table → pagination** card. The journal filters combine exact event key,
provider, catalog domain, severity and delivery status, validated by the server
before SQL-level pagination. Clear Filters and Rows/page links preserve the
canonical HTMX behavior. Notification delivery records are committed external
transport evidence, **never proof of human receipt** or a substitute for
Activity Audit.

This is a **specific, documented exception to the prior Notification Channels
framed-workspace presentation**, not permission to change other locked
Integration provider details or invent a new tab/section component. Regression
coverage lives in the existing Notification Channels contract test and verifier.
Review branch / DevContainer UAT only until executable validation, keyboard,
responsive light/dark checks, and operator acceptance are recorded. No release
or production provider mutation is implied.

## Notification Channels UAT Density & Journal Controls (#2680, 2026-10-22)

The operator-approved staging-UAT refinement consolidates each Delivery
Contract & Ownership boundary into a **single concise sentence per ownership
panel**, retaining Alert Source authority and KAORI's governed transport
evidence, without verbose duplicated supporting paragraphs.

The **Channel Inventory** header carries one accessible shared `info_tip`
(popover for pointer/keyboard/touch) documenting validation, operational
feedback, and secret-safe Activity Audit behavior. The former three static
guidance cards are not rendered; explanatory workflow information must not
become an alternate uncontrolled UI component.

The **Delivery Journal** section keeps one concise title/description
immediately above its table card and a separate Delivery Evidence Boundary
contextual surface before that heading. Both Channel Inventory and Delivery
Records use shared `table.inventory_block_header` owning the title, guide
where relevant, count, conditional Clear Filters header action, and
request-scoped `loading_bar`. Each shared `table.inventory_filter_bar_classes`
wrapper contains only `table_registry.filter_form` filter fields; Clear
Filters is not an inline filter-row control. The canonical registry actions
retain HTMX target, reset, Rows and pagination behavior. No fake progress
indicator, page-local positional workaround, provider delivery change or
global table layout override is permitted.

## Notification Channels Title Guide & Evidence Panel Refinement (#2685, 2026-10-22)

The **Channel Inventory** title-level contextual hover is the shared
`info_tip.render(..., variant='guide')`, not the icon-only field-level
variant. The canonical guide trigger remains keyboard-focusable, touch-
operable, and bound to the shared viewport-aware non-modal popover; no
private tooltip logic is introduced.

For Delivery Activity, the **Delivery Evidence Boundary** uses one
shared `operational_section_card`. A single full-width interpretation
panel emphasizes **provider acceptance does not prove recipient receipt or
readership**. Two unboxed, responsive supporting facts distinguish
**Committed Delivery Journal** from **Independent Activity Audit**; no
three-card nesting or implied audit production from provider sends. This
panel comes **before** the Delivery Journal title/description, which must
remain immediately above the canonical Delivery Records table card.
The design preserves external provider authority, existing table filters,
loading/pagination, RBAC, security boundary and committed evidence.

## Notification Channel Table Controls and Evidence Density (#2692, 2026-10-22)

Kubernetes Pod and Namespace Inventory table cards are the directly adopted
interaction and visual reference. For **Channel Inventory** and **Delivery
Records**, reuse `table.inventory_block_header` for title, contextual Guide,
filtered result count, conditional **Clear Filters** (in the header actions
slot), and the shared loading bar **within the header**. The filter bar is
the shared outer `table.inventory_filter_bar_classes` wrapper containing
only the canonical registry filter form with active fields. This supersedes
the earlier in-filter-row Clear Filters placement and custom `ml-auto`
workaround. Do not put the loading bar outside the owning table header.

The **Delivery Evidence Boundary** is one operational section, one
prominent provider-acceptance guardrail and two inline unboxed facts. It
must not become three visually competing cards. Provider acceptance
does not prove human receipt; provider send does not automatically
create a committed Activity Audit event. This presentation-only UAT
refinement leaves committed journal filtering, rows, source links,
provider delivery policy and permissions unchanged.

## Notification Channel Setup Summary Copy (#2699, 2026-10-23)

Email, Telegram, and Microsoft Teams setup summaries and the delivery
ownership label use concise one-sentence desktop-line targets. This affects
display copy only: provider prerequisites, adapter authorization, webhook
restrictions, credentials, transport TLS, routing, retry and evidence
boundaries remain unchanged. Smaller viewports may wrap naturally.

Email retains approved SMTP transport, sender identity and operational
recipients; Telegram retains a dedicated bot/destination and secure KAORI
credential boundary; Teams requires a Workflow webhook rather than a
legacy Office 365 connector; consumers still emit governed events while
Notification Channels owns the provider-delivery responsibility.
