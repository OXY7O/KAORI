# KAORI Info Tip Standard

## Purpose

`components/info_tip.html` is the canonical compact guidance pattern for dense forms and operational controls where permanent helper copy would make the interface unnecessarily tall.

The default field trigger remains the compact icon-only affordance. A block header may use a short text trigger such as **Status Guide**, **Membership Guide**, or **Group Guide** when an isolated icon would be ambiguous beside operational actions.

A text trigger must reuse the owning surface's existing button primitive. For canonical registries, pass `table_ui.action_classes()`; do not introduce page-local button styling.

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

For a form/card section, place the trigger beside the section title or in the header action area so the hover preview is outside dense control geometry. The owning surface must permit visible overflow for the desktop hover preview; do not trap the preview inside an `overflow-hidden` card. Rounded visual containment should be preserved by the card/header geometry rather than by clipping the Info Tip. For a registry with shared status or lifecycle vocabulary, place one text-trigger Info Tip in the **block header action area**, outside the horizontal table scroll container. Keep table rows to semantic labels and real actions.

## Interaction and responsive behavior

Info Tip uses two existing browser interaction paths rather than trying to position one hover surface everywhere:

- **desktop pointer hover** — show the compact anchored preview bubble;
- **click, touch, or keyboard activation** — open the same guidance in the browser native `<dialog>` top layer through KAORI's existing `native_dialogs.js` contract.

The hover preview is enabled only at the desktop breakpoint. Mobile does not depend on sticky `:hover`, focus-within positioning, transformed ancestors, or table/card overflow. The native dialog owns mobile/touch placement, viewport containment, focus, dismissal, and top-layer stacking.

Inactive guidance must not reserve document or table layout space.

## Content

Use one short title, one concise explanation, and only a few supporting points. Avoid oversized triggers, heavy blue treatment, or floating icons disconnected from context.

## Accessibility

The trigger is a real button with `aria-haspopup="dialog"` and `aria-controls`. Keyboard activation opens the native dialog, which provides an explicit Close action. Pointer users retain a non-blocking desktop hover preview.

## Example

```jinja
{% import "components/info_tip.html" as info_tip %}

{{ info_tip.render(
    'tenant-registry-status-tip',
    'Tenant Registry status',
    'Lifecycle is committed Tenant state; Actions show current operation readiness.',
    [
        'Ready — Tenant governance is active.',
        'Blocked — the Tenant stays valid while an action fails closed.'
    ],
    button_text='Status Guide',
    button_classes=table_ui.action_classes()
) }}
```

## Dense registry boundary

Do not place a multi-line Info Tip **inside a table row or its overflow-x container**. A shared glossary belongs in the block header. Genuinely row-specific operational evidence may use the existing native-dialog detail pattern when that evidence cannot be summarized by the shared vocabulary.
