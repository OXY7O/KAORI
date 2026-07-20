# KAORI Info Flow Standard

## Purpose

The Info Flow component explains a short, ordered operational or governance sequence. It is used when users need to understand **what happens first, what happens next, and where authority or eligibility is established**.

The reference implementations are **Role Assignment Flow** on Roles & Access, **Alertmanager Registration Flow** on Register Alertmanager Instance, and **Configuration Flow** on Alertmanager Instance Manage.

## When to use

Use Info Flow for a sequence of three to five meaningful stages, such as:

- capability definition → role composition → user assignment;
- connection registration → reachability verification → capability validation → scope assignment;
- request → approval → controlled execution;
- discovery → validation → readiness → operational use;
- save configuration → validate → observe runtime → review effective resolution.

Do not use it for:

- unordered feature lists;
- long documentation;
- raw diagnostics;
- more than five steps;
- status dashboards or metrics;
- actions that users must execute directly inside each row.

## Information architecture

The required order is:

```text
Expandable Header
↓
Ordered Vertical Timeline
↓
Optional Boundary Note
```

### Header

The header contains:

- one contextual icon;
- a Title Case component title;
- one short sentence-case description;
- one expand/collapse affordance.

The component is open by default when the flow is essential to completing the current page. It may be closed by default when it is supporting guidance only.

### Ordered steps

Each step contains:

- a two-digit sequence marker (`01`, `02`, `03`, ...);
- a Title Case step title;
- one concise sentence-case explanation.

Use three to five steps. Each explanation should communicate a state transition, authority boundary, eligibility rule, or required next action.

### Boundary note

The optional final note is reserved for a guardrail that applies to the complete flow. Examples:

- emergency authority is separate from ordinary role assignment;
- registration does not imply capability readiness;
- validation does not automatically create a scope binding.

Do not use the note as a generic tip or duplicate a step description.

## Visual contract

Container:

- `rounded-2xl`;
- standard KAORI card border and surface;
- restrained shadow;
- expandable header separated from content by one border.

Header:

- 44 px icon surface;
- 20 px icon;
- 16 px semibold title;
- 14 px supporting description.

Timeline:

- 32 px circular sequence marker;
- Violet Soft marker surface and Violet border;
- 14 px semibold step title;
- 12 px supporting description;
- 16 px vertical spacing between steps;
- one subtle vertical connector.

Boundary note:

- Violet Soft surface;
- Violet outline;
- 12 px text;
- one contextual 16 px icon.

## Typography and casing

Use Title Case for:

- Info Flow title;
- step titles.

Use sentence case for:

- header description;
- step explanations;
- boundary note.

Technical identifiers retain canonical casing. Never apply a mechanical `|title` filter to dynamic values such as `kube-system`, `OAuth`, `OIDC`, `v1beta1`, or provider profile keys.

## Content rules

Every step should answer at least one of these questions:

- What is created or established here?
- What prerequisite must pass?
- What changes after this stage?
- Which source remains authoritative?
- When does the object become eligible for operational use?
- What must the user do next?

Avoid vague labels such as `Setup`, `Process`, or `Complete` without a precise domain object.

## Shared implementation

Use:

```jinja
{% import "components/info_flow.html" as info_flow %}
```

Then:

```jinja
{% set steps = [
    ('Register Connection Identity', 'KAORI stores one reusable connection record.'),
    ('Verify Reachability', 'Test Connection confirms endpoint access before registration.'),
    ('Validate Capabilities', 'Full Validation establishes compatibility and readiness.'),
    ('Assign Operational Scope', 'Bindings determine where the source is eligible.')
] %}

{{ info_flow.render(
    'Alertmanager Registration Flow',
    'How a connection becomes an eligible operational source in KAORI.',
    steps,
    icon='waypoints',
    note='Registration alone does not establish readiness or scope eligibility.',
    open_by_default=true
) }}
```

Do not copy the timeline classes into page-local templates.

## Relationship to Context Guidance Card

Use Info Flow for the primary ordered workflow that users must understand to complete the page, including when that flow is placed in a right-side contextual column. Do not downgrade a primary flow to Context Guidance Card solely because the available column is narrow. Use the smaller Context Guidance Card only for secondary, normally collapsed ordered guidance. Do not duplicate the same sequence in both components.

## Accessibility

- Use native `details` and `summary` behavior.
- Keep the summary keyboard-operable.
- Do not remove visible focus behavior.
- Sequence must remain understandable without color.
- The DOM order must match the operational order.

## Responsive behavior

The component remains a single vertical timeline on all viewport sizes. Do not convert steps into horizontal columns because ordered explanations become harder to scan and wrap inconsistently.

## Review checklist

- Three to five ordered stages.
- Title Case title and step names.
- Sentence-case descriptions.
- Shared component used.
- Primary ordered flows use Info Flow even when placed in a sidebar.
- Two-digit markers generated by the component.
- One optional flow-wide boundary note.
- No metrics, tables, or embedded actions inside steps.
- Technical casing preserved.

## Prometheus reference implementations

Prometheus uses Info Flow for primary ordered workflows:

- Register/Edit Prometheus Connection → `Prometheus Integration Flow`;
- Prometheus Instance Manage → `Configuration Flow`;
- cluster-bound Prometheus Configuration → `Configuration Flow`.

These remain primary flows even when positioned in a right-side column.

Prometheus Configuration Flow is a primary provider workflow and uses Info Flow, matching Alertmanager Configuration Flow.
