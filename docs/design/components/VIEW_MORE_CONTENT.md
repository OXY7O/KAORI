# KAORI View More Content Standard

## Purpose

View More Content progressively reveals secondary guidance, reference detail, or evidence while keeping the initial workspace compact. It is not a substitute for a primary workflow, table detail page, or required form content.

The shared shell is:

```jinja
{% import "components/view_more_content.html" as view_more_content %}
```

Existing wrappers:

- `components/information_guide_card.html` for non-sequential reference items;
- `components/context_guidance_card.html` for secondary ordered guidance.

Primary ordered workflows use `components/info_flow.html`, not this component.

## When to Use

Use expandable content when:

- the content is useful but not required before the user can act;
- the collapsed title and description provide enough context;
- the expanded body remains concise and scannable;
- hiding the content does not conceal an error, blocker, readiness requirement, or destructive consequence.

Do not use it for:

- required form fields;
- generation readiness or blocking validation;
- primary request preview;
- critical errors;
- one related destination;
- long documentation better served by a dedicated page;
- a primary three-to-five-step flow.

## Visual Contract

- Container: `rounded-xl`, standard outline, card surface, restrained shadow.
- Header padding: 16 px horizontal, 14 px vertical.
- Icon surface: 36 px, `rounded-lg`, Violet Soft.
- Title: 14 px semibold, Title Case.
- Description: 12 px, sentence case, 20 px line height.
- Affordance: 12 px semibold text plus a 16 px chevron.
- Default closed label: `View Details`.
- Open label: `Collapse`.
- Expanded body padding: 16 px.

Do not use `View More` as a vague action when a more precise label such as `View Details`, `View Evidence`, or `View Sections` is available.

## Behavior and Accessibility

- Use native `details` and `summary`.
- Preserve keyboard behavior and visible focus.
- Default state is closed unless immediate visibility is operationally necessary.
- Expanded state must be understandable without animation.
- The header remains stable during HTMX updates.

## DRY Rule

Page templates do not recreate the expandable header, chevron, typography, border, or open/closed labels. Add a wrapper around `view_more_content.render(...)` when a repeatable content body is needed across modules.
