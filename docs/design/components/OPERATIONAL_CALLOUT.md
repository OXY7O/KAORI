# Operational Callout

## Purpose

`components/operational_callout.html` owns reusable informational and semantic callout geometry inside operational sections. It prevents page templates from copying semantic border, surface, icon, and text bundles.

## Variants

### Neutral

Use for explicit evidence boundaries, warnings, or the introduction to an action flow. Operational dashboards should avoid a generic “What This Summary Means” callout when the section title and evidence already establish meaning.

- neutral elevated outer surface;
- semantic icon tile;
- `text-sm font-semibold` title;
- `text-xs` description.

### Semantic

Use for compact interpretation cards such as Critical, Warning, Info, Normal, or Unknown.

- complete semantic soft surface;
- matching semantic border and text;
- icon included for recognition;
- not a compact status label.

## Usage

```jinja
{% import "components/operational_callout.html" as operational_callout %}

{{ operational_callout.render(
    'Warning',
    'Degradation or risk is developing. Investigate before escalation.',
    icon='triangle-alert',
    tone='warning',
    variant='semantic'
) }}
```

Page templates must not copy the semantic class bundle inline. Standard compact labels remain borderless and continue to use `table_label.html`.

## Access-denied guidance (reusable neutral variant)

The **Access Denied / Access Role Unavailable** view reuses the **existing** neutral callout rather than introducing a page-specific security card. Use the same component for similar role-review actions and authorization boundaries; the page owns the content and responsive column placement, while the component owns border, surface, icon, typography and accessible optional action.

```jinja
{% import "components/operational_callout.html" as operational_callout %}

<section class="grid items-stretch gap-3 lg:grid-cols-2"
         aria-label="Access resolution guidance">
    {{ operational_callout.render(
        'Access Administrator Action',
        'Ask an administrator to review your role and permissions.',
        icon='user-cog', tone='info', variant='neutral', extra_classes='h-full'
    ) }}
    {{ operational_callout.render(
        'Security Boundary',
        'Navigation is guidance; server-side permissions enforce access.',
        icon='shield-check', tone='info', variant='neutral', extra_classes='h-full'
    ) }}
</section>
```

- Use matching **neutral** surfaces for adjacent information and action guidance. A tinted semantic callout is reserved for an actual operational status/severity, not a generic 403 permission boundary.
- Keep meaningful icon/title text, natural wrapping, a single-column mobile layout and equal-height desktop cards.
- Rendered guidance is not an authorization gate: server-side RBAC/route protection and audit remain authoritative. Do not present an administrator-only action as something a denied Viewer can perform.

