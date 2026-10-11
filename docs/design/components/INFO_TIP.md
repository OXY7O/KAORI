# KAORI Info Tip Standard

## Purpose

`components/info_tip.html` is the canonical compact guidance pattern for dense forms and operational controls where permanent helper copy would make the interface unnecessarily tall.

The default trigger is the compact icon-only affordance. In canonical registries, shared status/lifecycle guidance belongs **inline beside the registry title**; do not add separate text actions such as **Status Guide**, **Membership Guide**, or **Group Guide**.

Text-trigger Info Tips remain an exception for surfaces where an icon-only trigger would be genuinely ambiguous and must reuse the owning surface's existing button primitive rather than introducing page-local styling.

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
independent of the help trigger; do not position the help icon in the
far-right header action corner.

For a form/card section, place the trigger **immediately beside the section title** so the same visual grammar is used across Tenant, Operations, Governance, Integrations, and future domains. The owning surface must permit visible overflow for the desktop hover preview; do not trap the preview inside an `overflow-hidden` card. Rounded visual containment should be preserved by the card/header geometry rather than by clipping the Info Tip.

For a canonical registry with shared status or lifecycle vocabulary, place one icon Info Tip **beside the registry title** through the shared table-header `title_extra` slot. The registry card opts into visible overflow while the table itself stays inside its dedicated `overflow-x-auto` container. Header actions remain reserved for operational actions such as Clear Filters, Add, Create, or navigation.

## Interaction and responsive behavior

Info Tip uses **one non-modal anchored popover** for every input method.

- **desktop hover** opens the shared popover;
- **keyboard focus** opens the same popover;
- **click/touch** toggles the same popover;
- **Escape**, outside click, HTMX replacement, resize, or scroll closes it.

The shared `info_tips.js` controller temporarily portals the popover to `document.body`, positions it from the trigger, flips above when needed, and clamps it to the viewport. The same element is therefore used on desktop and touch/keyboard paths, and ordinary card/table overflow cannot clip it.

Info Tip is deliberately non-modal: it never traps focus and never owns confirmation or workflow actions. If content requires a form, destructive acknowledgement, security decision, or long interactive workflow, use the relevant KAORI dialog/callout pattern instead.

Inactive guidance must not reserve document or table layout space.

## Content

Use one short title, one concise explanation, and only a few supporting points. Avoid oversized triggers, heavy blue treatment, or floating icons disconnected from context.

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
        placement='right'
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

## Dense registry boundary

Do not place a multi-line Info Tip **inside a table row or its overflow-x container**. A shared glossary belongs in the block header. Genuinely row-specific operational evidence may use the existing native-dialog detail pattern when that evidence cannot be summarized by the shared vocabulary.
