# KAORI Info Tip Standard

## Purpose

`components/info_tip.html` is the canonical compact guidance pattern for dense forms and operational controls where permanent helper copy would make the interface unnecessarily tall.

The trigger is a small circular information icon. The guidance bubble appears on pointer hover and keyboard/touch focus.

## Use

Use an Info Tip for contextual guidance that is helpful but not required to identify a field:

- derived/default values;
- scope rules;
- ownership or provider boundaries;
- non-secret delivery behavior;
- consequences that are already enforced server-side.

Do **not** hide validation errors, destructive confirmation, security incidents, stale evidence, or required workflow state inside an Info Tip. Those remain persistent callouts.

## Placement

Prefer the upper-right area of a form/card header. This preserves vertical space and keeps guidance discoverable without repeating helper paragraphs below every input.

## Content

Keep one short title, one concise explanation, and at most a few compact supporting points. The bubble supplements the field labels; it does not replace clear labels.

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
