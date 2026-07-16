# KAORI Design System v1

This document is the authoritative visual reference for KAORI interface work. New pages and redesigns must use the Tailwind design tokens defined in `frontend/styles.css`; page-specific color CSS is not allowed.

## Design direction

The visual concept is **KAORI Violet Infrastructure**: a modern enterprise interface with a violet brand identity, neutral operational surfaces, restrained elevation, and conventional infrastructure status semantics.

The interface must remain information-first. Violet establishes product identity and hierarchy, while health, readiness, risk, and process states retain their own semantic colors.

## Implementation contract

- Tailwind CSS v4 is the styling system.
- Design tokens are defined once in `frontend/styles.css`.
- Templates use semantic utilities such as `bg-surface-card`, `text-content-primary`, and `border-outline-default`.
- Do not introduce page-specific stylesheets for ordinary layout, spacing, typography, color, radius, shadow, or interaction states.
- Do not use raw hex colors in Jinja templates.
- Rebuild `app/static/css/output.css` after changing templates or design tokens.
- Light and dark mode must be validated together for every component.
- Status must never rely on color alone; pair it with a text label and, where useful, an icon.

## Brand palette

| Role | Light mode | Dark mode |
|---|---|---|
| Primary | `#7C3AED` | `#8B5CF6` |
| Primary hover | `#6D28D9` | `#9F7AEA` |
| Primary dark | `#5B21B6` | `#7C3AED` |
| Accent | `#A78BFA` | `#B9A2FF` |
| Primary soft | `#EDE9FE` | violet at 14% opacity |

Recommended light hero gradient: `#5B21B6 → #7C3AED → #8B5CF6`.

In dark mode, violet is an accent rather than the default surface color. Dark surfaces use charcoal-plum neutrals so controls, status, and data visualizations remain distinguishable.

## Surface and content tokens

Use functional token names instead of literal color names.

### Surfaces

- `surface-page`
- `surface-sidebar`
- `surface-card`
- `surface-elevated`
- `surface-hover`
- `surface-selected`
- `surface-overlay`

### Content

- `content-primary`
- `content-secondary`
- `content-muted`
- `content-disabled`
- `content-inverse`

### Outlines

- `outline-subtle`
- `outline-default`
- `outline-strong`
- `outline-focus`

## Infrastructure status semantics

| State | Meaning | Visual family |
|---|---|---|
| Normal / Healthy / Ready / Connected | Function is operating as expected | Green |
| Informational / Advisory | Useful context without direct risk | Blue |
| Warning / Degraded / At Risk / Partial | Reduced function or meaningful risk requires attention | Amber |
| Critical / Failed / Down / Blocked | Unavailable, failed, blocked, or high impact | Red |
| Unknown / Not Collected / Not Evaluated | KAORI cannot determine current condition | Slate |
| Disabled / Inactive / Not Configured | Intentionally inactive or not configured | Muted slate |
| Maintenance / Paused / Silenced | Controlled operational state | Violet |
| Pending / Syncing / Processing | Work is still in progress | Cyan |

Aggregated status precedence:

`Critical > Warning/Degraded > Pending > Unknown > Normal`

Do not treat missing data as healthy. Disabled, unknown, pending, and degraded are distinct states and must remain distinct in both copy and presentation.

## Typography

Use Inter through the global `font-sans` token.

- Page title: 24–28 px
- Hero metric: 26–32 px
- Section title: 18 px
- Card title: 15–16 px
- Body: 14 px
- Supporting text: 12–13 px
- Table content: 13–14 px
- Badge: 11–12 px

Use a monospace family for endpoints, resource identifiers, IP addresses, namespaces, queries, hashes, and similar technical values.

## Spacing and density

Use the Tailwind spacing scale. Prefer the following rhythm:

`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 px`

KAORI uses a comfortable-compact density suitable for operational work at 100% browser zoom. Avoid marketing-style whitespace and avoid compressing labels, values, and actions into visually ambiguous groups.

## Shape and elevation

- Inputs and compact buttons: 8–12 px radius
- Standard cards: 12–16 px radius
- Hero and modal surfaces: 16–24 px radius
- Pills and status chips: full radius where appropriate

Elevation levels:

1. Flat: internal sections and tables
2. Card: standard content surfaces
3. Elevated: menus, dialogs, and floating panels

Dark mode relies primarily on surface and outline separation, not heavy shadows.

## Interaction states

Every interactive component must define:

- default
- hover
- focus-visible
- active
- selected
- disabled
- loading
- error or success where applicable

Use a violet focus ring with a surface-colored offset. Keep transitions functional and short, normally 150–220 ms.

## Login page reference

The login page is the first implemented reference for the design system.

- Split layout on desktop; form-first layout on smaller screens.
- Violet brand panel with infrastructure-oriented visual context.
- White or neutral form surface using semantic surface tokens.
- Use comfortable-compact density and keep the complete desktop card usable at 100% browser zoom on a 1366×768 laptop viewport.
- Prefer `max-w-5xl`, compact vertical padding, 44 px controls, and restrained illustration height for authentication layouts.
- Local database authentication remains the only actionable provider until additional providers are implemented.
- Theme switching must work before authentication.
- Authentication errors use the critical semantic family; successful notices use the normal family.
- Security copy may describe RBAC and audit controls but must not imply unavailable authentication capabilities.

## Tailwind workflow

Install frontend dependencies once:

```bash
npm ci
```

Build CSS:

```bash
npm run build-css
```

Watch during development:

```bash
npm run watch-css
```

The production Docker build executes the same `build-css` script and copies the generated stylesheet into the runtime image.

## Review checklist

Validate each redesign in:

- light mode
- dark mode
- 1366×768
- 1440×900
- 1920×1080
- 100% browser zoom
- loading, empty, error, disabled, and permission states where applicable
- keyboard focus and visible focus rings
- collapsed and expanded navigation when the page uses the application shell
