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

Use this component only when ordered, directional **operator execution** is the actual task, not merely because a section is prominent. A main-content location alone does not justify a procedural flow.
The three canonical **Capacity & Demand** dashboards intentionally use `components/operational_capacity_decision.html` instead: source-qualified risk, interpretation, concise suggested action and six retained reference considerations in a compact **2×3 checklist-style matrix** without individual flow boxes, numbered steps or arrows. Keep Validate, Assess, Prioritize, Act, Verify and Record domain copy as reference information, never as an implicit provider execution sequence. The component remains read-only. Controlled Alert Interpretation & Response and Governed Reporting workflows retain their approved directional components.

Use `info_flow.html` for a page-level primary process. Use `context_guidance_card.html` only for optional secondary guidance in a genuine supporting rail. Do not collapse a flow that drives the current dashboard decision.
