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

## Notification Channel Inventory Row Density (#2708, 2026-10-23)

The Channel Inventory table keeps its approved shared header, loading,
filter controls, result count, pagination, provider-secret boundary,
and authorized Edit / Test / Delete actions. The **six-column** canonical
row reads Channel → Readiness → Routing Policy → Allowed Uses →
Delivery Evidence → Actions. Combining Last Test and Last Delivery in
a labeled evidence cell **does not combine their statuses or timestamps**.

Long event policies must not be rendered as a single unbounded
comma-delimited paragraph in normal monitoring view. Following the
operator-approved redesign #2721, the default row shows an allowed-use
count and **View policy** only. The preview is intentionally omitted for row density. The former
inline `details/summary` expansion is retired because it changes the
height of all neighboring table cells. An accessible, shared-pattern KAORI
native dialog lives **outside the table's horizontal scroll wrapper** and
contains the complete source-owned list, grouped by event capability.
The dialog provides keyboard/focus/Escape/backdrop and Close behavior,
a scrollable body and responsive columns, without new JS or modal
frameworks. Empty policies and committed report schedule references
retain explicit representations.

Keep the channel name as the primary identity, provider and destination
as supporting details, and long destination/domain labels inspectable
through standard title text without wrapping the default row indefinitely.
Actions retain CSRF and blocked-delete semantics. Wide operational
tables may scroll horizontally on narrow viewports, using the existing
KAORI table component; no truncation of the expanded event list or
policy-data mutation is permitted.

## Notification Channel Lifecycle Action Interaction (#2717, 2026-10-23)

Channel Inventory **Edit**, **Test Delivery**, and **Delete** follow the
existing KAORI native-dialog, HTMX workspace-refresh and Toast/Notification
Deck contracts. Edit retrieves the latest authorized form into the existing
configuration dialog without a full-page navigation, never redisplaying
encrypted provider credentials; Create/Edit Save and Test Delivery refresh
the committed Notification Channels workspace after the POST. A plain
GET/POST with server redirect remains available as fallback when HTMX is
not used. Active Channel Inventory filters, page and Rows settings are
preserved through bounded server-side redirect parameters.

**Delete is explicitly confirmed before sending any POST** using the
existing shared `destructive_confirmation_modal` and delegated handler:
the selected channel name, irreversible consequence, Cancel/Escape,
backdrop and focus-restoration apply. With JavaScript unavailable, Delete
fails closed rather than offering an unconfirmed destructive form. The
existing server-side deletion guard against committed delivery evidence and
report-schedule references is authoritative, regardless of UI state or
confirmation. CSRF, `integrations.manage`, Activity Audit and operational
feedback remain unchanged. HTMX mutation GET results deliver the existing
`operation_feedback_oob` Toast with no redundant full-document refresh.
No new provider API, transport, route policy, or modal implementation is
introduced.

## Notification Channel Inventory Controlled Row Height (#2721, 2026-10-23)

The Channel Inventory table's default row is a compact operator summary
regardless of whether Allowed Uses contains 0, 2, 13 or 50 entries.
The read-only `event_type_groups` view is derived from existing normalized
event labels, retaining the source event order and semantics; neither
event policy, authorization nor delivery behavior changes. The
`_channel_policy_dialog.html` partial uses existing KAORI native-dialog
chrome and is rendered outside the table for each paginated, authorized
channel. Dialog content shows allowed-use groups plus minimum severity,
routing domains and report schedule reference evidence. No credentials.

Delivery Evidence retains separate Test and Delivery statuses/timestamps;
this redesign only improves spacing and visual hierarchy. Edit/Test/Delete,
destructive confirmation, CSRF, RBAC, HTMX state, OOB operational feedback,
filter/header loading and pagination contracts remain unchanged. Do not
use inline row-expanding controls in dense operational inventory tables.

## Channel Inventory Symmetry, Scroll, and Deletion Guidance (#2731, 2026-10-23)

Policy modal uses one consistent full-width horizontal row per event
capability: left column is capability name/count; right column uses a
responsive two-column event list. This avoids uneven two-column cards
when capability event counts vary. Normal narrow/mobile widths stack
label and events without clipping.

Channel Inventory removes the unconditional 1280px minimum table width
in favor of a 1100px responsive baseline with wrapped action controls. Preserve six
functional columns, separate Test/Delivery evidence, and usable
Edit/Test/Delete actions. Horizontal scrolling is allowed only where
the available viewport cannot reasonably fit the table.

