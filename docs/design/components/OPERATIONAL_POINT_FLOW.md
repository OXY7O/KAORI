# Operational Point Flow

## Purpose

`app/templates/components/operational_point_flow.html` presents a short ordered operational sequence without turning every step into a card. It is intended for supporting guidance, not primary form content.

## Canonical use

Use the component when the user needs to understand a small sequence such as:

- upload material;
- select explicit targets;
- validate a preview;
- apply the operation;
- verify the outcome.

The canonical TLS bulk-rotation implementation places the point flow inside `View More Content`, closed by default. Required fields and actions remain visible outside the expandable section.

## Contract

- each item has a number, optional icon, concise title, and one short supporting sentence;
- the component uses no nested cards, step boxes, arrows, fixed height, or decorative timeline rail on desktop;
- mobile may use a thin vertical connector between points;
- target 3–5 steps;
- titles target 1–3 words;
- detail text targets one sentence and must not repeat form instructions;
- do not hide required validation errors or consequences inside the flow;
- use `operational_flow_steps.html` when each step itself is primary content requiring a larger explanation.
