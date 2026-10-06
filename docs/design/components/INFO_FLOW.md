# KAORI Info Flow Standard

## Purpose

The Info Flow component explains a short, ordered operational or governance sequence that users must understand to complete or operate the current page. It communicates what happens first, what happens next, and where authority, eligibility, or state is established.

Reference implementations include Role Assignment Flow, Alertmanager Registration Flow, and the Generate Report flow.

## When to use

Use Info Flow for three to five primary stages such as:

- capability definition → role composition → user assignment;
- connection registration → reachability verification → capability validation → scope assignment;
- request creation → controlled execution → artifact availability;
- discovery → validation → readiness → operational use.

Do not use it for unordered feature lists, long documentation, raw diagnostics, metrics, or actions embedded in each row.

## Visibility decision

Primary flow content is always visible. `info_flow.html` renders a static `<section>` and must not hide the process in `<details>`.

Use `context_guidance_card.html` for secondary ordered guidance that may be collapsed, especially in a right-side contextual rail. Do not duplicate the same sequence in both components.

The `open_by_default` macro argument remains accepted only for backward compatibility and has no visual effect.

## Information architecture

```text
Static Header
↓
Ordered Vertical Timeline
↓
Optional Boundary Note
```

Header content:

- one contextual icon;
- one Title Case title;
- one concise sentence-case description.

Each step contains:

- a two-digit sequence marker (`01`, `02`, `03`, ...);
- a Title Case step title;
- one concise sentence-case explanation.

The optional note is reserved for one guardrail that applies to the complete flow.

## Visual contract

Container:

- `rounded-2xl`;
- standard surface and border;
- restrained shadow;
- one divider between header and timeline.

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
- 16 px vertical spacing;
- one subtle vertical connector.

Boundary note:

- Violet Soft surface;
- Violet outline;
- 12 px text;
- one contextual 16 px icon.

## Embedded composition

When Info Flow belongs inside a larger canonical operational surface, use `embedded=true`.
Embedded mode removes the independent card border, radius, shadow, and outer padding while
keeping the shared ordered-timeline authority.

Embedded mode is intentionally denser than the standalone card:
- 32 px icon surface with a 16 px icon;
- 16 px semibold title;
- 12 px supporting description;
- 12 px vertical step rhythm;
- the canonical 32 px sequence marker and 14/12 px step typography remain unchanged.

This density is for parent-owned operational surfaces where the surrounding workspace already
provides hierarchy. Do not copy timeline classes into the page template and do not use embedded
mode merely to make a standalone Info Flow smaller.

## Shared implementation

```jinja
{% import "components/info_flow.html" as info_flow %}

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
    note='Registration alone does not establish readiness or scope eligibility.'
) }}

{# Inside an existing operational surface #}
{{ info_flow.render(
    'Initialization Path',
    'Complete the controlled bootstrap sequence.',
    steps,
    icon='list-checks',
    embedded=true
) }}
```

Do not copy timeline classes into page-local templates.

## Accessibility and responsive behavior

- The sequence remains understandable without color.
- DOM order matches operational order.
- The component remains a vertical timeline at all viewport sizes.
- There is no hidden primary content or expand/collapse affordance.

## Review checklist

- Three to five ordered stages.
- Primary flow remains visible.
- Title Case title and step names.
- Sentence-case descriptions.
- Shared component used.
- Embedded mode is used only inside a parent-owned surface.
- One optional flow-wide boundary note.
- No metrics, tables, or embedded actions inside steps.
- Technical casing preserved.
