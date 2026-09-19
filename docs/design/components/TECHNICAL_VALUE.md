# Technical Value

## Purpose

`components/technical_value.html` is the canonical owner for exact machine-oriented values such as IP addresses, UUIDs, Kubernetes versions, kernel versions, runtime identifiers, image references, and architecture names.

## Contract

- Detail and table values use normal proportional KAORI typography by default.
- Use `text-xs font-medium` through the shared macro; do not create a second typography hierarchy merely because a value is technical.
- Set `monospace=true` only for raw-copy identifiers, hashes, commands, code fragments, or values where character alignment materially improves verification.
- Do not turn technical values into status or metadata labels.
- Long identifiers may break across lines; values remain selectable.
- A copy action may be added only when the value is operationally useful to copy and the shared component owns that behavior.

## API

```jinja
{% import "components/technical_value.html" as technical_value %}
{{ technical_value.render(node.internal_ip) }}
{{ technical_value.render(record.fingerprint, monospace=true) }}
```

Use the `technical_row` helper in `components/details/_detail_content.html` inside detail cards.
