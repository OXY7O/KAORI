# KAORI Right Context Rail Standard

## Purpose

The right context rail holds supporting information beside a primary workflow without competing with the main task. It standardizes the desktop split, width, spacing, component order, and allowed side-box types.

Use the shared geometry from:

```jinja
{% import "components/context_rail.html" as context_rail %}
```

```jinja
<div class="{{ context_rail.layout_classes() }}">
    <main class="{{ context_rail.main_classes() }}">
        ...
    </main>
    <aside class="{{ context_rail.rail_classes() }}">
        ...
    </aside>
</div>
```

Do not copy the default 20rem or wide 22rem grid classes into page templates. Request the shared geometry through `context_rail.layout_classes()` or `context_rail.layout_classes('wide')`.

## Geometry

- Default desktop split: flexible primary workspace plus a fixed 20rem rail.
- Wide live-mutation split: flexible primary workspace plus a fixed 22rem rail.
- Gap between main and rail: 24 px.
- Gap between rail boxes: 16 px.
- Both columns use `min-w-0` to prevent overflow.
- Below the `xl` breakpoint, the rail stacks after the primary workspace.
- Rail boxes use intrinsic height. Do not stretch an unrelated box to match the main form.

## Allowed Side Boxes

Choose the component by information purpose:

| Need | Shared component |
|---|---|
| Primary ordered sequence | `components/info_flow.html` |
| One operationally related destination | `components/related_page_card.html` |
| Secondary expandable reference content | `components/information_guide_card.html` |
| Secondary expandable ordered guidance | `components/context_guidance_card.html` |
| Static page context or authority boundary | `components/page_context_card.html` |
| Compact peer-workspace summary | `components/workspace_summary_card.html` |
| Operational readiness or risk | A shared semantic status/readiness component owned by the domain |

Do not invent a new right-side card when one of these semantic purposes already matches.

Dark-mode surface ownership remains component-specific. In particular, `components/related_page_card.html` intentionally uses the global deep-Violet `.kaori-brand-domain-panel` in both themes, while Info Flow, guide/reference cards, page context, and ordinary readiness surfaces remain neutral unless their own standard explicitly says otherwise. Do not copy the Related Page Card Violet surface into unrelated rail boxes.

## Preferred Order

When several boxes are required, use this order:

1. Primary flow or readiness needed to complete the task.
2. Related workspace navigation.
3. Supporting information or reference guidance.

Keep the rail to one to three boxes. Primary Info Flow remains visible. Secondary summaries, guardrails, policy references, and related-workspace explanations are expandable and closed by default. More content normally belongs below the main workspace or on a dedicated page.

## Content Rules

- Titles use Title Case.
- Descriptions use sentence case.
- Keep descriptions concise; move long evidence to detail views or Activity Audit Log.
- Do not duplicate the same instruction in the hero, main form, and rail.
- Do not place tables, charts, large metrics, or multiple unrelated actions in the rail.
- A Related Page Card contains exactly one destination action.
- A primary ordered workflow remains Info Flow even when placed in the rail.

## Review Checklist

- Shared `context_rail` geometry is used.
- The main task remains visually dominant.
- Each side box has one clear semantic purpose.
- No page-local side-box shell or copied utility bundle exists.
- The rail stacks after the main content on smaller screens.
- No box is stretched to unrelated neighboring height.
