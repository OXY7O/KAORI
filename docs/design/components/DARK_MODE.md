# KAORI Dark Mode Standard v1.0

**Status:** Locked global color and surface contract
**Design direction:** Neutral-first dark mode with controlled KAORI Violet
**Canonical implementation:** `frontend/styles.css`

This document is the authoritative contract for dark-mode color, surface hierarchy, brand emphasis, contrast, and shared-shell behavior across authenticated KAORI pages.

Dark mode is not a direct inversion of light mode. It uses layered neutral surfaces for operational readability and reserves bright Violet for identity, focus, selection, and primary interaction.

## Core principle

The visual allocation target is:

```text
80% neutral operational surfaces
15% supporting outlines, muted surfaces, and semantic state
 5% bright KAORI Violet emphasis
```

A page must remain recognizably KAORI without making every label, icon, active state, card, and large surface bright Violet.

## Ownership

```text
Tokens and shared classes  frontend/styles.css
Compiled stylesheet        app/static/css/output.css
Application shell          app/templates/layouts/app.html
Navbar                     app/templates/components/navigation/navbar.html
Sidebar                    app/templates/components/navigation/sidebar.html
                           app/templates/components/navigation/*_menu.html
Hero                       app/templates/components/page_hero.html
Dark-mode verifier         scripts/verify_dark_mode_standard.py
Contract tests             tests/contracts/design/test_dark_mode_standard_contract.py
```

Page templates consume semantic tokens and shared component classes. They do not own dark-mode hex values, page-local palette overrides, or duplicate dark variants.

## Surface hierarchy

The dark-mode surface stack is fixed:

| Layer | Token | Value | Intended use |
|---|---|---|---|
| Canvas | `surface-page` | `#0F0D15` | Main scrolling page background |
| Sunken | `surface-sunken` | `#121019` | Recessed controls, code-adjacent regions, deep inset areas |
| Application shell | `surface-shell` | `#15121D` | Main frame and navbar |
| Sidebar | `surface-sidebar` | `#171321` | Persistent navigation frame |
| Card | `surface-card` | `#1D1925` | Standard content cards, inputs, tables |
| Muted surface | `surface-muted` | `#201B2A` | Supporting sections and quiet grouping |
| Elevated | `surface-elevated` | `#25202F` | Menus, drawers, dialogs, floating panels |
| Hover | `surface-hover` | `#282231` | Temporary hover emphasis |
| Selected | `surface-selected` | Violet at 14% opacity | Selected rows, choices, subordinate active state |
| Overlay | `surface-overlay` | `rgba(5, 3, 9, 0.76)` | Modal and drawer backdrop |

Required hierarchy:

```text
Canvas
└── Application shell
    ├── Navbar
    └── Page canvas
        ├── Card
        ├── Muted supporting surface
        └── Elevated overlay when opened
```

Adjacent layers must not use the same token. Separation should come primarily from surface difference and restrained outlines, not heavy shadows.

## Content hierarchy

| Role | Token | Dark value |
|---|---|---|
| Primary text | `content-primary` | `#F5F3F7` |
| Secondary text | `content-secondary` | `#CBC5D2` |
| Muted/supporting text | `content-muted` | `#9D95A7` |
| Disabled text | `content-disabled` | `#706878` |
| Inverse text | `content-inverse` | `#0F0D15` |

Rules:

- Ordinary headings and body text are neutral, not Violet.
- Violet text is reserved for links, current context, selected state, focus, and restrained metadata emphasis.
- Supporting descriptions must use `content-muted`, not low-opacity white or Lavender copied from the Hero.
- Disabled content remains readable and must not be confused with unavailable or unknown data.

## Outline hierarchy

| Role | Token | Dark value |
|---|---|---|
| Subtle | `outline-subtle` | `#2B2535` |
| Default | `outline-default` | `#373043` |
| Strong | `outline-strong` | `#4B4258` |
| Focus | `outline-focus` | `#A78BFA` |

Dark mode uses outlines only where they clarify structure. Avoid placing a strong outline around every nested card. A card inside another card should normally use either a different surface or one subtle divider, not both a heavy border and a shadow.

## KAORI Violet usage

Dark brand tokens:

| Role | Value |
|---|---|
| Primary action/focus | `#8B5CF6` |
| Primary hover | `#9D7CFA` |
| Primary pressed/dark | `#6D28D9` |
| Accent | `#C4B5FD` |
| Soft selected surface | Violet at 12–14% opacity |

Bright Violet is permitted for:

- primary buttons;
- focus rings;
- compact icon accents;
- links and selected metadata;
- active indicators;
- progress emphasis;
- small badges that represent brand context rather than operational state.

Bright Violet is prohibited as the default color for:

- page canvas;
- ordinary cards;
- descriptive text;
- every card icon;
- all navigation rows;
- operational health, warning, critical, or unknown state;
- large repeated surfaces below the Hero.

## Hero dark-mode treatment