A channel with committed delivery evidence or report-schedule
references cannot be hard-deleted: deletion is server-blocked by
`NotificationChannelDeletionBlocked` and must not cascade to audit
evidence. Instead of an inert disabled Delete control, show an accessible
**Locked** native dialog containing the exact count of delivery
records, count/name of report schedules, and safe next steps: disable
via existing Edit workflow to stop delivery, detach from report
schedules, and only hard-delete when both dependencies are zero.
Previously committed evidence remains authoritative; do not delete
history to clear the guard. No hard-delete override, new archive
semantics, data migration or bypass of RBAC/CSRF is authorized here.

## Responsive Channel Inventory Table Fit (#2734, 2026-10-23)

The accepted #2735 work establishes a row-wise capability policy dialog and a
native **Locked** deletion dependency dialog. Retain those authoritative
components. Channel Inventory uses a full-width fixed six-column table on
desktop rather than forcing a 1100px minimum; a smaller 980px table minimum
is reserved for narrow viewports where horizontal scrolling is intentional.
The existing deletion guard remains authoritative. For committed delivery
evidence, deactivate the channel through Edit rather than purging history.

## Channel Deletion Lock Presentation (#2734, 2026-10-23)

The protected deletion action is a **Locked** warning-tone button, never an
apparently inert Delete button or an unexplained `Why locked?` text action.
Its native KAORI dialog organizes lifecycle state, committed delivery
records, report schedule references, and safe next steps in distinct,
readable sections. The modal responds to the current channel Enabled state:
when Disabled, it explicitly says automatic delivery is already off but
retained records **still prevent hard delete**. When Enabled, it provides
an Edit action to disable future delivery. Counts are real committed
evidence, not inferred from delivery status badges. Report schedule names
are shown only when applicable.

Disabling a channel does **not** delete `NotificationDelivery` history,
change a report reference or satisfy the hard-delete guard. The underlying
`NotificationChannelDeletionBlocked` rule remains authoritative; only
a channel with both dependency counts zero can be hard deleted. Do not add
a delete override, cascade, credential exposure or new modal framework.

## Terminal Notification Channel Retirement — Persistence (#2748 / #2749)

An approved operational retirement is an irreversible `active → retired`
transition stored on the existing Notification Channel identity. It commits
`lifecycle_state`, `retired_at`, `retired_by_user_id`,
`retirement_reason`, and `enabled=false` while retaining all
`NotificationDelivery` rows and the provider/destination identity.
A required 8–500-character operator reason and removal of all report
schedule references are server-enforced. Retired channels cannot be
edited, tested, hard deleted, or restored through current routes.
Server audit events cover success and blocked retirement. Delivery
eligibility and Archived Channels UI are separate child workstreams.

## Retired Channel Delivery Eligibility (#2750)

Retired channels are excluded from operational posture and all selectable
consumer/provider destinations, not merely hidden in the registry.
Direct governed-event dispatch, alert dispatch, operator test/preview,
provider adapter send, and queued/failed recovery paths guard terminal
lifecycle state. In-progress retry records may be marked `skipped`
with an explicit retirement reason; committed historical sent/failed
evidence is never deleted. Source-linked historical journal remains
accessible. A retired channel is not reinstated by setting `enabled`.

## Archived Channels Inventory & Confirmation (#2751)

Channels workspace provides **Active** (default) and **Archived** lifecycle
views using the canonical **Framed Workspace Tabs / Style 2** server
navigation (`components/framed_workspace_tabs.html::render_navigation`),
identical to Activity Audit's Activity Register / Administrative Evidence
visual contract. The owning registry remains URL/HTMX-backed and inherits
the shared loading indicator, filter/Rows/pagination behavior. Do not
substitute page-local pill or segmented tab markup.
Archived channels remain read-only and display retirement timestamp,
operator ID, reason, source-owned policy and committed delivery count
through the existing native policy dialog. Archive view excludes
Edit, Test, Delete, and Retire controls. Active channels can open a
native Retire confirmation with mandatory bounded reason; active Report
Schedule references disable the confirmation until resolved. Backend
authorization, transaction and audit remain authoritative. Retiring
redirects to archived view via the existing HTMX workspace contract.

## Notification Channel Compact Row and Lifecycle Copy (#2760, 2026-10-23)

Historical note: #2760 used a six-column table with inline policy metadata
and a two-by-two action grid. This is **superseded** by #2774 for the
Channel Inventory row. Refer to the current Summary → Inspect → Act
contract below.

