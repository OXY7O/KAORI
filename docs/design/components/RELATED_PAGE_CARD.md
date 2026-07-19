# Related Page Card

## Purpose

The Related Page Card connects two KAORI workspaces that form one operational or governance workflow. It explains why the adjacent workspace matters, preserves the authority boundary between the pages, and provides one direct navigation action.

The reference implementation is the **Permission Catalog** card on **Roles & Access**. Roles package permissions, while Permission Catalog remains the authoritative registry of available capability keys.

## When to Use

Use this component only when all conditions are true:

1. The current page and destination page are separate workspaces.
2. The destination is required to understand, verify, consume, or continue the current workflow.
3. The relationship can be explained in one concise paragraph.
4. There is one clear destination action.

Examples:

- Roles & Access → Permission Catalog
- Kubernetes Integrations → Kubernetes Inventory
- Prometheus Integrations → Kubernetes Analytics
- Alertmanager Integrations → Alert Intelligence

Do not use it for generic recommendations, external documentation, unrelated shortcuts, or a list of possible destinations.

## Information Architecture

The card contains, in order:

1. **Relationship Eyebrow** — identifies the type of related workspace.
2. **Destination Title** — the canonical KAORI page or workspace name.
3. **Relationship Description** — explains how the current page contributes to the destination.
4. **Optional Authority Boundary** — clarifies ownership or responsibility between KAORI and an authoritative external platform.
5. **Single Navigation Action** — opens the destination workspace.

## Visual Contract

The shared implementation is:

```jinja
{% import "components/related_page_card.html" as related_page_card %}

{{ related_page_card.render(
    'Permission Catalog',
    'Permission keys are code-backed KAORI contracts.',
    url_for('settings.permission_catalog'),
    'Open Permission Catalog',
    icon='book-key',
    eyebrow='Related Access Workspace',
    boundary='Roles package permission keys into reusable access profiles.'
) }}
```

Geometry:

- `rounded-2xl`
- Violet contextual surface
- 20 px internal padding
- 44 px icon surface
- one full-width action
- full available height when placed beside primary content
- preferred desktop width: approximately 320 px

The card is contextual navigation, not a semantic health block. Do not use green, amber, or red as its primary surface.

## Placement

Preferred desktop placement is directly to the right of the primary block whose workflow it extends:

```text
Primary Workspace Context | Related Page Card
```

Use:

```text
xl:grid-cols-[minmax(0,1fr)_20rem]
```

On smaller screens, the card stacks below the primary block. Do not place it between a table header and its table, inside a filter bar, or inside a Hero action area.

## Content Rules

### Title and Action

Use Title Case:

- `Permission Catalog`
- `Kubernetes Inventory`
- `Open Alert Intelligence`

### Description and Boundary

Use sentence case. Name **KAORI** directly whenever KAORI is the subject or object.

### Relationship Accuracy

The description must answer:

- What does the current page provide?
- How does the destination consume or govern it?

The boundary note must answer, when relevant:

- Which external platform remains authoritative?
- What interpretation, governance, or history does KAORI provide?

## Action Contract

- Exactly one action.
- Action starts with a clear verb, normally `Open`.
- Destination must be a real KAORI route.
- Do not add secondary actions or overflow menus.
- Do not duplicate a primary CRUD action from the current page.

## Responsive and Accessibility

- Card stacks below primary content before `xl` breakpoint.
- Card uses a semantic `section` with an accessible label.
- Decorative icons use `aria-hidden="true"`.
- Link has visible focus treatment.
- Link text states the destination; avoid generic `View More` or `Open` labels.

## Prohibited Patterns

- More than one destination.
- Generic shortcut cards with no workflow explanation.
- Raw provider links or external documentation links.
- Metrics, charts, tables, or status dashboards inside the card.
- Destructive actions.
- Repeating the same destination already used as the page's primary Hero action.
- Copying the component classes into page templates instead of using the shared macro.

## Review Checklist

- [ ] The pages form one workflow or governance chain.
- [ ] The destination title is canonical and Title Case.
- [ ] The relationship is explained, not merely named.
- [ ] KAORI is named directly in product wording.
- [ ] Authority boundaries are accurate.
- [ ] Exactly one destination action exists.
- [ ] The card sits beside the relevant primary block on desktop.
- [ ] The shared component is used.