The canonical Hero is the only authenticated-page component permitted to use the token-owned dark tonal gradient.

The active dark background is:

```css
radial-gradient(circle at 14% 18%, rgba(167, 139, 250, 0.16), transparent 36%),
linear-gradient(120deg, #3B176E 0%, #4C1D95 52%, #32135D 100%)
```

The gradient is owned by `--kaori-hero-background` and applied only through `.kaori-hero-shell`.

Hero internal surfaces use:

- `.kaori-hero-panel` for the right context panel;
- `.kaori-hero-tile` for metric cards, icons, and supporting information;
- `.kaori-hero-chip` for eyebrow and metadata labels.

Rules:

- Do not use `bg-kaori-primary` as the Hero shell.
- Do not copy the Hero gradient into page templates.
- Do not add additional glows or gradients to cards below the Hero.
- The Hero remains visually important without becoming the brightest element across most of the viewport.

## Sidebar dark-mode treatment

The sidebar remains a dark inverse navigation surface in both themes, but dark mode reduces competing Violet emphasis.

Canonical classes:

```text
sidebar-parent-active
sidebar-parent-active-icon
sidebar-item-idle
sidebar-item-idle-icon
sidebar-section-label
```

Active parent behavior:

- light mode: solid KAORI Violet;
- dark mode: Violet at 18% opacity;
- dark mode adds a 3 px inset Violet indicator on the left;
- label remains white;
- icon uses the Accent Violet;
- no large Violet glow or elevated CTA-like appearance.

Submenu active state remains subordinate and uses a translucent surface plus Accent Violet. It must never use the same treatment as a primary action.

## Navbar and application shell

The main application frame and navbar use `surface-shell`, not `surface-card`.

This creates a stable hierarchy:

```text
page canvas < application shell < card < elevated menu
```

Navbar controls may use `surface-card`. Dropdowns, drawers, and menus use `surface-elevated`.

The navbar must not use raw Slate utilities such as `dark:bg-slate-*`. Theme behavior is owned by semantic tokens.

## Cards and repeated content

Standard cards use `surface-card` with `outline-default` or `outline-subtle` according to density.

Dark card hover behavior:

- background may rise to `surface-elevated`;
- border may use `outline-focus` only for an interactive card;
- shadow remains restrained;
- the entire card must not become Violet.

Large catalog grouping panels use `surface-card`; their internal brand/domain panel may use a dark Violet solid surface through `.kaori-brand-domain-panel`.

## Semantic status colors

Operational status colors remain semantic in dark mode:

- normal/healthy: green;
- information/pending: blue;
- warning/degraded: amber;
- critical/failed: red;
- unknown/disabled: slate;
- maintenance may use the documented maintenance mapping.

Violet must not replace these states. Every state includes text and, when useful, an icon.

## Gradient policy

Authenticated KAORI pages do not use decorative gradients.

The only approved exception is the canonical dark Hero gradient owned by `--kaori-hero-background`. Login/public marketing surfaces are governed separately.

A domain panel, card, table, sidebar item, navbar control, metric tile, or empty state must use a solid semantic surface.

## Interaction states

Every interactive component preserves:

- stable geometry;
- visible `focus-visible` ring;
- hover contrast without excessive brightness;
- selected state distinct from hover;
- disabled state distinct from unknown data;
- semantic error/success treatment.

Focus uses `outline-focus` and a surface-colored offset. Do not remove focus simply because a control already uses Violet.

## Accessibility and review targets

Review at minimum:

- 1366 × 768;
- 1440 × 900;
- 1920 × 1080;
- 100% browser zoom;
- expanded and collapsed sidebar;
- Hero with and without context panel;
- standard card, table, form, dropdown, modal, and drawer;
- normal, warning, critical, unknown, disabled, loading, and selected states.

Required outcomes:

- WCAG AA text contrast;
- surface layers are distinguishable without relying on shadows;
- primary content remains readable during long operational sessions;
- no large region uses Bright Violet except the controlled Hero identity surface;
- dark mode does not expose raw light-only surfaces.

## Prohibited patterns

- page-local `dark:bg-slate-*` or `dark:text-slate-*` for ordinary shared UI;
- raw dark hex values in Jinja templates;
- using `bg-kaori-primary` for large repeated cards;
- full-width active navigation that looks like a primary CTA in dark mode;
- Lavender body copy;
- all cards using the same surface as the page canvas;
- heavy shadow as the only layer separator;
- decorative gradients outside the canonical Hero;
- duplicate dark-mode token sets in module stylesheets.

## Change procedure

A global dark-mode change must update in one commit:

1. `frontend/styles.css`;
2. `app/static/css/output.css`;
3. this document;
4. affected shared component standards;
5. `scripts/verify_dark_mode_standard.py`;
6. dark-mode contract tests.

Run:

```bash
python scripts/verify_dark_mode_standard.py
python -m pytest -q tests/contracts/design/test_dark_mode_standard_contract.py
node scripts/verify_css_build.mjs
```
