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
5. The current page is a contextual workflow page rather than a navigation hub.

Examples:

- Roles & Access → Permission Catalog
- Kubernetes connection detail → Kubernetes Inventory
- Metrics Source connection detail → Kubernetes Analytics
- Alertmanager connection detail → Alert Intelligence

Do not use it for generic recommendations, external documentation, unrelated shortcuts, or a list of possible destinations.

## Placement Contract

### Allowed

Place the card on a contextual subpage where the relationship is operationally meaningful:

- create or registration page;
- edit or configuration page;
- detail page;
- validation workspace;
- workflow or wizard step.

The preferred location is the right-side contextual column beside the primary block it extends.

### Not Allowed

Do not place the card on an overview, landing, list, or registry page. In detail:

- overview pages;
- provider landing pages;
- registries;
- generic lists;
- portfolio or navigation hubs.

These pages already provide broad navigation and do not yet have a sufficiently specific workflow context.

### Single-Page Exception

A module that has no separate contextual subpage may use the card on its main page. **Roles & Access** is the reference exception because Permission Catalog is a distinct related workspace and the role workflow is managed on one primary page.

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
    url_for('access.permissions.index'),
    'Open Permission Catalog',
    icon='book-key',
    eyebrow='Related Access Workspace',
    boundary='Roles package permission keys into reusable access profiles.'
) }}
```

Geometry:

- `rounded-2xl`;
- violet contextual surface;
- 20 px internal padding;
- 44 px icon surface;
- one full-width action;
- intrinsic content height; the card must not stretch to the height of an unrelated form or workspace;
- preferred desktop width: approximately 320 px;
- minimum 24 px separation between content and the action.

The shared component uses an intrinsic layout with `mt-6` before the action. This preserves a clear 24 px separation without stretching the card to match a much taller adjacent form.

The card is contextual navigation, not a semantic health block. Do not use green, amber, or red as its primary surface.

### Dark Mode Contract

The card remains Violet in dark mode. It must **not** collapse to a neutral `surface-card`, because the Violet surface is the relationship cue for a cross-workspace handoff.

Canonical surface:

```text
Light  -> .kaori-brand-domain-panel -> #5B21B6
Dark   -> .kaori-brand-domain-panel -> #2F1A4F
```

The dark value is intentionally deeper than primary-action Violet so the card remains harmonious with `surface-page`, `surface-shell`, and `surface-card` while still reading as KAORI brand context. On-brand title/description/icon content uses `brand-foreground`, `brand-foreground-muted`, `brand-surface`, and `brand-surface-strong`.

This is a global component rule. Every page that imports `components/related_page_card.html` inherits the same light/dark behavior; do not add page-local `dark:bg-*` overrides. The exception applies only to related-workspace/domain context and must not be copied to ordinary forms, tables, status cards, modals, or repeated records.

## Desktop and Mobile Placement

Preferred desktop placement:

```text
Primary Workspace Context | Related Page Card
```

Use the shared geometry from `components/context_rail.html`; do not copy the 20rem grid utility into the page template. On smaller screens, the card stacks below the primary block. Do not place it between a table header and its table, inside a filter bar, or inside a Hero action area.

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
- Preserve at least 24 px between the preceding content and action.

## Responsive and Accessibility

- Card stacks below primary content before the `xl` breakpoint.
- Card uses a semantic `section` with an accessible label.
- Decorative icons use `aria-hidden="true"`.
- Link has visible focus treatment.
- Link text states the destination; avoid generic `View More` or `Open` labels.

## Prohibited Patterns

- Placement on an overview, landing, registry, or generic list page.
- More than one destination.
- Generic shortcut cards with no workflow explanation.
- Raw provider links or external documentation links.
- Metrics, charts, tables, or status dashboards inside the card.
- Destructive actions.
- Repeating the same destination already used as the page's primary Hero action.
- Copying the component classes into page templates instead of using the shared macro.
- Action button touching the content or authority boundary above.

## Review Checklist

- [ ] The pages form one workflow or governance chain.
- [ ] The current page is a contextual subpage, or the single-page exception is documented.
- [ ] The destination title is canonical and Title Case.
- [ ] The relationship is explained, not merely named.
- [ ] KAORI is named directly in product wording.
- [ ] Authority boundaries are accurate.
- [ ] Exactly one destination action exists.
- [ ] At least 24 px separates content from the action.
- [ ] The card uses intrinsic height and does not stretch with an unrelated neighboring block.
- [ ] The card sits beside the relevant primary block on desktop.
- [ ] The shared component is used.
