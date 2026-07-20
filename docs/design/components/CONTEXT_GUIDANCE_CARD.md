# KAORI Context Guidance Card Standard

## Purpose

The Context Guidance Card presents **secondary operational guidance** in a compact, expandable card. It is designed for the right-side contextual column of create, edit, configuration, validation, and detail workspaces.

The reference implementation is **After Registration** on Register Alertmanager Instance.

Use this component when the user may need concise supporting guidance, but the information must not compete with the primary form, status, or workflow.

## Information architecture

The required structure is:

```text
Expandable Header
↓
Compact Guidance Items
```

The header contains:

- one contextual icon;
- one Title Case title;
- one short sentence-case description;
- a native Details / Collapse affordance.

The body contains two to five concise **ordered** items with generated two-digit markers.

Non-sequential option, concept, or contract references belong in the Information Guide Card.

## Placement contract

Preferred placement:

- right-side contextual column;
- contextual subpage such as create, edit, detail, configuration, or validation;
- after primary workflow guidance and before destructive or unrelated controls.

Do not place the component on overview, landing, list, or registry pages merely to fill space.

Do not use it as a navigation card. Page relationships belong in the Related Page Card.

## Visual contract

Container:

- `rounded-xl`;
- standard outline and card surface;
- restrained shadow;
- native `details` element.

Header:

- `bg-surface-hover`;
- 16 px horizontal padding;
- 14 px vertical padding;
- 36 px icon surface;
- 16 px icon;
- 14 px semibold title;
- 12 px supporting description;
- visible keyboard focus ring.

Body:

- 16 px padding;
- 12 px text with 20 px line height;
- 12 px vertical separation;
- compact reading width suitable for a 320 px sidebar.

Ordered item:

```text
01  Step Title supporting explanation.
02  Step Title supporting explanation.
```

- 24 px marker column;
- two-digit Violet marker;
- Title Case label;
- sentence-case explanation on the same line.


## Open and closed behavior

Default state is **closed** because the component contains secondary guidance.

It may be open by default only when:

- the guidance is essential to completing the page;
- the page has no separate primary Info Flow;
- hiding the content would increase the chance of an invalid operation.

Do not force every right-side card open.

## Content rules

Use two to five items.

Each item must communicate one ordered operational instruction, such as:

- a required next step;
- a lifecycle progression;
- a configuration propagation sequence;
- a remediation sequence.

Keep each item to one concise explanation. Do not embed long paragraphs, raw diagnostics, tables, metrics, forms, or action buttons.

## Typography and casing

Use Title Case for:

- component title;
- item or step title.

Use sentence case for:

- header description;
- item explanation.

Technical identifiers retain canonical casing, including `Alertmanager`, `Prometheus`, `Kubernetes`, `API`, `TLS`, `OAuth`, `OIDC`, and file paths.

Do not apply a mechanical `|title` filter to dynamic technical values.

## Relationship to other components

### Info Flow

Use Info Flow for the **primary ordered workflow** of a page. It uses a larger visual hierarchy, a vertical timeline, and an optional flow-wide boundary note.

Use Context Guidance Card for **secondary supporting guidance** in the sidebar. It is denser, normally collapsed, and does not replace the primary workflow.

### Related Page Card

Use Related Page Card to navigate to one directly related KAORI workspace. It contains one destination action.

Context Guidance Card contains no navigation action.

### Semantic status or warning box

Use semantic info, warning, or critical surfaces when the message represents a current state, exception, risk, or required attention.

Do not color a Context Guidance Card merely because its subject is security or validation.

## Shared implementation

Import:

```jinja
{% import "components/context_guidance_card.html" as context_guidance_card %}
```

Ordered example:

```jinja
{% set after_registration_items = [
    ('Open the Registered Instance', 'and run Full Validation to establish readiness.'),
    ('Review Diagnostics', 'when readiness is degraded or blocked.'),
    ('Create Scope Bindings', 'and assign role and priority.'),
    ('Keep the Connection Enabled', 'when KAORI should resolve this source.')
] %}

{{ context_guidance_card.render(
    'After Registration',
    'Complete these steps before the source is used operationally.',
    after_registration_items,
    icon='list-checks'
) }}
```

For non-sequential option or concept guidance, use `components/information_guide_card.html` instead.

Do not copy the container, summary, marker, or typography classes into page-local templates.

## Accessibility

- Use native `details` and `summary` semantics.
- Preserve keyboard activation and visible focus.
- Keep the summary text meaningful without relying on the icon.
- Sequence remains understandable without color.
- DOM order must match reading and operational order.

## Responsive behavior

The card remains vertical at all breakpoints. It may move below the primary content when the page grid stacks, but its internal structure does not become horizontal.

## Prohibited patterns

- Local copies of the After Registration markup.
- Multiple actions inside the card.
- Tables, charts, metrics, or live status grids.
- Long documentation paragraphs.
- Warning colors without an actual warning state.
- Using the card as a generic navigation shortcut.
- More than five items.

## Review checklist

- Shared component imported.
- Right-side contextual placement is justified.
- Two to five concise items.
- Ordered markers are generated by the component.
- The items represent a genuine operational sequence.
- Title Case labels and sentence-case explanations.
- Default closed unless operationally essential.
- No page-local duplicate geometry.
- No actions, metrics, tables, or raw diagnostics.
