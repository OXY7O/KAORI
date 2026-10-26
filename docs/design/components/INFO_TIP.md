# KAORI Info Tip Standard

## Purpose

`components/info_tip.html` is the canonical compact guidance pattern for dense forms and operational controls where permanent helper copy would make the interface unnecessarily tall.

The default trigger remains compact **icon-only** with Lucide **info** (information glyph, never a question-mark icon) for field-level and dense inline context. For table/card/section **title-level** guidance, the approved standard is an explicit compact Violet **info + Guide** label immediately beside the title, using `info_tip.render(..., variant='guide')`. This is not a separate header action: reuse the same non-modal popover, content, and event controller. Do not add independent **Status Guide**, **Membership Guide**, or **Group Guide** action buttons.

The Guide trigger follows compact label geometry (`rounded-md`, not a full pill), with a subtle Violet surface, 12px text, a small info glyph and restrained hover/focus treatment. Both Info Tip variants share a restrained `rounded-lg` popover with soft border/elevation, a clear icon-and-title header, 14px readable description and separated supporting rows. Desktop target widths are 384px for icon help and 416px for Guide help; `max-w-[calc(100vw-2rem)]` shrinks either variant inside narrow viewports, and existing max-height/vertical scrolling keeps longer glossaries usable. The shared portal/controller remains authoritative for viewport positioning and dismissal. Reuse KAORI semantic tokens for dark mode; never introduce page-local help styles.

Legacy `button_text` Info Tips remain available for genuinely exceptional use cases. Keep field and inline triggers icon-only and compact, using the same **info** glyph as the title-level Guide. Do not substitute `circle-help` or a standalone question-mark trigger. The trigger size and input-mode handling must stay consistent with the shared component.

## Use

Use an Info Tip for contextual guidance that is helpful but not required to identify a field:

- derived/default values;
- scope rules;
- ownership or provider boundaries;
- non-secret delivery behavior;
- shared status vocabulary;
- lifecycle explanation already enforced server-side.

Do **not** hide validation errors, destructive confirmation, security incidents, stale evidence, or required workflow state inside an Info Tip. Those remain persistent callouts.

## Placement

For genuinely field-specific guidance, the icon trigger may sit inline beside the field label. When two or more controls share the same source, ownership, naming, lifecycle, or selection semantics, prefer **one consolidated Info Tip in the owning form/card/section header** instead of repeating a trigger on each control.

The Namespace Provisioning Allocation Change workspace applies this same
title-adjacent Info Tip pattern to its Native Allocation Change, Native
Governance Cutover, Capsule Tenant Quota Governance, and Capsule Shared
Allocation Governance sections. Capsule status/authority badges remain
independent of the help trigger; do not position title-level contextual guidance in the
far-right header action corner.

For a form/card section, place the trigger **immediately beside the section title** so the same visual grammar is used across Tenant, Operations, Governance, Integrations, and future domains. The owning surface must permit visible overflow for the desktop hover preview; do not trap the preview inside an `overflow-hidden` card. Rounded visual containment should be preserved by the card/header geometry rather than by clipping the Info Tip.

For Kubernetes Secret Operations, the selected Secret heading on the replacement content form is also a title-level owner: render its contextual replacement guide with `variant='guide'`. Keep actual secret type, namespace/key count, write scope, validation and hidden-value safeguards visible outside the popover; do not change field-specific icon help or operational behavior.

For a canonical registry with shared status or lifecycle vocabulary, place one **Guide label** Info Tip **beside the registry title** through the shared table-header `title_extra` slot. The registry card opts into visible overflow while the table itself stays inside its dedicated `overflow-x-auto` container. Header actions remain reserved for operational actions such as Clear Filters, Add, Create, or navigation.

For **Kubernetes Tenant**, title-level guidance in Tenant Setup, Discovery, Membership, Access, Credentials, Resource Profiles, Capacity Policy/Budget and Namespace Provisioning/Allocation sections uses the same compact Guide label. **Capsule Initial Owner** consolidates Owner Kind and Owner Subject explanations into one title-adjacent Guide because both fields describe the same provider ownership boundary; the field labels and required ownership state remain visible without hovering. Other genuinely field-specific principal/selection help and row-specific reconciliation evidence remain icon-only. The four Resource Profile resource-group disclosures render their Guide beside the heading **inside the summary**, never as a detached `Section help` row below it. Activating that Guide must not toggle the disclosure; the chevron and summary area still operate normally. Preserve required inline status/error guidance outside popovers.

