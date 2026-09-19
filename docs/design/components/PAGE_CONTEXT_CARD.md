# KAORI Page Context Card Standard

## Purpose

The Page Context Card explains what the current page or tab is responsible for. It is a compact, non-expandable orientation card for contextual sidebars.

Use it when a create, edit, detail, configuration, validation, or workflow subpage needs a short answer to:

- What is managed here?
- What is intentionally managed elsewhere?

The component is informational only. It is not a workflow, navigation shortcut, status panel, or documentation container.

## Placement contract

Preferred placement:

- first card in the right-side contextual column;
- before Configuration Flow, guidance, related workspace, or destructive controls;
- only on contextual subpages, not overview, landing, list, or registry pages.

Do not use it merely to fill an empty sidebar.

## Information architecture

```text
Optional Eyebrow
Title
Short Page Responsibility
Optional Boundary Line
```

The boundary line is used only to state which responsibilities remain in another tab or workspace.

## Visual contract

- `rounded-xl`;
- Violet Soft surface and Violet outline;
- restrained shadow;
- 16 px padding;
- 40 px contextual icon surface;
- optional 10 px uppercase metadata eyebrow;
- 14 px semibold Title Case title;
- 12 px sentence-case description;
- optional boundary separated by one Violet outline and a 16 px icon.

The card is always visible and must not use `details` or `summary`.

## Content limits

- one title;
- one concise description, preferably one or two short lines;
- at most one boundary sentence;
- no list;
- no action;
- no metric;
- no status badge;
- no warning color unless the message is genuinely a warning.

## Shared implementation

```jinja
{% import "components/page_context_card.html" as page_context_card %}

{{ page_context_card.render(
    'Configuration Workspace',
    'Manage the reusable connection identity, endpoint access, authentication, TLS trust, timeout, and enabled state.',
    icon='settings-2',
    boundary='Validation, runtime, and scope remain in their own tabs.'
) }}
```

## Relationship to other components

- **Context Guidance Card** explains an ordered supporting flow and is expandable.
- **Information Guide Card** compares non-sequential concepts or options.
- **Related Page Card** navigates to one related KAORI workspace.
- **Page Context Card** only explains the responsibility boundary of the current page or tab.

## Reference implementation

The Configuration Workspace card on Alertmanager Instance Manage is the reference implementation.

## Review checklist

- Current page responsibility is explicit.
- Optional boundary states only what remains elsewhere.
- Card is first in the contextual sidebar.
- Card is non-expandable and contains no action.
- Copy is short and does not repeat the complete workflow.
- Shared component is used without page-local geometry.
