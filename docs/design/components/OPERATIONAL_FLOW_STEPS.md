# Operational Flow Steps

## Purpose

`components/operational_flow_steps.html` renders a static box-based sequence inside a primary operational card. It is intended for action, response, validation, and reporting flows that must remain visible while the user reviews peer dashboard content.

## Canonical API

```jinja
{% import "components/operational_flow_steps.html" as operational_flow_steps %}

{% set rows = [
    [
        ('scan-search', 'Validate', 'Confirm scope and freshness'),
        ('list-filter', 'Prioritize', 'Identify risk and owner'),
        ('wrench', 'Act', 'Apply the approved change')
    ],
    [
        ('circle-check-big', 'Verify', 'Confirm recovery'),
        ('clipboard-check', 'Record', 'Preserve evidence')
    ]
] %}

{{ operational_flow_steps.render(rows, aria_label='Controlled Action Flow') }}
```

## Visual contract

- always visible; never expandable;
- two or three steps per row;
- standard `rounded-lg` step boxes;
- compact 28 px Violet-soft icon surfaces;
- horizontal arrows between steps and a vertical arrow between rows;
- `text-xs font-semibold` step title with `text-xs` supporting detail;
- parent operational card owns the section title, description, and outer shell.

## Decision rule

Use this component when the flow is one of two peer main-content boxes or is part of a primary operational section.

Use `info_flow.html` for a page-level primary process. Use `context_guidance_card.html` only for optional secondary guidance in a genuine supporting rail. Do not collapse a flow that drives the current dashboard decision.