Deletion Protection uses three concise statements for dependencies,
Disable guidance and the zero-evidence/zero-schedule hard-delete rule.
Terminal Retire confirmation uses a three-item semantic list: delivery
stops, channel becomes Archived/read-only, committed evidence is retained.
Do not soften server-side deletion/retirement governance to simplify copy.

## Notification Channels — Summary → Inspect → Act (#2774, 2026-10-23)

The Channel Inventory is a **five-column compact operational summary**:
Channel (shared title/provider+destination), Readiness (posture and
enabled/archived), Routing (minimum severity and counts of domains/allowed
uses), Last Delivery (committed outcome and timestamp), and Actions.
The normal table row exposes at most **two** controls: **Details** and,
only for authorized active channels, **View More**. Do not put Edit/Test/
Retire/Locked/Delete, complete event lists, Test Delivery evidence, or
dependency records directly in the row.

**Details** uses the canonical `components/side_drawer.html` and its
focus-contained Alpine controller. The drawer shows independently committed
Last Test and Last Delivery, severity/domains, all source-owned event
capabilities, record/schedule counts, lifecycle status and (when archived)
retirement operator/time/reason. No credentials or provider live calls.
Archived rows expose Details only, never a mutation affordance.

**View More** opens an anchored, compact dropdown using the existing KAORI
navbar Alpine open/outside/Escape and elevated-surface pattern. Render the
dropdown via `x-teleport="body"` to avoid the table's horizontal scroll
clipping it. Place it near its row trigger, adjust upward by available
viewport space, and close on outside click, Escape, scroll or resize.
Keep trigger `aria-expanded`/`aria-controls`, keyboard focus and
operator-scope checks. The dropdown delegates Edit, CSRF-protected Test,
native Retire and Locked dialogs, or destructive Delete confirmation; it
is **not** a modal and must not add an overlay or header/footer chrome.
Only those confirmation/explanation workflows remain native dialogs.
No browser `confirm()` or additional custom JS component. Existing URL/
HTMX filters, loading, Toast, pagination and default Rows=5 stay unchanged.

This replaces the older Channel Inventory six-column and 2×2 action-grid
recommendations while preserving historical change traceability. Do not
alter notification delivery, evidence retention, RBAC, or lifecycle
authority merely to simplify the UI.

### Destructive confirmation from View More (#2774, #2787)

The eligible Delete item in the teleported dropdown triggers KAORI's existing
destructive confirmation. Its CSRF-protected POST form remains **outside**
the dropdown and outside the table scroll wrapper, so confirmation can
submit once without a clipped/hidden modal submit dependency. When the
destructive confirmation or a native lifecycle dialog is open, suppress
outside-click dropdown dismissal to preserve focus restoration on Cancel.
Server-side dependency denial remains authoritative.

## Notification Channel View More Dropdown (#2787, 2026-10-23)

This user-approved refinement supersedes #2774's centered native More
action sheet, which created unnecessary modal chrome for a short action list.
The current row label is **View More** with chevron-down. The menu uses the
same elevated/rounded surface and borderless-hover action treatment as the
existing navbar Quick Actions/User Menu. It is teleported beyond horizontal
table clipping and anchored to the clicked row button via viewport geometry.
The dropdown's actual rendered height must be measured **after Alpine
visibility/teleport initialization**. Never use a hardcoded estimated height
to flip it, because that leaves a large gap above a lower-row trigger.
Position with an 8px trigger gap on either side, constrain available viewport
height for short screens, and suppress the pre-measurement flash. Focus the
first action with `preventScroll` so focusing a teleported item cannot
trigger an unwanted scroll-close event.
The only native dialogs are actual lifecycle explanations/confirmations,
including Retire, Locked, and Delete confirmation. The Details inspection
drawer is unchanged and Archived channels remain read-only. Keep keyboard
Tab/Escape, outside-click and scroll/resize closure, semantic labels,
permission boundaries, HTMX feedback and delivery audit intact.

## Notification Channels — Committed Overview and Lifecycle Modal Parity (#2800, 2026-10-23)

The **Overview** workspace summarizes the capabilities that exist in the
**Channels** and **Delivery Activity** workspaces. It does **not** repeat
all six supported transport-adapter/provider cards. Provider discovery,
configuration, and setup guides remain with Channels.

