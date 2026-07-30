# Technical Value

## Purpose

`components/technical_value.html` is the canonical owner for machine-oriented values such as IP addresses, UUIDs, Kubernetes versions, kernel versions, runtime identifiers, image references, and architecture names.

## Contract

- Use `font-mono text-xs` through the shared macro.
- Use proportional typography for resource names and human-readable descriptions.
- Do not turn technical values into status or metadata labels.
- Long identifiers may break across lines; values remain selectable.
- A copy action may be added only when the value is operationally useful to copy and the shared component owns that behavior.

## API

```jinja
{% import "components/technical_value.html" as technical_value %}
{{ technical_value.render(node.internal_ip) }}
```

Use the `technical_row` helper in `components/details/_detail_content.html` inside detail cards.
