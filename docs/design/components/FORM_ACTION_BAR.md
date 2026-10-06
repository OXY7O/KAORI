# Form Action Bar

## Purpose

The Form Action Bar is the standard footer for create, edit, and configuration forms. It pairs a concise operational cue with the form actions without repeating the workflow, validation model, or side effects already explained elsewhere on the page.

Use the shared macro:

```jinja
{% import "components/form_action_bar.html" as form_action_bar %}

{% call form_action_bar.render(
    'Register after Test Connection succeeds.',
    aria_label='Alertmanager Instance Actions'
) %}
    <button type="submit">Register Instance</button>
{% endcall %}
```

## Information Architecture

The component contains:

1. one concise helper sentence;
2. one action group;
3. one primary action and, when required, one closely related secondary action.

The helper explains the immediate condition or next consequence of the adjacent action. Detailed prerequisites, validation stages, authority boundaries, and remediation belong in field helper text, Connection Validation Header, Info Flow, Related Page Card, or validation evidence.

## Helper Copy Contract

The helper must:

- use sentence case;
- contain exactly one short sentence;
- remain 72 characters or fewer whenever the wording is static;
- describe one immediate condition, consequence, or next step;
- remain visually compact beside the action on a standard desktop layout.

Preferred:

- `Register after Test Connection succeeds.`
- `Save changes, then run Full Validation.`
- `Save to start Kubernetes inventory onboarding.`
- `Test changes before saving this configuration.`

Avoid:

- multi-sentence explanations;
- paragraph-length readiness or workflow summaries;
- repeating information already present in an Info Flow;
- explaining every downstream effect of the save operation;
- technical diagnostics or remediation instructions.

## Action Contract

- Use exactly one primary action.
- One secondary action is allowed only when it directly supports the same submission, such as `Cancel` or `Test Connection`.
- Place secondary actions before the primary action.
- Do not place unrelated navigation, destructive actions, or more than two controls in the bar.
- Buttons retain the global Button Standard geometry and focus behavior.

## Visual Contract

- one rounded `surface-card` action surface;
- visible `outline-default` border and subtle shadow;
- 16 px vertical padding;
- 20–24 px horizontal padding;
- responsive stacked layout on small screens;
- helper aligned left and action group aligned right on desktop;
- helper width limited to `max-w-xl`;
- optional 12 px semibold action title above the helper;
- helper typography: 12 px with 20 px line height;
- action group uses 8 px internal gap.

Do not render the action region as a full-width rectangular color strip. The shared component owns the complete action-surface geometry. Provider templates supply only the title/helper copy and action controls.

## Relationship to Connection Validation Header

Use Connection Validation Header for an action that validates or refreshes the content block immediately below it.

Use Form Action Bar for the final create, update, or save operation at the bottom of a form.

Do not move workflow explanations from the Connection Validation Header into the Form Action Bar. Each component should communicate only the action it directly governs.

## Responsive and Accessibility

- The helper appears before the action group in document order.
- The action group stacks on narrow screens and aligns right on larger screens.
- Supply an `aria_label` that identifies the form action region.
- Do not truncate or visually clamp helper text; keep the source wording short instead.
- Primary and secondary controls must preserve visible keyboard focus.

## Prohibited Patterns

- A paragraph beside `Register`, `Save`, or `Update`.
- More than one helper sentence.
- Helper copy longer than 72 characters without a documented exception.
- Duplicating the full integration workflow in the footer.
- Copying footer layout utilities into individual provider templates.
- Using warning or critical color for an ordinary save consequence.

## Review Checklist

- [ ] The shared Form Action Bar macro is used.
- [ ] The helper is one sentence and no more than 72 characters.
- [ ] The helper describes only the immediate action context.
- [ ] There is one primary action.
- [ ] Any secondary action directly supports the same submission.
- [ ] Detailed workflow information remains outside the footer.
- [ ] The action region has an accessible label.
