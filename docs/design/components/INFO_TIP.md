# KAORI Info Tip Standard

## Purpose

`components/info_tip.html` is the canonical compact guidance pattern for dense forms and operational controls where permanent helper copy would make the interface unnecessarily tall.

The trigger is a compact 24px neutral help affordance placed beside the content it explains. Violet is reserved for hover/focus emphasis. The guidance bubble appears on pointer hover and keyboard/touch focus.

## Use

Use an Info Tip for contextual guidance that is helpful but not required to identify a field:

- derived/default values;
- scope rules;
- ownership or provider boundaries;
- non-secret delivery behavior;
- consequences that are already enforced server-side.

Do **not** hide validation errors, destructive confirmation, security incidents, stale evidence, or required workflow state inside an Info Tip. Those remain persistent callouts.

## Placement

For a field, place the trigger inline beside the field label rather than at the far edge of the control. For a form/card header, upper-right placement remains appropriate. This keeps the relationship between trigger and content obvious without adding permanent helper paragraphs.

## Content

Use a compact card with one short title, one concise explanation, and at most a few supporting points. Avoid oversized circular triggers, heavy blue treatment, or floating icons disconnected from the label. The bubble supplements field labels; it does not replace clear labels.

## Accessibility

The trigger is keyboard-focusable, references the tooltip with `aria-describedby`, and the tooltip is exposed on `group-focus-within` as well as hover.

## Example

```jinja
{% import "components/info_tip.html" as info_tip %}

{{ info_tip.render(
    'tenant-setup-tip',
    'Tenant setup',
    'Create the ownership boundary before namespace and access workflows.',
    [
        'Slug is derived from the Tenant name when omitted.',
        'Only Ready clusters are eligible.',
        'Native Kubernetes is the admitted baseline.'
    ]
) }}
```