## Integration provider Overview headers

All canonical provider landing pages (Kubernetes, Metrics Source, Alertmanager,
MinIO, Harbor, Vault and GitHub) receive **one** standard Violet
`Guide` beside the **Integration Overview** section title. The owning
shared macro is
`integrations/components/_provider_frontpage.html::overview`, not
provider-specific markup or a new Info Tip implementation.

The Guide popover provides existing provider-owned Overview description
and the **complete** titles and descriptions from **Integration Contract**,
**Consumer Resolution**, and **Authority Boundary**. In the compact
Integration Overview design these three explanations live **only in the Guide**;
the old persistent three-column explanatory footer is removed across all
seven providers through the shared macro. The four operational KPI cards
(registered, validated/ready, needs attention, and provider-specific
coverage/grants) remain continuously visible, because status and readiness
must not be hidden in contextual help. No provider-specific overview markup,
new JS/CSS, or custom info icon is permitted.

The trigger uses a provider-title-derived ID to prevent duplicate
tooltip IDs within a page. It reuses `components/info_tip.html` and
`info_tips.js` for pointer hover, touch/click, keyboard focus, Escape,
viewport clamping, and light/dark; no separate scripts or hidden field-level
question icons. Section titles wrap naturally on mobile.

Provider Hero descriptions are concise, semantically accurate copy rather
than CSS `nowrap`/clamping. The GitHub Hero uses
`Register GitHub Apps with governed Source Control evidence.` to fit one
line in the reviewed 1440×900 viewport without changing other providers.
The shared Overview Guide does not alter KPI counts, operational readiness,
repository evidence, provider admission or backend behavior.

## Integration Workspace heading and Guide

All seven provider Integration landing pages (Kubernetes, Metrics Source,
Alertmanager, MinIO, Harbor, Vault, GitHub) use the shared
`components/integration_workspace_tabs.html` adapter. Its section heading
is **outside** the existing operational card: **Provider Connections &
Coverage** with the concise description **Monitor provider readiness,
committed coverage, and registered connections.** This outer heading
uses icon-free semantic typography and responsive spacing rather than
duplicated provider templates. The **inner Integration Workspace** card
retains its existing section icon and title-adjacent Violet Guide.

**Inside** the card, the existing **Integration Workspace** title owns a
single compact Violet `Guide` immediately beside it. The adapter passes
the canonical `info_tip.render(..., placement="right", variant="guide")`
as optional `title_extra` to the existing
`integrations/components/_workspace.html::section_header` macro.
This preserves the generic section header's default rendering for callers
without `title_extra` and keeps the Guide separate from right-aligned
operational actions. The Guide explains **Integration Coverage** (observed
and committed evidence where available), **Connection Registry** (canonical
registration and readiness), and the **Authority Boundary** (external
providers own native resources; KAORI normalizes and correlates committed
evidence). Do not imply that all external source inventory is already
complete, nor hide required readiness/errors in contextual help.

The two provider tabs, their URL-backed state, HTMX/Alpine behavior, default
five-row pagination, and connection authorization are unchanged. The existing
`info_tips.js` controller remains the only hover, focus, click/touch, Escape
and viewport-portal implementation. No individual provider page may add
another workspace Guide or a new script for this shared header.

## Provider detail heading Guides — GitHub UAT reference

Canonical GitHub connection detail sections use the **same title-adjacent
Violet info + Guide control** as Tenant Membership Registry and the
Integration Workspace. This is a labeled **Guide**, not a standalone `?`,
circle-help, or unlabelled `i` icon:

- **Connection Contract** — `integrations/source_control/github/uat_detail.html`
  passes an `info_tip.render(..., variant='guide', placement='right')`
  through `integrations/components/_workspace.html::section_header(title_extra=...)`.
- **GitHub Full Validation** —
  `integrations/source_control/github/partials/_detail_validation.html`
  passes the same variant through
  `components/connection_validation_header.html::render(title_extra=...)`.
- **Repository Inventory & Lifecycle** —
  `integrations/source_control/github/partials/_detail_inventory.html`
  follows the same shared connection header contract.

The **visible result** must contain
`data-kaori-info-tip-variant="guide"`, the icon `data-lucide="info"`,
and the adjacent literal label `Guide` inside the same trigger button.
Confirm those in the **rendered DOM**, not just from template text or the
presence of `info_tip.render`. A title-level Guide must be passed
**explicitly**, because the shared macro's default `variant='icon'` is
reserved for narrow field/row guidance. Keep the title and the Guide in
the same responsive header group and outside the far-right action slot.

