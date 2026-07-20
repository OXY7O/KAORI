# Connection Validation Header

## Purpose

The Connection Validation Header is the standard header for a connection block that exposes a verification, validation, refresh, or evidence-rebuild action. It keeps the operational instruction concise and places the action beside the context it affects.

Use the shared macro:

```jinja
{% import "components/connection_validation_header.html" as connection_validation_header %}

{% call connection_validation_header.render(
    'Endpoint & Access',
    'Validate endpoint access before registration.',
    icon='network'
) %}
    <button type="button">Test Connection</button>
{% endcall %}
```

## Information Architecture

The component contains:

1. contextual icon;
2. Title Case heading;
3. one short helper sentence;
4. one compact action group.

The helper explains the immediate purpose of the adjacent action. Detailed behavior, prerequisites, side effects, and remediation belong in field helper text, Info Flow, validation evidence, or Activity Audit Log.

## Content Contract

### Title

Use Title Case:

- `Endpoint & Access`
- `Validation Actions`
- `Compatibility & Capability Contract`
- `Runtime Health & Diagnostics`

### Helper

The helper must:

- use sentence case;
- contain one sentence;
- remain approximately 80 characters or fewer;
- fit on one visual line on a standard desktop layout where possible;
- describe the next operation, not the whole integration lifecycle.

Preferred:

- `Validate endpoint access before registration.`
- `Test reachability, then rebuild capability evidence.`
- `Refresh connection health and compatibility evidence.`

Avoid:

- multi-sentence explanations;
- provider architecture summaries;
- authority-boundary prose;
- long descriptions of every validation stage.

## Action Contract

- Use one or two closely related actions.
- The first action may be a neutral reachability check.
- The final action may be the primary validation or refresh action.
- Actions must affect the block immediately below the header.
- Do not place unrelated navigation, CRUD, or destructive actions in this header.

## Visual Contract

- `border-b border-outline-subtle`
- 16–20 px horizontal padding
- 40 px icon surface
- responsive stacked layout below large screens
- action group aligned right on desktop
- title: 16 px semibold
- helper: 12 px, one concise line

The component supplies header geometry only. Page templates supply the action controls through the macro call block.

## Responsive and Accessibility

- Header stacks action controls below the title on smaller screens.
- The header receives an accessible label from the title unless overridden.
- Decorative icons use `aria-hidden="true"`.
- Buttons retain visible focus states and explicit labels.
- HTMX loading indicators remain inside the affected connection block and sit directly below the rendered header, before form or table content.

## Prohibited Patterns

- Paragraph-length helper text.
- More than two actions.
- Warning or error prose inside the header helper.
- A button whose effect belongs to another section.
- Copying the header classes into provider templates.
- Using the component as a generic card header where no validation or refresh action exists.

## Review Checklist

- [ ] The title is Title Case.
- [ ] The helper is one sentence and approximately 80 characters or fewer.
- [ ] The action directly affects the adjacent connection block.
- [ ] There are no more than two actions.
- [ ] Detailed explanation is placed outside the header.
- [ ] The shared macro is used.
