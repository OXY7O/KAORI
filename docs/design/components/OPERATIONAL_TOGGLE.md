# Operational Toggle

## Purpose

The Operational Toggle is the standard container for boolean connection controls such as certificate verification, resolver eligibility, synchronization enablement, or explicitly risky exceptions.

Use the shared macro:

```jinja
{% import "components/operational_toggle.html" as operational_toggle %}

{% call operational_toggle.render(
    'Allow KAORI to Use This Connection',
    'Disabled connections remain stored but are excluded from scope resolution.'
) %}
    {{ form.enabled(...) }}
{% endcall %}
```

## Baseline Rule

Controls with equal operational weight use identical geometry and the neutral surface. A security-related label does not automatically receive violet, amber, or red emphasis.

Examples that use the neutral baseline:

- `Verify TLS Certificate`
- `Allow KAORI to Use This Connection`
- `Enable Runtime Discovery`
- `Enable Synchronization`

Semantic color is reserved for a real message that requires operator attention.

## Tone Contract

### Neutral

Use for normal operational and security controls.

```text
border-outline-default
bg-surface-card
text-content-primary
```

### Warning

Use when enabling the option creates an approved exception, weakens a safeguard, or requires operator review.

Examples:

- `Allow Legacy TLS Certificate`
- `Skip Certificate Verification`
- `Use Deprecated Compatibility Mode`

```text
border-status-warning-border
bg-status-warning-soft
text-status-warning-text
```

### Critical

Use only when enabling the option can cause destructive, irreversible, or high-impact behavior.

### Info

Use sparingly for a non-risk control that requires additional contextual emphasis. It is not the default for security settings.

## Information Architecture

Each toggle contains:

1. native checkbox or switch control;
2. Title Case label;
3. one concise sentence-case description.

The description explains the effect of the enabled or disabled state. It must not contain a full workflow, remediation guide, or unrelated policy text.

## Visual Contract

- equal minimum height for adjacent toggles;
- `rounded-lg`;
- 16 px padding;
- 12 px gap between control and content;
- 14 px semibold title;
- 12 px helper with 20 px line-height;
- identical geometry across neutral, warning, critical, and info tones.

Only semantic tokens change with tone. Spacing, typography, and control alignment do not change.

## Writing Rules

Preferred:

```text
Verify TLS Certificate
Reject untrusted or mismatched certificates.
```

```text
Allow KAORI to Use This Connection
Disabled connections remain stored but are excluded from scope resolution.
```

Avoid:

- vague labels such as `Enabled`;
- descriptions longer than two short lines;
- embedding maintenance procedures in the helper;
- coloring a normal control only because it is security-related.

## Accessibility

- Use a native checkbox whenever possible.
- The entire container may be the label target.
- Keep visible focus treatment on the control.
- Do not communicate risk by color alone; the label and description must state the exception.
- Preserve checked state and server-side validation.

## Prohibited Patterns

- Different geometry for adjacent boolean controls.
- Violet emphasis on one normal toggle and neutral styling on another equivalent toggle.
- Amber or red without a real exception or risk.
- A full paragraph inside the toggle.
- Page-local copies of the component classes.

## Review Checklist

- [ ] Equivalent toggles use the same neutral style.
- [ ] Warning or critical tone has a documented semantic reason.
- [ ] Title uses Title Case.
- [ ] Description is concise and sentence case.
- [ ] Geometry remains identical across tones.
- [ ] The shared macro is used.
