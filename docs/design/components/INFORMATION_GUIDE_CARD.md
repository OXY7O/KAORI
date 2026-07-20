# KAORI Information Guide Card Standard

## Purpose

The Information Guide Card presents **non-sequential reference guidance** in a compact, expandable right-side card. It is used when the user needs to compare options, understand named concepts, or distinguish related contracts without implying that the items must be completed in order.

The reference implementation is **Connection Type Guide** on Register Alertmanager Instance.

## Information architecture

The required structure is:

```text
Expandable Header
↓
Icon-led Reference Items
```

The header contains:

- one contextual icon;
- one Title Case title;
- one short sentence-case description;
- a native Details / Collapse affordance.

Each body item contains:

- one related icon;
- one Title Case item title;
- one concise sentence-case explanation.

Items are peers. The component does not use numbers, arrows, connectors, or visual sequencing.

## When to use

Use the Information Guide Card for:

- configuration option comparisons;
- ownership or deployment model explanations;
- contract or terminology references;
- concept distinctions;
- non-sequential operating modes;
- short decision-support guidance.

Do not use it for:

- required steps or lifecycle order;
- remediation sequences;
- current status, warning, or risk;
- navigation to another page;
- metrics, tables, forms, or actions.

## Placement contract

Preferred placement:

- right-side contextual column;
- create, edit, detail, configuration, or validation subpage;
- near the field or workflow whose concepts it explains.

Do not add the card to overview, landing, list, or registry pages merely to fill space.

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

Body item:

- 32 px neutral icon surface;
- 16 px item icon;
- 12 px semibold item title;
- 12 px explanation with 20 px line height;
- 12 px vertical padding;
- subtle divider between peer items.

The icon communicates item identity, not sequence or severity.

## Icon contract

Every item must use an icon related to its meaning.

Examples:

| Item | Recommended Icon |
|---|---|
| Externally Managed | `building-2` |
| Standalone | `box` |
| Shared Service | `network` |
| Managed for a Specific Scope | `target` |
| Connection Identity | `fingerprint` |
| Connection Contract | `file-check-2` |
| Capability Contract | `badge-check` |
| Scope Bindings | `link-2` |

Do not reuse the same generic icon for every item when meaningful distinctions are available.

Icons are decorative support. Item titles must remain understandable without them.

## Open and closed behavior

Default state is **closed** because this component contains supporting reference information.

It may be open by default only when the option distinction is required before the user can safely complete the form.

## Content rules

Use two to five items.

Each item must explain exactly one named option, concept, or contract. Keep the explanation concise and self-contained.

The header description should explain what the list helps the user compare or understand.

Correct:

```text
Connection Type Guide
Compare the ownership and deployment models for this endpoint.
```

Incorrect:

```text
Follow these steps to configure the connection.
```

The incorrect wording implies an ordered workflow.

## Typography and casing

Use Title Case for:

- component title;
- item title.

Use sentence case for:

- header description;
- item explanation.

Technical identifiers retain canonical casing, including `Alertmanager`, `Prometheus`, `Kubernetes`, `API`, `TLS`, `OAuth`, and `OIDC`.

Do not apply a mechanical `|title` filter to dynamic technical values.

## Relationship to other components

### Context Guidance Card

Use Context Guidance Card for **secondary ordered guidance**, including next steps, lifecycle propagation, or remediation sequences. It uses generated two-digit markers.

Use Information Guide Card when the items are peers and may be read in any order.

### Info Flow

Use Info Flow for the **primary ordered workflow** of a page. It has a larger hierarchy, a vertical timeline, and an optional flow-wide boundary note.

### Related Page Card

Use Related Page Card for one directly related KAORI destination. It contains one navigation action.

### Semantic information box

Use semantic information, warning, or critical surfaces for current state, exception, risk, or required attention.

## Shared implementation

Import:

```jinja
{% import "components/information_guide_card.html" as information_guide_card %}
```

Example:

```jinja
{% set connection_type_items = [
    ('building-2', 'Externally Managed', 'Lifecycle belongs to another team or service owner.'),
    ('box', 'Standalone', 'An independent endpoint with a dedicated operational purpose.'),
    ('network', 'Shared Service', 'A centralized connection reused across multiple scopes.'),
    ('target', 'Managed for a Specific Scope', 'Ownership follows one primary context.')
] %}

{{ information_guide_card.render(
    'Connection Type Guide',
    'Compare the ownership and deployment models for this endpoint.',
    connection_type_items,
    icon='boxes'
) }}
```

Do not copy the container, summary, divider, icon surface, or typography classes into page-local templates.

## Accessibility

- Use native `details` and `summary` semantics.
- Preserve keyboard activation and visible focus.
- Mark item icons `aria-hidden="true"`.
- Keep the item title meaningful without the icon.
- Preserve source order as the intended reading order.

## Responsive behavior

The card remains vertical at every breakpoint. It may move below the primary form when the page grid stacks, but item rows remain icon-left and content-right.

## Prohibited patterns

- Numbering peer options.
- Timeline connectors or arrows.
- Generic bullet icons for every item when specific icons are available.
- Actions inside the card.
- Tables, charts, metrics, forms, or raw diagnostics.
- Warning colors without an actual warning state.
- More than five items.

## Review checklist

- Shared component imported.
- Items are genuinely non-sequential.
- Two to five concise items.
- Every item has a relevant icon.
- No numbers, arrows, or timeline connector.
- Title Case labels and sentence-case explanations.
- Default closed unless required for safe completion.
- No page-local duplicate geometry.
