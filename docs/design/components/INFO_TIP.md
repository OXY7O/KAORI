# KAORI Info Tip Standard

## Purpose

`components/info_tip.html` is the canonical compact guidance pattern for dense forms and operational controls where permanent helper copy would make the interface unnecessarily tall.

The default trigger is the existing compact icon-only affordance. A block header may use the same component with a short text trigger such as **Status Guide** or **Group Guide** when an isolated help icon would look ambiguous beside other header actions. Violet remains the interaction emphasis.

## Use

Use an Info Tip for contextual guidance that is helpful but not required to identify a field:

- derived/default values;
- scope rules;
- ownership or provider boundaries;
- non-secret delivery behavior;
- shared status vocabulary;
- consequences that are already enforced server-side.

Do **not** hide validation errors, destructive confirmation, security incidents, stale evidence, or required workflow state inside an Info Tip. Those remain persistent callouts.

## Placement

For a field, place the icon trigger inline beside the field label. For a form/card header, upper-right placement remains appropriate.

For a registry with a shared status vocabulary, place one compact text-trigger Info Tip in the **block header action area**, outside the horizontal table scroll container. Keep the table rows to semantic labels; do not repeat a generic help control beside every row status.

## Responsive behavior

Desktop keeps the anchored hover/focus bubble.

On narrow/touch layouts, the guidance surface becomes a viewport-safe fixed bottom sheet with left/right viewport inset and bounded height. This prevents the tooltip from being clipped by card/table overflow or rendering partly outside the mobile viewport. Keyboard/touch focus continues to expose the same content.

The tooltip must not reserve layout space while inactive.

## Content

Use one short title, one concise explanation, and only a few supporting points. Avoid oversized triggers, heavy blue treatment, or floating icons disconnected from their context.

## Accessibility

The trigger is keyboard-focusable, references the tooltip with `aria-describedby`, and exposes guidance on `group-focus-within` as well as pointer hover. Text-trigger variants retain the same focus ring and semantic help icon.

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
    button_text='Status Guide'
) }}
```

## Dense registry boundary

Do not place a multi-line Info Tip **inside a table row or its overflow-x container**. A shared table glossary belongs in the block header. Genuinely row-specific operational evidence may use the existing top-layer detail/dialog pattern when that evidence cannot be summarized by the shared vocabulary.