Only evaluate the read-only aggregate when the **Overview** tab is open; Channels/Delivery Activity operations must not query this unused summary.
Read **committed KAORI state** for four KPI cards: active channel identities
(excluding retired), active enabled+successfully-tested eligible channels,
retired/archived identities, and all-time committed delivery records.
**Channel Readiness** includes enabled, operational, and attention-required
active channels, while **Delivery Outcomes** groups all-time committed
`sent`, `failed`, `queued`, and `skipped` records; unknown statuses
still count toward the committed total. **Recent Delivery** shows only the
latest five committed event/channel/outcome records, with a zero-record
empty state. Statuses show their time scope and link to the authoritative
Channels and Delivery Activity tabs. Provider acceptance never means human
receipt. No provider live requests, new mutation path, or inferred
time-window SLI is introduced.

The **Deletion Protected** and **Retire Channel** lifecycle modals follow
the same three-part KAORI header established by Channel Configuration:
semantic icon surface, contextual title/description, and close action.
Their footers share `components/action_button.html` primary/secondary
styles, surface/border, and spacing. The deletion modal retains protected
delivery/schedule counts and condition-aware Edit action. Retire keeps
required reason (8–500 characters), server-enforced schedule blockers,
CSRF and confirmation. The short copy must not imply that disabling
unlocks hard delete: hard delete requires zero delivery records and zero
report schedule references. Activity Audit, no-restore lifecycle, and
provider credential boundaries remain unchanged.

## Notification Channels — Compact Operational Snapshot UAT refinement (#2809, 2026-10-23)

The existing committed-state Overview remains authoritative as documented in #2800. Present
**one combined Violet operational card**, introduced by the canonical
`section_intro.render('Operational Snapshot', ...)` **outside and above the card**,
matching the "Delivery Contract & Ownership" hierarchy. Inside that single shared
`integration_ui.section_shell_classes()` surface, Channel Readiness and all-time
Delivery Outcomes share the left column; Recent Delivery uses the wider right column.
Use internal dividers rather than nested card shells. At small viewports the two
columns stack with a horizontal separator, and at desktop use a full-height vertical
divider. Inner section headers use `notification_subsection` with existing icons,
status labels and action classes, Violet tokens, and responsive Tailwind utilities.
Do not create a new UI macro or page-local CSS/JS to achieve this layout.

Each of up to five recent attempts shows **event**, **channel**, **operator-local
time** and committed **outcome**, with long identities truncated visually but
available in title attributes. The empty state remains explicit and the link
to Delivery Activity retains regular GET navigation plus full HTMX swap and URL
history. Readiness populations may overlap and must not be visualized as
exclusive slices. Unknown delivery outcomes must not silently disappear from
the separate all-time total. No synthetic health percentage, provider live
query, new endpoint, transport behavior, credential display, or evidence
mutation is permitted. DevContainer/browser light/dark, narrow viewport and
keyboard UAT is required before operator acceptance.

## Notification Channels — Details-first Channel Actions (#2823, 2026-10-23)

Human-approved refinement supersedes the **two-row-action** and teleported
**View More** prescriptions in #2774, #2787 and #2792 **for Notification
Channels only**. Keep the same five-column compact Channel Inventory but
show exactly one row action, **Details**, for active and archived channels.
Do not reintroduce an action dropdown, inline row mutation controls, or
bespoke JavaScript positioning.

Use the existing canonical `components/side_drawer.html` for
**Summary → Inspect → Act**. The drawer presents Operational Status,
independent committed Last Test and Last Delivery, then **Channel Actions**,
followed by complete Delivery Policy and Lifecycle & Governance evidence.
Only `lifecycle_state == 'active'` channels under authorized
`integrations.manage` can see Edit Channel (existing GET/HTMX),
Test Delivery (existing CSRF POST/HTMX), Retire Channel (existing native
confirmation), and Delete Locked / Delete Channel (existing dependency
explanation or shared destructive confirmation). Archived channels remain
read-only; no secret values are rendered.

Keep the hidden, CSRF-protected Delete submit **outside the drawer and table
scroll**, tied to the existing confirmation modal's stable
`data-destructive-submit-button-id`. Never loosen
`NotificationChannelDeletionBlocked` or lifecycle scheduling constraints.
A nested native or destructive confirmation temporarily owns focus; the
shared side-drawer focus trap must not steal Tab while such a confirmation
is active, and Escape within it must not close the underlying drawer.
After cancellation, focus returns to the opener in the drawer. Existing
focus/keyboard/HTMX, mobile, light/dark and authorized negative-scenario
UAT are mandatory before acceptance.

This is a UAT holding refinement only; provider delivery transports,
persistent committed evidence, RBAC, routes, schema and official admission
remain unchanged.