If a Dev Container screenshot still shows an isolated `?` or `i`
beside these titles while the current template has `variant='guide'`,
verify the running checkout is at the **latest holding UAT SHA**, restart
the application/template-rendering process if necessary, then reload the
page and inspect the actual button DOM. Do not introduce local icons, CSS,
JS or a competing hover implementation to disguise stale templates.
The existing `info_tips.js` controls hover, focus, touch, Escape and
viewport positioning. This provider-specific visual acceptance is distinct
from field-level icon-only help.

## Interaction and responsive behavior

Info Tip uses **one non-modal anchored popover** for every input method.

- **desktop hover** opens the shared popover from the icon or Guide pill;
- **keyboard focus** opens the same popover;
- **click/touch** toggles the same popover;
- **Escape**, outside click, HTMX replacement, resize, or scroll closes it.

The hover controller briefly defers dismissal when the pointer crosses the small trigger-to-panel gap, allowing long glossary panels to be reached and scrolled without pinning. Guide buttons inside disclosure summaries intercept the summary activation default, while the summary itself stays keyboard-operable. The shared `info_tips.js` controller temporarily portals the popover to `document.body` for ordinary pages, or into the closest open native `<dialog>` when its trigger belongs to a modal top layer. It positions the preview from the trigger, flips above when needed, and clamps it to the viewport. The optional `placement='top'` explicitly prefers an above-trigger preview for boundary Guides anchored to a bottom navigation footer, falling back below only when the upper viewport cannot accommodate it. Other `left`/`right` placements retain below-first behavior. This keeps field-level help visible inside Notification Channel dialogs without adding a second tooltip implementation. The same element supports desktop, touch, and keyboard paths; ordinary card/table overflow does not clip the preview.

Info Tip is deliberately non-modal: it never traps focus and never owns confirmation or workflow actions. If content requires a form, destructive acknowledgement, security decision, or long interactive workflow, use the relevant KAORI dialog/callout pattern instead.

The Jobs Configuration and Data Lifecycle domain-navigation footers use the same compact **Execution Boundary + Guide + Jobs & Executions** presentation. A Guide beside the visible footer label opens above; it keeps the full canonical boundary description. Jobs search owns the filtered/total count, so the footer stays one line without nested horizontal scrolling. On narrow viewports, the visible boundary label may truncate while the Guide's accessible title and content remain complete.

Inactive guidance must not reserve document or table layout space.

## Content

Use one short title, one concise explanation, and only a few supporting points. Render the explanation and supporting points with a consistent readable text hierarchy, soft row separators, wrapping for long values and enough whitespace to scan a glossary without treating each line as a new card. The item content remains domain-owned plain text (no inferred status severity or HTML interpretation). Avoid oversized triggers, heavy blue treatment, or floating icons disconnected from context.

## Accessibility

The trigger is a real button with `aria-expanded`, `aria-controls`, and `aria-describedby`. Keyboard focus/activation and pointer/touch users all receive the same non-modal popover. The popover uses `role="tooltip"` and does not trap focus.

## Example

```jinja
{% import "components/info_tip.html" as info_tip %}

{% set title_info %}
    {{ info_tip.render(
        'tenant-registry-status-tip',
        'Tenant Registry status',
        'Lifecycle is committed Tenant state; Actions show current operation readiness.',
        [
            'Ready — Tenant governance is active.',
            'Blocked — the Tenant stays valid while an action fails closed.'
        ],
        placement='right',
        variant='guide'
    ) }}
{% endset %}

{{ table_ui.inventory_block_header(
    'building-2',
    'Tenant Registry',
    'Committed Tenant ownership and lifecycle state.',
    'tenant-registry-loading',
    'Refreshing Tenant Registry',
    none,
    none,
    title_extra=title_info
) }}
```

## Rollout boundary

Apply the Guide variant to **title-level** Inventory and registry help (Kubernetes, Object Storage, Artifact Registry, Tenant) without changing field-level triggers or replacing semantic state badges. The tooltip contents are existing domain-owned guidance: the UI component must not invent help instructions, alter provider evidence, or change access policy. Reuse one controller for hover, focus and touch; no new JavaScript dialog or duplicate event listeners.

## Dense registry boundary

Do not place a multi-line Info Tip **inside a table row or its overflow-x container**. A shared glossary belongs in the block header. Genuinely row-specific operational evidence may use the existing native-dialog detail pattern when that evidence cannot be summarized by the shared vocabulary.
